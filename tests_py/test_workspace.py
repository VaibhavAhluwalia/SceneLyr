import json
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from scenelyr.api import app
from scenelyr import mcp_server as engine
from scenelyr import workspace
from scenelyr.commands import parse
from scenelyr.models import SemanticScene
from scenelyr.storage import load_import, save_scene
from scenelyr.store import SceneStore
from scenelyr.progress import observer
from scenelyr.pixels import extract_pixels


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('SCENELYR_DATA_DIR', str(tmp_path/'data'))
    monkeypatch.setattr(engine, 'store', SceneStore())
    workspace.previews.clear()
    scene = SemanticScene.model_validate({'id':'workspace-test','nodes':[
        {'id':'a','label':'Customer','kind':'actor'},
        {'id':'b','label':'Service','kind':'service'}],
        'edges':[{'id':'ab','from':'a','to':'b'}]})
    save_scene(scene)
    with TestClient(app) as client:
        yield client


def preview(client, message):
    response = client.post('/workspace/scenes/workspace-test/commands', json={'message':message})
    assert response.status_code == 200, response.text
    result=response.json()
    assert result['type']=='preview'
    return result


def apply(client, message):
    result=preview(client,message)
    response=client.post('/workspace/previews/'+result['token']+'/apply')
    assert response.status_code==200,response.text
    return response.json()['scene']


def test_preview_cancel_apply_and_undo_across_reload(client):
    planned=preview(client,'rename Customer to Client')
    assert load_import('workspace-test').nodes[0].label=='Customer'
    assert client.delete('/workspace/previews/'+planned['token']).status_code==200
    assert client.post('/workspace/previews/'+planned['token']+'/apply').status_code==410
    updated=apply(client,'rename Customer to Client')
    assert updated['nodes'][0]['label']=='Client'
    assert updated['history']['canUndo']
    reopened=client.get('/workspace/scenes/workspace-test').json()
    assert reopened['history']['canUndo']
    assert apply(client,'undo')['nodes'][0]['label']=='Customer'
    assert apply(client,'redo')['nodes'][0]['label']=='Client'
    assert client.get('/ui/export/workspace-test/json').json()['nodes'][0]['label']=='Client'


def test_stale_preview_cannot_overwrite_external_edit(client):
    planned=preview(client,'rename Customer to Client')
    external=load_import('workspace-test')
    external.nodes[0].label='External edit';save_scene(external)
    result=client.post('/workspace/previews/'+planned['token']+'/apply')
    assert result.status_code==409
    assert load_import('workspace-test').nodes[0].label=='External edit'
    assert not client.get('/workspace/scenes/workspace-test').json()['history']['canUndo']


def test_expired_preview_and_natural_language_fallback(client, monkeypatch):
    planned=preview(client,'add Cache')
    workspace.previews[planned['token']]['created']-=601
    assert client.post('/workspace/previews/'+planned['token']+'/apply').status_code==410
    monkeypatch.setattr(workspace, 'run_codex', lambda *args: {
        'message':'Codex inspected the request.', 'tools':['inspect_scene'], 'threadId':'thread-test'
    })
    result=client.post('/workspace/scenes/workspace-test/commands',json={'message':'make this beautiful'})
    assert result.status_code==200 and result.json()['type']=='job'
    completed=wait_job(client,result.json()['job'])
    assert completed['result']['type']=='agent'
    assert len(load_import('workspace-test').nodes)==2


def test_natural_language_agent_uses_codex_bridge_and_returns_scene(client, monkeypatch):
    calls = []
    def codex(scene_id, message, selected, report=None):
        calls.append((scene_id, message, selected))
        if report:
            report({'stage':'tool','state':'complete','tool':'inspect_scene','message':'inspect_scene completed.'})
        return {'message':'Inspected with SceneLyr.', 'tools':['inspect_scene'], 'threadId':'thread-test'}
    monkeypatch.setattr(workspace, 'run_codex', codex)
    response = client.post('/workspace/scenes/workspace-test/agent', json={
        'message':'Please understand this diagram', 'selected':'a'
    })
    assert response.status_code == 200
    job = wait_job(client, response.json()['job'])
    result = job['result']
    assert result['type'] == 'agent' and result['tools'] == ['inspect_scene']
    assert result['scene']['id'] == 'workspace-test'
    assert calls == [('workspace-test', 'Please understand this diagram', 'a')]


def test_semantic_commands_use_registered_mcp_tools(client, monkeypatch):
    calls=[]
    original=engine.rename_object
    def renamed(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(engine,'rename_object',renamed)
    apply(client,'rename Customer to Client')
    assert calls==[{'scene_id':'workspace-test','object_id':'a','label':'Client'}]
    apply(client,'add Cache')
    scene=apply(client,'connect Client to Cache')
    assert len(scene['scene']['edges'])==2
    scene=apply(client,'reverse ab')
    assert scene['scene']['edges'][0]['from']=='b'
    scene=apply(client,'reconnect ab from Cache to Service')
    assert scene['scene']['edges'][0]['from']=='cache'
    scene=apply(client,'remove ab')
    assert len(scene['scene']['edges'])==1
    scene=apply(client,'remove Cache')
    assert len(scene['scene']['nodes'])==2 and not scene['scene']['edges']
    apply(client,'undo')
    assert len(load_import('workspace-test').nodes)==3


def test_ambiguous_names_and_invalid_references_do_not_mutate(client):
    apply(client,'add Customer')
    result=client.post('/workspace/scenes/workspace-test/commands',json={'message':'rename Customer to User'})
    assert result.status_code==422
    result=client.post('/workspace/scenes/workspace-test/commands',json={'message':'connect a to a'})
    assert result.status_code==422
    assert len(load_import('workspace-test').edges)==1


def image_bytes():
    img=np.full((180,420,3),255,np.uint8)
    cv2.rectangle(img,(20,40),(130,140),(0,0,0),2)
    cv2.rectangle(img,(290,40),(400,140),(0,0,0),2)
    cv2.arrowedLine(img,(130,90),(290,90),(0,0,0),2)
    return cv2.imencode('.png',img)[1].tobytes()


def wait_job(client, key):
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        data=client.get('/workspace/jobs/'+key).json()
        if data['state']!='running':return data
        time.sleep(.02)
    pytest.fail('Background job did not finish')


def test_real_import_events_partial_results_and_unique_uploads(client):
    ids=[]
    for _ in range(2):
        result=client.post('/workspace/imports',files={'image':('diagram.png',image_bytes(),'image/png')})
        assert result.status_code==202
        job=wait_job(client,result.json()['job'])
        assert job['state']=='complete',job
        ids.append(job['scene_id'])
        events=job['events']
        assert events[0]=={'stage':'upload','state':'complete','bytes':len(image_bytes())}
        assert {'objects','text','routes','arrowheads','junctions','saved'} <= {e['stage'] for e in events}
        assert len(job['partial'])==2
        assert events[-1]=={'stage':'saved','state':'complete'}
        scene=client.get('/workspace/scenes/'+job['scene_id']).json()
        assert len(scene['nodes'])==2
        assert client.get(scene['sourceUrl']).status_code==200
    assert ids[0]!=ids[1]


def test_failed_import_never_reports_completion(client):
    result=client.post('/workspace/imports',files={'image':('broken.png',b'broken','image/png')})
    job=wait_job(client,result.json()['job'])
    assert job['state']=='failed' and 'scene_id' not in job
    assert not any(e['stage']=='saved' and e['state']=='complete' for e in job['events'])
    assert client.post('/workspace/imports',files={'image':('file.svg',b'<svg/>','image/svg+xml')}).status_code==415


def test_progress_observer_does_not_change_output(tmp_path):
    path=tmp_path/'source.png';path.write_bytes(image_bytes());events=[]
    original=extract_pixels(path,use_ocr=False).to_dict()
    token=observer.set(events.append)
    try: observed=extract_pixels(path,use_ocr=False).to_dict()
    finally:observer.reset(token)
    assert original==observed
    assert any(e['stage']=='text' and e['state']=='unavailable' for e in events)


def test_local_auth_and_cross_origin_protection(client):
    account = client.get('/workspace/account').json()
    assert account['mode'] in {'local', 'codex'}
    assert 'credential' not in json.dumps(account).lower()
    assert client.post('/workspace/account/login').status_code==409
    assert client.post('/workspace/validation',headers={'Origin':'https://evil.example'}).status_code==403
    assert client.get('/workspace/history',headers={'Host':'evil.example'}).status_code==403
    assert client.get('/workspace/history',headers={'Sec-Fetch-Site':'cross-site'}).status_code==403
    assert client.get('/').headers['content-security-policy'].startswith("default-src 'self'")
    assert client.get('/web/workspace.js').status_code==200


def test_storage_rejects_traversal(client):
    from scenelyr.storage import scene_folder
    for value in ['../other','/tmp/other','..','bad/path']:
        with pytest.raises(ValueError):scene_folder(value)


def test_app_server_adapter_projects_safe_fields():
    from scenelyr.app_server_auth import AppServerAuth
    calls=[]
    def request(method, params):
        calls.append((method,params))
        if method=='account/read':
            return {'account':{'type':'chatgpt','email':'private@example.invalid','accessToken':'secret'}}
        return {'authUrl':'https://auth.openai.com/authorize?state=opaque','loginId':'login','accessToken':'secret'}
    adapter=AppServerAuth(request)
    assert adapter.account()=={'mode':'chatgpt','label':'ChatGPT connected','loginAvailable':True}
    assert 'secret' not in json.dumps(adapter.start_login())
    assert calls==[('account/read',{'refreshToken':False}),('account/login/start',{'type':'chatgpt'})]
    with pytest.raises(ValueError):AppServerAuth(lambda *_:{'authUrl':'http://evil.example'}).start_login()
