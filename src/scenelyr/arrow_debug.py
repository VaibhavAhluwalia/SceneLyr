"""Deterministic, reviewable debug stages for connector extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .models import SemanticScene
from .image_masks import build_semantic_masks
from .path_detector import prepare_path_mask


STAGE_FILENAMES = {
    "grayscale": "01-grayscale.png",
    "threshold": "02-threshold.png",
    "objectMask": "03-object-mask.png",
    "textMask": "04-text-mask.png",
    "connectorMask": "05-connector-mask.png",
    "bridgedConnectors": "06-bridged-connectors.png",
    "pathSkeleton": "07-path-skeleton.png",
    "tracedPaths": "08-traced-paths.png",
    "maskOverlay": "09-mask-overlay.png",
    "components": "10-components.png",
    "lineCandidates": "11-line-candidates.png",
}


def _load_image(path: str | Path) -> np.ndarray:
    raw = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot create arrow debug stages from {path}")
    return image


def build_arrow_debug(image: np.ndarray, scene: SemanticScene) -> tuple[dict[str, np.ndarray], list[dict[str, int]], dict[str, Any]]:
    """Return named debug images and raw line candidates without changing the scene."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    boxes = []
    for node in scene.nodes:
        bounds = node.metadata.get("sourceBounds")
        if bounds and len(bounds) == 4:
            boxes.append((*[int(value) for value in bounds], node.metadata.get("shape", "rectangle")))
    text_bounds = [item["bounds"] for item in scene.metadata.get("ocrRegions", [])
                   if len(item.get("bounds", [])) == 4]
    cutoff = int(scene.metadata.get("arrowDetectionProfile", {}).get("settings", {}).get("brightnessCutoff", 220))
    masks, mask_profile = build_semantic_masks(gray, boxes, text_bounds, brightness_cutoff=cutoff)
    threshold = masks["rawInk"]
    connector_mask = masks["connectorMask"]
    prepared_paths, path_profile = prepare_path_mask(connector_mask, boxes)
    height, width = connector_mask.shape

    mask_overlay = image.copy()
    overlay = np.zeros_like(image)
    overlay[masks["objectMask"] > 0] = (230, 90, 80)
    overlay[masks["textMask"] > 0] = (40, 175, 230)
    overlay[masks["connectorMask"] > 0] = (70, 175, 85)
    active = np.any(overlay > 0, axis=2)
    mask_overlay[active] = cv2.addWeighted(mask_overlay, .35, overlay, .65, 0)[active]

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(connector_mask, 8)
    components = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    palette = ((0, 92, 255), (64, 190, 64), (255, 96, 32), (220, 70, 190), (0, 180, 220))
    for component in range(1, component_count):
        area = int(stats[component, cv2.CC_STAT_AREA])
        if area < 12:
            continue
        color = palette[(component - 1) % len(palette)]
        components[labels == component] = color

    min_length = max(12, round(min(width, height) * 0.025))
    max_gap = max(4, round(min(width, height) * 0.012))
    lines = cv2.HoughLinesP(
        connector_mask,
        rho=1,
        theta=np.pi / 180,
        threshold=max(10, min_length // 2),
        minLineLength=min_length,
        maxLineGap=max_gap,
    )
    overlay = image.copy()
    candidates: list[dict[str, int]] = []
    if lines is not None:
        normalized = sorted(tuple(int(value) for value in line) for line in lines.reshape(-1, 4))
        for index, (x1, y1, x2, y2) in enumerate(normalized, start=1):
            candidates.append({"id": index, "x1": x1, "y1": y1, "x2": x2, "y2": y2})
            cv2.line(overlay, (x1, y1), (x2, y2), (0, 0, 255), 3, cv2.LINE_AA)
            cv2.circle(overlay, (x1, y1), 5, (255, 110, 0), -1)
            cv2.circle(overlay, (x2, y2), 5, (0, 180, 60), -1)

    traced_paths = image.copy()
    for edge in scene.edges:
        if edge.metadata.get("method") != "pixel-path-graph":
            continue
        points = edge.metadata.get("points", [])
        if len(points) < 2:
            continue
        polyline = np.asarray(points, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(traced_paths, [polyline], False, (40, 70, 235), 4, cv2.LINE_AA)
        cv2.circle(traced_paths, tuple(points[0]), 6, (255, 130, 20), -1)
        cv2.circle(traced_paths, tuple(points[-1]), 7, (35, 180, 70), -1)

    return {
        "grayscale": gray,
        "threshold": threshold,
        "objectMask": masks["objectMask"],
        "textMask": masks["textMask"],
        "connectorMask": connector_mask,
        "bridgedConnectors": prepared_paths["bridged"],
        "pathSkeleton": prepared_paths["skeleton"],
        "tracedPaths": traced_paths,
        "maskOverlay": mask_overlay,
        "components": components,
        "lineCandidates": overlay,
    }, candidates, {"mask": mask_profile, "path": path_profile}


def persist_arrow_debug(scene: SemanticScene, source_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Write every M1 stage and a manifest beside the persisted scene."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stages, candidates, profiles = build_arrow_debug(_load_image(source_path), scene)
    stage_records = []
    for name, image in stages.items():
        path = output / STAGE_FILENAMES[name]
        if not cv2.imwrite(str(path), image):
            raise OSError(f"Could not write arrow debug stage: {path}")
        stage_records.append({"id": name, "file": str(path)})
    manifest = {
        "schemaVersion": 3,
        "sceneId": scene.id,
        "sourceImage": str(source_path),
        "maskProfile": profiles["mask"],
        "pathProfile": scene.metadata.get("pathDetectionProfile", profiles["path"]),
        "stages": stage_records,
        "lineCandidates": candidates,
        "candidateCount": len(candidates),
        "detectedEdgeCount": len(scene.edges),
        "reviewRequired": True,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest"] = str(manifest_path)
    scene.metadata["arrowDebug"] = manifest
    return manifest
