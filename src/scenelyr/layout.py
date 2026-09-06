"""Dependency-free deterministic layered layout and orthogonal routing."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import SemanticScene


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class PositionedNode:
    id: str
    label: str
    kind: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class PositionedEdge:
    id: str
    from_: str
    to: str
    kind: str
    label: str | None
    points: tuple[Point, ...]


@dataclass(frozen=True)
class LayoutScene:
    width: float
    height: float
    nodes: tuple[PositionedNode, ...]
    edges: tuple[PositionedEdge, ...]

    def to_dict(self) -> dict:
        result = asdict(self)
        for edge in result["edges"]:
            edge["from"] = edge.pop("from_")
        return result


def _node_size(label: str, kind: str) -> tuple[float, float]:
    if kind in {"actor", "external"}:
        return 170, 74
    if kind in {"database", "cache", "queue"}:
        return 180, 78
    return max(170, min(260, 100 + len(label) * 7)), 76


def _layers(scene: SemanticScene) -> list[list[str]]:
    """Stable Kahn layering; cycles are broken by lexical id."""
    node_ids = sorted(node.id for node in scene.nodes)
    incoming = {node_id: set() for node_id in node_ids}
    outgoing = {node_id: set() for node_id in node_ids}
    for edge in scene.edges:
        incoming[edge.to].add(edge.from_)
        outgoing[edge.from_].add(edge.to)
    remaining = set(node_ids)
    layers: list[list[str]] = []
    while remaining:
        ready = sorted(node_id for node_id in remaining if not (incoming[node_id] & remaining))
        if not ready:
            ready = [min(remaining)]
        layers.append(ready)
        remaining -= set(ready)
    return layers


def layout_scene(scene: SemanticScene) -> LayoutScene:
    density = scene.intent.density if scene.intent else "balanced"
    direction = scene.intent.direction if scene.intent else "left-to-right"
    node_gap = {"compact": 32, "balanced": 48, "spacious": 72}[density]
    layer_gap = {"compact": 72, "balanced": 110, "spacious": 150}[density]
    margin_x, margin_y = 64, 96
    semantic = {node.id: node for node in scene.nodes}
    layers = _layers(scene)
    sizes = {node.id: _node_size(node.label, node.kind) for node in scene.nodes}
    positioned: dict[str, PositionedNode] = {}

    if direction == "left-to-right":
        layer_widths = [max((sizes[node_id][0] for node_id in layer), default=0) for layer in layers]
        layer_heights = [sum(sizes[node_id][1] for node_id in layer) + node_gap * max(0, len(layer) - 1) for layer in layers]
        canvas_inner_height = max(layer_heights, default=0)
        x = margin_x
        for layer, layer_width, layer_height in zip(layers, layer_widths, layer_heights):
            y = margin_y + (canvas_inner_height - layer_height) / 2
            for node_id in layer:
                width, height = sizes[node_id]
                item = semantic[node_id]
                positioned[node_id] = PositionedNode(node_id, item.label, item.kind, x, y, width, height)
                y += height + node_gap
            x += layer_width + layer_gap
        width = (x - layer_gap + margin_x) if layers else 2 * margin_x
        height = canvas_inner_height + 2 * margin_y
    else:
        layer_heights = [max((sizes[node_id][1] for node_id in layer), default=0) for layer in layers]
        layer_widths = [sum(sizes[node_id][0] for node_id in layer) + node_gap * max(0, len(layer) - 1) for layer in layers]
        canvas_inner_width = max(layer_widths, default=0)
        y = margin_y
        for layer, layer_width, layer_height in zip(layers, layer_widths, layer_heights):
            x = margin_x + (canvas_inner_width - layer_width) / 2
            for node_id in layer:
                width, height = sizes[node_id]
                item = semantic[node_id]
                positioned[node_id] = PositionedNode(node_id, item.label, item.kind, x, y, width, height)
                x += width + node_gap
            y += layer_height + layer_gap
        width = canvas_inner_width + 2 * margin_x
        height = (y - layer_gap + margin_y) if layers else 2 * margin_y

    routed = []
    for index, edge in enumerate(scene.edges):
        source, target = positioned[edge.from_], positioned[edge.to]
        if direction == "left-to-right":
            start = Point(source.x + source.width, source.y + source.height / 2)
            end = Point(target.x, target.y + target.height / 2)
            middle = (start.x + end.x) / 2
            points = (start, Point(middle, start.y), Point(middle, end.y), end)
        else:
            start = Point(source.x + source.width / 2, source.y + source.height)
            end = Point(target.x + target.width / 2, target.y)
            middle = (start.y + end.y) / 2
            points = (start, Point(start.x, middle), Point(end.x, middle), end)
        routed.append(PositionedEdge(edge.id or f"edge-{index + 1}", edge.from_, edge.to, edge.kind, edge.label, points))
    ordered_nodes = tuple(positioned[node.id] for node in scene.nodes)
    return LayoutScene(float(width), float(height), ordered_nodes, tuple(routed))

