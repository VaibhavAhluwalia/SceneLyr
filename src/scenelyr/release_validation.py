"""Release acceptance fixtures and a portable validation report."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .pixels import extract_pixels


@dataclass(frozen=True)
class Fixture:
    id: str
    description: str
    draw: Callable[[], np.ndarray]
    expected_nodes: int
    expected_edges: tuple[tuple[str, str], ...]
    expected_junctions: tuple[str, ...] = ()
    expected_withheld: int = 0
    expected_arrowheads: tuple[str, ...] = ()
    expected_tones: tuple[str, ...] = ()


def _canvas(width: int = 420, height: int = 260) -> np.ndarray:
    return np.full((height, width, 3), 255, np.uint8)


def _box(image: np.ndarray, bounds: tuple[int, int, int, int], color: tuple[int, int, int]) -> None:
    x, y, width, height = bounds
    cv2.rectangle(image, (x, y), (x + width, y + height), color, -1)


def _head(image: np.ndarray, tip: tuple[int, int], base_x: int, half_height: int = 10,
          color: tuple[int, int, int] = (20, 20, 20)) -> None:
    cv2.fillConvexPoly(image, np.asarray([tip, (base_x, tip[1] - half_height),
                                         (base_x, tip[1] + half_height)], np.int32), color)


def _straight() -> np.ndarray:
    image = _canvas()
    _box(image, (20, 90, 90, 70), (220, 170, 50))
    _box(image, (310, 90, 90, 70), (70, 170, 230))
    cv2.line(image, (110, 125), (296, 125), (20, 20, 20), 3)
    _head(image, (310, 125), 294)
    return image


def _elbow() -> np.ndarray:
    image = _canvas()
    _box(image, (20, 30, 90, 65), (220, 170, 50))
    _box(image, (310, 165, 90, 65), (70, 170, 230))
    cv2.line(image, (110, 62), (205, 62), (20, 20, 20), 3)
    cv2.line(image, (205, 62), (205, 197), (20, 20, 20), 3)
    cv2.line(image, (205, 197), (296, 197), (20, 20, 20), 3)
    _head(image, (310, 197), 294)
    return image


def _branch() -> np.ndarray:
    image = _canvas()
    _box(image, (20, 95, 80, 70), (220, 170, 50))
    _box(image, (320, 20, 80, 60), (70, 170, 230))
    _box(image, (320, 180, 80, 60), (70, 170, 230))
    cv2.line(image, (100, 130), (210, 130), (20, 20, 20), 3)
    cv2.line(image, (210, 50), (210, 210), (20, 20, 20), 3)
    cv2.line(image, (210, 50), (306, 50), (20, 20, 20), 3)
    cv2.line(image, (210, 210), (306, 210), (20, 20, 20), 3)
    _head(image, (320, 50), 304)
    _head(image, (320, 210), 304)
    return image


def _join() -> np.ndarray:
    image = _canvas()
    _box(image, (20, 20, 80, 60), (220, 170, 50))
    _box(image, (20, 180, 80, 60), (220, 170, 50))
    _box(image, (320, 95, 80, 70), (70, 170, 230))
    cv2.line(image, (100, 50), (210, 50), (20, 20, 20), 3)
    cv2.line(image, (100, 210), (210, 210), (20, 20, 20), 3)
    cv2.line(image, (210, 50), (210, 210), (20, 20, 20), 3)
    cv2.line(image, (210, 130), (306, 130), (20, 20, 20), 3)
    _head(image, (320, 130), 304)
    return image


def _crossing() -> np.ndarray:
    image = _canvas()
    _box(image, (10, 95, 75, 70), (220, 170, 50))
    _box(image, (335, 95, 75, 70), (70, 170, 230))
    _box(image, (170, 10, 80, 60), (130, 120, 220))
    _box(image, (170, 190, 80, 60), (130, 120, 220))
    cv2.line(image, (85, 130), (335, 130), (20, 20, 20), 3)
    cv2.line(image, (210, 70), (210, 190), (20, 20, 20), 3)
    return image


def _ambiguous() -> np.ndarray:
    image = _branch()
    # Remove both heads while preserving the three-way shared component.
    cv2.rectangle(image, (302, 34), (320, 66), (255, 255, 255), -1)
    cv2.rectangle(image, (302, 194), (320, 226), (255, 255, 255), -1)
    cv2.line(image, (210, 50), (320, 50), (20, 20, 20), 3)
    cv2.line(image, (210, 210), (320, 210), (20, 20, 20), 3)
    return image


def _pale() -> np.ndarray:
    image = _canvas()
    _box(image, (20, 90, 90, 70), (220, 170, 50))
    _box(image, (310, 90, 90, 70), (70, 170, 230))
    pale = (175, 175, 175)
    cv2.line(image, (110, 125), (296, 125), pale, 3)
    _head(image, (310, 125), 294, color=pale)
    return image


def _broken() -> np.ndarray:
    image = _canvas()
    _box(image, (20, 30, 90, 65), (220, 170, 50))
    _box(image, (310, 165, 90, 65), (70, 170, 230))
    cv2.line(image, (110, 62), (195, 62), (20, 20, 20), 3)
    cv2.line(image, (204, 62), (205, 197), (20, 20, 20), 3)
    cv2.line(image, (205, 197), (296, 197), (20, 20, 20), 3)
    _head(image, (310, 197), 294)
    return image


def _open_v() -> np.ndarray:
    image = _canvas(height=220)
    _box(image, (20, 75, 90, 70), (220, 170, 50))
    _box(image, (330, 75, 70, 70), (70, 170, 230))
    cv2.line(image, (110, 110), (330, 110), (20, 20, 20), 2)
    cv2.line(image, (330, 110), (305, 92), (20, 20, 20), 2)
    cv2.line(image, (330, 110), (305, 128), (20, 20, 20), 2)
    return image


def _diagonal() -> np.ndarray:
    image = _canvas(width=440, height=280)
    _box(image, (20, 30, 90, 65), (220, 170, 50))
    _box(image, (330, 185, 90, 65), (70, 170, 230))
    cv2.line(image, (110, 70), (330, 217), (20, 20, 20), 3)
    return image


FIXTURES = (
    Fixture("straight-filled", "Straight connector with a filled arrowhead", _straight, 2,
            (("object-1", "object-2"),), expected_arrowheads=("filled-triangle",), expected_tones=("dark",)),
    Fixture("bent-filled", "Bent connector with an ordered route", _elbow, 2,
            (("object-1", "object-2"),), expected_arrowheads=("filled-triangle",), expected_tones=("dark",)),
    Fixture("one-to-many-branch", "One source branches to two headed targets", _branch, 3,
            (("object-2", "object-1"), ("object-2", "object-3")), ("branch",),
            expected_arrowheads=("filled-triangle",), expected_tones=("dark",)),
    Fixture("many-to-one-join", "Two sources join one headed target", _join, 3,
            (("object-1", "object-2"), ("object-3", "object-2")), ("join",),
            expected_arrowheads=("filled-triangle",), expected_tones=("dark",)),
    Fixture("clean-crossing", "Two thin pass-through lines cross without a junction dot", _crossing, 4,
            (("object-2", "object-3"), ("object-1", "object-4")), ("crossing",)),
    Fixture("ambiguous-three-way", "A three-way component without direction is withheld", _ambiguous, 3,
            (), (), 1),
    Fixture("pale-filled", "Pale connector ink and arrowhead remain detectable", _pale, 2,
            (("object-1", "object-2"),), expected_arrowheads=("filled-triangle",), expected_tones=("pale",)),
    Fixture("lightly-broken-elbow", "A small aligned gap is repaired before route tracing", _broken, 2,
            (("object-1", "object-2"),), expected_arrowheads=("filled-triangle",), expected_tones=("dark",)),
    Fixture("open-v", "An open V arrowhead is distinguished from a filled head", _open_v, 2,
            (("object-1", "object-2"),), expected_arrowheads=("open-v",), expected_tones=("dark",)),
    Fixture("diagonal-route", "A diagonal connector is preserved as a relationship", _diagonal, 2,
            (("object-1", "object-2"),)),
)


def _evaluate(fixture: Fixture, image_path: Path) -> dict:
    scene = extract_pixels(image_path, scene_id=f"release-{fixture.id}", use_ocr=False)
    actual_edges = {(edge.from_, edge.to) for edge in scene.edges}
    expected_edges = set(fixture.expected_edges)
    junction_profile = scene.metadata.get("junctionDetectionProfile", {})
    actual_junctions = sorted({edge.metadata.get("junctionType") for edge in scene.edges
                               if edge.metadata.get("junctionType")})
    actual_arrowheads = sorted({edge.metadata.get("arrowhead", {}).get("type") for edge in scene.edges
                                if edge.metadata.get("arrowhead")})
    actual_tones = sorted({edge.metadata.get("arrowhead", {}).get("tone") for edge in scene.edges
                           if edge.metadata.get("arrowhead")})
    checks = {
        "objects": len(scene.nodes) == fixture.expected_nodes,
        "relationships": actual_edges == expected_edges,
        "junctionTypes": actual_junctions == sorted(fixture.expected_junctions),
        "withheld": int(junction_profile.get("results", {}).get("withheld", 0)) == fixture.expected_withheld,
        "arrowheadTypes": actual_arrowheads == sorted(fixture.expected_arrowheads),
        "arrowheadTones": actual_tones == sorted(fixture.expected_tones),
        "deterministic": scene.metadata.get("modelUsed") is False,
    }
    return {
        "id": fixture.id,
        "description": fixture.description,
        "image": str(image_path),
        "passed": all(checks.values()),
        "checks": checks,
        "expected": {"objects": fixture.expected_nodes, "edges": sorted([list(edge) for edge in expected_edges]),
                     "junctionTypes": list(fixture.expected_junctions), "withheld": fixture.expected_withheld},
        "actual": {"objects": len(scene.nodes), "edges": sorted([list(edge) for edge in actual_edges]),
                   "junctionTypes": actual_junctions,
                   "arrowheadTypes": actual_arrowheads, "arrowheadTones": actual_tones,
                   "withheld": junction_profile.get("results", {}).get("withheld", 0),
                   "warnings": scene.metadata.get("warnings", [])},
    }


def _report_html(report: dict) -> str:
    rows = []
    for item in report["fixtures"]:
        checks = "".join(f"<span class='check {'ok' if passed else 'bad'}'>{html.escape(name)}</span>"
                         for name, passed in item["checks"].items())
        expected = html.escape(json.dumps(item["expected"]["edges"]))
        actual = html.escape(json.dumps(item["actual"]["edges"]))
        rows.append(f"<article class='case'><img src='fixtures/{item['id']}.png' alt='{html.escape(item['description'])}'>"
                    f"<div><div class='status {'pass' if item['passed'] else 'fail'}'>{'PASS' if item['passed'] else 'REVIEW'}</div>"
                    f"<h2>{html.escape(item['id'])}</h2><p>{html.escape(item['description'])}</p><div class='checks'>{checks}</div>"
                    f"<dl><dt>Expected edges</dt><dd>{expected}</dd><dt>Detected edges</dt><dd>{actual}</dd></dl></div></article>")
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>SceneLyr release validation</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#eef2f7;color:#172033;font:15px system-ui}}main{{max-width:1100px;margin:auto;padding:32px 18px}}header,.case{{background:white;border:1px solid #dbe2eb;border-radius:18px;box-shadow:0 10px 28px #23395d12}}header{{padding:28px;margin-bottom:20px}}h1{{margin:.2rem 0}}.summary{{display:flex;gap:12px;flex-wrap:wrap}}.metric{{background:#f4f6fa;border-radius:12px;padding:12px 18px}}.metric b{{font-size:28px;display:block}}.case{{display:grid;grid-template-columns:minmax(240px,42%) 1fr;gap:22px;padding:18px;margin:16px 0}}.case img{{width:100%;background:#fafafa;border-radius:12px}}.status{{display:inline-block;padding:5px 9px;border-radius:999px;font-weight:800;font-size:12px}}.pass,.ok{{background:#dcfce7;color:#166534}}.fail,.bad{{background:#fee2e2;color:#991b1b}}.checks{{display:flex;gap:7px;flex-wrap:wrap}}.check{{padding:5px 8px;border-radius:8px;font-size:12px}}dt{{font-weight:700;margin-top:12px}}dd{{margin:4px 0;font:12px ui-monospace;overflow-wrap:anywhere}}@media(max-width:720px){{.case{{grid-template-columns:1fr}}}}</style><main><header><div class='status {'pass' if report['passed'] else 'fail'}'>{'RELEASE READY' if report['passed'] else 'REVIEW REQUIRED'}</div><h1>SceneLyr R-01 validation</h1><p>Deterministic image-to-scene acceptance matrix. Each diagram is generated locally and imported through the public pixel pipeline.</p><div class='summary'><div class='metric'><b>{report['summary']['passed']}/{report['summary']['total']}</b>fixtures passed</div><div class='metric'><b>{report['summary']['checksPassed']}/{report['summary']['checksTotal']}</b>checks passed</div></div></header>{''.join(rows)}</main></html>"""


def run_release_validation(output_dir: str | Path) -> dict:
    """Generate the public fixture matrix, execute it, and save JSON plus HTML evidence."""
    output = Path(output_dir)
    fixture_dir = output / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for fixture in FIXTURES:
        image_path = fixture_dir / f"{fixture.id}.png"
        if not cv2.imwrite(str(image_path), fixture.draw()):
            raise OSError(f"Could not write fixture {image_path}")
        results.append(_evaluate(fixture, image_path))
    checks_total = sum(len(item["checks"]) for item in results)
    checks_passed = sum(sum(item["checks"].values()) for item in results)
    report = {
        "schemaVersion": 1,
        "passed": all(item["passed"] for item in results),
        "summary": {"total": len(results), "passed": sum(item["passed"] for item in results),
                    "checksTotal": checks_total, "checksPassed": checks_passed},
        "fixtures": results,
        "provenance": "All fixture images are generated by SceneLyr from OpenCV drawing primitives; no external or personal images.",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output / "report.html").write_text(_report_html(report), encoding="utf-8")
    report["files"] = {"json": str(output / "report.json"), "html": str(output / "report.html")}
    return report
