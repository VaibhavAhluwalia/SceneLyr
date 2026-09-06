# SceneLyr

**The semantic visual layer for AI agents.**

SceneLyr turns semantic intent into structured, editable, presentation-quality visual scenes without forcing agents to micromanage coordinates.

## Thesis

Coding agents usually understand *what* a visual should communicate, but existing drawing interfaces force them to express that understanding through low-level graphical operations. SceneLyr introduces a semantic scene representation between agent intent and rendering.

```text
Agent intent
    ↓
Semantic Scene
    ↓
Layout + Assets + Constraints
    ↓
SVG · PPTX · Canvas
```

## V0 goal

Given a semantic architecture description, produce a polished SVG deterministically with far fewer agent operations than coordinate-level drawing tools.

The first benchmark scene is a food-delivery ordering architecture with external actors, services, asynchronous infrastructure, cache, and persistent storage.

## Initial architecture

- `packages/core` — semantic visual IR and validation
- `packages/layout` — deterministic graph layout and constraints
- `packages/svg` — SVG renderer
- `packages/mcp` — high-level agent/MCP interface
- `examples` — reference semantic scenes
- `benchmarks` — prompts and evaluation fixtures
- `docs` — architecture and Visual IR specification

## Design principles

1. Agents express meaning, not coordinates.
2. Geometry is deterministic and inspectable.
3. Every scene remains editable after generation.
4. Semantic edits should not regenerate unrelated visual elements.
5. Rendering targets are adapters; the semantic scene is the source of truth.
6. Visual quality is evaluated, not assumed.

## Status

Early prototype. Private while the core representation and benchmark are being established.
