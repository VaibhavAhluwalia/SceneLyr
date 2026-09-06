import { describe, expect, it } from "vitest";
import { addEdge, addNode, createScene, removeNode, updateNode, validateScene } from "../packages/core/src/index.js";

describe("semantic IR", () => {
  it("edits scenes without coordinates", () => {
    let scene = createScene({ id: "test", title: "Test" });
    scene = addNode(scene, { id: "a", label: "A", kind: "service" });
    scene = addNode(scene, { id: "b", label: "B", kind: "database" });
    scene = addEdge(scene, { from: "a", to: "b", kind: "write" });
    scene = updateNode(scene, "a", { label: "API" });
    expect(scene.nodes[0].label).toBe("API");
    expect(Object.keys(scene.nodes[0])).not.toContain("x");
    expect(validateScene(scene)).toEqual([]);
    scene = removeNode(scene, "b");
    expect(scene.edges).toHaveLength(0);
  });

  it("detects broken relationships", () => {
    const scene = createScene({ id: "broken" });
    scene.edges.push({ from: "missing", to: "also-missing" });
    expect(validateScene(scene).map((issue) => issue.code)).toEqual(expect.arrayContaining(["missing-source", "missing-target"]));
  });
});
