import { describe, expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import type { SemanticScene } from "../packages/core/src/index.js";
import { layoutScene } from "../packages/layout/src/index.js";

describe("ELK layout", () => {
  it("is deterministic for the same semantic scene", async () => {
    const scene = JSON.parse(await readFile("examples/swiggy.scene.json", "utf8")) as SemanticScene;
    const first = await layoutScene(scene);
    const second = await layoutScene(scene);
    expect(first.nodes).toEqual(second.nodes);
    expect(first.edges).toEqual(second.edges);
    expect(first.width).toBeGreaterThan(500);
  });

  it("does not overlap node rectangles", async () => {
    const scene = JSON.parse(await readFile("examples/swiggy.scene.json", "utf8")) as SemanticScene;
    const layout = await layoutScene(scene);
    for (let i = 0; i < layout.nodes.length; i += 1) {
      for (let j = i + 1; j < layout.nodes.length; j += 1) {
        const a = layout.nodes[i];
        const b = layout.nodes[j];
        const overlap = a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
        expect(overlap, `${a.id} overlaps ${b.id}`).toBe(false);
      }
    }
  });
});
