import { assertValidScene, type SemanticScene } from "../packages/core/src/index.js";
import { layoutScene } from "../packages/layout/src/index.js";
import { renderSvg } from "../packages/svg/src/index.js";
import { writeFile } from "node:fs/promises";

const scene: SemanticScene = {
  version: "0.1",
  id: "swiggy-order-flow",
  intent: {
    title: "Swiggy Order Architecture",
    purpose: "Explain the order path and supporting infrastructure",
    audience: "engineering presentation",
    direction: "left-to-right",
    density: "balanced"
  },
  nodes: [
    { id: "customer", label: "Customer", kind: "actor" },
    { id: "app", label: "Swiggy App", kind: "service" },
    { id: "gateway", label: "API Gateway", kind: "service" },
    { id: "orders", label: "Order Service", kind: "service", importance: "primary" },
    { id: "restaurant", label: "Restaurant", kind: "external" },
    { id: "rider", label: "Delivery Partner", kind: "external" },
    { id: "kafka", label: "Kafka", kind: "queue" },
    { id: "redis", label: "Redis", kind: "cache" },
    { id: "postgres", label: "PostgreSQL", kind: "database" }
  ],
  edges: [
    { from: "customer", to: "app", kind: "request" },
    { from: "app", to: "gateway", kind: "request" },
    { from: "gateway", to: "orders", kind: "request" },
    { from: "orders", to: "restaurant", kind: "request" },
    { from: "orders", to: "rider", kind: "request" },
    { from: "orders", to: "kafka", kind: "async" },
    { from: "orders", to: "redis", kind: "read" },
    { from: "orders", to: "postgres", kind: "write" }
  ]
};

assertValidScene(scene);
const svg = renderSvg(layoutScene(scene));
await writeFile("swiggy.svg", svg, "utf8");
console.log("Wrote swiggy.svg");
