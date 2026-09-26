"""Local workspace transport: bounded jobs, previews and MCP-backed semantics."""
from __future__ import annotations

import copy
import json
import secrets
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from . import mcp_server as engine
from .auth import auth
from .commands import HELP, MUTATIONS, execute, parse, revision
from .compiler import compile_scene
from .codex_bridge import list_codex_models, run_codex
from .models import SemanticScene
from .progress import observer
from .storage import data_root, list_imports, load_import

router = APIRouter(prefix='/workspace')
lock = threading.RLock()
job_lock = threading.RLock()
pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='scenelyr')
jobs: dict[str, dict] = {}
previews: dict[str, dict] = {}
STAGES = ['upload', 'objects', 'text', 'routes', 'arrowheads', 'junctions', 'saved']
MAX_UPLOAD = 25 * 1024 * 1024


def safe_id(scene_id: str) -> str:
    if not scene_id or scene_id in {'.', '..'} or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for c in scene_id):
        raise HTTPException(400, 'Invalid scene identifier.')
    return scene_id


def get_scene(scene_id: str) -> SemanticScene:
    safe_id(scene_id)
    # Disk is authoritative across independent MCP processes. Invalidate stale local undo.
    disk = load_import(scene_id)
    try:
        current = engine.store.get(scene_id)
    except KeyError:
        current = None
    if disk is not None and (current is None or revision(disk) != revision(current)):
        engine.store.replace(disk)
        current = disk
    if current is None:
        raise HTTPException(404, 'Scene not found. Choose another scene or import an image.')
    return current


def payload(scene: SemanticScene) -> dict:
    compiled = compile_scene(scene)
    nodes = []
    for node in scene.nodes:
        item = node.model_dump(by_alias=True, exclude_none=True)
        base = f'/ui/scenes/{quote(scene.id, safe="")}/objects/{quote(node.id, safe="")}'
        item.update({'cropUrl': base+'/crop' if node.metadata.get('cropPath') else None,
                     'recordUrl': base+'/record', 'layerUrl': base+'/layer'})
        nodes.append(item)
    return {'id': scene.id, 'title': (scene.intent.title if scene.intent else None) or scene.metadata.get('originalFilename') or scene.id,
            'revision': revision(scene), 'scene': scene.to_dict(), 'nodes': nodes,
            'svg': compiled.svg, 'history': engine.store.history(scene.id),
            'sourceUrl': f'/workspace/scenes/{scene.id}/source' if scene.metadata.get('sourceImage') else None}


def fail(error: Exception) -> HTTPException:
    if isinstance(error, HTTPException):
        return error
    if isinstance(error, (ValueError, KeyError, StopIteration)):
        return HTTPException(422, str(error) or 'The selected item no longer exists.')
    return HTTPException(500, 'The local operation failed. Your scene remains available; retry or reopen it.')


@router.get('/account')
def account():
    return auth.account()


@router.get('/models')
def models():
    try:
        items = list_codex_models()
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error
    return {'models': [{
        'id': item.get('model') or item.get('id'),
        'name': item.get('displayName') or item.get('model') or item.get('id'),
        'defaultEffort': item.get('defaultReasoningEffort'),
        'efforts': [value.get('reasoningEffort') for value in item.get('supportedReasoningEfforts', [])
                    if value.get('reasoningEffort')],
        'isDefault': bool(item.get('isDefault')),
    } for item in items if item.get('model') or item.get('id')]}


@router.post('/account/login')
def login():
    try:
        return auth.start_login()
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get('/history')
def history():
    return {'scenes': [{'id': row['id'], 'title': row.get('filename') or row['id'],
                        'objects': row['objects'], 'connections': row['connections'], 'modified': row['modified']}
                       for row in list_imports()]}


@router.get('/scenes/{scene_id}')
def scene(scene_id: str):
    with lock:
        return payload(get_scene(scene_id))


@router.get('/scenes/{scene_id}/source')
def source(scene_id: str):
    with lock:
        value = get_scene(scene_id).metadata.get('sourceImage')
    target = Path(value or '')
    try:
        target.resolve().relative_to((data_root() / 'imports' / scene_id).resolve())
    except ValueError:
        raise HTTPException(404, 'Source image is unavailable.')
    if not target.is_file():
        raise HTTPException(404, 'Source image is unavailable.')
    return FileResponse(target)


@router.get('/scenes/{scene_id}/debug')
def debug(scene_id: str):
    with lock:
        get_scene(scene_id)
    root = data_root() / 'imports' / scene_id / 'debug'
    return {'files': [{'name': p.name, 'url': f'/workspace/scenes/{scene_id}/debug/{quote(p.name)}'}
                      for p in sorted(root.glob('*.png')) if not p.name.startswith('._')]}


@router.get('/scenes/{scene_id}/debug/{name}')
def debug_file(scene_id: str, name: str):
    safe_id(scene_id)
    if Path(name).name != name or not name.endswith('.png'):
        raise HTTPException(404, 'Debug image not found.')
    target = data_root() / 'imports' / scene_id / 'debug' / name
    if not target.is_file():
        raise HTTPException(404, 'Debug image not found.')
    return FileResponse(target)


def new_job(kind: str) -> tuple[str, dict]:
    with job_lock:
        now = time.monotonic()
        for key in list(jobs):
            if jobs[key]['state'] in {'complete', 'failed'} and now-jobs[key]['created'] > 3600:
                del jobs[key]
        if sum(j['state'] == 'running' for j in jobs.values()) >= 2:
            raise HTTPException(429, 'Two local operations are already running. Wait for one to finish.')
        if len(jobs) >= 100:
            finished = next((k for k, v in jobs.items() if v['state'] != 'running'), None)
            if finished:
                del jobs[finished]
        key = secrets.token_urlsafe(20)
        job = {'id': key, 'kind': kind, 'state': 'running', 'created': now, 'events': [], 'partial': []}
        jobs[key] = job
        return key, job


def event(job: dict, value: dict):
    with job_lock:
        value = copy.deepcopy(value)
        if 'nodes' in value:
            job['partial'] = value.pop('nodes')
        job['events'].append(value)
        job['stage'] = value.get('stage')


def import_job(job: dict, content: bytes, filename: str):
    token = observer.set(lambda value: event(job, value))
    try:
        # New imports have unique IDs so re-uploading never overwrites edited scenes.
        scene_id = 'scene-' + secrets.token_hex(8)
        with tempfile.TemporaryDirectory(prefix='scenelyr-') as directory:
            path = Path(directory) / (Path(filename).name or 'image.png')
            path.write_bytes(content)
            imported = SemanticScene.model_validate_json(engine.import_pixels(str(path), scene_id))
        with job_lock:
            job.update(state='complete', scene_id=imported.id)
    except Exception as error:
        with job_lock:
            job.update(state='failed', error=fail(error).detail)
    finally:
        observer.reset(token)


@router.post('/imports', status_code=202)
async def start_import(image: Annotated[UploadFile, File()]):
    if image.content_type not in {'image/png', 'image/jpeg', 'image/webp', 'image/bmp', 'application/octet-stream'}:
        raise HTTPException(415, 'Choose a PNG, JPG, WebP or BMP image.')
    content = await image.read(MAX_UPLOAD+1)
    await image.close()
    if not content or len(content) > MAX_UPLOAD:
        raise HTTPException(413, 'Choose a nonempty image smaller than 25 MB.')
    key, job = new_job('import')
    event(job, {'stage': 'upload', 'state': 'complete', 'bytes': len(content)})
    pool.submit(import_job, job, content, image.filename or 'image.png')
    return {'job': key, 'stages': STAGES}


@router.get('/jobs/{job_id}')
def job_status(job_id: str):
    with job_lock:
        job = copy.deepcopy(jobs.get(job_id))
    if not job:
        raise HTTPException(404, 'This operation expired. Reopen the saved scene or retry.')
    job.pop('created', None)
    return job


class CommandRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    selected: str | None = None
    model: str | None = Field(default=None, max_length=100, pattern=r'^[A-Za-z0-9._-]+$')
    effort: str | None = Field(default=None, max_length=30, pattern=r'^[A-Za-z0-9_-]+$')


@router.post('/scenes/{scene_id}/agent')
def agent_command(scene_id: str, request: CommandRequest):
    """Start a visible Codex job using the configured SceneLyr MCP tools."""
    safe_id(scene_id)
    with lock:
        get_scene(scene_id)
    key, job = new_job('agent')
    event(job, {'stage': 'queued', 'state': 'complete', 'message': 'Request queued for Codex.'})
    pool.submit(agent_job, job, scene_id, request.message, request.selected, request.model, request.effort)
    return {'type': 'job', 'kind': 'agent', 'job': key, 'summary': 'Codex request started.'}


def agent_job(job: dict, scene_id: str, message: str, selected: str | None,
              model: str | None, effort: str | None):
    try:
        result = run_codex(scene_id, message, selected, lambda value: event(job, value), model, effort)
        with lock:
            updated = payload(get_scene(scene_id))
        with job_lock:
            job.update(state='complete', result={"type": "agent", **result, "scene": updated})
    except Exception as error:
        with job_lock:
            job.update(state='failed', error=str(error) or 'Codex could not complete this request.')


@router.post('/scenes/{scene_id}/commands')
def command(scene_id: str, request: CommandRequest):
    parsed = None
    with lock:
        try:
            scene = get_scene(scene_id)
            parsed = parse(scene, request.message, request.selected)
            if parsed.tool in MUTATIONS:
                now = time.monotonic()
                for key in list(previews):
                    if now-previews[key]['created'] > 600:
                        del previews[key]
                if len(previews) >= 200:
                    del previews[next(iter(previews))]
                token = secrets.token_urlsafe(24)
                previews[token] = {'created': now, 'revision': revision(scene), 'command': parsed}
                return {'type': 'preview', 'token': token, 'tool': parsed.tool,
                        'summary': parsed.summary, 'revision': revision(scene)}
            if parsed.tool == 'export':
                return {'type': 'download', 'summary': parsed.summary,
                        'url': f'/ui/export/{scene_id}/{parsed.arguments["kind"]}'}
            if parsed.tool == 'validate':
                return start_validation()
            result = execute(parsed)
            return {'type': 'result', 'tool': parsed.tool, 'summary': 'Scene rendered.' if parsed.tool == 'render_scene' else
                    f'{len(scene.nodes)} objects, {len(scene.edges)} connections. ' + ' '.join(scene.metadata.get('warnings', [])),
                    'scene': payload(scene)}
        except ValueError as error:
            if not str(error).startswith('This local command was not recognized.'):
                raise fail(error) from error
        except Exception as error:
            raise fail(error) from error
    # Natural language intentionally leaves the deterministic parser and runs
    # without holding the shared scene lock during a model turn.
    return agent_command(scene_id, request)


@router.delete('/previews/{token}')
def discard(token: str):
    with lock:
        previews.pop(token, None)
    return {'discarded': True}


@router.post('/previews/{token}/apply')
def apply(token: str):
    with lock:
        preview = previews.get(token)
        if not preview or time.monotonic()-preview['created'] > 600:
            raise HTTPException(410, 'Preview expired. Send the command again.')
        command = preview['command']
        scene = get_scene(command.arguments['scene_id'])
        if revision(scene) != preview['revision']:
            previews.pop(token, None)
            raise HTTPException(409, 'The scene changed after this preview. Send the command again to review the latest version.')
        try:
            result = execute(command)
            updated = SemanticScene.model_validate_json(result)
            previews.pop(token, None)
            return {'type': 'result', 'tool': command.tool, 'summary': command.summary + ' — saved locally.', 'scene': payload(updated)}
        except Exception as error:
            raise fail(error) from error


def validation_job(job: dict):
    try:
        result = json.loads(engine.run_release_validation(str(data_root()/'release-validation')))
        with job_lock:
            job.update(state='complete', summary=result['summary'], passed=result['passed'], reportUrl='/ui/release-validation/report')
    except Exception as error:
        with job_lock:
            job.update(state='failed', error=fail(error).detail)


@router.post('/validation', status_code=202)
def start_validation():
    with job_lock:
        existing = next((j for j in jobs.values() if j['kind'] == 'validation' and j['state'] == 'running'), None)
        if existing:
            return {'type': 'job', 'job': existing['id'], 'summary': 'Release validation is running.'}
        key, job = new_job('validation')
    pool.submit(validation_job, job)
    return {'type': 'job', 'job': key, 'summary': 'Release validation started.'}


async def local_guard(request: Request, call_next):
    # No CORS. Browser writes must originate here; CLI clients may omit Origin.
    host = request.url.hostname
    if host not in {'127.0.0.1', 'localhost', '::1', 'testserver'}:
        return JSONResponse({'detail': 'SceneLyr serves local workspaces only.'}, status_code=403)
    origin = request.headers.get('origin')
    if origin and (urlsplit(origin).netloc != request.url.netloc or urlsplit(origin).scheme != request.url.scheme):
        return JSONResponse({'detail': 'Cross-origin access is not allowed.'}, status_code=403)
    if request.headers.get('sec-fetch-site') == 'cross-site':
        return JSONResponse({'detail': 'Cross-site access is not allowed.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    if request.url.path == '/':
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response
