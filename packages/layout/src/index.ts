import ELK from "elkjs/lib/elk.bundled.js";
import type { SemanticScene } from "../../core/src/index.js";

export interface LayoutPoint {
  x: number;
  y: number;
}

export interface PositionedNode {
  id: string;
  label: string;
  kind: string;
  x: number;
  y: number;
  width: number;
  height: number;
  importance?: string;
  assetId?: string;
  icon?: string;
  group?: string;
}

export interface PositionedEdge {
  id: string;
  from: string;
  to: string;
  label?: string;
  kind?: string;
  points: LayoutPoint[];
}

export interface LayoutScene {
  width: number;
  height: number;
  nodes: PositionedNode[];
  edges: PositionedEdge[];
}

const elk = new ELK();

function nodeSize(label: string, kind: string): { width: number; height: number } {
  if (kind === "actor" || kind === "external") return { width: 170, height: 74 };
  if (kind === "database" || kind === "cache" || kind === "queue") return { width: 180, height: 78 };
  const width = Math.max(170, Math.min(260, 100 + label.length * 7));
  return { width, height: 76 };
}

function fallbackPoints(a: PositionedNode, b: PositionedNode): LayoutPoint[] {
  const start = { x: a.x + a.width, y: a.y + a.height / 2 };
  const end = { x: b.x, y: b.y + b.height / 2 };
  const midX = (start.x + end.x) / 2;
  return [start, { x: midX, y: start.y }, { x: midX, y: end.y }, end];
}

/** SceneLyr owns geometry. The agent supplies semantic nodes and relationships only. */
export async function layoutScene(scene: SemanticScene): Promise<LayoutScene> {
  const direction = scene.intent?.direction === "top-to-bottom" ? "DOWN" : "RIGHT";
  const density = scene.intent?.density ?? "balanced";
  const nodeGap = density === "compact" ? 32 : density === "spacious" ? 72 : 48;
  const layerGap = density === "compact" ? 72 : density === "spacious" ? 150 : 110;

  const graph: any = {
    id: scene.id,
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": direction,
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.spacing.nodeNode": String(nodeGap),
      "elk.layered.spacing.nodeNodeBetweenLayers": String(layerGap),
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
      "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.padding": "[top=96,left=64,bottom=64,right=64]"
    },
    children: scene.nodes.map((node) => {
      const size = nodeSize(node.label, node.kind);
      return { id: node.id, width: size.width, height: size.height };
    }),
    edges: scene.edges.map((edge, index) => ({
      id: edge.id ?? `edge-${index + 1}`,
      sources: [edge.from],
      targets: [edge.to],
      labels: edge.label ? [{ text: edge.label, width: Math.max(42, edge.label.length * 7), height: 20 }] : undefined
    }))
  };

  const result: any = await elk.layout(graph);
  const semanticById = new Map(scene.nodes.map((node) => [node.id, node]));
  const nodes: PositionedNode[] = (result.children ?? []).map((node: any) => {
    const semantic = semanticById.get(node.id)!;
    return {
      id: node.id,
      label: semantic.label,
      kind: semantic.kind,
      x: node.x ?? 0,
      y: node.y ?? 0,
      width: node.width ?? 180,
      height: node.height ?? 76,
      importance: semantic.importance,
      assetId: semantic.assetId,
      icon: semantic.icon,
      group: semantic.group
    };
  });

  const positionedById = new Map(nodes.map((node) => [node.id, node]));
  const semanticEdgeById = new Map(scene.edges.map((edge, index) => [edge.id ?? `edge-${index + 1}`, edge]));
  const edges: PositionedEdge[] = (result.edges ?? []).map((edge: any) => {
    const semantic = semanticEdgeById.get(edge.id)!;
    const firstSection = edge.sections?.[0];
    const points: LayoutPoint[] = firstSection
      ? [firstSection.startPoint, ...(firstSection.bendPoints ?? []), firstSection.endPoint].map((point: any) => ({ x: point.x, y: point.y }))
      : fallbackPoints(positionedById.get(semantic.from)!, positionedById.get(semantic.to)!);
    return {
      id: edge.id,
      from: semantic.from,
      to: semantic.to,
      label: semantic.label,
      kind: semantic.kind,
      points
    };
  });

  return {
    width: Math.ceil(result.width ?? 1200),
    height: Math.ceil(result.height ?? 700),
    nodes,
    edges
  };
}
