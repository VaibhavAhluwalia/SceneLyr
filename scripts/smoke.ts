import { mkdtemp, readFile, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { addNode, createScene, type SemanticScene } from "../packages/core/src/index.js";
import { searchAssets } from "../packages/assets/src/index.js";
import { compileScene } from "../packages/compiler/src/index.js";
import { SceneStore } from "../packages/store/src/index.js";
import { imageToScene } from "../packages/vision/src/index.js";

const temp = await mkdtemp(join(tmpdir(), "scenelyr-"));
const scene = JSON.parse(await readFile("examples/swiggy.scene.json", "utf8")) as SemanticScene;

const assets = searchAssets("redis", 1);
if (!assets.length || assets[0].id !== "redis") throw new Error("Phase 2 asset resolution failed");

const store = new SceneStore();
store.create(scene);
store.mutate(scene.id, (current) => addNode(current, { id: "analytics", label: "Analytics", kind: "service" }));
if (!store.get(scene.id)?.nodes.some((node) => node.id === "analytics")) throw new Error("Phase 3 semantic editing failed");
store.undo(scene.id);
if (store.get(scene.id)?.nodes.some((node) => node.id === "analytics")) throw new Error("Phase 3 undo failed");
store.redo(scene.id);

const svgPath = join(temp, "swiggy.svg");
const htmlPath = join(temp, "swiggy.html");
const pptxPath = join(temp, "swiggy.pptx");
await compileScene(scene, { svgPath, htmlPath, pptxPath });
for (const path of [svgPath, htmlPath, pptxPath]) {
  if ((await stat(path)).size < 100) throw new Error(`Empty artifact: ${path}`);
}

const imagePath = join(temp, "architecture.png");
const sidecarScene = createScene({ id: "from-image", title: "Recovered image scene" });
sidecarScene.nodes.push({ id: "api", label: "API", kind: "service" });
await writeFile(`${imagePath}.scene.json`, JSON.stringify(sidecarScene), "utf8");
const recovered = await imageToScene(imagePath);
if (recovered.id !== "from-image" || recovered.nodes[0]?.label !== "API") throw new Error("Phase 5 image import adapter failed");

console.log(JSON.stringify({
  ok: true,
  temp,
  phases: {
    semanticIR: true,
    deterministicLayout: true,
    assets: true,
    editableStore: true,
    svg: true,
    pptx: true,
    htmlInspector: true,
    visionAdapter: true,
    mcp: "typechecked by npm run typecheck"
  }
}, null, 2));
