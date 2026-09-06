import type { SemanticNode } from "../../core/src/index.js";

export interface AssetCandidate {
  id: string;
  label: string;
  glyph: string;
  keywords: string[];
  source: "builtin";
  score?: number;
}

const BUILTIN_ASSETS: AssetCandidate[] = [
  { id: "actor", label: "Person", glyph: "USR", keywords: ["customer", "user", "person", "actor"], source: "builtin" },
  { id: "app", label: "Application", glyph: "APP", keywords: ["app", "mobile", "client", "frontend"], source: "builtin" },
  { id: "gateway", label: "API Gateway", glyph: "API", keywords: ["api", "gateway", "edge"], source: "builtin" },
  { id: "service", label: "Service", glyph: "SVC", keywords: ["service", "worker", "backend", "microservice"], source: "builtin" },
  { id: "restaurant", label: "Restaurant", glyph: "RST", keywords: ["restaurant", "merchant", "store"], source: "builtin" },
  { id: "rider", label: "Delivery", glyph: "DRV", keywords: ["rider", "driver", "delivery", "courier"], source: "builtin" },
  { id: "kafka", label: "Kafka", glyph: "K", keywords: ["kafka", "event bus", "stream", "queue"], source: "builtin" },
  { id: "redis", label: "Redis", glyph: "R", keywords: ["redis", "cache"], source: "builtin" },
  { id: "postgres", label: "PostgreSQL", glyph: "PG", keywords: ["postgres", "postgresql", "sql", "database"], source: "builtin" },
  { id: "database", label: "Database", glyph: "DB", keywords: ["database", "storage", "persistent"], source: "builtin" },
  { id: "queue", label: "Queue", glyph: "Q", keywords: ["queue", "async", "message", "event"], source: "builtin" },
  { id: "cache", label: "Cache", glyph: "C", keywords: ["cache", "memory"], source: "builtin" },
  { id: "external", label: "External system", glyph: "EXT", keywords: ["external", "partner", "third party"], source: "builtin" },
  { id: "image", label: "Image", glyph: "IMG", keywords: ["image", "visual", "photo", "asset"], source: "builtin" }
];

function score(query: string, candidate: AssetCandidate): number {
  const q = query.toLowerCase().trim();
  if (!q) return 0;
  let value = 0;
  if (candidate.id === q) value += 12;
  if (candidate.label.toLowerCase() === q) value += 10;
  if (candidate.label.toLowerCase().includes(q)) value += 5;
  for (const keyword of candidate.keywords) {
    if (keyword === q) value += 8;
    else if (q.includes(keyword) || keyword.includes(q)) value += 3;
  }
  return value;
}

export function searchAssets(query: string, limit = 5): AssetCandidate[] {
  return BUILTIN_ASSETS
    .map((candidate) => ({ ...candidate, score: score(query, candidate) }))
    .filter((candidate) => (candidate.score ?? 0) > 0)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, limit);
}

export function resolveNodeAsset(node: SemanticNode): AssetCandidate {
  const explicit = node.icon ? searchAssets(node.icon, 1)[0] : undefined;
  if (explicit) return explicit;
  const semantic = searchAssets(`${node.label} ${node.kind}`, 1)[0];
  if (semantic) return semantic;
  return BUILTIN_ASSETS.find((candidate) => candidate.id === node.kind) ?? BUILTIN_ASSETS.find((candidate) => candidate.id === "service")!;
}

export function listBuiltinAssets(): AssetCandidate[] {
  return BUILTIN_ASSETS.map((asset) => ({ ...asset }));
}
