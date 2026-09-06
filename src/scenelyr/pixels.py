"""Offline geometric diagram importer: pixels in, rules out, no model/network."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .models import SemanticScene
from .ocr import available as ocr_available, read_text

MAX_PIXELS = 16_000_000


def _outline_candidates(mask: np.ndarray, width: int, height: int) -> list[tuple[int, int, int, int, str]]:
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []
    found = []
    for index, contour in enumerate(contours):
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if min(w, h) < 24 or area < 500 or area > width * height * .8 or hierarchy[0][index][3] == -1:
            continue
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, .025 * perimeter, True)
        fill = area / (w * h)
        if w * h > width * height * .6 and fill < .3:
            continue
        if fill > .85 or (len(polygon) == 4 and fill >= .65):
            shape = "rectangle"
        elif len(polygon) == 4 and .40 < fill < .65:
            shape = "diamond"
        elif len(polygon) >= 6 and .65 < fill < .85:
            shape = "ellipse"
        else:
            continue
        found.append((x, y, w, h, shape))
    return found


def _overlap_ratio(a: tuple, b: tuple) -> float:
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    intersection = max(0, right - left) * max(0, bottom - top)
    return intersection / min(a[2] * a[3], b[2] * b[3])


def _arrow_score(xs: np.ndarray, ys: np.ndarray, box: tuple[int, int, int, int, str]) -> int:
    """Count connector ink around its closest approach to one object."""
    x, y, w, h, _ = box
    dx = np.maximum(np.maximum(x - xs, xs - (x + w)), 0)
    dy = np.maximum(np.maximum(y - ys, ys - (y + h)), 0)
    nearest = int(np.argmin(dx * dx + dy * dy))
    px, py = xs[nearest], ys[nearest]
    return int(np.count_nonzero((xs - px) ** 2 + (ys - py) ** 2 <= 18 ** 2))


def _decode(path: str | Path) -> tuple[bytes, np.ndarray]:
    raw = Path(path).read_bytes()
    decoded = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
    if decoded is None:
        raise ValueError("Unsupported or invalid image")
    if decoded.ndim == 2:
        image = cv2.cvtColor(decoded, cv2.COLOR_GRAY2BGR)
    elif decoded.shape[2] == 4:
        opacity = decoded[:, :, 3:4].astype(np.float32) / 255
        image = (decoded[:, :, :3] * opacity + 255 * (1 - opacity)).astype(np.uint8)
    else:
        image = decoded[:, :, :3]
    if image.shape[0] * image.shape[1] > MAX_PIXELS:
        raise ValueError("Image exceeds 16 million pixels; resize before importing")
    return raw, image


def extract_pixels(path: str | Path, *, scene_id: str | None = None, use_ocr: bool = True) -> SemanticScene:
    raw, image = _decode(path)
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Close small breaks separately in each axis without flooding whole regions.
    repair_gap = max(5, min(21, round(min(width, height) * .09)))
    horizontal = cv2.getStructuringElement(cv2.MORPH_RECT, (repair_gap, 3))
    vertical = cv2.getStructuringElement(cv2.MORPH_RECT, (3, repair_gap))
    repaired = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, horizontal)
    repaired = cv2.morphologyEx(repaired, cv2.MORPH_CLOSE, vertical)
    candidates = _outline_candidates(ink, width, height)
    repaired_candidates = _outline_candidates(repaired, width, height)
    if len(candidates) < 2 and len(repaired_candidates) > len(candidates):
        candidates = repaired_candidates
    outline_boxes = candidates

    # Saturated filled regions are likely objects; thin connectors disappear on opening.
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    color_mask = np.where((hsv[:, :, 1] > 55) & (hsv[:, :, 2] > 80), 255, 0).astype(np.uint8)
    color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_OPEN, np.ones((13, 13), np.uint8))
    color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    color_contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    color_boxes = []
    for contour in color_contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if min(w, h) < 24 or area < 500 or area > width * height * .8:
            continue
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, .025 * perimeter, True)
        fill = area / (w * h)
        if w * h > width * height * .6 and fill < .3:
            continue
        if len(polygon) == 4 and fill < .68:
            points = polygon.reshape(-1, 2)
            diagonal = sum(abs(int(points[(i + 1) % 4][0]) - int(points[i][0])) > 5 and
                           abs(int(points[(i + 1) % 4][1]) - int(points[i][1])) > 5 for i in range(4))
            shape = "diamond" if diagonal == 4 else "parallelogram"
        elif len(polygon) >= 6 and fill < .9:
            shape = "ellipse"
        else:
            shape = "rectangle"
        color_boxes.append((x, y, w, h, shape))

    # Large outlines crossing filled nodes are normally connector loops.
    candidates = [box for box in outline_boxes if not any(_overlap_ratio(box, color) > .15 for color in color_boxes)] + color_boxes
    candidates.sort(key=lambda box: (box[1], box[0]))
    boxes = [box for box in candidates if not any(
        outer != box and outer[0] <= box[0] and outer[1] <= box[1] and
        outer[0] + outer[2] >= box[0] + box[2] and outer[1] + outer[3] >= box[1] + box[3]
        for outer in candidates)]
    unique = []
    for box in boxes:
        x, y, w, h, _ = box
        if not any(abs(x - other[0]) < 5 and abs(y - other[1]) < 5 and abs(w - other[2]) < 10 and abs(h - other[3]) < 10 for other in unique):
            unique.append(box)
    boxes = sorted(unique, key=lambda box: (box[1], box[0]))

    nodes, residual = [], repaired.copy()
    for index, (x, y, w, h, shape) in enumerate(boxes):
        nodes.append({"id": f"object-{index + 1}", "label": f"Object {index + 1}", "kind": "asset",
                      "metadata": {"shape": shape, "sourceBounds": [x, y, w, h],
                                   "labelStatus": "unread", "method": "pixel-contour"}})
        cv2.rectangle(residual, (max(0, x - 5), max(0, y - 5)),
                      (min(width - 1, x + w + 5), min(height - 1, y + h + 5)), 0, -1)

    ocr_items, ocr_error = [], None
    if use_ocr and ocr_available():
        try:
            ocr_items = read_text(path, width, height)
            for node, (x, y, w, h, _) in zip(nodes, boxes):
                matches = []
                for item in ocr_items:
                    tx, ty, tw, th = item["bounds"]
                    center_x, center_y = tx + tw / 2, ty + th / 2
                    if x <= center_x <= x + w and y <= center_y <= y + h:
                        matches.append(item)
                if matches:
                    matches.sort(key=lambda item: (item["bounds"][1], item["bounds"][0]))
                    node["label"] = " ".join(item["text"] for item in matches)
                    node["metadata"]["labelStatus"] = "ocr"
                    node["metadata"]["ocrConfidence"] = round(
                        sum(item["confidence"] for item in matches) / len(matches), 4)
                    node["metadata"]["ocrBounds"] = [item["bounds"] for item in matches]
        except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as error:
            ocr_error = str(error)

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(residual, 8)
    edges = []
    unread = sum(node["metadata"]["labelStatus"] == "unread" for node in nodes)
    warnings = []
    if unread:
        warnings.append(f"Text was not recovered for {unread} object(s); placeholder names remain.")
    if not use_ocr or not ocr_available():
        warnings.append("Local OCR is unavailable; geometry extraction still completed.")
    if ocr_error:
        warnings.append("Local OCR failed; geometry extraction still completed.")
    unknown_directions = 0
    for component in range(1, component_count):
        if stats[component, cv2.CC_STAT_AREA] < 12:
            continue
        ys, xs = np.where(labels == component)
        attached = []
        for index, (x, y, w, h, _) in enumerate(boxes):
            dx = np.maximum(np.maximum(x - xs, xs - (x + w)), 0)
            dy = np.maximum(np.maximum(y - ys, ys - (y + h)), 0)
            if np.min(dx * dx + dy * dy) <= 12 ** 2:
                attached.append(index)
        if len(attached) == 2:
            first, second = attached
            first_score, second_score = _arrow_score(xs, ys, boxes[first]), _arrow_score(xs, ys, boxes[second])
            direction = "unknown"
            if max(first_score, second_score) >= min(first_score, second_score) * 1.35 + 4:
                if first_score > second_score:
                    first, second = second, first
                direction = "inferred"
            else:
                unknown_directions += 1
            edges.append({"id": f"connection-{len(edges) + 1}", "from": nodes[first]["id"], "to": nodes[second]["id"],
                          "kind": "relationship", "metadata": {"direction": direction,
                          "endpointInk": [first_score, second_score], "requiresReview": True,
                          "method": "pixel-connectivity"}})
        elif len(attached) > 2:
            warnings.append("Connector touches more than two objects; crossing or branch withheld.")
    if unknown_directions:
        warnings.append(f"Arrow direction could not be inferred for {unknown_directions} connection(s).")
    if not nodes:
        warnings.append("No supported enclosed objects detected; image is not decomposed.")
    payload = {"version": "0.2", "id": scene_id or "pixels-" + hashlib.sha256(raw).hexdigest()[:16],
               "nodes": nodes, "edges": edges, "groups": [], "constraints": [], "assets": [],
               "metadata": {"importMode": "deterministic", "sourceImage": str(path),
                            "sourceSize": [width, height], "warnings": warnings,
                            "requiresReview": True, "modelUsed": False,
                            "ocrUsesLocalModel": bool(use_ocr and ocr_available()),
                            "ocrEngine": "apple-vision-local" if use_ocr and ocr_available() else None,
                            "ocrObservations": len(ocr_items)}}
    return SemanticScene.model_validate(payload)


def extract(path: str | Path) -> dict:
    """Compatibility helper for the original standalone experiment."""
    return extract_pixels(path, use_ocr=False).to_dict()
