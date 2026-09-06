from pathlib import Path

import cv2
import numpy as np

from scenelyr.pixels import extract_pixels


def diagram() -> np.ndarray:
    image = np.full((240, 500, 3), 255, np.uint8)
    cv2.rectangle(image, (30, 70), (170, 170), (0, 0, 0), 2)
    cv2.rectangle(image, (330, 70), (470, 170), (0, 0, 0), 2)
    cv2.arrowedLine(image, (170, 120), (330, 120), (0, 0, 0), 2, tipLength=.08)
    return image


def test_pixel_import_is_repeatable(tmp_path):
    path = tmp_path / "flow.png"
    cv2.imwrite(str(path), diagram())
    first = extract_pixels(path, use_ocr=False)
    second = extract_pixels(path, use_ocr=False)
    assert first.to_dict() == second.to_dict()
    assert len(first.nodes) == 2
    assert len(first.edges) == 1
    assert first.metadata["modelUsed"] is False


def test_pixel_limits_are_explicit(tmp_path):
    blank = tmp_path / "blank.png"
    cv2.imwrite(str(blank), np.full((100, 100, 3), 255, np.uint8))
    scene = extract_pixels(blank, use_ocr=False)
    assert scene.nodes == []
    assert "not decomposed" in scene.metadata["warnings"][-1]
