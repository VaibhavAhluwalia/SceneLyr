# SceneLyr implementation status

SceneLyr is a Python modular monolith. The production path is intentionally small:

1. Pydantic models validate the coordinate-free semantic scene.
2. Core operations mutate nodes and relationships while preserving schema validity.
3. The deterministic layout engine assigns geometry and routes connectors.
4. Asset, SVG, HTML, and PowerPoint adapters produce inspectable outputs.
5. OpenCV and Apple Vision OCR recover supported diagram objects and printed labels.
6. Persistent storage keeps imports and edits under `data/imports`.
7. FastAPI provides the optional local browser UI.
8. The Python MCP server exposes high-level tools directly to agents.

## Current boundary

The deterministic importer works best with clean flowcharts and architecture diagrams.
It can recover enclosed shapes, printed text, basic connectors, and source bounds.
Every inferred connector remains reviewable because dense crossings, branches,
handwriting, photographs, and semantic object recognition are not guaranteed from
pixel geometry alone.

## Quality gates

- `pytest` passes the Python unit and adapter suite.
- `scenelyr validate` accepts the example scene.
- `scenelyr compile` creates non-empty SVG, HTML, and editable PPTX outputs.
- The MCP server registers its complete tool surface over stdio.
- Browser edits persist immediately to the import folder.
