# Testing SceneLyr

## Automated tests

SceneLyr requires Python 3.11 or newer. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

The suite covers the semantic model, deterministic layout and compilation, pixel
geometry extraction, OCR integration, local persistence, the FastAPI browser adapter,
and MCP tool registration.

## Manual smoke test

```bash
.venv/bin/scenelyr validate examples/swiggy.scene.json
.venv/bin/scenelyr compile examples/swiggy.scene.json artifacts
```

Inspect `artifacts/swiggy.svg` and `artifacts/swiggy.html`, then open the PPTX in
PowerPoint, Keynote, LibreOffice Impress, or Google Slides to verify native editability.

For the easiest image-import test on macOS, double-click `Start SceneLyr.command`,
drop a clean diagram into the browser, and inspect its objects, connections, JSON,
SVG, HTML, and PowerPoint outputs.

## MCP

Run the direct Python MCP server with:

```bash
.venv/bin/scenelyr mcp
```

The installed SceneLyr Codex plugin launches this same server automatically. FastAPI
and the browser UI are not involved in MCP calls.
