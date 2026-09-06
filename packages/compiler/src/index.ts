import { mkdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { assertValidScene, type SemanticScene } from "../../core/src/index.js";
import { layoutScene, type LayoutScene } from "../../layout/src/index.js";
import { renderSvg } from "../../svg/src/index.js";
import { writePptx } from "../../pptx/src/index.js";

export interface CompileOptions {
  svgPath?: string;
  pptxPath?: string;
  htmlPath?: string;
}

export interface CompileResult {
  scene: SemanticScene;
  layout: LayoutScene;
  svg: string;
  html: string;
}

async function ensureParent(path: string): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
}

export function renderPreviewHtml(scene: SemanticScene, svg: string): string {
  const serialized = JSON.stringify(scene).replace(/</g, "\\u003c");
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>${scene.intent?.title ?? scene.id} · SceneLyr</title>
<style>
  :root { font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #0f172a; background: #e2e8f0; }
  body { margin: 0; display: grid; grid-template-columns: minmax(0, 1fr) 320px; min-height: 100vh; }
  main { padding: 24px; overflow: auto; }
  .canvas { background: white; border-radius: 18px; box-shadow: 0 20px 50px rgba(15,23,42,.12); overflow: auto; min-height: calc(100vh - 48px); display:flex; align-items:center; justify-content:center; }
  .canvas svg { max-width: 100%; height: auto; }
  aside { background:#0f172a; color:#e2e8f0; padding:20px; overflow:auto; }
  h2 { margin:0 0 8px; font-size:18px; }
  p { color:#94a3b8; font-size:13px; line-height:1.5; }
  pre { white-space:pre-wrap; font-size:11px; color:#cbd5e1; background:#111827; padding:12px; border-radius:12px; }
  [data-scene-id] { cursor:pointer; }
  [data-scene-id].selected rect:first-of-type { stroke:#2563eb !important; stroke-width:4 !important; }
</style>
</head>
<body>
<main><div class="canvas">${svg}</div></main>
<aside>
  <h2>SceneLyr inspector</h2>
  <p>Click a semantic node to inspect it. The scene graph remains the source of truth; geometry is renderer-owned.</p>
  <pre id="selection">Select a node…</pre>
  <h2 style="margin-top:24px">Scene JSON</h2>
  <pre id="scene"></pre>
</aside>
<script id="scene-data" type="application/json">${serialized}</script>
<script>
  const scene = JSON.parse(document.getElementById('scene-data').textContent);
  document.getElementById('scene').textContent = JSON.stringify(scene, null, 2);
  document.querySelectorAll('[data-scene-id]').forEach(el => el.addEventListener('click', () => {
    document.querySelectorAll('[data-scene-id]').forEach(x => x.classList.remove('selected'));
    el.classList.add('selected');
    const node = scene.nodes.find(n => n.id === el.dataset.sceneId);
    document.getElementById('selection').textContent = JSON.stringify(node, null, 2);
  }));
</script>
</body>
</html>`;
}

export async function compileScene(scene: SemanticScene, options: CompileOptions = {}): Promise<CompileResult> {
  assertValidScene(scene);
  const layout = await layoutScene(scene);
  const svg = renderSvg(layout, scene);
  const html = renderPreviewHtml(scene, svg);

  if (options.svgPath) {
    await ensureParent(options.svgPath);
    await writeFile(options.svgPath, svg, "utf8");
  }
  if (options.htmlPath) {
    await ensureParent(options.htmlPath);
    await writeFile(options.htmlPath, html, "utf8");
  }
  if (options.pptxPath) {
    await ensureParent(options.pptxPath);
    await writePptx(layout, scene, options.pptxPath);
  }

  return { scene, layout, svg, html };
}
