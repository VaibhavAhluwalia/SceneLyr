#!/usr/bin/env node
import { readFile, writeFile } from "node:fs/promises";
import { basename, extname, join } from "node:path";
import { compileScene } from "../../compiler/src/index.js";
import { imageToScene } from "../../vision/src/index.js";
import type { SemanticScene } from "../../core/src/index.js";

function help(): never {
  console.log(`SceneLyr CLI\n\nCommands:\n  compile <scene.json> [output-dir]\n  import-image <image-path> [output-scene.json]\n  example\n  mcp  (use: npm run mcp)\n`);
  process.exit(0);
}

async function compileFile(scenePath: string, outputDir = "artifacts") {
  const scene = JSON.parse(await readFile(scenePath, "utf8")) as SemanticScene;
  const name = basename(scenePath, extname(scenePath)).replace(/\.scene$/, "");
  await compileScene(scene, {
    svgPath: join(outputDir, `${name}.svg`),
    htmlPath: join(outputDir, `${name}.html`),
    pptxPath: join(outputDir, `${name}.pptx`)
  });
  console.log(`Compiled ${scene.id} → ${outputDir}`);
}

const [command, first, second] = process.argv.slice(2);
if (!command || command === "help" || command === "--help") help();

if (command === "compile") {
  if (!first) help();
  await compileFile(first, second);
} else if (command === "import-image") {
  if (!first) help();
  const scene = await imageToScene(first);
  const output = second ?? `${first}.scene.json`;
  await writeFile(output, JSON.stringify(scene, null, 2), "utf8");
  console.log(`Imported visual → ${output}`);
} else if (command === "example") {
  await compileFile("examples/swiggy.scene.json");
} else {
  help();
}
