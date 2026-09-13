"""Deterministic semantic masks for diagram object, text, and connector ink."""

from __future__ import annotations

from typing import Any, Iterable

import cv2
import numpy as np


def _clamped_rectangle(mask: np.ndarray, bounds: Iterable[int], value: int, padding: int = 0) -> None:
    x, y, width, height = (int(item) for item in bounds)
    image_height, image_width = mask.shape
    left = max(0, x - padding)
    top = max(0, y - padding)
    right = min(image_width - 1, x + width - 1 + padding)
    bottom = min(image_height - 1, y + height - 1 + padding)
    if right >= left and bottom >= top:
        cv2.rectangle(mask, (left, top), (right, bottom), value, -1)


def build_semantic_masks(
    gray: np.ndarray,
    boxes: list[tuple[int, int, int, int, str]],
    text_bounds: list[list[int]] | None = None,
    *,
    brightness_cutoff: int = 220,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Build independent masks while retaining long connector strokes through text regions."""
    if gray.ndim != 2:
        raise ValueError("Semantic masks require a grayscale image")
    text_bounds = text_bounds or []
    short_sides = [min(width, height) for _, _, width, height, _ in boxes]
    median_short_side = float(np.median(short_sides)) if short_sides else max(24.0, min(gray.shape) * .1)
    text_padding = max(1, min(8, round(median_short_side * .025)))
    line_span = max(9, min(41, round(median_short_side * .22)))

    raw_ink = np.where(gray <= int(brightness_cutoff), 255, 0).astype(np.uint8)
    object_mask = np.zeros_like(raw_ink)
    for x, y, width, height, _ in boxes:
        _clamped_rectangle(object_mask, (x, y, width, height), 255)

    text_mask = np.zeros_like(raw_ink)
    for bounds in text_bounds:
        if len(bounds) == 4:
            _clamped_rectangle(text_mask, bounds, 255, text_padding)

    # Long horizontal or vertical strokes are captured before text is removed. This
    # restores a connector that runs behind a label without restoring short letters.
    horizontal = cv2.morphologyEx(raw_ink, cv2.MORPH_OPEN, np.ones((1, line_span), np.uint8))
    vertical = cv2.morphologyEx(raw_ink, cv2.MORPH_OPEN, np.ones((line_span, 1), np.uint8))
    line_support = cv2.bitwise_or(horizontal, vertical)
    outside_objects = cv2.bitwise_not(object_mask)
    connector_mask = cv2.bitwise_and(raw_ink, outside_objects)
    connector_mask = cv2.bitwise_and(connector_mask, cv2.bitwise_not(text_mask))
    connector_mask = cv2.bitwise_or(connector_mask, cv2.bitwise_and(line_support, outside_objects))

    profile = {
        "version": 1,
        "brightnessCutoff": int(brightness_cutoff),
        "measurements": {"medianNodeShortSide": round(median_short_side, 2)},
        "settings": {"objectPadding": 0, "textPadding": text_padding, "lineSupportSpan": line_span},
        "regions": {"objects": len(boxes), "text": len(text_bounds)},
        "pixels": {
            "rawInk": int(np.count_nonzero(raw_ink)),
            "objectMask": int(np.count_nonzero(object_mask)),
            "textMask": int(np.count_nonzero(text_mask)),
            "connectorMask": int(np.count_nonzero(connector_mask)),
        },
        "grayscalePreserved": True,
    }
    return {
        "rawInk": raw_ink,
        "objectMask": object_mask,
        "textMask": text_mask,
        "lineSupport": line_support,
        "connectorMask": connector_mask,
    }, profile
