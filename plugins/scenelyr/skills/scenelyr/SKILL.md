---
name: scenelyr
description: Use SceneLyr's local MCP tools to import diagram images, inspect or edit semantic objects and arrows, and export JSON, SVG, HTML, or PowerPoint. Trigger when the user asks to extract a flowchart or architecture diagram, correct OCR labels, reconnect/reverse diagram arrows, or render a saved SceneLyr scene.
---

# SceneLyr

Use the SceneLyr MCP tools instead of manipulating diagram pixels or coordinates directly.

## Import and inspect

1. Call `import_pixels` with an absolute local image path.
2. Read the returned warnings, object labels, OCR confidence, and relationships.
3. Tell the user which results require review. Never imply that OCR, arrow direction,
   or semantic type is perfectly accurate.

## Edit

- Use `rename_object` to correct OCR text.
- Use `reverse_arrow` when endpoints are correct but direction is wrong.
- Use `reconnect_arrow` when an arrow attaches to the wrong objects.
- Use the semantic node and relationship tools for structural changes.
- Do not invent raw coordinate edits; SceneLyr owns deterministic layout.

## Persist and export

Mutations save locally and regenerate SceneLyr artifacts. Use `inspect_scene` to verify
the final graph, `render_scene` for SVG text, and `export_scene` for requested files.
