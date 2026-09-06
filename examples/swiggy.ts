import { readFile } from "node:fs/promises";
import { compileScene } from "../packages/compiler/src/index.js";
import type { SemanticScene } from "../packages/core/src/index.js";

const scene = JSON.parse(await readFile("examples/swiggy.scene.json", "utf8")) as SemanticScene;
await compileScene(scene, {
  svgPath: "artifacts/swiggy.svg",
  htmlPath: "artifacts/swiggy.html",
  pptxPath: "artifacts/swiggy.pptx"
});
console.log("SceneLyr example complete: artifacts/swiggy.svg, .html and .pptx");
