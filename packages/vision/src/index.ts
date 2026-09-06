import { readFile } from "node:fs/promises";
import { extname } from "node:path";
import { assertValidScene, createScene, type SemanticScene } from "../../core/src/index.js";

export interface VisionOptions {
  endpoint?: string;
  model?: string;
  apiKey?: string;
  sceneId?: string;
}

function mimeFor(path: string): string {
  const ext = extname(path).toLowerCase();
  if (ext === ".jpg" || ext === ".jpeg") return "image/jpeg";
  if (ext === ".webp") return "image/webp";
  if (ext === ".gif") return "image/gif";
  return "image/png";
}

function extractJson(text: string): string {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fenced) return fenced[1].trim();
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start >= 0 && end > start) return text.slice(start, end + 1);
  return text;
}

function normalizeScene(value: any, sceneId: string): SemanticScene {
  const scene: SemanticScene = {
    version: "0.2",
    id: value.id || sceneId,
    intent: value.intent ?? { title: value.title ?? sceneId, direction: "left-to-right", density: "balanced", style: "presentation" },
    nodes: Array.isArray(value.nodes) ? value.nodes : [],
    edges: Array.isArray(value.edges) ? value.edges : [],
    groups: Array.isArray(value.groups) ? value.groups : [],
    constraints: Array.isArray(value.constraints) ? value.constraints : [],
    assets: Array.isArray(value.assets) ? value.assets : [],
    metadata: value.metadata ?? {}
  };
  assertValidScene(scene);
  return scene;
}

export async function imageToScene(imagePath: string, options: VisionOptions = {}): Promise<SemanticScene> {
  const sceneId = options.sceneId ?? `imported-${Date.now()}`;
  const sidecarPath = `${imagePath}.scene.json`;

  try {
    const sidecar = await readFile(sidecarPath, "utf8");
    return normalizeScene(JSON.parse(sidecar), sceneId);
  } catch (error: any) {
    if (error?.code !== "ENOENT") throw error;
  }

  const endpoint = options.endpoint ?? process.env.SCENELYR_VISION_ENDPOINT;
  const model = options.model ?? process.env.SCENELYR_VISION_MODEL;
  const apiKey = options.apiKey ?? process.env.SCENELYR_VISION_API_KEY;

  if (!endpoint || !model) {
    const fallback = createScene({
      id: sceneId,
      title: "Imported visual",
      purpose: "Fallback scene created because no vision provider was configured",
      direction: "left-to-right"
    });
    fallback.nodes.push({
      id: "source-image",
      label: "Source image",
      kind: "image",
      description: imagePath,
      metadata: { sourceImage: imagePath, decomposition: "pending" }
    });
    fallback.metadata = { sourceImage: imagePath, visionProvider: "none" };
    return fallback;
  }

  const bytes = await readFile(imagePath);
  const dataUrl = `data:${mimeFor(imagePath)};base64,${bytes.toString("base64")}`;
  const prompt = `You are converting a visual into SceneLyr semantic IR. Return JSON only.\n\nSchema:\n{\n  \"id\": \"string\",\n  \"intent\": { \"title\": \"string\", \"purpose\": \"string\", \"direction\": \"left-to-right|top-to-bottom\", \"density\": \"compact|balanced|spacious\", \"style\": \"technical|presentation|minimal\" },\n  \"nodes\": [{ \"id\": \"string\", \"label\": \"string\", \"kind\": \"actor|service|database|cache|queue|external|asset|image|note|group\", \"description\": \"optional\", \"icon\": \"optional\" }],\n  \"edges\": [{ \"from\": \"node-id\", \"to\": \"node-id\", \"kind\": \"request|async|read|write|event|relationship\", \"label\": \"optional\" }]\n}\n\nRecover semantic objects and relationships. Do not emit x/y coordinates. Preserve labels exactly when readable.`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(apiKey ? { authorization: `Bearer ${apiKey}` } : {})
    },
    body: JSON.stringify({
      model,
      messages: [{
        role: "user",
        content: [
          { type: "text", text: prompt },
          { type: "image_url", image_url: { url: dataUrl } }
        ]
      }],
      temperature: 0
    })
  });

  if (!response.ok) throw new Error(`Vision provider failed: ${response.status} ${await response.text()}`);
  const payload: any = await response.json();
  const content = payload.choices?.[0]?.message?.content;
  if (typeof content !== "string") throw new Error("Vision provider returned no text content");
  return normalizeScene(JSON.parse(extractJson(content)), sceneId);
}
