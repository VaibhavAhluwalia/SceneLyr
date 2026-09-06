"""Optional HTTP adapter. The core works without a web server."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from .compiler import compile_scene
from .models import SemanticScene
from .pixels import extract_pixels
from .storage import data_root, list_imports, load_import, persist_import, save_scene
from .store import SceneStore

app = FastAPI(title="SceneLyr", version="0.1.0")
store = SceneStore()
ui_scenes: dict[str, SemanticScene] = {}

UI = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SceneLyr</title><style>
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#172033;background:#f4f6fb}*{box-sizing:border-box}body{margin:0}.shell{max-width:1800px;margin:auto;padding:32px 22px 60px}header{display:flex;align-items:center;justify-content:space-between;margin-bottom:26px}.brand{font-weight:800;font-size:25px}.badge{font-size:12px;background:#e8f7ef;color:#197046;padding:7px 11px;border-radius:999px}.card{background:white;border:1px solid #e1e6f0;border-radius:20px;box-shadow:0 12px 40px rgba(25,40,75,.08)}.drop{padding:54px 24px;text-align:center;border:2px dashed #aebbd4;margin:0;border-radius:20px;transition:.15s}.drop.over{border-color:#5b66e8;background:#f5f5ff}.drop h1{font-size:27px;margin:0 0 8px}.drop p{color:#69758c;margin:0 0 22px}.button{display:inline-block;border:0;border-radius:12px;background:#4f5bd5;color:white;font-weight:700;padding:12px 18px;cursor:pointer;text-decoration:none}.button.secondary{background:#eef0ff;color:#404ab5}.button.tiny{padding:7px 9px;font-size:11px}.small{font-size:12px;color:#7b8598;margin-top:15px}#file{display:none}.status{display:none;padding:17px 20px;margin-top:18px}.status.show{display:block}.result{display:none;margin-top:22px;grid-template-columns:minmax(0,1fr) 420px;gap:20px}.result.show{display:grid}.preview{padding:18px;min-height:420px;display:flex;align-items:center;justify-content:center;overflow:auto}.preview svg{max-width:100%;height:auto}.side{padding:20px}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}.metric{background:#f5f7fb;border-radius:12px;padding:12px}.metric b{font-size:24px;display:block}.metric span{font-size:12px;color:#69758c}.warn{background:#fff8e7;color:#765714;padding:11px;border-radius:10px;font-size:12px;margin:8px 0}.saved{background:#eaf8f0;color:#176640;padding:11px;border-radius:10px;font-size:12px;overflow-wrap:anywhere}.downloads{display:grid;gap:8px;margin-top:16px}.downloads a{text-align:center}.objects{margin-top:20px}.object{border:1px solid #e1e6f0;border-radius:10px;padding:10px;margin:8px 0;font-size:12px}.object b{display:block;font-size:13px;margin-bottom:5px}.object code{color:#59657b;display:block;margin:5px 0}.object-head{display:grid;grid-template-columns:74px 1fr;gap:10px;align-items:center}.object-crop{width:74px;height:58px;object-fit:contain;background:#f5f7fb;border:1px solid #e1e6f0;border-radius:8px}.asset-links{display:flex;gap:10px;margin-top:7px}.asset-links a{color:#404ab5;font-weight:700;text-decoration:none}.editrow{display:flex;gap:6px}.editrow input,.editrow select{min-width:0;flex:1;border:1px solid #cfd6e4;border-radius:8px;padding:7px;background:white}.confidence{color:#197046;font-weight:600}.json{max-height:260px;overflow:auto;background:#172033;color:#dbe4f5;border-radius:10px;padding:10px;font-size:10px;white-space:pre-wrap}details summary{cursor:pointer;font-weight:700;margin:12px 0}.error{color:#9b1c31;background:#fff0f2}@media(max-width:780px){.result.show{grid-template-columns:1fr}.shell{padding:18px 12px}.drop{padding:38px 16px}}
</style></head><body><div class="shell"><header><div class="brand">SceneLyr</div><div class="badge">Local OCR · no cloud</div></header>
<section class="card" style="padding:18px;margin-bottom:20px"><h2>Saved library</h2><p id="libraryLocation" class="small"></p><div id="library">Loading saved scenes…</div></section>
<section id="drop" class="drop card"><h1>Turn a diagram into editable objects</h1><p>Drop a PNG, JPG or WebP here. SceneLyr analyzes it locally on this Mac.</p><label class="button" for="file">Choose an image</label><input id="file" type="file" accept="image/png,image/jpeg,image/webp,image/bmp"><div class="small">Best for clean flowcharts and architecture diagrams · maximum 25 MB</div></section>
<section id="status" class="status card">Analyzing pixels…</section>
<section id="result" class="result"><div id="preview" class="preview card"></div><aside class="side card"><h2 style="margin:0">Result</h2><div class="metrics"><div class="metric"><b id="objects">0</b><span>objects</span></div><div class="metric"><b id="connections">0</b><span>connections</span></div></div><div id="saved" class="saved"></div><div id="warnings"></div><div class="objects"><h3>Extracted objects</h3><div id="objectList"></div><h3>Connections</h3><div id="edgeList"></div><details><summary>Inspect complete JSON</summary><pre id="rawJson" class="json"></pre></details></div><div class="downloads"><a id="json" class="button" href="#">Download objects (JSON)</a><a id="pptx" class="button secondary" href="#">Download editable PowerPoint</a><a id="svg" class="button secondary" href="#">Download SVG</a><a id="html" class="button secondary" href="#">Download inspector</a></div></aside></section>
</div><script>
const drop=document.getElementById('drop'),input=document.getElementById('file'),status=document.getElementById('status'),result=document.getElementById('result');
function setStatus(text,error=false){status.textContent=text;status.className='status card show'+(error?' error':'')}
let current=null;
async function loadLibrary(){try{const response=await fetch('/ui/history');if(!response.ok)throw new Error('Could not load saved scenes');const data=await response.json();document.getElementById('libraryLocation').textContent='Stored on this computer: '+data.dataFolder;const list=document.getElementById('library');list.replaceChildren();for(const item of data.imports){const b=document.createElement('button');b.className='button secondary';b.style='margin:4px';b.textContent=(item.filename||item.id)+' · '+item.objects+' layers · '+item.connections+' connections';b.title=item.folder;b.onclick=()=>request('/ui/scenes/'+encodeURIComponent(item.id),{}).catch(e=>setStatus(e.message,true));list.append(b)}if(!data.imports.length)list.textContent='No saved diagrams yet.'}catch(e){document.getElementById('library').textContent=e.message}}
loadLibrary();const requested=new URLSearchParams(location.search).get('scene');if(requested)request('/ui/scenes/'+encodeURIComponent(requested),{}).catch(e=>setStatus(e.message,true));

function renderResult(body){current=body;status.classList.remove('show');result.classList.add('show');document.getElementById('preview').innerHTML='';const frame=document.createElement('iframe');frame.title='Scene layers and assets';frame.style='width:100%;height:780px;border:0';frame.srcdoc=body.inspector;document.getElementById('preview').append(frame);loadLibrary();document.getElementById('objects').textContent=body.objects;document.getElementById('connections').textContent=body.connections;document.getElementById('saved').textContent='Saved locally: '+body.folder;document.getElementById('warnings').innerHTML=body.warnings.map(x=>`<div class="warn">${escapeHtml(x)}</div>`).join('');document.getElementById('objectList').innerHTML=body.nodes.map(n=>`<div class="object" data-node="${escapeHtml(n.id)}"><div class="object-head">${n.cropUrl?`<img class="object-crop" src="${escapeHtml(n.cropUrl)}" alt="Original crop for ${escapeHtml(n.label)}">`:'<div class="object-crop"></div>'}<div><b>${escapeHtml(n.shape)} ${n.confidence!=null?`<span class="confidence">· OCR ${Math.round(n.confidence*100)}%</span>`:''}</b><div class="editrow"><input aria-label="Label for ${escapeHtml(n.id)}" value="${escapeHtml(n.label)}"><button class="button tiny save-node">Save</button></div></div></div><code>${escapeHtml(n.id)} · bounds [${n.bounds.join(', ')}]</code><div class="asset-links"><a href="${escapeHtml(n.recordUrl)}" target="_blank">Object JSON</a><a href="${escapeHtml(n.layerUrl)}" target="_blank">SVG layer</a>${n.cropUrl?`<a href="${escapeHtml(n.cropUrl)}" target="_blank">Crop</a>`:''}</div></div>`).join('')||'<div class="warn">No supported objects were detected.</div>';const options=body.nodes.map(n=>`<option value="${escapeHtml(n.id)}">${escapeHtml(n.label)}</option>`).join('');document.getElementById('edgeList').innerHTML=body.edges.map(e=>`<div class="object" data-edge="${escapeHtml(e.id)}"><b>${escapeHtml(e.from)} → ${escapeHtml(e.to)}</b><div class="editrow"><select class="edge-from">${options}</select><select class="edge-to">${options}</select><button class="button tiny save-edge">Save</button></div><div class="editrow" style="margin-top:6px"><input class="edge-label" placeholder="Arrow label" value="${escapeHtml(e.label||'')}"><button class="button tiny reverse-edge">Reverse</button></div><code>${escapeHtml(e.id)} · ${escapeHtml(e.direction)}</code></div>`).join('')||'<div class="small">No connections detected.</div>';body.edges.forEach(e=>{const el=document.querySelector(`[data-edge="${CSS.escape(e.id)}"]`);el.querySelector('.edge-from').value=e.from;el.querySelector('.edge-to').value=e.to});document.getElementById('rawJson').textContent=JSON.stringify(body.scene,null,2);for(const kind of ['json','pptx','svg','html'])document.getElementById(kind).href=`/ui/export/${encodeURIComponent(body.id)}/${kind}`;}
async function request(url,options){setStatus('Saving your edit locally…');const response=await fetch(url,options);const body=await response.json();if(!response.ok)throw new Error(body.detail||'Edit failed');renderResult(body)}
async function run(file){if(!file)return;if(file.size>25*1024*1024){setStatus('That image is larger than 25 MB.',true);return}setStatus('Detecting objects, reading text and saving locally…');result.classList.remove('show');const data=new FormData();data.append('image',file);try{const response=await fetch('/ui/import',{method:'POST',body:data});const body=await response.json();if(!response.ok)throw new Error(body.detail||'Import failed');renderResult(body)}catch(error){setStatus(error.message,true)}}
document.getElementById('objectList').addEventListener('click',async event=>{if(!event.target.classList.contains('save-node'))return;const row=event.target.closest('[data-node]');try{await request(`/ui/scenes/${encodeURIComponent(current.id)}/nodes/${encodeURIComponent(row.dataset.node)}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({label:row.querySelector('input').value})})}catch(error){setStatus(error.message,true)}});
document.getElementById('edgeList').addEventListener('click',async event=>{const row=event.target.closest('[data-edge]');if(!row)return;try{if(event.target.classList.contains('reverse-edge'))await request(`/ui/scenes/${encodeURIComponent(current.id)}/edges/${encodeURIComponent(row.dataset.edge)}/reverse`,{method:'POST'});if(event.target.classList.contains('save-edge'))await request(`/ui/scenes/${encodeURIComponent(current.id)}/edges/${encodeURIComponent(row.dataset.edge)}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({from_id:row.querySelector('.edge-from').value,to_id:row.querySelector('.edge-to').value,label:row.querySelector('.edge-label').value})})}catch(error){setStatus(error.message,true)}});
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}input.addEventListener('change',()=>run(input.files[0]));for(const name of ['dragenter','dragover'])drop.addEventListener(name,e=>{e.preventDefault();drop.classList.add('over')});for(const name of ['dragleave','drop'])drop.addEventListener(name,e=>{e.preventDefault();drop.classList.remove('over')});drop.addEventListener('drop',e=>run(e.dataTransfer.files[0]));
</script></body></html>'''


class PixelImportRequest(BaseModel):
    path: str
    scene_id: str | None = None


class NodeEdit(BaseModel):
    label: str
    kind: str | None = None


class EdgeEdit(BaseModel):
    from_id: str | None = None
    to_id: str | None = None
    label: str | None = None


def _ui_payload(scene: SemanticScene) -> dict:
    compiled = compile_scene(scene)
    return {"id": scene.id, "objects": len(scene.nodes), "connections": len(scene.edges),
            "warnings": scene.metadata.get("warnings", []), "svg": compiled.svg, "inspector": compiled.html,
            "folder": str(data_root() / "imports" / scene.id), "scene": scene.to_dict(),
            "nodes": [{"id": node.id, "label": node.label, "kind": node.kind,
                       "shape": node.metadata.get("shape", "unknown"),
                       "confidence": node.metadata.get("ocrConfidence"),
                       "bounds": node.metadata.get("sourceBounds", []),
                       "cropUrl": f"/ui/scenes/{scene.id}/objects/{node.id}/crop" if node.metadata.get("cropPath") else None,
                       "recordUrl": f"/ui/scenes/{scene.id}/objects/{node.id}/record",
                       "layerUrl": f"/ui/scenes/{scene.id}/objects/{node.id}/layer"} for node in scene.nodes],
            "edges": [{"id": edge.id, "from": edge.from_, "to": edge.to, "label": edge.label,
                       "direction": edge.metadata.get("direction", "unknown")} for edge in scene.edges]}


@app.get("/", response_class=HTMLResponse)
def user_interface() -> str:
    return UI


@app.get("/ui/history")
def ui_history() -> dict:
    return {"dataFolder": str(data_root()), "imports": list_imports()}


@app.post("/ui/import")
async def ui_import(image: Annotated[UploadFile, File()]) -> dict:
    if image.content_type not in {"image/png", "image/jpeg", "image/webp", "image/bmp", "application/octet-stream"}:
        raise HTTPException(415, "Please choose a PNG, JPG, WebP or BMP image.")
    content = await image.read(25 * 1024 * 1024 + 1)
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(413, "Image is larger than 25 MB.")
    suffix = Path(image.filename or "image.png").suffix or ".png"
    temporary = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    path = Path(temporary.name)
    try:
        temporary.write(content); temporary.close()
        scene = extract_pixels(path)
        paths = persist_import(scene, content, image.filename or "uploaded-image.png")
        ui_scenes[scene.id] = scene
        return _ui_payload(scene)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    finally:
        temporary.close()
        path.unlink(missing_ok=True)


def _editable_scene(scene_id: str) -> SemanticScene:
    scene = ui_scenes.get(scene_id) or load_import(scene_id)
    if not scene:
        raise HTTPException(404, "Scene was not found.")
    return scene


@app.get("/ui/scenes/{scene_id}")
def ui_open_scene(scene_id: str) -> dict:
    scene = load_import(scene_id)
    if scene is None:
        raise HTTPException(404, "Saved scene was not found.")
    ui_scenes[scene_id] = scene
    return _ui_payload(scene)


@app.get("/ui/scenes/{scene_id}/objects/{node_id}/{kind}")
def ui_object_asset(scene_id: str, node_id: str, kind: str):
    scene = _editable_scene(scene_id)
    node = next((item for item in scene.nodes if item.id == node_id), None)
    if not node:
        raise HTTPException(404, "Object was not found.")
    metadata_key = {"crop": "cropPath", "record": "objectRecordPath", "layer": "assetPath"}.get(kind)
    if not metadata_key:
        raise HTTPException(404, "Unknown object asset type.")
    target = Path(node.metadata.get(metadata_key, ""))
    object_root = data_root() / "imports" / scene.id / "assets" / "objects"
    try:
        target.resolve().relative_to(object_root.resolve())
    except (ValueError, OSError):
        raise HTTPException(404, "Object asset was not found.")
    if not target.is_file():
        raise HTTPException(404, "Object asset was not found.")
    media_type = {"crop": "image/png", "record": "application/json", "layer": "image/svg+xml"}[kind]
    return FileResponse(target, media_type=media_type)


@app.patch("/ui/scenes/{scene_id}/nodes/{node_id}")
def ui_edit_node(scene_id: str, node_id: str, edit: NodeEdit) -> dict:
    scene = _editable_scene(scene_id)
    data = scene.to_dict()
    node = next((item for item in data["nodes"] if item["id"] == node_id), None)
    if not node:
        raise HTTPException(404, "Object was not found.")
    node["label"] = edit.label.strip() or node["label"]
    if edit.kind:
        node["kind"] = edit.kind
    node.setdefault("metadata", {})["labelStatus"] = "user-edited"
    try:
        updated = SemanticScene.model_validate(data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    ui_scenes[scene_id] = updated
    save_scene(updated)
    return _ui_payload(updated)


@app.patch("/ui/scenes/{scene_id}/edges/{edge_id}")
def ui_edit_edge(scene_id: str, edge_id: str, edit: EdgeEdit) -> dict:
    scene = _editable_scene(scene_id)
    data = scene.to_dict()
    edge = next((item for item in data["edges"] if item.get("id") == edge_id), None)
    if not edge:
        raise HTTPException(404, "Connection was not found.")
    if edit.from_id:
        edge["from"] = edit.from_id
    if edit.to_id:
        edge["to"] = edit.to_id
    if edit.label is not None:
        edge["label"] = edit.label.strip() or None
    edge.setdefault("metadata", {})["direction"] = "user-edited"
    try:
        updated = SemanticScene.model_validate(data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    ui_scenes[scene_id] = updated
    save_scene(updated)
    return _ui_payload(updated)


@app.post("/ui/scenes/{scene_id}/edges/{edge_id}/reverse")
def ui_reverse_edge(scene_id: str, edge_id: str) -> dict:
    scene = _editable_scene(scene_id)
    data = scene.to_dict()
    edge = next((item for item in data["edges"] if item.get("id") == edge_id), None)
    if not edge:
        raise HTTPException(404, "Connection was not found.")
    edge["from"], edge["to"] = edge["to"], edge["from"]
    edge.setdefault("metadata", {})["direction"] = "user-reversed"
    updated = SemanticScene.model_validate(data)
    ui_scenes[scene_id] = updated
    save_scene(updated)
    return _ui_payload(updated)


@app.get("/ui/export/{scene_id}/{kind}")
def ui_export(scene_id: str, kind: str):
    scene = ui_scenes.get(scene_id) or load_import(scene_id)
    if not scene:
        raise HTTPException(404, "Result is no longer available. Import the image again.")
    if kind == "json":
        return Response(json.dumps(scene.to_dict(), indent=2), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{scene.id}.scene.json"'})
    compiled = compile_scene(scene)
    if kind == "svg":
        return Response(compiled.svg, media_type="image/svg+xml",
                        headers={"Content-Disposition": f'attachment; filename="{scene.id}.svg"'})
    if kind == "html":
        return Response(compiled.html, media_type="text/html",
                        headers={"Content-Disposition": f'attachment; filename="{scene.id}.html"'})
    if kind == "pptx":
        target = data_root() / "imports" / scene.id / "editable.pptx"
        if not target.exists():
            compile_scene(scene, pptx_path=target)
        return FileResponse(target, filename=f"{scene.id}.pptx",
                            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
    raise HTTPException(404, "Unknown export type.")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "engine": "python", "deterministic": True}


@app.get("/capabilities")
def capabilities() -> dict:
    return {
        "modelRequired": False,
        "supported": ["scene validation", "layered layout", "SVG", "HTML inspector", "editable PPTX",
                      "offline rectangle/ellipse/diamond/filled-shape detection", "simple connector recovery"],
        "reviewRequired": ["OCR/text", "ambiguous arrow direction", "branches/crossings", "photos", "hand-drawn diagrams"],
    }


@app.post("/scenes", response_model=SemanticScene)
def create_scene(scene: SemanticScene) -> SemanticScene:
    try:
        return store.create(scene)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.get("/scenes", response_model=list[SemanticScene])
def list_scenes() -> list[SemanticScene]:
    return store.list()


@app.get("/scenes/{scene_id}", response_model=SemanticScene)
def get_scene(scene_id: str) -> SemanticScene:
    try:
        return store.get(scene_id)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error


@app.post("/import/pixels", response_model=SemanticScene)
def import_pixels(request: PixelImportRequest) -> SemanticScene:
    try:
        path = Path(request.path)
        scene = extract_pixels(path, scene_id=request.scene_id)
        return store.create(scene)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.get("/scenes/{scene_id}/svg")
def scene_svg(scene_id: str) -> Response:
    try:
        return Response(compile_scene(store.get(scene_id)).svg, media_type="image/svg+xml")
    except KeyError as error:
        raise HTTPException(404, str(error)) from error


@app.get("/scenes/{scene_id}/inspect", response_class=HTMLResponse)
def scene_inspector(scene_id: str) -> str:
    try:
        return compile_scene(store.get(scene_id)).html
    except KeyError as error:
        raise HTTPException(404, str(error)) from error
