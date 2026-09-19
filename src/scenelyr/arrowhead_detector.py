"""Deterministic arrowhead classification at recovered connector endpoints."""

from __future__ import annotations

from typing import Any

import numpy as np


def build_arrowhead_profile(boxes: list[tuple[int, int, int, int, str]]) -> dict[str, Any]:
    short_sides = [min(width, height) for _, _, width, height, _ in boxes]
    median_short_side = float(np.median(short_sides)) if short_sides else 80.0
    return {
        "version": 1,
        "measurements": {"medianNodeShortSide": round(median_short_side, 2)},
        "settings": {
            "inspectionLength": max(22, min(48, round(median_short_side * .38))),
            "minimumWingSpan": max(4, min(14, round(median_short_side * .08))),
            "minimumHeadLength": max(5, min(12, round(median_short_side * .08))),
            "minimumExpansion": 1.55,
            "minimumHeadScore": .42,
            "directionScoreMargin": .12,
            "filledDensity": .82,
            "narrowAspect": .62,
            "paleBrightness": 140,
        },
    }


def _endpoint_candidate(
    gray: np.ndarray,
    mask: np.ndarray,
    endpoint: list[int],
    interior: list[int],
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Measure widening and fill near one endpoint in route-oriented coordinates."""
    endpoint_vector = np.asarray(endpoint, dtype=float) - np.asarray(interior, dtype=float)
    magnitude = float(np.linalg.norm(endpoint_vector))
    if magnitude < 1:
        return {"detected": False, "score": 0.0, "reason": "no-endpoint-tangent"}
    outward = endpoint_vector / magnitude
    perpendicular = np.asarray((-outward[1], outward[0]))
    length = int(settings["inspectionLength"])
    radius = length + 3
    x, y = int(endpoint[0]), int(endpoint[1])
    y1, y2 = max(0, y - radius), min(mask.shape[0], y + radius + 1)
    x1, x2 = max(0, x - radius), min(mask.shape[1], x + radius + 1)
    local_y, local_x = np.where(mask[y1:y2, x1:x2] > 0)
    if not len(local_x):
        return {"detected": False, "score": 0.0, "reason": "no-endpoint-ink"}
    xs, ys = local_x + x1, local_y + y1
    relative = np.column_stack((xs - x, ys - y)).astype(float)
    outward_progress = relative @ outward
    lateral = relative @ perpendicular
    axis_tolerance = max(3.0, float(settings["minimumWingSpan"]) * .65)
    nearby = (np.abs(lateral) <= axis_tolerance) & (outward_progress >= -length) & (outward_progress <= 4)
    if not np.any(nearby):
        return {"detected": False, "score": 0.0, "reason": "no-oriented-ink"}
    # The visible tip can stop just outside an object mask, so anchor the analysis
    # at the furthest outward connector pixel rather than the nominal box boundary.
    tip_index = int(np.argmax(np.where(nearby, outward_progress, -np.inf)))
    tip = np.asarray((xs[tip_index], ys[tip_index]), dtype=float)
    tip_relative = np.column_stack((xs - tip[0], ys - tip[1])).astype(float)
    inward_distance = -(tip_relative @ outward)
    lateral = tip_relative @ perpendicular
    selected = ((inward_distance >= -1.5) & (inward_distance <= length) &
                (np.abs(lateral) <= length * .8))
    if np.count_nonzero(selected) < 8:
        return {"detected": False, "score": 0.0, "reason": "insufficient-endpoint-ink"}

    distances = inward_distance[selected]
    offsets = lateral[selected]
    selected_x, selected_y = xs[selected], ys[selected]
    bins = np.clip(np.rint(distances).astype(int), 0, length)
    widths, counts = np.zeros(length + 1), np.zeros(length + 1, dtype=int)
    for position in range(length + 1):
        values = offsets[bins == position]
        if len(values):
            widths[position] = float(values.max() - values.min() + 1)
            counts[position] = len(values)
    # The arrowhead can occupy most of a short endpoint window. The narrowest
    # occupied cross-section in the inward half is the best local shaft estimate.
    tail_start = max(2, round(length * .45))
    tail_widths = widths[tail_start:][widths[tail_start:] > 0]
    shaft_width = float(np.min(tail_widths)) if len(tail_widths) else 1.0
    head_limit = max(3, round(length * .72))
    ignore_tip_bins = max(2, round(float(settings["minimumWingSpan"]) * .35))
    head_widths = widths[:head_limit + 1].copy()
    head_widths[:ignore_tip_bins] = 0
    maximum_width = float(head_widths.max(initial=0))
    expansion = maximum_width / max(1.0, shaft_width)
    wide_bins = np.where(head_widths >= max(float(settings["minimumWingSpan"]), shaft_width * 1.55))[0]
    head_length = int(wide_bins.max() + 1) if len(wide_bins) else 0
    envelope = float(np.sum(widths[ignore_tip_bins:head_length])) if head_length else 0.0
    ink_count = int(np.sum(counts[ignore_tip_bins:head_length])) if head_length else 0
    fill_density = ink_count / max(1.0, envelope)
    head_pixels = (bins >= ignore_tip_bins) & (bins < max(ignore_tip_bins + 1, head_length))
    positive = int(np.count_nonzero(offsets[head_pixels] > shaft_width / 2))
    negative = int(np.count_nonzero(offsets[head_pixels] < -shaft_width / 2))
    wing_balance = min(positive, negative) / max(1, max(positive, negative))
    aspect = maximum_width / max(1.0, float(head_length))
    expansion_score = min(1.0, max(0.0, (expansion - 1.0) / 2.4))
    span_score = min(1.0, maximum_width / max(1.0, float(settings["minimumWingSpan"]) * 2))
    score = expansion_score * .48 + span_score * .27 + wing_balance * .25
    detected = bool(
        maximum_width >= float(settings["minimumWingSpan"])
        and head_length >= int(settings["minimumHeadLength"])
        and expansion >= float(settings["minimumExpansion"])
        and score >= float(settings["minimumHeadScore"])
        and positive > 0 and negative > 0
    )
    if not detected:
        head_type = "none"
    elif aspect < float(settings["narrowAspect"]):
        head_type = "narrow"
    elif fill_density >= float(settings["filledDensity"]):
        head_type = "filled-triangle"
    else:
        head_type = "open-v"
    brightness_values = gray[selected_y[head_pixels], selected_x[head_pixels]] if np.any(head_pixels) else np.array([])
    brightness = float(np.median(brightness_values)) if len(brightness_values) else 0.0
    return {
        "detected": detected,
        "type": head_type,
        "tone": "pale" if detected and brightness >= float(settings["paleBrightness"]) else "dark",
        "score": round(float(score), 4),
        "tip": [int(round(tip[0])), int(round(tip[1]))],
        "headLength": head_length,
        "maximumWidth": round(maximum_width, 2),
        "shaftWidth": round(shaft_width, 2),
        "expansion": round(expansion, 3),
        "fillDensity": round(fill_density, 3),
        "wingBalance": round(wing_balance, 3),
        "aspect": round(aspect, 3),
        "medianBrightness": round(brightness, 1),
    }


def classify_arrowheads(
    gray: np.ndarray,
    connector_mask: np.ndarray,
    edges: list[dict[str, Any]],
    boxes: list[tuple[int, int, int, int, str]],
) -> dict[str, Any]:
    """Classify both route endpoints and use strong arrowhead evidence for direction."""
    profile = build_arrowhead_profile(boxes)
    settings = profile["settings"]
    classified = 0
    unresolved = 0
    for edge in edges:
        points = edge.get("metadata", {}).get("points", [])
        if len(points) < 2:
            continue
        start = _endpoint_candidate(gray, connector_mask, points[0], points[1], settings)
        end = _endpoint_candidate(gray, connector_mask, points[-1], points[-2], settings)
        edge["metadata"]["arrowheadCandidates"] = {"start": start, "end": end}
        candidates = [("start", start), ("end", end)]
        candidates.sort(
            key=lambda item: float(item[1].get("score", 0)) if item[1].get("detected") else 0.0,
            reverse=True,
        )
        winner_name, winner = candidates[0]
        runner_score = (float(candidates[1][1].get("score", 0))
                        if candidates[1][1].get("detected") else 0.0)
        decisive = bool(
            winner.get("detected")
            and float(winner.get("score", 0)) - runner_score >= float(settings["directionScoreMargin"])
        )
        if decisive:
            if winner_name == "start":
                edge["from"], edge["to"] = edge["to"], edge["from"]
                edge["metadata"]["points"] = list(reversed(points))
            edge["metadata"]["direction"] = "arrowhead"
            edge["metadata"]["arrowhead"] = {**winner, "endpoint": "to"}
            edge["metadata"]["arrowheadProfileVersion"] = profile["version"]
            edge["metadata"]["requiresReview"] = bool(float(winner["score"]) < .65)
            classified += 1
        else:
            edge["metadata"]["arrowhead"] = None
            edge["metadata"]["arrowheadProfileVersion"] = profile["version"]
            unresolved += 1
    profile["results"] = {"classified": classified, "unresolved": unresolved, "examined": classified + unresolved}
    return profile
