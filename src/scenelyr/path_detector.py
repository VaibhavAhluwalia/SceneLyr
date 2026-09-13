"""Deterministic tracing for bent, diagonal, curved, and lightly broken connectors."""

from __future__ import annotations

from collections import deque
from typing import Any

import cv2
import numpy as np


def build_path_profile(boxes: list[tuple[int, int, int, int, str]]) -> dict[str, Any]:
    short_sides = [min(width, height) for _, _, width, height, _ in boxes]
    median_short_side = float(np.median(short_sides)) if short_sides else 80.0
    return {
        "version": 1,
        "measurements": {"medianNodeShortSide": round(median_short_side, 2)},
        "settings": {
            "gapSpan": max(3, min(17, round(median_short_side * .09))),
            "attachmentDistance": max(5, min(20, round(median_short_side * .14))),
            "minimumComponentArea": max(10, round(median_short_side * .18)),
            "simplifyEpsilon": max(1.5, min(6.0, median_short_side * .035)),
        },
    }


def _directional_kernel(span: int, direction: str) -> np.ndarray:
    if direction == "horizontal":
        return np.ones((3, span), np.uint8)
    if direction == "vertical":
        return np.ones((span, 3), np.uint8)
    kernel = np.zeros((span, span), np.uint8)
    if direction == "diagonal-down":
        cv2.line(kernel, (0, 0), (span - 1, span - 1), 1, 3)
    else:
        cv2.line(kernel, (0, span - 1), (span - 1, 0), 1, 3)
    return kernel


def bridge_connector_gaps(mask: np.ndarray, span: int) -> tuple[np.ndarray, np.ndarray]:
    """Close short gaps independently in four directions and record added pixels."""
    binary = np.where(mask > 0, 255, 0).astype(np.uint8)
    variants = [binary]
    for direction in ("horizontal", "vertical", "diagonal-down", "diagonal-up"):
        variants.append(cv2.morphologyEx(binary, cv2.MORPH_CLOSE, _directional_kernel(span, direction)))
    bridged = variants[0]
    for variant in variants[1:]:
        bridged = cv2.bitwise_or(bridged, variant)
    added = cv2.bitwise_and(bridged, cv2.bitwise_not(binary))
    return bridged, added


def skeletonize(mask: np.ndarray) -> np.ndarray:
    """Reduce binary strokes to a deterministic one-pixel-wide centerline."""
    working = np.where(mask > 0, 255, 0).astype(np.uint8)
    skeleton = np.zeros_like(working)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    while cv2.countNonZero(working):
        opened = cv2.morphologyEx(working, cv2.MORPH_OPEN, element)
        skeleton = cv2.bitwise_or(skeleton, cv2.subtract(working, opened))
        working = cv2.erode(working, element)
    return skeleton


def prepare_path_mask(mask: np.ndarray, boxes: list[tuple[int, int, int, int, str]]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    profile = build_path_profile(boxes)
    bridged, added = bridge_connector_gaps(mask, int(profile["settings"]["gapSpan"]))
    skeleton = skeletonize(bridged)
    profile["pixels"] = {
        "input": int(np.count_nonzero(mask)),
        "bridged": int(np.count_nonzero(bridged)),
        "addedByBridging": int(np.count_nonzero(added)),
        "skeleton": int(np.count_nonzero(skeleton)),
    }
    return {"bridged": bridged, "bridgePixels": added, "skeleton": skeleton}, profile


def _distance_to_box(xs: np.ndarray, ys: np.ndarray, box: tuple[int, int, int, int, str]) -> np.ndarray:
    x, y, width, height, _ = box
    dx = np.maximum(np.maximum(x - xs, xs - (x + width - 1)), 0)
    dy = np.maximum(np.maximum(y - ys, ys - (y + height - 1)), 0)
    return dx * dx + dy * dy


def _nearest_pixel(xs: np.ndarray, ys: np.ndarray, box: tuple[int, int, int, int, str]) -> tuple[int, int]:
    index = int(np.argmin(_distance_to_box(xs, ys, box)))
    return int(xs[index]), int(ys[index])


def _nearest_path_pixel(path_mask: np.ndarray, point: tuple[int, int], component_mask: np.ndarray) -> tuple[int, int] | None:
    ys, xs = np.where((path_mask > 0) & component_mask)
    if not len(xs):
        return None
    distances = (xs - point[0]) ** 2 + (ys - point[1]) ** 2
    index = int(np.argmin(distances))
    return int(xs[index]), int(ys[index])


def _shortest_path(skeleton: np.ndarray, start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    height, width = skeleton.shape
    queue = deque([start])
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    neighbors = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))
    while queue:
        current = queue.popleft()
        if current == end:
            break
        for dx, dy in neighbors:
            candidate = current[0] + dx, current[1] + dy
            if not (0 <= candidate[0] < width and 0 <= candidate[1] < height):
                continue
            if candidate in previous or not skeleton[candidate[1], candidate[0]]:
                continue
            previous[candidate] = current
            queue.append(candidate)
    if end not in previous:
        return []
    path, current = [], end
    while current is not None:
        path.append(current)
        current = previous[current]
    return list(reversed(path))


def _simplify_path(path: list[tuple[int, int]], epsilon: float) -> list[list[int]]:
    if len(path) <= 2:
        return [[x, y] for x, y in path]
    contour = np.array(path, dtype=np.int32).reshape(-1, 1, 2)
    simplified = cv2.approxPolyDP(contour, epsilon, False).reshape(-1, 2)
    points = [[int(x), int(y)] for x, y in simplified]
    if points[0] != list(path[0]):
        points.insert(0, list(path[0]))
    if points[-1] != list(path[-1]):
        points.append(list(path[-1]))
    return points


def _endpoint_ink(xs: np.ndarray, ys: np.ndarray, point: tuple[int, int], radius: int) -> int:
    return int(np.count_nonzero((xs - point[0]) ** 2 + (ys - point[1]) ** 2 <= radius ** 2))


def trace_connector_paths(
    connector_mask: np.ndarray,
    boxes: list[tuple[int, int, int, int, str]],
    node_ids: list[str],
    *,
    known_pairs: set[frozenset[str]] | None = None,
    direction_settings: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, np.ndarray]]:
    """Trace unambiguous two-object connector components into ordered scene edges."""
    known_pairs = known_pairs or set()
    direction_settings = direction_settings or {}
    prepared, profile = prepare_path_mask(connector_mask, boxes)
    bridged, added, skeleton = prepared["bridged"], prepared["bridgePixels"], prepared["skeleton"]
    count, labels, stats, _ = cv2.connectedComponentsWithStats(bridged, 8)
    attachment_distance = int(profile["settings"]["attachmentDistance"])
    minimum_area = int(profile["settings"]["minimumComponentArea"])
    epsilon = float(profile["settings"]["simplifyEpsilon"])
    endpoint_radius = int(direction_settings.get("endpointLength", max(8, attachment_distance)))
    ratio = float(direction_settings.get("directionRatio", 1.25))
    margin = int(direction_settings.get("directionMargin", 8))
    edges: list[dict[str, Any]] = []
    withheld: list[dict[str, Any]] = []

    for component in range(1, count):
        area = int(stats[component, cv2.CC_STAT_AREA])
        if area < minimum_area:
            continue
        component_mask = labels == component
        ys, xs = np.where(component_mask)
        attached = [index for index, box in enumerate(boxes)
                    if int(np.min(_distance_to_box(xs, ys, box))) <= attachment_distance ** 2]
        if len(attached) != 2:
            if len(attached) > 2:
                withheld.append({"component": component, "reason": "touches-more-than-two-objects",
                                 "objects": [node_ids[index] for index in attached]})
            continue
        first, second = attached
        pair = frozenset((node_ids[first], node_ids[second]))
        if pair in known_pairs:
            continue
        first_near = _nearest_pixel(xs, ys, boxes[first])
        second_near = _nearest_pixel(xs, ys, boxes[second])
        # Search on the complete bridged stroke. Morphological skeletons are useful
        # for review, but can disconnect at sharp corners and arrowheads.
        start = _nearest_path_pixel(bridged, first_near, component_mask)
        end = _nearest_path_pixel(bridged, second_near, component_mask)
        if start is None or end is None:
            continue
        pixel_path = _shortest_path(np.where(component_mask, bridged, 0).astype(np.uint8), start, end)
        if not pixel_path:
            continue
        endpoint_ink = [_endpoint_ink(xs, ys, start, endpoint_radius),
                        _endpoint_ink(xs, ys, end, endpoint_radius)]
        low, high = min(endpoint_ink), max(endpoint_ink)
        direction_known = high >= low * ratio + margin
        if direction_known and endpoint_ink[0] > endpoint_ink[1]:
            first, second = second, first
            pixel_path.reverse()
            endpoint_ink.reverse()
        points = _simplify_path(pixel_path, epsilon)
        added_count = int(np.count_nonzero(added[component_mask]))
        bridge_fraction = added_count / max(1, area)
        confidence = max(.0, min(1.0, .9 - bridge_fraction * 1.5))
        edges.append({
            "id": f"path-connection-{len(edges) + 1}",
            "from": node_ids[first],
            "to": node_ids[second],
            "kind": "relationship",
            "metadata": {
                "points": points,
                "direction": "inferred" if direction_known else "unknown",
                "endpointInk": endpoint_ink,
                "confidence": round(confidence, 4),
                "bridgePixels": added_count,
                "bridgeFraction": round(bridge_fraction, 4),
                "componentArea": area,
                "pathPixelLength": len(pixel_path),
                "profileVersion": profile["version"],
                "requiresReview": bool(not direction_known or confidence < .75),
                "method": "pixel-path-graph",
            },
        })
        known_pairs.add(pair)
    profile["withheld"] = withheld
    profile["tracedPathCount"] = len(edges)
    return edges, profile, prepared
