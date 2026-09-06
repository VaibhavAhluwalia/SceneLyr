"""Strict, JSON-compatible SceneLyr 0.2 data models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NodeKind = Literal["actor", "service", "database", "cache", "queue", "external", "asset", "image", "note", "group"]
EdgeKind = Literal["request", "async", "read", "write", "event", "relationship"]
Importance = Literal["primary", "secondary", "supporting"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SceneIntent(Model):
    title: str | None = None
    purpose: str | None = None
    audience: str | None = None
    direction: Literal["left-to-right", "top-to-bottom"] = "left-to-right"
    density: Literal["compact", "balanced", "spacious"] = "balanced"
    style: Literal["technical", "presentation", "minimal"] = "presentation"


class NodeStyle(Model):
    emphasis: Literal["normal", "strong"] | None = None
    shape: Literal["rounded", "pill", "circle"] | None = None
    accent: str | None = None


class SemanticNode(Model):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: NodeKind
    description: str | None = None
    icon: str | None = None
    asset_id: str | None = Field(default=None, alias="assetId")
    group: str | None = None
    importance: Importance | None = None
    style: NodeStyle | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticEdge(Model):
    id: str | None = None
    from_: str = Field(alias="from", min_length=1)
    to: str = Field(min_length=1)
    kind: EdgeKind = "relationship"
    label: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticGroup(Model):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    node_ids: list[str] = Field(alias="nodeIds", default_factory=list)


class SemanticConstraint(Model):
    type: Literal["parallel", "before", "after", "same-rank"]
    node_ids: list[str] = Field(alias="nodeIds", min_length=1)
    description: str | None = None


class SemanticAsset(Model):
    id: str = Field(min_length=1)
    type: Literal["icon", "image", "logo", "illustration"]
    source: Literal["builtin", "file", "url", "generated"]
    uri: str
    alt: str | None = None
    license: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticScene(Model):
    version: Literal["0.2"] = "0.2"
    id: str = Field(min_length=1)
    intent: SceneIntent | None = None
    nodes: list[SemanticNode] = Field(default_factory=list)
    edges: list[SemanticEdge] = Field(default_factory=list)
    groups: list[SemanticGroup] = Field(default_factory=list)
    constraints: list[SemanticConstraint] = Field(default_factory=list)
    assets: list[SemanticAsset] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> "SemanticScene":
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Node ids must be unique")
        edge_ids = [edge.id for edge in self.edges if edge.id]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("Edge ids must be unique")
        known_nodes = set(node_ids)
        for edge in self.edges:
            if edge.from_ not in known_nodes or edge.to not in known_nodes:
                raise ValueError(f"Edge {edge.id or '<unnamed>'} references an unknown node")
            if edge.from_ == edge.to:
                raise ValueError(f"Self edge on {edge.from_}")
        for group in self.groups:
            if not set(group.node_ids) <= known_nodes:
                raise ValueError(f"Group {group.id} references an unknown node")
        for constraint in self.constraints:
            if not set(constraint.node_ids) <= known_nodes:
                raise ValueError("Constraint references an unknown node")
        known_assets = {asset.id for asset in self.assets}
        for node in self.nodes:
            if node.asset_id and node.asset_id not in known_assets:
                raise ValueError(f"Node {node.id} references unknown asset {node.asset_id}")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)

