"""Deterministic arrow recovery for aligned flowchart nodes."""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

PROFILE_VERSION = 1
DEFAULT_ARROW_SETTINGS = {
    "brightnessCutoff": 220,
    "minimumCoverage": 0.72,
    "corridorWidthScale": 0.18,
    "minimumCorridorHalfWidth": 12,
    "endpointNodeScale": 0.22,
    "minimumEndpointLength": 8,
    "maximumEndpointLength": 64,
    "directionRatio": 1.25,
    "directionMargin": 8,
}


def build_detection_profile(
    gray: np.ndarray,
    boxes: list[tuple[int, int, int, int, str]],
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a versioned, image-scaled profile with explicit override provenance."""
    overrides = overrides or {}
    allowed = {*DEFAULT_ARROW_SETTINGS, "endpointLength"}
    unknown = sorted(set(overrides) - allowed)
    if unknown:
        raise ValueError(f"Unknown arrow setting(s): {', '.join(unknown)}")
    settings = dict(DEFAULT_ARROW_SETTINGS)
    supplied = {key: value for key, value in overrides.items() if key in settings}
    settings.update(supplied)
    if not 0 <= int(settings["brightnessCutoff"]) <= 254:
        raise ValueError("brightnessCutoff must be between 0 and 254")
    if not 0 < float(settings["minimumCoverage"]) <= 1:
        raise ValueError("minimumCoverage must be greater than 0 and at most 1")
    if float(settings["corridorWidthScale"]) <= 0 or int(settings["minimumCorridorHalfWidth"]) < 1:
        raise ValueError("corridor width settings must be positive")
    if float(settings["endpointNodeScale"]) <= 0:
        raise ValueError("endpointNodeScale must be positive")
    if int(settings["minimumEndpointLength"]) < 1 or int(settings["maximumEndpointLength"]) < int(settings["minimumEndpointLength"]):
        raise ValueError("endpoint length limits are invalid")
    if float(settings["directionRatio"]) < 1 or int(settings["directionMargin"]) < 0:
        raise ValueError("direction comparison settings are invalid")
    short_sides = [min(width, height) for _, _, width, height, _ in boxes]
    median_short_side = float(np.median(short_sides)) if short_sides else 100.0
    endpoint_length = round(median_short_side * float(settings["endpointNodeScale"]))
    endpoint_length = max(int(settings["minimumEndpointLength"]),
                          min(int(settings["maximumEndpointLength"]), endpoint_length))
    if "endpointLength" in overrides:
        endpoint_length = int(overrides["endpointLength"])
        if not 1 <= endpoint_length <= 512:
            raise ValueError("endpointLength must be between 1 and 512")
        supplied["endpointLength"] = endpoint_length
    return {
        "version": PROFILE_VERSION,
        "mode": "automatic-with-overrides" if supplied else "automatic",
        "sourceSize": [int(gray.shape[1]), int(gray.shape[0])],
        "measurements": {"medianNodeShortSide": round(median_short_side, 2)},
        "settings": {**settings, "endpointLength": endpoint_length},
        "overrides": supplied,
        "fallbacksUsed": [] if boxes else ["medianNodeShortSide"],
    }


def _blocked(
    first: tuple[int, int, int, int, str],
    second: tuple[int, int, int, int, str],
    boxes: list[tuple[int, int, int, int, str]],
    axis: str,
) -> bool:
    ax, ay, aw, ah, _ = first
    bx, by, bw, bh, _ = second
    if axis == "horizontal":
        left, right = sorted((first, second), key=lambda item: item[0])
        corridor = (left[0] + left[2], min(ay, by), right[0], max(ay + ah, by + bh))
    else:
        top, bottom = sorted((first, second), key=lambda item: item[1])
        corridor = (min(ax, bx), top[1] + top[3], max(ax + aw, bx + bw), bottom[1])
    x1, y1, x2, y2 = corridor
    for candidate in boxes:
        if candidate is first or candidate is second:
            continue
        x, y, width, height, _ = candidate
        if x < x2 and x + width > x1 and y < y2 and y + height > y1:
            return True
    return False


def _corridor_candidate(
    mask: np.ndarray,
    first: tuple[int, int, int, int, str],
    second: tuple[int, int, int, int, str],
    axis: str,
    settings: dict[str, Any],
) -> dict[str, Any] | None:
    ax, ay, aw, ah, _ = first
    bx, by, bw, bh, _ = second
    ac = (ax + aw / 2, ay + ah / 2)
    bc = (bx + bw / 2, by + bh / 2)
    half_width = max(int(settings["minimumCorridorHalfWidth"]),
                     round(min(aw, ah, bw, bh) * float(settings["corridorWidthScale"])))
    if axis == "horizontal":
        left, right = sorted((first, second), key=lambda item: item[0])
        start, end = left[0] + left[2], right[0]
        center = round((ac[1] + bc[1]) / 2)
        region = mask[max(0, center - half_width):center + half_width + 1, start:end]
        occupied = np.count_nonzero(np.any(region, axis=0))
        length = max(1, end - start)
        end_span = min(int(settings["endpointLength"]), length)
        endpoint_ink = [int(np.count_nonzero(region[:, :end_span])), int(np.count_nonzero(region[:, -end_span:]))]
        points = [[start, center], [end, center]]
        ordered = [left, right]
    else:
        top, bottom = sorted((first, second), key=lambda item: item[1])
        start, end = top[1] + top[3], bottom[1]
        center = round((ac[0] + bc[0]) / 2)
        region = mask[start:end, max(0, center - half_width):center + half_width + 1]
        occupied = np.count_nonzero(np.any(region, axis=1))
        length = max(1, end - start)
        end_span = min(int(settings["endpointLength"]), length)
        endpoint_ink = [int(np.count_nonzero(region[:end_span, :])), int(np.count_nonzero(region[-end_span:, :]))]
        points = [[center, start], [center, end]]
        ordered = [top, bottom]
    coverage = float(occupied / length)
    if length < 8 or coverage < float(settings["minimumCoverage"]):
        return None
    low, high = min(endpoint_ink), max(endpoint_ink)
    direction_known = bool(high >= low * float(settings["directionRatio"]) + int(settings["directionMargin"]))
    if direction_known and endpoint_ink[0] > endpoint_ink[1]:
        ordered.reverse()
        points.reverse()
    confidence = float(min(1.0, coverage * .72 + min(1.0, high / max(1, low + 25)) * .28))
    return {
        "fromBox": ordered[0],
        "toBox": ordered[1],
        "points": points,
        "coverage": round(coverage, 4),
        "endpointInk": endpoint_ink,
        "direction": "inferred" if direction_known else "unknown",
        "confidence": round(confidence, 4),
        "endpointLength": end_span,
        "corridorHalfWidth": half_width,
    }


def detect_aligned_arrows(
    gray: np.ndarray,
    boxes: list[tuple[int, int, int, int, str]],
    node_ids: list[str],
    *,
    profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Recover straight arrows between adjacent, horizontally or vertically aligned nodes."""
    profile = profile or build_detection_profile(gray, boxes)
    settings = profile["settings"]
    brightness_cutoff = int(settings["brightnessCutoff"])
    mask = np.where(gray <= brightness_cutoff, 255, 0).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 7), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 3), np.uint8))
    found: list[dict[str, Any]] = []
    for first_index, first in enumerate(boxes):
        ax, ay, aw, ah, _ = first
        ac = (ax + aw / 2, ay + ah / 2)
        for second_index in range(first_index + 1, len(boxes)):
            second = boxes[second_index]
            bx, by, bw, bh, _ = second
            bc = (bx + bw / 2, by + bh / 2)
            horizontal = abs(ac[1] - bc[1]) <= min(ah, bh) * .28
            vertical = abs(ac[0] - bc[0]) <= min(aw, bw) * .28
            axis = "horizontal" if horizontal else "vertical" if vertical else None
            if axis is None or _blocked(first, second, boxes, axis):
                continue
            candidate = _corridor_candidate(mask, first, second, axis, settings)
            if candidate is None:
                continue
            from_index = boxes.index(candidate.pop("fromBox"))
            to_index = boxes.index(candidate.pop("toBox"))
            found.append({
                "id": f"connection-{len(found) + 1}",
                "from": node_ids[from_index],
                "to": node_ids[to_index],
                "kind": "relationship",
                "metadata": {
                    **candidate,
                    "axis": axis,
                    "brightnessCutoff": brightness_cutoff,
                    "profileVersion": profile["version"],
                    "requiresReview": bool(candidate["direction"] == "unknown" or candidate["confidence"] < .82),
                    "method": "pixel-intensity-corridor",
                },
            })
    return found


def attach_branch_labels(edges: list[dict[str, Any]], ocr_items: list[dict[str, Any]]) -> None:
    """Attach standalone Yes/No OCR observations to the nearest recovered path."""
    for item in ocr_items:
        text = str(item.get("text", "")).strip()
        if text.casefold() not in {"yes", "no"}:
            continue
        x, y, width, height = item["bounds"]
        point = (x + width / 2, y + height / 2)
        best: tuple[float, dict[str, Any]] | None = None
        for edge in edges:
            path = edge.get("metadata", {}).get("points", [])
            if len(path) != 2:
                continue
            (x1, y1), (x2, y2) = path
            dx, dy = x2 - x1, y2 - y1
            length_squared = dx * dx + dy * dy
            if not length_squared:
                continue
            position = max(0.0, min(1.0, ((point[0] - x1) * dx + (point[1] - y1) * dy) / length_squared))
            nearest = (x1 + position * dx, y1 + position * dy)
            distance = math.hypot(point[0] - nearest[0], point[1] - nearest[1])
            if best is None or distance < best[0]:
                best = (distance, edge)
        if best is not None and best[0] <= 45:
            best[1]["label"] = text
            best[1]["metadata"]["labelConfidence"] = item.get("confidence")
            best[1]["metadata"]["labelBounds"] = item["bounds"]
