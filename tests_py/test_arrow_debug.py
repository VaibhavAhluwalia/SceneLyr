import json
from pathlib import Path

import cv2
import numpy as np

from scenelyr.arrow_debug import STAGE_FILENAMES, persist_arrow_debug
from scenelyr.arrow_score import score_arrows
from scenelyr.models import SemanticScene
from scenelyr.pixels import extract_pixels
from scenelyr.storage import persist_import


def _simple_scene() -> SemanticScene:
    return SemanticScene.model_validate({
        "id": "arrow-debug-test",
        "nodes": [
            {"id": "left", "label": "Start", "kind": "asset", "metadata": {"shape": "rectangle", "sourceBounds": [20, 50, 100, 70]}},
            {"id": "right", "label": "End", "kind": "asset", "metadata": {"shape": "rectangle", "sourceBounds": [280, 50, 100, 70]}},
        ],
        "edges": [],
    })


def test_debug_stages_and_manifest_are_persisted(tmp_path):
    image = np.full((180, 400, 3), 255, np.uint8)
    cv2.rectangle(image, (20, 50), (120, 120), (0, 0, 0), 2)
    cv2.rectangle(image, (280, 50), (380, 120), (0, 0, 0), 2)
    cv2.arrowedLine(image, (120, 85), (280, 85), (0, 0, 0), 2, tipLength=.12)
    source = tmp_path / "source.png"
    cv2.imwrite(str(source), image)
    manifest = persist_arrow_debug(_simple_scene(), source, tmp_path / "debug")
    assert [item["id"] for item in manifest["stages"]] == list(STAGE_FILENAMES)
    assert all(Path(item["file"]).is_file() for item in manifest["stages"])
    assert Path(manifest["manifest"]).is_file()
    assert manifest["candidateCount"] > 0


def test_arrow_score_reports_zero_baseline():
    scene = _simple_scene()
    expected = [{"id": "A-01", "from": "left", "to": "right"}]
    score = score_arrows(scene, expected)
    assert score["expectedCount"] == 1
    assert score["detectedCount"] == 0
    assert score["totals"] == {"pathFound": 0, "sourceCorrect": 0, "destinationCorrect": 0, "directionCorrect": 0, "labelCorrect": 0}


def test_import_persists_debug_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("SCENELYR_DATA_DIR", str(tmp_path / "data"))
    image = np.full((180, 400, 3), 255, np.uint8)
    cv2.rectangle(image, (20, 50), (120, 120), (0, 0, 0), 2)
    cv2.rectangle(image, (280, 50), (380, 120), (0, 0, 0), 2)
    cv2.arrowedLine(image, (120, 85), (280, 85), (0, 0, 0), 2, tipLength=.12)
    source = tmp_path / "flow.png"
    cv2.imwrite(str(source), image)
    scene = extract_pixels(source, scene_id="persisted-debug", use_ocr=False)
    paths = persist_import(scene, source.read_bytes(), source.name)
    manifest = json.loads((paths["folder"] / "debug" / "manifest.json").read_text())
    assert manifest["sceneId"] == "persisted-debug"
    assert len(manifest["stages"]) == 5
    assert "Arrow debug" in paths["html"].read_text()
