import type { SemanticScene } from "../../core/src/index.js";

export interface PositionedNode {
  id: string;
  label: string;
  kind: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PositionedEdge {
  from: string;
  to: string;
  label?: string;
  kind?: string;
}

export interface LayoutScene {
  width: number;
  height: number;
  nodes: PositionedNode[];
  edges: PositionedEdge[];
}

/**
 * Dependency-layer layout. Agents specify relationships; SceneLyr owns geometry.
 * This intentionally starts dependency-free so the IR contract can stabilize
 * before an ELK adapter is introduced.
 */
export function layoutScene(scene: SemanticScene): LayoutScene {
  const incoming = new Map(scene.nodes.map((node) => [node.id, 0]));
  const outgoing = new Map(scene.nodes.map((node) => [node.id, [] as string[]]));
  for (const edge of scene.edges) {
    incoming.set(edge.to, (incoming.get(edge.to) ?? 0) + 1);
    outgoing.get(edge.from)?.push(edge.to);
  }

  const level = new Map<string, number>();
  const queue = scene.nodes.filter((node) => incoming.get(node.id) === 0).map((node) => node.id);
  for (const id of queue) level.set(id, 0);

  while (queue.length) {
    const id = queue.shift()!;
    for (const next of outgoing.get(id) ?? []) {
      level.set(next, Math.max(level.get(next) ?? 0, (level.get(id) ?? 0) + 1));
      incoming.set(next, (incoming.get(next) ?? 1) - 1);
      if (incoming.get(next) === 0) queue.push(next);
    }
  }

  for (const node of scene.nodes) if (!level.has(node.id)) level.set(node.id, 0);
  const layers = new Map<number, typeof scene.nodes>();
  for (const node of scene.nodes) {
    const n = level.get(node.id)!;
    layers.set(n, [...(layers.get(n) ?? []), node]);
  }

  const horizontal = scene.intent?.direction !== "top-to-bottom";
  const gapX = scene.intent?.density === "compact" ? 80 : 130;
  const gapY = scene.intent?.density === "compact" ? 40 : 70;
  const nodeW = 180;
  const nodeH = 72;
  const margin = 60;
  const positioned: PositionedNode[] = [];

  for (const [layer, nodes] of [...layers.entries()].sort(([a], [b]) => a - b)) {
    nodes.forEach((node, row) => positioned.push({
      id: node.id,
      label: node.label,
      kind: node.kind,
      x: horizontal ? margin + layer * (nodeW + gapX) : margin + row * (nodeW + gapX),
      y: horizontal ? margin + row * (nodeH + gapY) : margin + layer * (nodeH + gapY),
      width: nodeW,
      height: nodeH
    }));
  }

  return {
    width: Math.max(800, ...positioned.map((n) => n.x + n.width + margin)),
    height: Math.max(450, ...positioned.map((n) => n.y + n.height + margin)),
    nodes: positioned,
    edges: scene.edges.map((edge) => ({ from: edge.from, to: edge.to, label: edge.label, kind: edge.kind }))
  };
}
