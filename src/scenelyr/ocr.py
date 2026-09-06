"""On-device OCR adapter using Apple's built-in Vision framework."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path


def available() -> bool:
    return platform.system() == "Darwin" and shutil.which("swiftc") is not None


def _binary() -> Path:
    source = Path(__file__).with_name("ocr.swift")
    cache = Path.home() / "Library" / "Application Support" / "SceneLyr" / "tools"
    cache.mkdir(parents=True, exist_ok=True)
    binary = cache / "scenelyr-ocr"
    if not binary.exists() or binary.stat().st_mtime < source.stat().st_mtime:
        subprocess.run([shutil.which("swiftc") or "swiftc", str(source), "-o", str(binary)],
                       check=True, capture_output=True, text=True, timeout=120)
    return binary


def read_text(path: str | Path, width: int, height: int) -> list[dict]:
    if not available():
        return []
    result = subprocess.run([str(_binary()), str(path)], check=True, capture_output=True,
                            text=True, timeout=60)
    observations = json.loads(result.stdout)
    items = []
    for item in observations:
        # Vision coordinates use a bottom-left normalized origin.
        x = round(item["x"] * width)
        y = round((1 - item["y"] - item["height"]) * height)
        w = round(item["width"] * width)
        h = round(item["height"] * height)
        items.append({"text": item["text"].strip(), "confidence": round(float(item["confidence"]), 4),
                      "bounds": [x, y, w, h]})
    return sorted((item for item in items if item["text"]), key=lambda item: (item["bounds"][1], item["bounds"][0]))

