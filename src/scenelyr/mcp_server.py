"""Direct Python MCP server; FastAPI and Node are not required."""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .assets import search_assets
from .compiler import compile_scene
from .core import add_edge, add_node, create_scene, remove_node, update_node
from .models import SemanticScene
from .pixels import extract_pixels
from .storage import list_imports, load_import, persist_import, save_scene
from .store import SceneStore

mcp = FastMCP("scenelyr")
store = SceneStore()


def _json(scene: SemanticScene | dict | list) -> str:
    value = scene.to_dict() if isinstance(scene, SemanticScene) else scene
    return json.dumps(value, indent=2, ensure_ascii=False)


def _get(scene_id: str) -> SemanticScene:
    try:
        return store.get(scene_id)
    except KeyError:
        scene = load_import(scene_id)
        if not scene:
            raise ValueError(f"Unknown scene: {scene_id}")
        return store.create(scene)


def _mutate(scene_id: str, update) -> SemanticScene:
    _get(scene_id)
    scene = store.mutate(scene_id, update)
    save_scene(scene)
    return scene


@mcp.tool()
def create_scene_tool(scene_id: str, title: str | None = None, purpose: str | None = None,
                      direction: str = "left-to-right", density: str = "balanced") -> str:
    """Create a coordinate-free semantic scene."""
    scene = create_scene(scene_id, title=title, purpose=purpose, direction=direction, density=density)
    scene = store.create(scene)
    save_scene(scene)
    return _json(scene)


@mcp.tool()
def add_node_tool(scene_id: str, node_id: str, label: str, kind: str = "service") -> str:
    """Add a semantic object to a scene."""
    return _json(_mutate(scene_id, lambda scene: add_node(scene, {"id": node_id, "label": label, "kind": kind})))


@mcp.tool()
def update_node_tool(scene_id: str, node_id: str, label: str | None = None,
                     kind: str | None = None) -> str:
    """Update a semantic object without coordinates."""
    patch = {key: value for key, value in {"label": label, "kind": kind}.items() if value is not None}
    return _json(_mutate(scene_id, lambda scene: update_node(scene, node_id, **patch)))


@mcp.tool()
def remove_node_tool(scene_id: str, node_id: str) -> str:
    """Remove an object and its relationships."""
    return _json(_mutate(scene_id, lambda scene: remove_node(scene, node_id)))


@mcp.tool()
def add_relationship_tool(scene_id: str, from_id: str, to_id: str,
                          kind: str = "relationship", label: str | None = None) -> str:
    """Connect two semantic objects."""
    edge = {"from": from_id, "to": to_id, "kind": kind, "label": label}
    return _json(_mutate(scene_id, lambda scene: add_edge(scene, edge)))


@mcp.tool()
def inspect_scene(scene_id: str) -> str:
    """Return a scene as JSON."""
    return _json(_get(scene_id))


@mcp.tool()
def list_scenes() -> str:
    """List active in-memory scenes."""
    known = {scene.id: {"id": scene.id, "nodes": len(scene.nodes), "edges": len(scene.edges)} for scene in store.list()}
    for item in list_imports():
        known.setdefault(item["id"], {"id": item["id"], "nodes": item["objects"], "edges": item["connections"]})
    return _json(list(known.values()))


@mcp.tool()
def import_scene(scene_json: str) -> str:
    """Import a SceneLyr 0.2 JSON document."""
    scene = store.create(SemanticScene.model_validate_json(scene_json))
    save_scene(scene)
    return _json(scene)


@mcp.tool()
def import_pixels(path: str, scene_id: str | None = None) -> str:
    """Deterministically recover supported diagram objects from an image; no model or network."""
    source = Path(path)
    scene = extract_pixels(source, scene_id=scene_id)
    persist_import(scene, source.read_bytes(), source.name)
    try:
        store.create(scene)
    except ValueError:
        pass
    return _json(scene)


@mcp.tool()
def render_scene(scene_id: str) -> str:
    """Render a scene to SVG text."""
    return compile_scene(_get(scene_id)).svg


@mcp.tool()
def export_scene(scene_id: str, output_dir: str, basename: str | None = None,
                 pptx: bool = True) -> str:
    """Export SVG, HTML and optionally editable PowerPoint."""
    scene = _get(scene_id)
    name = basename or scene.id
    svg_path, html_path = f"{output_dir}/{name}.svg", f"{output_dir}/{name}.html"
    pptx_path = f"{output_dir}/{name}.pptx" if pptx else None
    compile_scene(scene, svg_path=svg_path, html_path=html_path, pptx_path=pptx_path)
    json_path = Path(output_dir) / f"{name}.json"
    json_path.write_text(_json(scene), encoding="utf-8")
    return _json({"json": str(json_path), "svg": svg_path, "html": html_path, "pptx": pptx_path})


@mcp.tool()
def find_asset(query: str, limit: int = 5) -> str:
    """Search the deterministic built-in asset catalog."""
    return _json(search_assets(query, limit))


@mcp.tool()
def undo_scene(scene_id: str) -> str:
    """Undo the most recent mutation."""
    scene = store.undo(scene_id); save_scene(scene); return _json(scene)


@mcp.tool()
def redo_scene(scene_id: str) -> str:
    """Redo the most recently undone mutation."""
    scene = store.redo(scene_id); save_scene(scene); return _json(scene)


@mcp.tool()
def rename_object(scene_id: str, object_id: str, label: str) -> str:
    """Correct OCR text or rename an extracted object, then persist and re-render it."""
    return _json(_mutate(scene_id, lambda scene: update_node(scene, object_id, label=label,
                 metadata={**next(node.metadata for node in scene.nodes if node.id == object_id), "labelStatus": "agent-edited"})))


@mcp.tool()
def reverse_arrow(scene_id: str, edge_id: str) -> str:
    """Reverse a relationship direction without manipulating coordinates."""
    def reverse(scene: SemanticScene) -> SemanticScene:
        data = scene.to_dict()
        edge = next((item for item in data["edges"] if item.get("id") == edge_id), None)
        if not edge:
            raise ValueError(f"Unknown edge: {edge_id}")
        edge["from"], edge["to"] = edge["to"], edge["from"]
        edge.setdefault("metadata", {})["direction"] = "agent-reversed"
        return SemanticScene.model_validate(data)
    return _json(_mutate(scene_id, reverse))


@mcp.tool()
def reconnect_arrow(scene_id: str, edge_id: str, from_object: str, to_object: str,
                    label: str | None = None) -> str:
    """Attach an existing relationship to different semantic objects."""
    def reconnect(scene: SemanticScene) -> SemanticScene:
        data = scene.to_dict()
        edge = next((item for item in data["edges"] if item.get("id") == edge_id), None)
        if not edge:
            raise ValueError(f"Unknown edge: {edge_id}")
        edge.update({"from": from_object, "to": to_object})
        if label is not None:
            edge["label"] = label
        edge.setdefault("metadata", {})["direction"] = "agent-edited"
        return SemanticScene.model_validate(data)
    return _json(_mutate(scene_id, reconnect))


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
