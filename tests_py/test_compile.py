from pathlib import Path

from scenelyr.compiler import compile_scene
from scenelyr.layout import layout_scene
from scenelyr.models import SemanticScene


def swiggy() -> SemanticScene:
    return SemanticScene.model_validate_json(Path("examples/swiggy.scene.json").read_text())


def test_layout_is_deterministic():
    first = layout_scene(swiggy()).to_dict()
    assert first == layout_scene(swiggy()).to_dict()
    assert len(first["nodes"]) == 9
    assert len(first["edges"]) == 8


def test_compile_writes_svg_html_and_editable_pptx(tmp_path):
    svg, html, pptx = tmp_path / "scene.svg", tmp_path / "scene.html", tmp_path / "scene.pptx"
    result = compile_scene(swiggy(), svg_path=svg, html_path=html, pptx_path=pptx)
    assert "<svg" in result.svg and "SceneLyr inspector" in result.html
    assert svg.stat().st_size > 1000 and html.stat().st_size > 1000 and pptx.stat().st_size > 10_000

