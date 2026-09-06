# Python-first SceneLyr

SceneLyr's Python implementation is a modular monolith. One package owns the scene
contract and deterministic behavior; HTTP and MCP are thin adapters around it.

## Easiest way to run it

On macOS, double-click `Start SceneLyr.command` in the repository folder. The first
launch creates a private environment in `~/Library/Application Support/SceneLyr`,
installs what is needed, and opens the local drag-and-drop interface. Later launches
reuse that setup. Keep the small terminal window open while using the app; close it
or press Control-C to stop SceneLyr.

Every uploaded image and result is automatically stored under `data/imports` in the
SceneLyr repository. Each import has its own folder containing the original image,
`scene.json`, `preview.svg`, `inspector.html`, and `editable.pptx`. The `data` folder
is excluded from Git so personal images are not accidentally committed.

Each import also has an inspectable asset hierarchy under `assets/objects`. Every
extracted object receives its own folder containing `crop.png` from the original
image, an independently rendered `layer.svg`, and a structured `object.json`. The
object record keeps its text and OCR confidence, source and rendered bounds,
provenance, parent scene, and incoming/outgoing relationships. `assets/manifest.json`
is the scene-level tree linking all of these object folders.

The browser inspector lets you correct OCR labels, reconnect arrow endpoints, add an
arrow label, and reverse direction. Every edit immediately updates `scene.json`, SVG,
HTML, and PowerPoint on disk.

## Included

- Pydantic SceneLyr 0.2 models compatible with existing scene JSON
- immutable-style create/add/update/remove operations
- in-memory store with undo and redo
- stable, dependency-free layered layout and orthogonal routing
- SVG renderer and clickable HTML inspector
- editable PowerPoint export through `python-pptx`
- deterministic OpenCV diagram importer
- on-device Apple Vision OCR with editable labels and confidence
- direct Python MCP server over stdio
- optional FastAPI service
- pytest regression suite

## Commands

```bash
scenelyr validate examples/swiggy.scene.json
scenelyr compile examples/swiggy.scene.json artifacts
scenelyr import-pixels input.png output.scene.json
scenelyr capabilities
scenelyr mcp
scenelyr serve --host 127.0.0.1 --port 8000
```

The MCP process communicates directly with an agent over stdio. It does not pass
through FastAPI and does not require Node.js.

Imported scenes persist across MCP restarts. MCP also exposes `rename_object`,
`reverse_arrow`, and `reconnect_arrow`; the layout engine recalculates coordinates.

## Deterministic boundary

The deterministic importer is designed for clean flowcharts and architecture diagrams.
It can recover supported enclosed shapes, their source bounds, and simple connector
components. It may infer an arrow direction from endpoint geometry, but marks every
imported relationship for review.

It cannot reliably understand arbitrary photographs from pixels alone. Apple Vision can
read many printed labels, but semantic classification, handwriting, crossed/branched connectors, and unconstrained
real-world objects remain explicit review or future optional-provider territory.

## Runtime architecture

Python is the only application runtime. The core package owns models, layout, rendering,
storage, OCR, and pixel extraction. FastAPI provides the optional local browser UI, while
the MCP adapter communicates directly with Codex over standard input/output. Neither
adapter introduces a second application language or duplicates the core behavior.
