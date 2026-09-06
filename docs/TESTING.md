# Testing SceneLyr

## Requirements

- Node.js 20+
- npm

## One-command verification

```bash
npm install
npm run check
npm run smoke
```

`npm run smoke` exercises every phase and writes temporary SVG, HTML and PPTX artifacts.

## Generate the reference architecture

```bash
npm run example
```

Outputs:

- `artifacts/swiggy.svg`
- `artifacts/swiggy.html`
- `artifacts/swiggy.pptx`

Open the HTML file to inspect semantic nodes interactively. Open the PPTX in PowerPoint, Keynote, LibreOffice Impress, or Google Slides import to verify native editability.

## CLI

```bash
npm run cli -- compile examples/swiggy.scene.json artifacts
npm run cli -- import-image ./diagram.png ./diagram.scene.json
```

Without a vision endpoint, image import creates a safe whole-image semantic node. For real visual decomposition, point SceneLyr at an OpenAI-compatible multimodal chat-completions endpoint:

```bash
export SCENELYR_VISION_ENDPOINT="https://your-provider/v1/chat/completions"
export SCENELYR_VISION_MODEL="your-vision-model"
export SCENELYR_VISION_API_KEY="..."   # optional for local endpoints
npm run cli -- import-image ./diagram.png
```

## MCP

Start the stdio server:

```bash
npm run mcp
```

For MCP Inspector:

```bash
npx @modelcontextprotocol/inspector npm run mcp
```

The key test is that the agent creates and edits a scene with semantic calls only. It should never need to provide coordinates.

Suggested manual sequence:

1. `create_scene` with id `demo`.
2. `add_node` for Customer, App, API Gateway, Order Service and PostgreSQL.
3. `add_relationship` between them.
4. `render_scene`.
5. `update_node` to rename or emphasize a service.
6. `render_scene` again.
7. `export_scene` with PPTX enabled.

## CI

The GitHub Actions workflow runs type checking, unit tests, and the complete smoke test on every pull request and push to `main`.
