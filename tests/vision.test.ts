import { describe, expect, it } from "vitest";
import { mkdtemp, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createScene } from "../packages/core/src/index.js";
import { imageToScene } from "../packages/vision/src/index.js";

describe("image import", () => {
  it("supports an offline semantic sidecar for deterministic tests", async () => {
    const dir = await mkdtemp(join(tmpdir(), "scenelyr-vision-"));
    const image = join(dir, "diagram.png");
    const scene = createScene({ id: "imported", title: "Imported" });
    scene.nodes.push({ id: "gateway", label: "Gateway", kind: "service" });
    await writeFile(`${image}.scene.json`, JSON.stringify(scene), "utf8");
    const result = await imageToScene(image);
    expect(result.id).toBe("imported");
    expect(result.nodes[0].label).toBe("Gateway");
  });

  it("falls back to a whole-image semantic node when no vision endpoint is configured", async () => {
    const result = await imageToScene("does-not-need-to-exist.png", { sceneId: "fallback" });
    expect(result.id).toBe("fallback");
    expect(result.nodes[0].kind).toBe("image");
  });
});
