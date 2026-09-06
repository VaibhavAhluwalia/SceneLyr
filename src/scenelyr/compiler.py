"""End-to-end validation, layout, SVG/HTML and PPTX compilation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .layout import LayoutScene, layout_scene
from .models import SemanticScene
from .render import render_html, render_svg, write_pptx


@dataclass(frozen=True)
class CompileResult:
    scene: SemanticScene
    layout: LayoutScene
    svg: str
    html: str


def compile_scene(scene: SemanticScene, *, svg_path: str | Path | None = None,
                  html_path: str | Path | None = None, pptx_path: str | Path | None = None) -> CompileResult:
    layout = layout_scene(scene)
    svg = render_svg(layout, scene)
    html = render_html(scene, svg)
    for path, content in ((svg_path, svg), (html_path, html)):
        if path:
            target = Path(path); target.parent.mkdir(parents=True, exist_ok=True); target.write_text(content, encoding="utf-8")
    if pptx_path:
        write_pptx(layout, scene, pptx_path)
    return CompileResult(scene, layout, svg, html)

