import { describe, expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import type { SemanticScene } from "../packages/core/src/index.js";
import { compileScene } from "../packages/compiler/src/index.js";

describe("compiler", () => {
  it("compiles semantic intent to editable SVG and inspector HTML", async () => {
    const scene = JSON.parse(await readFile("examples/swiggy.scene.json", "utf8")) as SemanticScene;
    const result = await compileScene(scene);
    expect(result.svg).toContain("data-scene-id=\"orders\"");
    expect(result.svg).toContain("Order Service");
    expect(result.html).toContain("SceneLyr inspector");
    expect(result.layout.nodes).toHaveLength(scene.nodes.length);
  });
});
