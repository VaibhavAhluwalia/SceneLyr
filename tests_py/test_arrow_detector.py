import cv2
import numpy as np
import pytest

from scenelyr.arrow_detector import build_detection_profile
from scenelyr.pixels import extract_pixels


def _write_flowchart(tmp_path):
    image = np.full((620, 1200, 3), 255, dtype=np.uint8)
    cv2.ellipse(image, (100, 140), (70, 40), 0, 0, 360, (220, 235, 255), -1)
    cv2.ellipse(image, (100, 140), (70, 40), 0, 0, 360, (0, 0, 0), 2)
    cv2.rectangle(image, (250, 100), (390, 180), (225, 245, 225), -1)
    cv2.rectangle(image, (250, 100), (390, 180), (0, 0, 0), 2)
    cv2.rectangle(image, (490, 100), (630, 180), (240, 235, 210), -1)
    cv2.rectangle(image, (490, 100), (630, 180), (0, 0, 0), 2)
    cv2.rectangle(image, (730, 100), (870, 180), (235, 225, 245), -1)
    cv2.rectangle(image, (730, 100), (870, 180), (0, 0, 0), 2)
    cv2.ellipse(image, (1050, 140), (75, 40), 0, 0, 360, (225, 240, 245), -1)
    cv2.ellipse(image, (1050, 140), (75, 40), 0, 0, 360, (0, 0, 0), 2)
    cv2.rectangle(image, (490, 300), (630, 380), (245, 230, 220), -1)
    cv2.rectangle(image, (490, 300), (630, 380), (0, 0, 0), 2)
    cv2.ellipse(image, (560, 520), (75, 40), 0, 0, 360, (225, 240, 235), -1)
    cv2.ellipse(image, (560, 520), (75, 40), 0, 0, 360, (0, 0, 0), 2)
    for start, end in [
        ((170, 140), (250, 140)), ((390, 140), (490, 140)),
        ((630, 140), (730, 140)), ((870, 140), (975, 140)),
        ((560, 180), (560, 300)), ((560, 380), (560, 480)),
    ]:
        cv2.arrowedLine(image, start, end, (195, 195, 195), 3, tipLength=.16)
    source = tmp_path / "generated-flowchart.png"
    cv2.imwrite(str(source), image)
    return source


def test_generated_flowchart_recovers_all_six_arrow_paths(tmp_path):
    scene = extract_pixels(_write_flowchart(tmp_path), scene_id="generated-flow", use_ocr=False)
    assert len(scene.nodes) == 7
    assert len(scene.edges) == 6
    assert {(edge.from_, edge.to) for edge in scene.edges} == {
        ("object-1", "object-2"), ("object-2", "object-3"),
        ("object-3", "object-4"), ("object-4", "object-5"),
        ("object-3", "object-6"), ("object-6", "object-7"),
    }
    assert all(edge.metadata["direction"] == "inferred" for edge in scene.edges)
    assert all(edge.metadata["method"] == "pixel-intensity-corridor" for edge in scene.edges)
    assert all(edge.metadata["confidence"] >= .8 for edge in scene.edges)


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


def test_scene_and_edges_record_arrow_profile(tmp_path):
    scene = extract_pixels(_write_flowchart(tmp_path), scene_id="profile-evidence", use_ocr=False)
    profile = scene.metadata["arrowDetectionProfile"]
    assert profile["version"] == 1 and profile["mode"] == "automatic"
    assert profile["settings"]["endpointLength"] > 0
    assert all(edge.metadata["profileVersion"] == profile["version"] for edge in scene.edges
               if edge.metadata["method"] == "pixel-intensity-corridor")
