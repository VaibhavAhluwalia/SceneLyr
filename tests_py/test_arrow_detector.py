import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from scenelyr.arrow_detector import build_detection_profile
from scenelyr.arrow_score import score_arrows
from scenelyr.ocr import available as ocr_available
from scenelyr.pixels import extract_pixels


def test_real_flowchart_recovers_all_six_arrow_paths():
    fixture = json.loads(Path("tests_py/fixtures/basic-flowchart.expected.json").read_text())
    scene = extract_pixels(fixture["sourceImage"], scene_id=fixture["sceneId"], use_ocr=False)
    result = score_arrows(scene, fixture["arrows"])
    assert result["detectedCount"] == 6
    assert result["totals"]["pathFound"] == 6
    assert result["totals"]["sourceCorrect"] == 6
    assert result["totals"]["destinationCorrect"] == 6
    assert result["totals"]["directionCorrect"] == 6
    assert all(edge.metadata["method"] == "pixel-intensity-corridor" for edge in scene.edges)
    assert all(edge.metadata["confidence"] >= .8 for edge in scene.edges)


def test_real_flowchart_attaches_yes_and_no_labels_when_ocr_is_available():
    if not ocr_available():
        pytest.skip("Local OCR is unavailable on this platform")
    fixture = json.loads(Path("tests_py/fixtures/basic-flowchart.expected.json").read_text())
    scene = extract_pixels(fixture["sourceImage"], scene_id=fixture["sceneId"], use_ocr=True)
    result = score_arrows(scene, fixture["arrows"])
    assert result["totals"]["labelCorrect"] == 6


def test_light_gray_arrow_is_preserved(tmp_path):
    image = 255 * __import__("numpy").ones((180, 400, 3), dtype="uint8")
    cv2.rectangle(image, (20, 50), (120, 120), (0, 0, 0), 2)
    cv2.rectangle(image, (280, 50), (380, 120), (0, 0, 0), 2)
    cv2.arrowedLine(image, (120, 85), (280, 85), (195, 195, 195), 3, tipLength=.12)
    source = tmp_path / "light-arrow.png"
    cv2.imwrite(str(source), image)
    scene = extract_pixels(source, scene_id="light-arrow", use_ocr=False)
    assert len(scene.edges) == 1
    assert scene.edges[0].metadata["method"] == "pixel-intensity-corridor"


def test_detection_profile_scales_endpoint_zone_and_records_overrides():
    gray = np.full((600, 1000), 255, dtype=np.uint8)
    small = [(10, 10, 100, 50, "rectangle"), (250, 10, 100, 50, "rectangle")]
    large = [(10, 10, 300, 180, "rectangle"), (600, 10, 300, 180, "rectangle")]
    small_profile = build_detection_profile(gray, small)
    large_profile = build_detection_profile(gray, large)
    assert small_profile["settings"]["endpointLength"] < large_profile["settings"]["endpointLength"]
    overridden = build_detection_profile(gray, small, {"endpointLength": 31, "minimumCoverage": .8})
    assert overridden["mode"] == "automatic-with-overrides"
    assert overridden["settings"]["endpointLength"] == 31
    assert overridden["settings"]["minimumCoverage"] == .8
    assert overridden["overrides"] == {"minimumCoverage": .8, "endpointLength": 31}
    with pytest.raises(ValueError, match="Unknown arrow setting"):
        build_detection_profile(gray, small, {"mysteryValue": 4})
    with pytest.raises(ValueError, match="minimumCoverage"):
        build_detection_profile(gray, small, {"minimumCoverage": 1.5})


def test_scene_and_edges_record_arrow_profile():
    fixture = json.loads(Path("tests_py/fixtures/basic-flowchart.expected.json").read_text())
    scene = extract_pixels(fixture["sourceImage"], scene_id="profile-evidence", use_ocr=False)
    profile = scene.metadata["arrowDetectionProfile"]
    assert profile["version"] == 1 and profile["mode"] == "automatic"
    assert profile["settings"]["endpointLength"] > 0
    assert all(edge.metadata["profileVersion"] == profile["version"] for edge in scene.edges
               if edge.metadata["method"] == "pixel-intensity-corridor")
