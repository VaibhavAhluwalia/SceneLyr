# SceneLyr implementation phases

SceneLyr now has a testable vertical slice for every originally planned phase. These are MVP implementations, not claims that each subsystem is production-complete.

## Phase 0 — Semantic Visual IR

Implemented in `packages/core`.

- coordinate-free nodes and relationships
- scene intent, groups, constraints and assets
- validation
- semantic mutation helpers

**Gate:** an agent can describe a visual without supplying x/y coordinates.

## Phase 1 — Intent → diagram

Implemented through `packages/layout`, `packages/svg`, and `packages/compiler`.

- ELK layered layout
- deterministic geometry and orthogonal edge routing
- semantic node sizing
- presentation-oriented SVG renderer
- HTML inspector

**Gate:** `npm run example` compiles `examples/swiggy.scene.json` to SVG/HTML/PPTX.

## Phase 2 — Asset intelligence

Implemented in `packages/assets` as an offline deterministic baseline.

- semantic asset search
- technology/role matching
- built-in glyphs
- node asset resolution

The provider boundary is deliberately small so Iconify, Simple Icons, web search or generated assets can be added without changing the Scene IR.

**Gate:** `find_asset` is exposed over MCP and `searchAssets("redis")` resolves Redis.

## Phase 3 — Agent-editable scene state

Implemented in `packages/store` and the HTML inspector.

- semantic mutations
- history
- undo/redo
- persistent scene identity while layout is regenerated
- clickable semantic node inspection in generated HTML

This is the MVP state layer. A full interactive canvas SDK can later consume the same store/IR.

**Gate:** MCP can add/update/remove nodes and undo/redo without manipulating coordinates.

## Phase 4 — Presentation export

Implemented in `packages/pptx`.

- native PowerPoint shapes and text
- semantic styling
- routed connectors
- editable PPTX output

**Gate:** `npm run smoke` creates a non-empty `.pptx`.

## Phase 5 — Image → semantic scene

Implemented in `packages/vision` with three modes:

1. deterministic `.scene.json` sidecar for offline tests;
2. OpenAI-compatible vision endpoint configured with `SCENELYR_VISION_ENDPOINT`, `SCENELYR_VISION_MODEL`, and optional `SCENELYR_VISION_API_KEY`;
3. graceful whole-image semantic node fallback when no vision model is configured.

The vision prompt explicitly requests semantic objects and relationships and forbids x/y coordinates.

**Gate:** test suite validates sidecar recovery; a configured multimodal endpoint can perform real decomposition.

## Agent interface — MCP

`packages/mcp` exposes high-level tools:

- `create_scene`
- `add_node`
- `update_node`
- `remove_node`
- `add_relationship`
- `inspect_scene`
- `list_scenes`
- `validate_scene`
- `find_asset`
- `render_scene`
- `export_scene`
- `import_scene`
- `import_image`
- `undo_scene`
- `redo_scene`

No tool accepts x/y coordinates.
