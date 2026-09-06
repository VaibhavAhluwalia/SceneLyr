import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import {
  addEdge,
  addNode,
  createScene,
  removeNode,
  updateNode,
  validateScene,
  type EdgeKind,
  type NodeKind,
  type SemanticScene
} from "../../core/src/index.js";
import { searchAssets } from "../../assets/src/index.js";
import { compileScene } from "../../compiler/src/index.js";
import { imageToScene } from "../../vision/src/index.js";
import { SceneStore } from "../../store/src/index.js";

const NODE_KINDS = ["actor", "service", "database", "cache", "queue", "external", "asset", "image", "note", "group"] as const;
const EDGE_KINDS = ["request", "async", "read", "write", "event", "relationship"] as const;
const text = (value: unknown) => ({ content: [{ type: "text" as const, text: typeof value === "string" ? value : JSON.stringify(value, null, 2) }] });

export function createSceneLyrServer(store = new SceneStore()): McpServer {
  const server = new McpServer({ name: "scenelyr", version: "0.1.0" });

  server.tool("create_scene", {
    id: z.string().min(1),
    title: z.string().optional(),
    purpose: z.string().optional(),
    audience: z.string().optional(),
    direction: z.enum(["left-to-right", "top-to-bottom"]).optional(),
    density: z.enum(["compact", "balanced", "spacious"]).optional()
  }, async (args) => text(store.create(createScene(args))));

  server.tool("add_node", {
    sceneId: z.string(), id: z.string(), label: z.string(), kind: z.enum(NODE_KINDS),
    description: z.string().optional(), icon: z.string().optional(), group: z.string().optional(),
    importance: z.enum(["primary", "secondary", "supporting"]).optional()
  }, async ({ sceneId, ...node }) => text(store.mutate(sceneId, (scene) => addNode(scene, node as any))));

  server.tool("update_node", {
    sceneId: z.string(), nodeId: z.string(), label: z.string().optional(), kind: z.enum(NODE_KINDS).optional(),
    description: z.string().optional(), icon: z.string().optional(), importance: z.enum(["primary", "secondary", "supporting"]).optional()
  }, async ({ sceneId, nodeId, ...patch }) => text(store.mutate(sceneId, (scene) => updateNode(scene, nodeId, patch as any))));

  server.tool("remove_node", { sceneId: z.string(), nodeId: z.string() }, async ({ sceneId, nodeId }) =>
    text(store.mutate(sceneId, (scene) => removeNode(scene, nodeId))));

  server.tool("add_relationship", {
    sceneId: z.string(), from: z.string(), to: z.string(), kind: z.enum(EDGE_KINDS).optional(), label: z.string().optional()
  }, async ({ sceneId, ...edge }) => text(store.mutate(sceneId, (scene) => addEdge(scene, edge as any))));

  server.tool("inspect_scene", { sceneId: z.string() }, async ({ sceneId }) => {
    const scene = store.get(sceneId);
    if (!scene) throw new Error(`Unknown scene: ${sceneId}`);
    return text(scene);
  });

  server.tool("list_scenes", {}, async () => text(store.list().map((scene) => ({ id: scene.id, title: scene.intent?.title, nodes: scene.nodes.length, edges: scene.edges.length }))));

  server.tool("validate_scene", { sceneId: z.string() }, async ({ sceneId }) => {
    const scene = store.get(sceneId);
    if (!scene) throw new Error(`Unknown scene: ${sceneId}`);
    return text({ valid: validateScene(scene).length === 0, issues: validateScene(scene) });
  });

  server.tool("find_asset", { query: z.string(), limit: z.number().int().positive().max(20).optional() }, async ({ query, limit }) => text(searchAssets(query, limit ?? 5)));

  server.tool("render_scene", { sceneId: z.string() }, async ({ sceneId }) => {
    const scene = store.get(sceneId);
    if (!scene) throw new Error(`Unknown scene: ${sceneId}`);
    const result = await compileScene(scene);
    return text(result.svg);
  });

  server.tool("export_scene", {
    sceneId: z.string(), outputDir: z.string(), basename: z.string().optional(), pptx: z.boolean().optional()
  }, async ({ sceneId, outputDir, basename, pptx }) => {
    const scene = store.get(sceneId);
    if (!scene) throw new Error(`Unknown scene: ${sceneId}`);
    const name = basename ?? scene.id;
    const paths = {
      svgPath: join(outputDir, `${name}.svg`),
      htmlPath: join(outputDir, `${name}.html`),
      pptxPath: pptx === false ? undefined : join(outputDir, `${name}.pptx`)
    };
    await compileScene(scene, paths);
    return text(paths);
  });

  server.tool("import_scene", { sceneJson: z.string() }, async ({ sceneJson }) => {
    const raw = JSON.parse(sceneJson);
    const scene: SemanticScene = { ...raw, version: "0.2" };
    return text(store.create(scene));
  });

  server.tool("import_image", { path: z.string(), sceneId: z.string().optional() }, async ({ path, sceneId }) => {
    const scene = await imageToScene(path, { sceneId });
    return text(store.create(scene));
  });

  server.tool("undo_scene", { sceneId: z.string() }, async ({ sceneId }) => text(store.undo(sceneId)));
  server.tool("redo_scene", { sceneId: z.string() }, async ({ sceneId }) => text(store.redo(sceneId)));

  return server;
}

export async function serveStdio(): Promise<void> {
  const server = createSceneLyrServer();
  await server.connect(new StdioServerTransport());
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await serveStdio();
}
