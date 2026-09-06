export type NodeKind =
  | "actor"
  | "service"
  | "database"
  | "cache"
  | "queue"
  | "external"
  | "asset"
  | "group";

export type EdgeKind = "request" | "async" | "read" | "write" | "event" | "relationship";

export interface SemanticNode {
  id: string;
  label: string;
  kind: NodeKind;
  description?: string;
  icon?: string;
  group?: string;
  importance?: "primary" | "secondary" | "supporting";
  metadata?: Record<string, string | number | boolean>;
}

export interface SemanticEdge {
  id?: string;
  from: string;
  to: string;
  kind?: EdgeKind;
  label?: string;
  description?: string;
}

export interface SceneIntent {
  title?: string;
  purpose?: string;
  audience?: string;
  direction?: "left-to-right" | "top-to-bottom";
  density?: "compact" | "balanced" | "spacious";
}

export interface SemanticScene {
  version: "0.1";
  id: string;
  intent?: SceneIntent;
  nodes: SemanticNode[];
  edges: SemanticEdge[];
}

export interface SceneValidationIssue {
  code: string;
  message: string;
  path?: string;
}

export function validateScene(scene: SemanticScene): SceneValidationIssue[] {
  const issues: SceneValidationIssue[] = [];
  const ids = new Set<string>();

  for (const [index, node] of scene.nodes.entries()) {
    if (ids.has(node.id)) {
      issues.push({ code: "duplicate-node", message: `Duplicate node id: ${node.id}`, path: `nodes.${index}.id` });
    }
    ids.add(node.id);
  }

  for (const [index, edge] of scene.edges.entries()) {
    if (!ids.has(edge.from)) {
      issues.push({ code: "missing-source", message: `Unknown edge source: ${edge.from}`, path: `edges.${index}.from` });
    }
    if (!ids.has(edge.to)) {
      issues.push({ code: "missing-target", message: `Unknown edge target: ${edge.to}`, path: `edges.${index}.to` });
    }
    if (edge.from === edge.to) {
      issues.push({ code: "self-edge", message: `Self edge on ${edge.from}`, path: `edges.${index}` });
    }
  }

  return issues;
}

export function assertValidScene(scene: SemanticScene): SemanticScene {
  const issues = validateScene(scene);
  if (issues.length) {
    throw new Error(`Invalid SceneLyr scene:\n${issues.map((issue) => `- ${issue.message}`).join("\n")}`);
  }
  return scene;
}
