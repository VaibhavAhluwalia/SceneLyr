import cv2
import numpy as np

from scenelyr.image_masks import build_semantic_masks


def test_text_mask_removes_letters_but_preserves_connector_through_label():
    image = np.full((180, 420), 255, np.uint8)
    cv2.rectangle(image, (20, 50), (120, 125), 0, 2)
    cv2.rectangle(image, (300, 50), (400, 125), 0, 2)
    cv2.line(image, (120, 88), (300, 88), 80, 3)
    cv2.putText(image, "GO", (184, 94), cv2.FONT_HERSHEY_SIMPLEX, .8, 0, 2, cv2.LINE_AA)

    masks, profile = build_semantic_masks(
        image,
        [(20, 50, 101, 76, "rectangle"), (300, 50, 101, 76, "rectangle")],
        [[180, 68, 55, 32]],
        brightness_cutoff=220,
    )

    assert np.count_nonzero(masks["objectMask"]) > 0
    assert np.count_nonzero(masks["textMask"]) > 0
    assert np.count_nonzero(masks["connectorMask"][87:90, 122:299]) > 170 * 3
    assert masks["connectorMask"][73, 187] == 0
    assert profile["settings"]["textPadding"] > 0
    assert profile["settings"]["lineSupportSpan"] > 0
    assert profile["grayscalePreserved"] is True


def test_mask_settings_scale_with_detected_object_size():
    gray = np.full((500, 900), 255, np.uint8)
    _, small = build_semantic_masks(gray, [(10, 10, 80, 40, "rectangle")])
    _, large = build_semantic_masks(gray, [(10, 10, 320, 180, "rectangle")])
    assert small["settings"]["lineSupportSpan"] < large["settings"]["lineSupportSpan"]
    assert small["settings"]["textPadding"] < large["settings"]["textPadding"]
