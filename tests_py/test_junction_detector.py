import cv2
import numpy as np

from scenelyr.junction_detector import detect_junctions


def _filled_head(mask, tip, base_a, base_b):
    cv2.fillConvexPoly(mask, np.array([tip, base_a, base_b], np.int32), 255)


def test_recovers_one_to_many_branch_from_two_arrowheaded_leaves():
    boxes = [(10, 80, 50, 40, "rectangle"), (250, 20, 50, 40, "rectangle"),
             (250, 140, 50, 40, "rectangle")]
    mask = np.zeros((210, 330), np.uint8)
    cv2.line(mask, (60, 100), (150, 100), 255, 3)
    cv2.line(mask, (150, 40), (150, 160), 255, 3)
    cv2.line(mask, (150, 40), (236, 40), 255, 3)
    cv2.line(mask, (150, 160), (236, 160), 255, 3)
    _filled_head(mask, (250, 40), (234, 30), (234, 50))
    _filled_head(mask, (250, 160), (234, 150), (234, 170))
    gray = np.where(mask > 0, 25, 255).astype(np.uint8)

    edges, profile = detect_junctions(gray, mask, boxes, ["source", "top", "bottom"])

    assert {(edge["from"], edge["to"]) for edge in edges} == {("source", "top"), ("source", "bottom")}
    assert all(edge["metadata"]["junctionType"] == "branch" for edge in edges)
    assert profile["results"]["branches"] == 1


def test_recovers_many_to_one_join_from_single_arrowheaded_leaf():
    boxes = [(10, 20, 50, 40, "rectangle"), (10, 140, 50, 40, "rectangle"),
             (250, 80, 50, 40, "rectangle")]
    mask = np.zeros((210, 330), np.uint8)
    cv2.line(mask, (60, 40), (150, 40), 255, 3)
    cv2.line(mask, (60, 160), (150, 160), 255, 3)
    cv2.line(mask, (150, 40), (150, 160), 255, 3)
    cv2.line(mask, (150, 100), (236, 100), 255, 3)
    _filled_head(mask, (250, 100), (234, 90), (234, 110))
    gray = np.where(mask > 0, 25, 255).astype(np.uint8)

    edges, profile = detect_junctions(gray, mask, boxes, ["top", "bottom", "target"])

    assert {(edge["from"], edge["to"]) for edge in edges} == {("top", "target"), ("bottom", "target")}
    assert all(edge["metadata"]["junctionType"] == "join" for edge in edges)
    assert profile["results"]["joins"] == 1


def test_pairs_opposite_endpoints_at_crossing_without_junction_dot():
    boxes = [(5, 80, 45, 40, "rectangle"), (270, 80, 45, 40, "rectangle"),
             (138, 5, 45, 40, "rectangle"), (138, 155, 45, 40, "rectangle")]
    mask = np.zeros((200, 320), np.uint8)
    cv2.line(mask, (50, 100), (270, 100), 255, 3)
    cv2.line(mask, (160, 45), (160, 155), 255, 3)
    gray = np.where(mask > 0, 25, 255).astype(np.uint8)

    edges, profile = detect_junctions(gray, mask, boxes, ["left", "right", "top", "bottom"])

    assert {frozenset((edge["from"], edge["to"])) for edge in edges} == {
        frozenset(("left", "right")), frozenset(("top", "bottom"))}
    assert all(edge["metadata"]["junctionType"] == "crossing" for edge in edges)
    assert profile["results"]["crossings"] == 1


def test_withholds_three_way_junction_without_direction_evidence():
    boxes = [(10, 80, 50, 40, "rectangle"), (250, 20, 50, 40, "rectangle"),
             (250, 140, 50, 40, "rectangle")]
    mask = np.zeros((210, 330), np.uint8)
    cv2.line(mask, (60, 100), (150, 100), 255, 3)
    cv2.line(mask, (150, 40), (150, 160), 255, 3)
    cv2.line(mask, (150, 40), (250, 40), 255, 3)
    cv2.line(mask, (150, 160), (250, 160), 255, 3)
    gray = np.where(mask > 0, 25, 255).astype(np.uint8)

    edges, profile = detect_junctions(gray, mask, boxes, ["source", "top", "bottom"])

    assert edges == []
    assert profile["withheld"][0]["reason"] == "ambiguous-junction-direction"


def test_does_not_treat_dense_four_way_junction_as_pass_through_crossing():
    boxes = [(5, 80, 45, 40, "rectangle"), (270, 80, 45, 40, "rectangle"),
             (138, 5, 45, 40, "rectangle"), (138, 155, 45, 40, "rectangle")]
    mask = np.zeros((200, 320), np.uint8)
    cv2.line(mask, (50, 100), (270, 100), 255, 3)
    cv2.line(mask, (160, 45), (160, 155), 255, 3)
    cv2.circle(mask, (160, 100), 7, 255, -1)
    gray = np.where(mask > 0, 25, 255).astype(np.uint8)

    edges, profile = detect_junctions(gray, mask, boxes, ["left", "right", "top", "bottom"])

    assert edges == []
    assert profile["results"]["crossings"] == 0
    assert profile["withheld"][0]["reason"] == "ambiguous-junction-direction"
