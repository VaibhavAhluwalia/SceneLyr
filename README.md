# SceneLyr

**The semantic visual layer for AI agents.**

SceneLyr turns semantic intent into structured, editable, presentation-quality visual scenes without forcing agents to micromanage coordinates. It is implemented as one Python package with optional browser and MCP adapters.

```text
Codex / Claude / other agents
              ↓
          SceneLyr IR
              ↓
      Assets + Constraints
              ↓
     deterministic Python layout
              ↓
   SVG · HTML inspector · PPTX
```

## Why

Coding agents generally understand what a visual should communicate. The expensive part is forcing them to express that understanding as low-level drawing operations: x/y coordinates, shape placement, arrow routing, retries and spacing fixes.

SceneLyr moves that work into a visual compiler. Agents describe semantic nodes and relationships. SceneLyr owns geometry.

## Status

The repository now contains a testable MVP slice for every planned phase:

- **Semantic Visual IR** — coordinate-free scene graph, assets, constraints and validation
- **Deterministic layout** — Python layered layout with routed edges
- **Asset intelligence** — offline semantic asset resolver with a provider boundary
- **Editable scene state** — semantic mutations, history, undo and redo
- **SVG + inspector** — presentation-oriented SVG and clickable HTML semantic inspector
- **PowerPoint** — native editable PPTX shapes/text/connectors
- **Image import** — sidecar test mode, OpenAI-compatible vision adapter, and safe fallback
- **MCP** — high-level semantic tools for coding agents
- **CLI + tests + CI** — reproducible local and GitHub verification

See `docs/PHASES.md` for the implementation gates.

## Python quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/scenelyr compile examples/swiggy.scene.json
.venv/bin/scenelyr import-pixels diagram.png extracted.scene.json
```

The Python package provides strict SceneLyr models, deterministic layout, SVG/HTML/PPTX export, offline pixel import, an optional FastAPI service, and a direct Python MCP server. FastAPI is an adapter—not a requirement for MCP or local use.

```bash
.venv/bin/scenelyr serve
.venv/bin/scenelyr mcp
```

The compile command writes:

```text
artifacts/swiggy.svg
artifacts/swiggy.html
artifacts/swiggy.pptx
```

## MCP

```bash
.venv/bin/scenelyr mcp
```

The direct Python MCP exposes semantic operations such as `create_scene_tool`, `add_node_tool`, `add_relationship_tool`, `find_asset`, `render_scene`, `export_scene`, `import_pixels`, `undo_scene`, and `redo_scene`. It communicates over stdio and does not require FastAPI or Node.js.

The repository also contains an installable Codex plugin under `plugins/scenelyr` and
a marketplace manifest under `.agents/plugins`. The plugin launches this same Python
MCP server; it does not introduce a separate processing engine.

**There is intentionally no `move_node(x, y)` tool.**

An agent should say that two systems are related, parallel, downstream, asynchronous, persistent, cached, external, and so on. The renderer decides how that meaning becomes geometry.

## Reference interaction

```text
"Create a presentation-quality food delivery ordering architecture."
        ↓
Agent creates semantic scene
        ↓
SceneLyr resolves assets and relationships
        ↓
Python computes layout + edge routes
        ↓
SceneLyr renders SVG / PPTX
        ↓
Agent can semantically revise one node and re-render
```

## Repository map

```text
src/scenelyr/   Python-first implementation
  models.py     strict SceneLyr 0.2 contract
  pixels.py     deterministic image decomposition
  layout.py     deterministic layered layout
  render.py     SVG, HTML and editable PPTX
  api.py        optional FastAPI adapter
  mcp_server.py direct Python MCP server
tests_py/       Python regression and adapter tests
examples/
  swiggy.scene.json
docs/
```

## Design principles

1. Agents express meaning, not coordinates.
2. The semantic scene is the source of truth.
3. Geometry is deterministic and inspectable.
4. Semantic edits should not regenerate unrelated meaning.
5. Renderers and asset providers are adapters.
6. Every output should remain as editable as its target format permits.
7. Visual quality is measured, not assumed.

## Real image decomposition

For deterministic diagram import, no provider is required:

```bash
.venv/bin/scenelyr import-pixels architecture.png architecture.scene.json
```

No model provider is required. Deterministic import is intended for clean diagrams; arbitrary photographs and semantic interpretation remain outside its reliable boundary.

## Next quality frontier

The architecture is now testable end-to-end. The next work should be judged against competitors rather than by adding more primitives: benchmark tool calls, generation time, overlap/crossing defects, human preference, and slide-readiness versus raw SVG, Mermaid, Excalidraw MCP and other canvas agents.

## Release status

SceneLyr 0.1 is experimental software. Clean flowcharts are the supported target;
low-resolution images, crossed or branched connectors, handwriting, photographs, OCR,
and inferred arrow direction require human review. See `docs/RELEASING.md` before
publishing a tag or package.
