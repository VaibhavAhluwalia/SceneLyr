"""Immutable-style semantic scene operations."""

from __future__ import annotations

from typing import Any

from .models import SceneIntent, SemanticEdge, SemanticNode, SemanticScene


def create_scene(scene_id: str, **intent: Any) -> SemanticScene:
    return SemanticScene(id=scene_id, intent=SceneIntent(**intent))


def _copy(scene: SemanticScene) -> SemanticScene:
    return scene.model_copy(deep=True)


def add_node(scene: SemanticScene, node: SemanticNode | dict[str, Any]) -> SemanticScene:
    node = node if isinstance(node, SemanticNode) else SemanticNode.model_validate(node)
    if any(item.id == node.id for item in scene.nodes):
        raise ValueError(f"Node already exists: {node.id}")
    data = scene.to_dict()
    data["nodes"].append(node.model_dump(by_alias=True, exclude_none=True))
    return SemanticScene.model_validate(data)


def update_node(scene: SemanticScene, node_id: str, **patch: Any) -> SemanticScene:
    data = scene.to_dict()
    for index, node in enumerate(data["nodes"]):
        if node["id"] == node_id:
            data["nodes"][index] = {**node, **patch, "id": node_id}
            return SemanticScene.model_validate(data)
    raise ValueError(f"Unknown node: {node_id}")


def remove_node(scene: SemanticScene, node_id: str) -> SemanticScene:
    data = scene.to_dict()
    data["nodes"] = [node for node in data["nodes"] if node["id"] != node_id]
    data["edges"] = [edge for edge in data["edges"] if edge["from"] != node_id and edge["to"] != node_id]
    for group in data.get("groups", []):
        group["nodeIds"] = [item for item in group["nodeIds"] if item != node_id]
    return SemanticScene.model_validate(data)


def add_edge(scene: SemanticScene, edge: SemanticEdge | dict[str, Any]) -> SemanticScene:
    raw = edge.model_dump(by_alias=True, exclude_none=True) if isinstance(edge, SemanticEdge) else dict(edge)
    raw.setdefault("id", f"{raw['from']}__{raw['to']}__{len(scene.edges) + 1}")
    if any(item.id == raw["id"] for item in scene.edges):
        raise ValueError(f"Edge already exists: {raw['id']}")
    data = scene.to_dict()
    data["edges"].append(raw)
    return SemanticScene.model_validate(data)


def remove_edge(scene: SemanticScene, edge_id: str) -> SemanticScene:
    data = scene.to_dict()
    data["edges"] = [edge for edge in data["edges"] if edge.get("id") != edge_id]
    return SemanticScene.model_validate(data)

