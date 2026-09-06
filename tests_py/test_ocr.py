import cv2
import numpy as np
import pytest

from scenelyr.ocr import available
from scenelyr.pixels import extract_pixels


@pytest.mark.skipif(not available(), reason="Apple Vision OCR is macOS-only")
def test_local_ocr_labels_an_enclosed_object(tmp_path):
    image = np.full((220, 420, 3), 255, np.uint8)
    cv2.rectangle(image, (40, 50), (380, 180), (0, 0, 0), 3)
    cv2.putText(image, "PAYMENT API", (78, 130), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    path = tmp_path / "ocr.png"
    cv2.imwrite(str(path), image)
    scene = extract_pixels(path)
    assert len(scene.nodes) == 1
    assert "PAYMENT" in scene.nodes[0].label.upper()
    assert scene.nodes[0].metadata["labelStatus"] == "ocr"
