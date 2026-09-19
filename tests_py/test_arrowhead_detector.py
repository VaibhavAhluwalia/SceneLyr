import cv2
import numpy as np

from scenelyr.arrowhead_detector import classify_arrowheads


BOXES = [(5, 35, 25, 50, "rectangle"), (170, 35, 25, 50, "rectangle")]


def _edge():
    return {"id": "edge-1", "from": "left", "to": "right", "kind": "relationship",
            "metadata": {"points": [[30, 60], [170, 60]], "direction": "unknown", "requiresReview": True}}


def test_classifies_filled_triangle_and_sets_direction():
    gray = np.full((120, 200), 255, np.uint8)
    mask = np.zeros_like(gray)
    cv2.line(mask, (30, 60), (158, 60), 255, 3)
    cv2.fillConvexPoly(mask, np.array([[170, 60], [153, 49], [153, 71]], np.int32), 255)
    gray[mask > 0] = 30
    edges = [_edge()]

    profile = classify_arrowheads(gray, mask, edges, BOXES)

    assert profile["results"]["classified"] == 1
    assert edges[0]["metadata"]["direction"] == "arrowhead"
    assert edges[0]["metadata"]["arrowhead"]["type"] == "filled-triangle"
    assert edges[0]["metadata"]["arrowhead"]["endpoint"] == "to"


def test_classifies_open_v_arrowhead():
    gray = np.full((120, 200), 255, np.uint8)
    mask = np.zeros_like(gray)
    cv2.line(mask, (30, 60), (170, 60), 255, 2)
    cv2.line(mask, (170, 60), (153, 48), 255, 2)
    cv2.line(mask, (170, 60), (153, 72), 255, 2)
    gray[mask > 0] = 25
    edges = [_edge()]

    classify_arrowheads(gray, mask, edges, BOXES)

    assert edges[0]["metadata"]["arrowhead"]["type"] == "open-v"


def test_records_pale_arrowhead_tone():
    gray = np.full((120, 200), 255, np.uint8)
    mask = np.zeros_like(gray)
    cv2.line(mask, (30, 60), (158, 60), 255, 3)
    cv2.fillConvexPoly(mask, np.array([[170, 60], [153, 49], [153, 71]], np.int32), 255)
    gray[mask > 0] = 190
    edges = [_edge()]

    classify_arrowheads(gray, mask, edges, BOXES)

    assert edges[0]["metadata"]["arrowhead"]["tone"] == "pale"


def test_plain_line_is_left_unresolved():
    gray = np.full((120, 200), 255, np.uint8)
    mask = np.zeros_like(gray)
    cv2.line(mask, (30, 60), (170, 60), 255, 3)
    gray[mask > 0] = 20
    edges = [_edge()]

    profile = classify_arrowheads(gray, mask, edges, BOXES)

    assert profile["results"]["unresolved"] == 1
    assert edges[0]["metadata"]["arrowhead"] is None
    assert edges[0]["metadata"]["direction"] == "unknown"
