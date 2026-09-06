export type NodeKind =
  | "actor"
  | "service"
  | "database"
  | "cache"
  | "queue"
  | "external"
  | "asset"
  | "image"
  | "note"
  | "group";

export type EdgeKind =
  | "request"
  | "async"
  | "read"
  | "write"
  | "event"
  | "relationship";

export type Importance = "primary" | "secondary" | "supporting";

export interface SceneIntent {
  title?: string;
  purpose?: string;
  audience?: string;
  direction?: "left-to-right" | "top-to-bottom";
  density?: "compact" | "balanced" | "spacious";
  style?: "technical" | "presentation" | "minimal";
}

export interface NodeStyle {
  emphasis?: "normal" | "strong";
  shape?: "rounded" | "pill" | "circle";
  accent?: string;
}

export interface SemanticNode {
  id: string;
  label: string;
  kind: NodeKind;
  description?: string;
  icon?: string;
  assetId?: string;
  group?: string;
  importance?: Importance;
  style?: NodeStyle;
  metadata?: Record<string, unknown>;
}

export interface SemanticEdge {
  id?: string;
  from: string;
  to: string;
  kind?: EdgeKind;
  label?: string;
  description?: string;
  metadata?: Record<string, unknown>;
}

export interface SemanticGroup {
  id: string;
  label: string;
  nodeIds: string[];
}

export interface SemanticConstraint {
  type: "parallel" | "before" | "after" | "same-rank";
  nodeIds: string[];
  description?: string;
}

export interface SemanticAsset {
  id: string;
  type: "icon" | "image" | "logo" | "illustration";
  source: "builtin" | "file" | "url" | "generated";
  uri: string;
  alt?: string;
  license?: string;
  metadata?: Record<string, unknown>;
}

export interface SemanticScene {
  version: "0.2";
  id: string;
  intent?: SceneIntent;
  nodes: SemanticNode[];
  edges: SemanticEdge[];
  groups?: SemanticGroup[];
  constraints?: SemanticConstraint[];
  assets?: SemanticAsset[];
  metadata?: Record<string, unknown>;
}

export interface SceneValidationIssue {
  code: string;
  message: string;
  path?: string;
}

export interface CreateSceneInput {
  id: string;
  title?: string;
  purpose?: string;
  audience?: string;
  direction?: SceneIntent["direction"];
  density?: SceneIntent["density"];
  style?: SceneIntent["style"];
}

export function createScene(input: CreateSceneInput): SemanticScene {
  return {
    version: "0.2",
    id: input.id,
    intent: {
      title: input.title,
      purpose: input.purpose,
      audience: input.audience,
      direction: input.direction ?? "left-to-right",
      density: input.density ?? "balanced",
      style: input.style ?? "presentation"
    },
    nodes: [],
    edges: [],
    assets: [],
    groups: [],
    constraints: []
  };
}

export function cloneScene(scene: SemanticScene): SemanticScene {
  return structuredClone(scene);
}

export function addNode(scene: SemanticScene, node: SemanticNode): SemanticScene {
  if (scene.nodes.some((item) => item.id === node.id)) {
    throw new Error(`Node already exists: ${node.id}`);
  }
  return { ...cloneScene(scene), nodes: [...scene.nodes, structuredClone(node)] };
}

export function updateNode(
  scene: SemanticScene,
  nodeId: string,
  patch: Partial<Omit<SemanticNode, "id">>
): SemanticScene {
  if (!scene.nodes.some((node) => node.id === nodeId)) {
    throw new Error(`Unknown node: ${nodeId}`);
  }
  return {
    ...cloneScene(scene),
    nodes: scene.nodes.map((node) =>
      node.id === nodeId ? { ...structuredClone(node), ...structuredClone(patch), id: nodeId } : structuredClone(node)
    )
  };
}

export function removeNode(scene: SemanticScene, nodeId: string): SemanticScene {
  return {
    ...cloneScene(scene),
    nodes: scene.nodes.filter((node) => node.id !== nodeId),
    edges: scene.edges.filter((edge) => edge.from !== nodeId && edge.to !== nodeId),
    groups: scene.groups?.map((group) => ({
      ...group,
      nodeIds: group.nodeIds.filter((id) => id !== nodeId)
    }))
  };
}

export function addEdge(scene: SemanticScene, edge: SemanticEdge): SemanticScene {
  const id = edge.id ?? `${edge.from}__${edge.to}__${scene.edges.length + 1}`;
  if (scene.edges.some((item) => item.id === id)) {
    throw new Error(`Edge already exists: ${id}`);
  }
  const next = { ...structuredClone(edge), id };
  const result = { ...cloneScene(scene), edges: [...scene.edges, next] };
  assertValidScene(result);
  return result;
}

export function removeEdge(scene: SemanticScene, edgeId: string): SemanticScene {
  return { ...cloneScene(scene), edges: scene.edges.filter((edge) => edge.id !== edgeId) };
}

export function attachAsset(scene: SemanticScene, asset: SemanticAsset): SemanticScene {
  const assets = scene.assets ?? [];
  const nextAssets = assets.some((item) => item.id === asset.id)
    ? assets.map((item) => (item.id === asset.id ? structuredClone(asset) : structuredClone(item)))
    : [...assets, structuredClone(asset)];
  return { ...cloneScene(scene), assets: nextAssets };
}

export function validateScene(scene: SemanticScene): SceneValidationIssue[] {
  const issues: SceneValidationIssue[] = [];
  const ids = new Set<string>();

  if (!scene.id.trim()) issues.push({ code: "scene-id", message: "Scene id cannot be empty", path: "id" });

  for (const [index, node] of scene.nodes.entries()) {
    if (!node.id.trim()) issues.push({ code: "node-id", message: "Node id cannot be empty", path: `nodes.${index}.id` });
    if (!node.label.trim()) issues.push({ code: "node-label", message: `Node ${node.id} has an empty label`, path: `nodes.${index}.label` });
    if (ids.has(node.id)) {
      issues.push({ code: "duplicate-node", message: `Duplicate node id: ${node.id}`, path: `nodes.${index}.id` });
    }
    ids.add(node.id);
  }

  const edgeIds = new Set<string>();
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
    if (edge.id) {
      if (edgeIds.has(edge.id)) issues.push({ code: "duplicate-edge", message: `Duplicate edge id: ${edge.id}`, path: `edges.${index}.id` });
      edgeIds.add(edge.id);
    }
  }

  for (const [index, group] of (scene.groups ?? []).entries()) {
    for (const nodeId of group.nodeIds) {
      if (!ids.has(nodeId)) issues.push({ code: "group-node", message: `Group ${group.id} references unknown node ${nodeId}`, path: `groups.${index}` });
    }
  }

  for (const [index, constraint] of (scene.constraints ?? []).entries()) {
    for (const nodeId of constraint.nodeIds) {
      if (!ids.has(nodeId)) issues.push({ code: "constraint-node", message: `Constraint references unknown node ${nodeId}`, path: `constraints.${index}` });
    }
  }

  const assetIds = new Set((scene.assets ?? []).map((asset) => asset.id));
  for (const [index, node] of scene.nodes.entries()) {
    if (node.assetId && !assetIds.has(node.assetId)) {
      issues.push({ code: "missing-asset", message: `Node ${node.id} references unknown asset ${node.assetId}`, path: `nodes.${index}.assetId` });
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
