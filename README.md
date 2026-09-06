# SceneLyr

**The semantic visual layer for AI agents.**

SceneLyr turns semantic intent into structured, editable, presentation-quality visual scenes without forcing agents to micromanage coordinates.

```text
Codex / Claude / other agents
              ↓
          SceneLyr IR
              ↓
      Assets + Constraints
              ↓
      deterministic ELK layout
              ↓
   SVG · HTML inspector · PPTX
```

## Why

Coding agents generally understand what a visual should communicate. The expensive part is forcing them to express that understanding as low-level drawing operations: x/y coordinates, shape placement, arrow routing, retries and spacing fixes.

SceneLyr moves that work into a visual compiler. Agents describe semantic nodes and relationships. SceneLyr owns geometry.

## Status

The repository now contains a testable MVP slice for every planned phase:

- **Semantic Visual IR** — coordinate-free scene graph, assets, constraints and validation
- **Deterministic layout** — ELK layered layout with routed edges
- **Asset intelligence** — offline semantic asset resolver with a provider boundary
- **Editable scene state** — semantic mutations, history, undo and redo
- **SVG + inspector** — presentation-oriented SVG and clickable HTML semantic inspector
- **PowerPoint** — native editable PPTX shapes/text/connectors
- **Image import** — sidecar test mode, OpenAI-compatible vision adapter, and safe fallback
- **MCP** — high-level semantic tools for coding agents
- **CLI + tests + CI** — reproducible local and GitHub verification

See `docs/PHASES.md` for the implementation gates.

## Quick test

```bash
npm install
npm run check
npm run smoke
npm run example
```

The example writes:

```text
artifacts/swiggy.svg
artifacts/swiggy.html
artifacts/swiggy.pptx
```

The smoke test covers all phases, including native PPTX generation and deterministic image-import sidecar recovery.

## MCP

```bash
npm run mcp
```

The MCP exposes semantic operations such as `create_scene`, `add_node`, `add_relationship`, `find_asset`, `render_scene`, `export_scene`, `import_image`, `undo_scene`, and `redo_scene`.

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
ELK computes layout + edge routes
        ↓
SceneLyr renders SVG / PPTX
        ↓
Agent can semantically revise one node and re-render
```

## Repository map

```text
packages/
  core/       semantic Visual IR + validation + mutations
  layout/     ELK deterministic layout
  assets/     semantic asset search/resolution
  store/      editable scene state + undo/redo
  svg/        SVG renderer
  pptx/       editable PowerPoint exporter
  compiler/   end-to-end compilation + HTML inspector
  vision/     image → semantic scene adapter
  mcp/        agent-facing MCP server
  cli/        local command-line interface
examples/
  swiggy.scene.json
scripts/
  smoke.ts
tests/
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

For real PNG/JPG → semantic-scene recovery, configure any OpenAI-compatible multimodal endpoint:

```bash
SCENELYR_VISION_ENDPOINT=... \
SCENELYR_VISION_MODEL=... \
SCENELYR_VISION_API_KEY=... \
npm run cli -- import-image architecture.png
```

No provider is required for the rest of SceneLyr or for the automated tests.

## Next quality frontier

The architecture is now testable end-to-end. The next work should be judged against competitors rather than by adding more primitives: benchmark tool calls, generation time, overlap/crossing defects, human preference, and slide-readiness versus raw SVG, Mermaid, Excalidraw MCP and other canvas agents.
