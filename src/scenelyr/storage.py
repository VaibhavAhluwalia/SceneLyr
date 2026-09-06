"""Local, inspectable persistence for imported scenes and generated artifacts."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import cv2

from .compiler import compile_scene
from .models import SemanticScene


def data_root() -> Path:
    configured = os.environ.get("SCENELYR_DATA_DIR")
    root = Path(configured).expanduser() if configured else Path(__file__).resolve().parents[2] / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def persist_import(scene: SemanticScene, source: bytes, filename: str) -> dict[str, Path]:
    folder = data_root() / "imports" / re.sub(r"[^a-zA-Z0-9._-]", "-", scene.id)
    folder.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        suffix = ".img"
    paths = {"folder": folder, "source": folder / f"source{suffix}", "json": folder / "scene.json",
             "svg": folder / "preview.svg", "html": folder / "inspector.html", "pptx": folder / "editable.pptx"}
    paths["source"].write_bytes(source)
    scene.metadata.update({"sourceImage": str(paths["source"]), "originalFilename": filename, "dataFolder": str(folder)})
    persist_assets(scene, folder)
    paths["json"].write_text(json.dumps(scene.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    compile_scene(scene, svg_path=paths["svg"], html_path=paths["html"], pptx_path=paths["pptx"])
    return paths


def save_scene(scene: SemanticScene) -> dict[str, Path]:
    """Persist semantic edits while preserving the originally uploaded image."""
    folder = data_root() / "imports" / scene.id
    folder.mkdir(parents=True, exist_ok=True)
    paths = {"folder": folder, "json": folder / "scene.json", "svg": folder / "preview.svg",
             "html": folder / "inspector.html", "pptx": folder / "editable.pptx"}
    scene.metadata["dataFolder"] = str(folder)
    persist_assets(scene, folder)
    paths["json"].write_text(json.dumps(scene.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    compile_scene(scene, svg_path=paths["svg"], html_path=paths["html"], pptx_path=paths["pptx"])
    return paths


def load_import(scene_id: str) -> SemanticScene | None:
    path = data_root() / "imports" / scene_id / "scene.json"
    return SemanticScene.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None


def list_imports() -> list[dict]:
    imports = data_root() / "imports"
    results = []
    for scene_file in imports.glob("*/scene.json") if imports.exists() else []:
        try:
            scene = SemanticScene.model_validate_json(scene_file.read_text(encoding="utf-8"))
            results.append({"id": scene.id, "objects": len(scene.nodes), "connections": len(scene.edges),
                            "filename": scene.metadata.get("originalFilename"), "folder": str(scene_file.parent),
                            "modified": scene_file.stat().st_mtime})
        except (ValueError, OSError):
            continue
    return sorted(results, key=lambda item: item["modified"], reverse=True)


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "-", value).strip(".-") or "object"


def _source_image(scene: SemanticScene):
    source_path = scene.metadata.get("sourceImage")
    if not source_path or not Path(source_path).is_file():
        return None
    return cv2.imread(str(source_path), cv2.IMREAD_UNCHANGED)


def _crop_object(image, bounds: list | None, target: Path, padding: int = 4) -> bool:
    if image is None or not bounds or len(bounds) != 4:
        return False
    x, y, width, height = (int(value) for value in bounds)
    image_height, image_width = image.shape[:2]
    left, top = max(0, x - padding), max(0, y - padding)
    right, bottom = min(image_width, x + width + padding), min(image_height, y + height + padding)
    if right <= left or bottom <= top:
        return False
    return bool(cv2.imwrite(str(target), image[top:bottom, left:right]))


def persist_assets(scene: SemanticScene, folder: Path) -> None:
    """Persist a browsable scene → object → files hierarchy for every node."""
    import xml.etree.ElementTree as ET
    from .layout import layout_scene
    from .render import render_svg

    assets = folder / "assets"
    objects = assets / "objects"
    assets.mkdir(parents=True, exist_ok=True)
    objects.mkdir(parents=True, exist_ok=True)
    layout = layout_scene(scene)
    tree = ET.fromstring(render_svg(layout, scene))
    entries = []
    legacy_layers = []
    positions = {node.id: node for node in layout.nodes}
    source_image = _source_image(scene)
    current_folders = {_safe_name(node.id) for node in scene.nodes}
    for old_folder in objects.iterdir():
        if old_folder.is_dir() and old_folder.name not in current_folders:
            shutil.rmtree(old_folder)

    generated_assets = {asset.id: asset for asset in scene.assets if not asset.id.startswith("extracted-")}
    for node in scene.nodes:
        object_folder = objects / _safe_name(node.id)
        object_folder.mkdir(parents=True, exist_ok=True)
        layer_path = object_folder / "layer.svg"
        crop_path = object_folder / "crop.png"
        record_path = object_folder / "object.json"
        pos = positions[node.id]
        wrapper = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": f"{pos.x-3} {pos.y-3} {pos.width+6} {pos.height+6}"})
        layer = next(el for el in tree if el.get("data-scene-id") == node.id)
        wrapper.append(layer)
        layer_path.write_text(ET.tostring(wrapper, encoding="unicode"), encoding="utf-8")
        has_crop = _crop_object(source_image, node.metadata.get("sourceBounds"), crop_path)
        if not has_crop and crop_path.exists():
            crop_path.unlink()

        asset_id = f"extracted-{node.id}"
        if has_crop:
            from .models import SemanticAsset
            generated_assets[asset_id] = SemanticAsset(
                id=asset_id, type="image", source="file", uri=str(crop_path), alt=node.label,
                metadata={"role": "source-object-crop", "parentSceneId": scene.id,
                          "objectId": node.id, "sourceBounds": node.metadata.get("sourceBounds")},
            )
            node.asset_id = asset_id
        elif node.asset_id and node.asset_id.startswith("extracted-"):
            node.asset_id = None

        incoming = [edge.to_dict() if hasattr(edge, "to_dict") else edge.model_dump(by_alias=True, exclude_none=True)
                    for edge in scene.edges if edge.to == node.id]
        outgoing = [edge.to_dict() if hasattr(edge, "to_dict") else edge.model_dump(by_alias=True, exclude_none=True)
                    for edge in scene.edges if edge.from_ == node.id]
        text_record = {
            "value": node.label,
            "status": node.metadata.get("labelStatus", "semantic"),
            "confidence": node.metadata.get("ocrConfidence"),
            "bounds": node.metadata.get("ocrBounds", []),
            "engine": scene.metadata.get("ocrEngine"),
        }
        record = {
            "schemaVersion": 1,
            "id": node.id,
            "parent": {"type": "scene", "id": scene.id},
            "semantic": {"label": node.label, "kind": node.kind, "description": node.description,
                         "group": node.group, "importance": node.importance},
            "text": text_record,
            "geometry": {
                "shape": node.metadata.get("shape"),
                "sourceBounds": node.metadata.get("sourceBounds"),
                "renderedBounds": {"x": pos.x, "y": pos.y, "width": pos.width, "height": pos.height},
            },
            "relationships": {"incoming": incoming, "outgoing": outgoing},
            "files": {"sourceImage": scene.metadata.get("sourceImage"),
                      "crop": str(crop_path) if has_crop else None, "layer": str(layer_path)},
            "provenance": {"method": node.metadata.get("method"),
                           "importMode": scene.metadata.get("importMode"),
                           "modelUsed": scene.metadata.get("modelUsed", False)},
            "children": [],
        }
        record_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        node.metadata.update({"assetPath": str(layer_path), "objectFolder": str(object_folder),
                              "objectRecordPath": str(record_path)})
        if has_crop:
            node.metadata["cropPath"] = str(crop_path)
        else:
            node.metadata.pop("cropPath", None)
        entries.append({"type": "object", "id": node.id, "label": node.label,
                        "record": str(record_path), "crop": str(crop_path) if has_crop else None,
                        "layer": str(layer_path), "children": []})
        legacy_layers.append({"id": node.id, "label": node.label, "file": str(layer_path),
                              "sourceImage": scene.metadata.get("sourceImage"),
                              "sourceBounds": node.metadata.get("sourceBounds"),
                              "position": {"x": pos.x, "y": pos.y,
                                           "width": pos.width, "height": pos.height}})

    scene.assets = list(generated_assets.values())
    manifest_path = assets / "manifest.json"
    manifest = {
        "schemaVersion": 1,
        "sceneId": scene.id,
        "layers": legacy_layers,
        "root": {"type": "scene", "id": scene.id, "sourceImage": scene.metadata.get("sourceImage"),
                 "sceneRecord": str(folder / "scene.json"), "children": entries},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    scene.metadata["assetManifest"] = str(manifest_path)
