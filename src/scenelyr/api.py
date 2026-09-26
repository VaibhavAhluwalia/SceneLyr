"""Optional HTTP adapter. The core works without a web server."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from .compiler import compile_scene
from .models import SemanticScene
from .pixels import extract_pixels
from .release_validation import run_release_validation
from .storage import data_root, list_imports, load_import, persist_import, save_scene
from .store import SceneStore

app = FastAPI(title="SceneLyr", version="0.1.0")
store = SceneStore()
ui_scenes: dict[str, SemanticScene] = {}

UI = (Path(__file__).parent / 'web' / 'workspace.html').read_text(encoding='utf-8')


class PixelImportRequest(BaseModel):
    path: str
    scene_id: str | None = None


class NodeEdit(BaseModel):
    label: str
    kind: str | None = None


class EdgeEdit(BaseModel):
    from_id: str | None = None
    to_id: str | None = None
    label: str | None = None


def _ui_payload(scene: SemanticScene) -> dict:
    compiled = compile_scene(scene)
    return {"id": scene.id, "objects": len(scene.nodes), "connections": len(scene.edges),
            "warnings": scene.metadata.get("warnings", []), "svg": compiled.svg, "inspector": compiled.html,
            "folder": str(data_root() / "imports" / scene.id), "scene": scene.to_dict(),
            "nodes": [{"id": node.id, "label": node.label, "kind": node.kind,
                       "shape": node.metadata.get("shape", "unknown"),
                       "confidence": node.metadata.get("ocrConfidence"),
                       "bounds": node.metadata.get("sourceBounds", []),
                       "cropUrl": f"/ui/scenes/{scene.id}/objects/{node.id}/crop" if node.metadata.get("cropPath") else None,
                       "recordUrl": f"/ui/scenes/{scene.id}/objects/{node.id}/record",
                       "layerUrl": f"/ui/scenes/{scene.id}/objects/{node.id}/layer"} for node in scene.nodes],
            "edges": [{"id": edge.id, "from": edge.from_, "to": edge.to, "label": edge.label,
                       "direction": edge.metadata.get("direction", "unknown")} for edge in scene.edges]}


@app.get("/", response_class=HTMLResponse)
def user_interface() -> str:
    return UI


@app.get("/ui/history")
def ui_history() -> dict:
    return {"dataFolder": str(data_root()), "imports": list_imports()}


@app.post("/ui/release-validation")
def ui_release_validation() -> dict:
    report = run_release_validation(data_root() / "release-validation")
    return {"passed": report["passed"], "summary": report["summary"],
            "reportUrl": "/ui/release-validation/report"}


@app.get("/ui/release-validation/report")
def ui_release_validation_report():
    target = data_root() / "release-validation" / "report.html"
    if not target.is_file():
        raise HTTPException(404, "Run release validation first.")
    return FileResponse(target, media_type="text/html")


@app.post("/ui/import")
async def ui_import(image: Annotated[UploadFile, File()]) -> dict:
    if image.content_type not in {"image/png", "image/jpeg", "image/webp", "image/bmp", "application/octet-stream"}:
        raise HTTPException(415, "Please choose a PNG, JPG, WebP or BMP image.")
    content = await image.read(25 * 1024 * 1024 + 1)
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(413, "Image is larger than 25 MB.")
    suffix = Path(image.filename or "image.png").suffix or ".png"
    temporary = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    path = Path(temporary.name)
    try:
        temporary.write(content); temporary.close()
        scene = extract_pixels(path)
        paths = persist_import(scene, content, image.filename or "uploaded-image.png")
        ui_scenes[scene.id] = scene
        return _ui_payload(scene)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    finally:
        temporary.close()
        path.unlink(missing_ok=True)


def _editable_scene(scene_id: str) -> SemanticScene:
    scene = load_import(scene_id) or ui_scenes.get(scene_id)
    if not scene:
        raise HTTPException(404, "Scene was not found.")
    return scene


@app.get("/ui/scenes/{scene_id}")
def ui_open_scene(scene_id: str) -> dict:
    scene = load_import(scene_id)
    if scene is None:
        raise HTTPException(404, "Saved scene was not found.")
    ui_scenes[scene_id] = scene
    return _ui_payload(scene)


@app.get("/ui/scenes/{scene_id}/objects/{node_id}/{kind}")
def ui_object_asset(scene_id: str, node_id: str, kind: str):
    scene = _editable_scene(scene_id)
    node = next((item for item in scene.nodes if item.id == node_id), None)
    if not node:
        raise HTTPException(404, "Object was not found.")
    metadata_key = {"crop": "cropPath", "record": "objectRecordPath", "layer": "assetPath"}.get(kind)
    if not metadata_key:
        raise HTTPException(404, "Unknown object asset type.")
    target = Path(node.metadata.get(metadata_key, ""))
    object_root = data_root() / "imports" / scene.id / "assets" / "objects"
    try:
        target.resolve().relative_to(object_root.resolve())
    except (ValueError, OSError):
        raise HTTPException(404, "Object asset was not found.")
    if not target.is_file():
        raise HTTPException(404, "Object asset was not found.")
    media_type = {"crop": "image/png", "record": "application/json", "layer": "image/svg+xml"}[kind]
    return FileResponse(target, media_type=media_type)


@app.patch("/ui/scenes/{scene_id}/nodes/{node_id}")
def ui_edit_node(scene_id: str, node_id: str, edit: NodeEdit) -> dict:
    from .workspace import get_scene, lock, fail
    from .mcp_server import update_node_tool
    with lock:
        try:
            get_scene(scene_id)
            updated = SemanticScene.model_validate_json(update_node_tool(scene_id, node_id, edit.label, edit.kind))
            ui_scenes[scene_id] = updated
            return _ui_payload(updated)
        except Exception as error:
            raise fail(error) from error


@app.patch("/ui/scenes/{scene_id}/edges/{edge_id}")
def ui_edit_edge(scene_id: str, edge_id: str, edit: EdgeEdit) -> dict:
    from .workspace import get_scene, lock, fail
    from .mcp_server import reconnect_arrow
    with lock:
        try:
            scene = get_scene(scene_id)
            edge = next((item for item in scene.edges if item.id == edge_id), None)
            if not edge:
                raise HTTPException(404, "Connection was not found.")
            updated = SemanticScene.model_validate_json(reconnect_arrow(
                scene_id, edge_id, edit.from_id or edge.from_, edit.to_id or edge.to, edit.label))
            ui_scenes[scene_id] = updated
            return _ui_payload(updated)
        except Exception as error:
            raise fail(error) from error


@app.post("/ui/scenes/{scene_id}/edges/{edge_id}/reverse")
def ui_reverse_edge(scene_id: str, edge_id: str) -> dict:
    from .workspace import get_scene, lock, fail
    from .mcp_server import reverse_arrow
    with lock:
        try:
            get_scene(scene_id)
            updated = SemanticScene.model_validate_json(reverse_arrow(scene_id, edge_id))
            ui_scenes[scene_id] = updated
            return _ui_payload(updated)
        except Exception as error:
            raise fail(error) from error


@app.get("/ui/export/{scene_id}/{kind}")
def ui_export(scene_id: str, kind: str):
    scene = load_import(scene_id) or ui_scenes.get(scene_id)
    if not scene:
        raise HTTPException(404, "Result is no longer available. Import the image again.")
    if kind == "json":
        return Response(json.dumps(scene.to_dict(), indent=2), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{scene.id}.scene.json"'})
    compiled = compile_scene(scene)
    if kind == "svg":
        return Response(compiled.svg, media_type="image/svg+xml",
                        headers={"Content-Disposition": f'attachment; filename="{scene.id}.svg"'})
    if kind == "html":
        return Response(compiled.html, media_type="text/html",
                        headers={"Content-Disposition": f'attachment; filename="{scene.id}.html"'})
    if kind == "pptx":
        target = data_root() / "imports" / scene.id / "editable.pptx"
        if not target.exists():
            compile_scene(scene, pptx_path=target)
        return FileResponse(target, filename=f"{scene.id}.pptx",
                            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
    raise HTTPException(404, "Unknown export type.")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "engine": "python", "deterministic": True}


@app.get("/capabilities")
def capabilities() -> dict:
    return {
        "modelRequired": False,
        "supported": ["scene validation", "layered layout", "SVG", "HTML inspector", "editable PPTX",
                      "offline rectangle/ellipse/diamond/filled-shape detection",
                      "straight/bent/diagonal connectors", "filled/open/pale arrowheads",
                      "branches, joins, and clean crossings"],
        "reviewRequired": ["OCR/text", "ambiguous arrow direction", "dense or ambiguous junctions",
                           "photos", "hand-drawn diagrams"],
    }


@app.post("/scenes", response_model=SemanticScene)
def create_scene(scene: SemanticScene) -> SemanticScene:
    try:
        return store.create(scene)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.get("/scenes", response_model=list[SemanticScene])
def list_scenes() -> list[SemanticScene]:
    return store.list()


@app.get("/scenes/{scene_id}", response_model=SemanticScene)
def get_scene(scene_id: str) -> SemanticScene:
    try:
        return store.get(scene_id)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error


@app.post("/import/pixels", response_model=SemanticScene)
def import_pixels(request: PixelImportRequest) -> SemanticScene:
    try:
        path = Path(request.path)
        scene = extract_pixels(path, scene_id=request.scene_id)
        return store.create(scene)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.get("/scenes/{scene_id}/svg")
def scene_svg(scene_id: str) -> Response:
    try:
        return Response(compile_scene(store.get(scene_id)).svg, media_type="image/svg+xml")
    except KeyError as error:
        raise HTTPException(404, str(error)) from error


@app.get("/scenes/{scene_id}/inspect", response_class=HTMLResponse)
def scene_inspector(scene_id: str) -> str:
    try:
        return compile_scene(store.get(scene_id)).html
    except KeyError as error:
        raise HTTPException(404, str(error)) from error


from .workspace import router as workspace_router, local_guard
app.include_router(workspace_router)
app.mount('/web', StaticFiles(directory=Path(__file__).parent / 'web'), name='workspace-assets')
app.middleware('http')(local_guard)
