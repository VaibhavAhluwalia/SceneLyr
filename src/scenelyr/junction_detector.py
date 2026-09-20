"""Deterministic branch, join, and crossing recovery for multi-object ink components."""

from __future__ import annotations

from itertools import combinations
from math import hypot
from typing import Any

import cv2
import numpy as np

from .arrowhead_detector import classify_arrowheads
from .path_detector import (
    _distance_to_box,
    _nearest_path_pixel,
    _nearest_pixel,
    _shortest_path,
    _simplify_path,
    prepare_path_mask,
)


def build_junction_profile(boxes: list[tuple[int, int, int, int, str]]) -> dict[str, Any]:
    short_sides = [min(width, height) for _, _, width, height, _ in boxes]
    median_short_side = float(np.median(short_sides)) if short_sides else 80.0
    return {
        "version": 1,
        "measurements": {"medianNodeShortSide": round(median_short_side, 2)},
        "settings": {
            "centerRadius": max(7, min(16, round(median_short_side * .225))),
            "crossingOppositionTolerance": .35,
            "junctionDotDensity": .77,
            "maximumAttachments": 4,
        },
    }


def _crossing_pairs(points: dict[int, tuple[int, int]]) -> tuple[list[tuple[int, int]], float]:
    indices = list(points)
    center = np.mean(np.asarray([points[index] for index in indices], dtype=float), axis=0)
    vectors = {index: np.asarray(points[index], dtype=float) - center for index in indices}
    pairings = [
        ((indices[0], indices[1]), (indices[2], indices[3])),
        ((indices[0], indices[2]), (indices[1], indices[3])),
        ((indices[0], indices[3]), (indices[1], indices[2])),
    ]

    def opposition(pair: tuple[int, int]) -> float:
        first, second = vectors[pair[0]], vectors[pair[1]]
        denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
        cosine = float(np.dot(first, second) / denominator) if denominator else 1.0
        return abs(cosine + 1.0)

    scored = [(sum(opposition(pair) for pair in pairing), list(pairing)) for pairing in pairings]
    score, pairs = min(scored, key=lambda item: item[0])
    return pairs, float(score / 2)


def _junction_center(component_mask: np.ndarray, points: dict[int, tuple[int, int]]) -> tuple[int, int]:
    target = np.mean(np.asarray(list(points.values()), dtype=float), axis=0)
    ys, xs = np.where(component_mask)
    index = int(np.argmin((xs - target[0]) ** 2 + (ys - target[1]) ** 2))
    return int(xs[index]), int(ys[index])


def _center_density(component_mask: np.ndarray, center: tuple[int, int], radius: int) -> float:
    height, width = component_mask.shape
    x1, x2 = max(0, center[0] - radius), min(width, center[0] + radius + 1)
    y1, y2 = max(0, center[1] - radius), min(height, center[1] + radius + 1)
    yy, xx = np.ogrid[y1:y2, x1:x2]
    disk = (xx - center[0]) ** 2 + (yy - center[1]) ** 2 <= radius ** 2
    return float(np.count_nonzero(component_mask[y1:y2, x1:x2] & disk) / max(1, np.count_nonzero(disk)))


def detect_junctions(
    gray: np.ndarray,
    connector_mask: np.ndarray,
    boxes: list[tuple[int, int, int, int, str]],
    node_ids: list[str],
    *,
    known_pairs: set[frozenset[str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Recover crossings and arrowhead-supported branches/joins from shared ink."""
    known_pairs = known_pairs or set()
    prepared, path_profile = prepare_path_mask(connector_mask, boxes)
    bridged = prepared["bridged"]
    count, labels, stats, _ = cv2.connectedComponentsWithStats(bridged, 8)
    profile = build_junction_profile(boxes)
    settings = profile["settings"]
    attachment_distance = int(path_profile["settings"]["attachmentDistance"])
    minimum_area = int(path_profile["settings"]["minimumComponentArea"])
    epsilon = float(path_profile["settings"]["simplifyEpsilon"])
    output: list[dict[str, Any]] = []
    withheld: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for component in range(1, count):
        area = int(stats[component, cv2.CC_STAT_AREA])
        if area < minimum_area:
            continue
        component_mask = labels == component
        ys, xs = np.where(component_mask)
        attached = [index for index, box in enumerate(boxes)
                    if int(np.min(_distance_to_box(xs, ys, box))) <= attachment_distance ** 2]
        if len(attached) < 3:
            continue
        if len(attached) > int(settings["maximumAttachments"]):
            withheld.append({"component": component, "reason": "too-many-attachments",
                             "objects": [node_ids[index] for index in attached]})
            continue
        near = {index: _nearest_pixel(xs, ys, boxes[index]) for index in attached}
        endpoints = {index: _nearest_path_pixel(bridged, near[index], component_mask) for index in attached}
        if any(point is None for point in endpoints.values()):
            withheld.append({"component": component, "reason": "attachment-without-path"})
            continue
        endpoints = {index: point for index, point in endpoints.items() if point is not None}
        center = _junction_center(component_mask, endpoints)
        density = _center_density(component_mask, center, int(settings["centerRadius"]))
        component_path_mask = np.where(component_mask, bridged, 0).astype(np.uint8)
        routes: dict[frozenset[int], list[list[int]]] = {}
        route_edges: list[dict[str, Any]] = []
        for first, second in combinations(attached, 2):
            path = _shortest_path(component_path_mask, endpoints[first], endpoints[second])
            if not path:
                continue
            points = _simplify_path(path, epsilon)
            routes[frozenset((first, second))] = points
            route_edges.append({
                "from": node_ids[first], "to": node_ids[second], "kind": "relationship",
                "metadata": {"points": points, "direction": "unknown", "requiresReview": True},
            })
        if len(routes) < len(attached) - 1:
            withheld.append({"component": component, "reason": "incomplete-route-set"})
            continue

        selected: list[tuple[int, int]] = []
        junction_type = "ambiguous"
        opposition = None
        if len(attached) == 4:
            pairs, opposition = _crossing_pairs(endpoints)
            if (opposition <= float(settings["crossingOppositionTolerance"])
                    and density < float(settings["junctionDotDensity"])):
                selected = pairs
                junction_type = "crossing"

        if not selected:
            classify_arrowheads(gray, connector_mask, route_edges, boxes)
            headed = {node_ids.index(edge["to"]) for edge in route_edges
                      if edge["metadata"].get("direction") == "arrowhead"}
            sources = [index for index in attached if index not in headed]
            if len(headed) == 1 and len(sources) >= 2:
                target = next(iter(headed))
                selected = [(source, target) for source in sources]
                junction_type = "join"
            elif len(sources) == 1 and len(headed) >= 2:
                selected = [(sources[0], target) for target in sorted(headed)]
                junction_type = "branch"
            else:
                withheld.append({"component": component, "reason": "ambiguous-junction-direction",
                                 "objects": [node_ids[index] for index in attached],
                                 "arrowheadedObjects": [node_ids[index] for index in sorted(headed)]})
                records.append({"component": component, "center": list(center), "type": "withheld",
                                "attachments": len(attached), "centerDensity": round(density, 4)})
                continue

        for first, second in selected:
            pair = frozenset((node_ids[first], node_ids[second]))
            if pair in known_pairs:
                continue
            points = routes.get(frozenset((first, second)))
            if not points:
                continue
            if points[0] != list(endpoints[first]):
                points = list(reversed(points))
            output.append({
                "id": f"junction-connection-{len(output) + 1}",
                "from": node_ids[first], "to": node_ids[second], "kind": "relationship",
                "metadata": {
                    "points": points,
                    "direction": "junction-arrowheads" if junction_type in {"branch", "join"} else "unknown",
                    "junctionType": junction_type,
                    "junctionCenter": list(center),
                    "junctionDotDensity": round(density, 4),
                    "attachmentCount": len(attached),
                    "componentArea": area,
                    "crossingOpposition": round(opposition, 4) if opposition is not None else None,
                    "profileVersion": profile["version"],
                    "requiresReview": junction_type == "crossing",
                    "method": "pixel-junction-graph",
                },
            })
            known_pairs.add(pair)
        records.append({"component": component, "center": list(center), "type": junction_type,
                        "attachments": len(attached), "centerDensity": round(density, 4),
                        "routesAdded": len(selected)})

    profile["junctions"] = records
    profile["withheld"] = withheld
    profile["results"] = {
        "edgesAdded": len(output),
        "branches": sum(record["type"] == "branch" for record in records),
        "joins": sum(record["type"] == "join" for record in records),
        "crossings": sum(record["type"] == "crossing" for record in records),
        "withheld": len(withheld),
    }
    return output, profile
