import cv2
import numpy as np

from scenelyr.path_detector import trace_connector_paths
from scenelyr.pixels import extract_pixels


BOXES = [(20, 20, 80, 60, "rectangle"), (260, 120, 80, 60, "rectangle")]
NODE_IDS = ["source", "target"]


def test_traces_an_elbow_connector_as_an_ordered_path():
    mask = np.zeros((220, 380), np.uint8)
    cv2.line(mask, (100, 50), (180, 50), 255, 3)
    cv2.line(mask, (180, 50), (180, 150), 255, 3)
    cv2.arrowedLine(mask, (180, 150), (260, 150), 255, 3, tipLength=.22)

    edges, profile, _ = trace_connector_paths(mask, BOXES, NODE_IDS)

    assert len(edges) == 1
    assert edges[0]["metadata"]["method"] == "pixel-path-graph"
    assert len(edges[0]["metadata"]["points"]) >= 3
    assert profile["tracedPathCount"] == 1


def test_bridges_a_small_break_and_records_the_added_pixels():
    mask = np.zeros((220, 380), np.uint8)
    cv2.line(mask, (100, 50), (176, 50), 255, 3)
    cv2.line(mask, (184, 50), (184, 150), 255, 3)
    cv2.arrowedLine(mask, (184, 150), (260, 150), 255, 3, tipLength=.22)

    edges, profile, prepared = trace_connector_paths(mask, BOXES, NODE_IDS)

    assert len(edges) == 1
    assert profile["pixels"]["addedByBridging"] > 0
    assert np.count_nonzero(prepared["bridgePixels"]) > 0


def test_withholds_a_component_that_touches_three_objects():
    boxes = BOXES + [(150, 120, 60, 50, "rectangle")]
    mask = np.zeros((220, 380), np.uint8)
    cv2.line(mask, (100, 50), (180, 50), 255, 3)
    cv2.line(mask, (180, 50), (180, 145), 255, 3)
    cv2.line(mask, (180, 145), (260, 145), 255, 3)

    edges, profile, _ = trace_connector_paths(mask, boxes, NODE_IDS + ["branch"])

    assert edges == []
    assert profile["withheld"][0]["reason"] == "touches-more-than-two-objects"


def test_pixel_import_stores_path_profile_and_non_aligned_route(tmp_path):
    image = np.full((220, 380, 3), 255, np.uint8)
    cv2.rectangle(image, (20, 20), (100, 80), (64, 150, 230), -1)
    cv2.rectangle(image, (260, 120), (340, 180), (70, 185, 110), -1)
    cv2.line(image, (100, 50), (180, 50), (20, 20, 20), 3)
    cv2.line(image, (180, 50), (180, 150), (20, 20, 20), 3)
    cv2.arrowedLine(image, (180, 150), (260, 150), (20, 20, 20), 3, tipLength=.22)
    source = tmp_path / "elbow.png"
    cv2.imwrite(str(source), image)

    scene = extract_pixels(source, use_ocr=False)

    path_edges = [edge for edge in scene.edges if edge.metadata.get("method") == "pixel-path-graph"]
    assert len(path_edges) == 1
    assert len(path_edges[0].metadata["points"]) >= 3
    assert scene.metadata["pathDetectionProfile"]["tracedPathCount"] == 1
