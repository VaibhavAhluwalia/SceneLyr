import type { LayoutScene } from "../../layout/src/index.js";

const esc = (value: string) => value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" }[c]!));

export function renderSvg(scene: LayoutScene): string {
  const nodes = new Map(scene.nodes.map((node) => [node.id, node]));
  const edges = scene.edges.map((edge) => {
    const a = nodes.get(edge.from)!;
    const b = nodes.get(edge.to)!;
    const x1 = a.x + a.width;
    const y1 = a.y + a.height / 2;
    const x2 = b.x;
    const y2 = b.y + b.height / 2;
    const mid = (x1 + x2) / 2;
    return `<path d="M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}" fill="none" stroke="#64748b" stroke-width="2" marker-end="url(#arrow)"/>`;
  }).join("\n");

  const boxes = scene.nodes.map((node) => `
    <g data-scene-id="${esc(node.id)}">
      <rect x="${node.x}" y="${node.y}" width="${node.width}" height="${node.height}" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
      <text x="${node.x + node.width / 2}" y="${node.y + 43}" text-anchor="middle" font-family="Inter, ui-sans-serif, system-ui" font-size="16" font-weight="600" fill="#0f172a">${esc(node.label)}</text>
    </g>`).join("\n");

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${scene.width}" height="${scene.height}" viewBox="0 0 ${scene.width} ${scene.height}">
  <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b"/></marker></defs>
  <rect width="100%" height="100%" fill="#f8fafc"/>
  ${edges}
  ${boxes}
</svg>`;
}
