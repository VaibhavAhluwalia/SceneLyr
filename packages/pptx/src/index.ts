import PptxGenJS from "pptxgenjs";
import type { SemanticScene } from "../../core/src/index.js";
import { resolveNodeAsset } from "../../assets/src/index.js";
import type { LayoutScene, LayoutPoint } from "../../layout/src/index.js";

const PALETTE: Record<string, { fill: string; line: string; accent: string }> = {
  actor: { fill: "EFF6FF", line: "93C5FD", accent: "2563EB" },
  service: { fill: "FFFFFF", line: "CBD5E1", accent: "334155" },
  database: { fill: "F0FDF4", line: "86EFAC", accent: "16A34A" },
  cache: { fill: "FFF7ED", line: "FDBA74", accent: "EA580C" },
  queue: { fill: "FAF5FF", line: "D8B4FE", accent: "9333EA" },
  external: { fill: "F8FAFC", line: "CBD5E1", accent: "64748B" },
  image: { fill: "FDF2F8", line: "F9A8D4", accent: "DB2777" },
  asset: { fill: "FDF2F8", line: "F9A8D4", accent: "DB2777" },
  note: { fill: "FFFBEB", line: "FCD34D", accent: "D97706" },
  group: { fill: "F8FAFC", line: "94A3B8", accent: "475569" }
};

function fit(layout: LayoutScene) {
  const slideW = 13.333;
  const slideH = 7.5;
  const padX = 0.5;
  const top = 0.85;
  const padBottom = 0.35;
  const scale = Math.min((slideW - padX * 2) / layout.width, (slideH - top - padBottom) / layout.height);
  const xOffset = (slideW - layout.width * scale) / 2;
  return { scale, xOffset, yOffset: top };
}

function transform(point: LayoutPoint, scale: number, xOffset: number, yOffset: number) {
  return { x: xOffset + point.x * scale, y: yOffset + point.y * scale };
}

export async function writePptx(layout: LayoutScene, semantic: SemanticScene, outputPath: string): Promise<void> {
  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "SceneLyr";
  pptx.subject = semantic.intent?.purpose ?? "Semantic visual scene";
  pptx.title = semantic.intent?.title ?? semantic.id;
  pptx.company = "SceneLyr";
  pptx.lang = "en-US";

  const slide = pptx.addSlide();
  slide.background = { color: "F8FAFC" };
  slide.addText(semantic.intent?.title ?? semantic.id, {
    x: 0.55, y: 0.18, w: 12.2, h: 0.35,
    fontFace: "Aptos", fontSize: 20, bold: true, color: "0F172A", margin: 0
  });
  if (semantic.intent?.purpose) {
    slide.addText(semantic.intent.purpose, {
      x: 0.55, y: 0.54, w: 12.2, h: 0.22,
      fontFace: "Aptos", fontSize: 10, color: "64748B", margin: 0
    });
  }

  const { scale, xOffset, yOffset } = fit(layout);
  for (const edge of layout.edges) {
    for (let index = 0; index < edge.points.length - 1; index += 1) {
      const a = transform(edge.points[index], scale, xOffset, yOffset);
      const b = transform(edge.points[index + 1], scale, xOffset, yOffset);
      slide.addShape(pptx.ShapeType.line, {
        x: a.x,
        y: a.y,
        w: b.x - a.x,
        h: b.y - a.y,
        line: {
          color: "64748B",
          width: 1.3,
          dash: edge.kind === "async" || edge.kind === "event" ? "dash" : "solid",
          endArrowType: index === edge.points.length - 2 ? "triangle" : "none"
        }
      });
    }
  }

  for (const node of layout.nodes) {
    const semanticNode = semantic.nodes.find((item) => item.id === node.id)!;
    const palette = PALETTE[node.kind] ?? PALETTE.service;
    const x = xOffset + node.x * scale;
    const y = yOffset + node.y * scale;
    const w = node.width * scale;
    const h = node.height * scale;
    const asset = resolveNodeAsset(semanticNode);
    const strong = semanticNode.importance === "primary" || semanticNode.style?.emphasis === "strong";

    slide.addShape(pptx.ShapeType.roundRect, {
      x, y, w, h,
      rectRadius: 0.08,
      fill: { color: palette.fill },
      line: { color: strong ? palette.accent : palette.line, width: strong ? 1.8 : 1 }
    });

    const iconW = Math.min(0.34, w * 0.22);
    slide.addShape(pptx.ShapeType.roundRect, {
      x: x + 0.12,
      y: y + (h - iconW) / 2,
      w: iconW,
      h: iconW,
      fill: { color: palette.accent },
      line: { color: palette.accent, transparency: 100 }
    });
    slide.addText(asset.glyph, {
      x: x + 0.12,
      y: y + (h - iconW) / 2 + 0.015,
      w: iconW,
      h: iconW - 0.02,
      fontFace: "Aptos",
      fontSize: 7,
      bold: true,
      color: "FFFFFF",
      align: "center",
      valign: "mid",
      margin: 0
    });
    slide.addText(node.label, {
      x: x + 0.54,
      y: y + 0.06,
      w: Math.max(0.2, w - 0.64),
      h: Math.max(0.2, h - 0.12),
      fontFace: "Aptos",
      fontSize: Math.max(8, Math.min(12, h * 18)),
      bold: strong,
      color: "0F172A",
      valign: "mid",
      margin: 0
    });
  }

  await pptx.writeFile({ fileName: outputPath });
}
