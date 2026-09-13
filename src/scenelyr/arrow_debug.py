"""Deterministic, reviewable debug stages for connector extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .models import SemanticScene


STAGE_FILENAMES = {
    "grayscale": "01-grayscale.png",
    "threshold": "02-threshold.png",
    "connectorMask": "03-connector-mask.png",
    "components": "04-components.png",
    "lineCandidates": "05-line-candidates.png",
}


def _load_image(path: str | Path) -> np.ndarray:
    raw = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot create arrow debug stages from {path}")
    return image


def build_arrow_debug(image: np.ndarray, scene: SemanticScene) -> tuple[dict[str, np.ndarray], list[dict[str, int]]]:
    """Return named debug images and raw line candidates without changing the scene."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, threshold = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    connector_mask = threshold.copy()
    height, width = connector_mask.shape
    for node in scene.nodes:
        bounds = node.metadata.get("sourceBounds")
        if not bounds or len(bounds) != 4:
            continue
        x, y, box_width, box_height = (int(value) for value in bounds)
        cv2.rectangle(
            connector_mask,
            (max(0, x - 5), max(0, y - 5)),
            (min(width - 1, x + box_width + 5), min(height - 1, y + box_height + 5)),
            0,
            -1,
        )

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

    return {
        "grayscale": gray,
        "threshold": threshold,
        "connectorMask": connector_mask,
        "components": components,
        "lineCandidates": overlay,
    }, candidates


def persist_arrow_debug(scene: SemanticScene, source_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Write every M1 stage and a manifest beside the persisted scene."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stages, candidates = build_arrow_debug(_load_image(source_path), scene)
    stage_records = []
    for name, image in stages.items():
        path = output / STAGE_FILENAMES[name]
        if not cv2.imwrite(str(path), image):
            raise OSError(f"Could not write arrow debug stage: {path}")
        stage_records.append({"id": name, "file": str(path)})
    manifest = {
        "schemaVersion": 1,
        "sceneId": scene.id,
        "sourceImage": str(source_path),
        "nodeMaskPadding": 5,
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
