"""SceneLyr's Python command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compiler import compile_scene
from .models import SemanticScene
from .pixels import extract_pixels


def _scene(path: str) -> SemanticScene:
    return SemanticScene.model_validate_json(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scenelyr", description="Python-first deterministic visual compiler")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate SceneLyr JSON")
    validate.add_argument("scene")
    compile_cmd = commands.add_parser("compile", help="render SVG, inspector HTML and PPTX")
    compile_cmd.add_argument("scene"); compile_cmd.add_argument("output_dir", nargs="?", default="artifacts")
    pixel = commands.add_parser("import-pixels", help="recover diagram objects using offline pixel rules")
    pixel.add_argument("image"); pixel.add_argument("output", nargs="?"); pixel.add_argument("--scene-id")
    serve = commands.add_parser("serve", help="run optional FastAPI HTTP adapter")
    serve.add_argument("--host", default="127.0.0.1"); serve.add_argument("--port", type=int, default=8000)
    commands.add_parser("mcp", help="run direct Python MCP server over stdio")
    commands.add_parser("capabilities", help="show honest deterministic coverage and limits")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        scene = _scene(args.scene); print(json.dumps({"valid": True, "id": scene.id}, indent=2))
    elif args.command == "compile":
        scene, root = _scene(args.scene), Path(args.output_dir)
        name = Path(args.scene).name.removesuffix(".json").removesuffix(".scene")
        compile_scene(scene, svg_path=root / f"{name}.svg", html_path=root / f"{name}.html", pptx_path=root / f"{name}.pptx")
        print(json.dumps({"scene": scene.id, "output": str(root)}, indent=2))
    elif args.command == "import-pixels":
        scene = extract_pixels(args.image, scene_id=args.scene_id)
        output = Path(args.output or f"{args.image}.scene.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(scene.to_dict(), indent=2), encoding="utf-8")
        print(json.dumps({"scene": scene.id, "objects": len(scene.nodes), "connections": len(scene.edges), "output": str(output)}, indent=2))
    elif args.command == "serve":
        import uvicorn
        uvicorn.run("scenelyr.api:app", host=args.host, port=args.port)
    elif args.command == "mcp":
        from .mcp_server import main as mcp_main
        mcp_main()
    elif args.command == "capabilities":
        print(json.dumps({"modelUsed": False, "works": ["strict scene JSON", "deterministic layout", "SVG/HTML/PPTX",
              "outlined and filled flowchart objects", "simple connectors", "limited geometric arrow inference"],
              "requiresReview": ["text/OCR", "semantic object meaning", "crossings and branches", "photos", "handwriting"]}, indent=2))


if __name__ == "__main__":
    main()

