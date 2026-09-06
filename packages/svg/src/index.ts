import type { SemanticScene } from "../../core/src/index.js";
import { resolveNodeAsset } from "../../assets/src/index.js";
import type { LayoutPoint, LayoutScene, PositionedNode } from "../../layout/src/index.js";

export interface SvgRenderOptions {
  background?: string;
  showPurpose?: boolean;
}

const esc = (value: string) => value.replace(/[&<>"']/g, (char) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&apos;"
}[char]!));

const COLORS: Record<string, { fill: string; stroke: string; accent: string }> = {
  actor: { fill: "#eff6ff", stroke: "#93c5fd", accent: "#2563eb" },
  service: { fill: "#ffffff", stroke: "#cbd5e1", accent: "#334155" },
  database: { fill: "#f0fdf4", stroke: "#86efac", accent: "#16a34a" },
  cache: { fill: "#fff7ed", stroke: "#fdba74", accent: "#ea580c" },
  queue: { fill: "#faf5ff", stroke: "#d8b4fe", accent: "#9333ea" },
  external: { fill: "#f8fafc", stroke: "#cbd5e1", accent: "#64748b" },
  image: { fill: "#fdf2f8", stroke: "#f9a8d4", accent: "#db2777" },
  asset: { fill: "#fdf2f8", stroke: "#f9a8d4", accent: "#db2777" },
  note: { fill: "#fffbeb", stroke: "#fcd34d", accent: "#d97706" },
  group: { fill: "#f8fafc", stroke: "#94a3b8", accent: "#475569" }
};

function route(points: LayoutPoint[]): string {
  if (!points.length) return "";
  return `M ${points[0].x} ${points[0].y} ${points.slice(1).map((point) => `L ${point.x} ${point.y}`).join(" ")}`;
}

function midpoint(points: LayoutPoint[]): LayoutPoint {
  if (!points.length) return { x: 0, y: 0 };
  return points[Math.floor(points.length / 2)];
}

function renderNode(node: PositionedNode, semantic: SemanticScene): string {
  const original = semantic.nodes.find((item) => item.id === node.id)!;
  const palette = COLORS[node.kind] ?? COLORS.service;
  const asset = resolveNodeAsset(original);
  const strong = original.importance === "primary" || original.style?.emphasis === "strong";
  const iconX = node.x + 18;
  const iconY = node.y + node.height / 2 - 15;
  const textX = node.x + 62;
  return `
  <g data-scene-id="${esc(node.id)}" data-kind="${esc(node.kind)}">
    <rect x="${node.x}" y="${node.y}" width="${node.width}" height="${node.height}" rx="16" fill="${palette.fill}" stroke="${strong ? palette.accent : palette.stroke}" stroke-width="${strong ? 2.5 : 1.5}"/>
    <rect x="${iconX}" y="${iconY}" width="34" height="30" rx="9" fill="${palette.accent}"/>
    <text x="${iconX + 17}" y="${iconY + 19}" text-anchor="middle" font-family="Inter, ui-sans-serif, system-ui" font-size="10" font-weight="700" fill="#ffffff">${esc(asset.glyph)}</text>
    <text x="${textX}" y="${node.y + node.height / 2 + 5}" font-family="Inter, ui-sans-serif, system-ui" font-size="15" font-weight="${strong ? 700 : 600}" fill="#0f172a">${esc(node.label)}</text>
  </g>`;
}

export function renderSvg(layout: LayoutScene, semantic: SemanticScene, options: SvgRenderOptions = {}): string {
  const title = semantic.intent?.title ?? semantic.id;
  const purpose = semantic.intent?.purpose;
  const background = options.background ?? "#f8fafc";

  const edges = layout.edges.map((edge) => {
    const asyncEdge = edge.kind === "async" || edge.kind === "event";
    const labelPoint = midpoint(edge.points);
    return `
    <g data-edge-id="${esc(edge.id)}">
      <path d="${route(edge.points)}" fill="none" stroke="#64748b" stroke-width="2" ${asyncEdge ? 'stroke-dasharray="7 6"' : ""} marker-end="url(#arrow)"/>
      ${edge.label ? `<text x="${labelPoint.x + 8}" y="${labelPoint.y - 8}" font-family="Inter, ui-sans-serif, system-ui" font-size="11" fill="#475569">${esc(edge.label)}</text>` : ""}
    </g>`;
  }).join("\n");

  const nodes = layout.nodes.map((node) => renderNode(node, semantic)).join("\n");
  const subtitle = options.showPurpose !== false && purpose
    ? `<text x="64" y="58" font-family="Inter, ui-sans-serif, system-ui" font-size="13" fill="#64748b">${esc(purpose)}</text>`
    : "";

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${layout.width}" height="${layout.height}" viewBox="0 0 ${layout.width} ${layout.height}">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b"/>
    </marker>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.08"/></filter>
  </defs>
  <rect width="100%" height="100%" fill="${background}"/>
  <text x="64" y="34" font-family="Inter, ui-sans-serif, system-ui" font-size="22" font-weight="700" fill="#0f172a">${esc(title)}</text>
  ${subtitle}
  ${edges}
  ${nodes}
</svg>`;
}
