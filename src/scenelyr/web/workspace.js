'use strict';
const $ = id => document.getElementById(id);
const state = {scene:null, selected:null, zoom:1, preview:null, busy:false, importing:false, importJob:null, lastFile:null, sourceObjectUrl:null, overlay:false, library:[], models:[], openGeneration:0};
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const quote = value => '"' + String(value).replace(/\\/g,'\\\\').replace(/"/g,'\\"') + '"';
const sceneURL = id => '/workspace/scenes/' + encodeURIComponent(id);
const stageNames = {upload:'Upload',objects:'Objects',text:'Text',routes:'Routes',arrowheads:'Arrowheads',junctions:'Junctions',saved:'Saved scene'};
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
function remember(key, value) { try { localStorage.setItem('scenelyr.'+key,value); } catch {} }
function recall(key) { try { return localStorage.getItem('scenelyr.'+key); } catch { return null; } }
async function api(url, options={}) {
 const response = await fetch(url, options);
 let result;
 try { result = await response.json(); } catch { throw new Error('The local server did not respond. Check that SceneLyr is running, then retry.'); }
 if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'The request was invalid. Check the command and retry.');
 return result;
}
const post = (url, data={}) => api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
function notice(message, error=false) { $('notice').textContent=message; $('notice').classList.toggle('error',error); $('notice').hidden=!message; }
function clearChatEmpty(){const empty=$('chat-empty');if(empty)empty.remove();}
function updateMessageCount(){const count=$('timeline').querySelectorAll('.chat-message').length;$('conversation-count').textContent=count+' message'+(count===1?'':'s');}
function log(message, kind='assistant', tool='Codex') {
 clearChatEmpty();const role=kind==='user'?'user':kind==='error'?'error':'assistant';
 const row=document.createElement('article');row.className='chat-message '+role;
 const avatar=document.createElement('span');avatar.className='chat-avatar';avatar.setAttribute('aria-hidden','true');avatar.textContent=role==='user'?'Y':'◇';
 const content=document.createElement('div');content.className='chat-content';
 const meta=document.createElement('div');meta.className='chat-meta';
 const name=document.createElement('strong');name.textContent=role==='user'?'You':tool;
 const time=document.createElement('span');time.textContent='Now';meta.append(name,time);
 const copy=document.createElement('div');copy.className='chat-copy';copy.textContent=message;
 content.append(meta,copy);row.append(avatar,content);$('timeline').append(row);
 while($('timeline').children.length>80)$('timeline').firstChild.remove();
 updateMessageCount();$('timeline').scrollTop=$('timeline').scrollHeight;return row;
}
function beginActivity(){
 clearChatEmpty();const details=document.createElement('details');details.className='activity-card';details.open=true;
 const summary=document.createElement('summary');summary.textContent='Codex is working';
 const list=document.createElement('ol');details.append(summary,list);$('timeline').append(details);$('timeline').scrollTop=$('timeline').scrollHeight;
 return {details,summary,list,count:0};
}
function addActivity(panel,activity){
 const item=document.createElement('li');item.dataset.state=activity.state;
 const icon=document.createElement('span');icon.className='activity-icon';icon.textContent=activity.state==='complete'?'✓':activity.state==='failed'?'!':'…';
 const copy=document.createElement('span');const name=activity.tool?'SceneLyr MCP · '+activity.tool:'Codex';copy.textContent=name+' — '+activity.message;
 item.append(icon,copy);panel.list.append(item);panel.count++;panel.summary.textContent='Codex is working · '+panel.count+' step'+(panel.count===1?'':'s');$('timeline').scrollTop=$('timeline').scrollHeight;
}
function error(error) { notice(error.message || String(error),true); log(error.message || String(error),'error'); }
function busy(value) { state.busy=value; $('send').disabled=value; $('undo').disabled=value || !state.scene?.history.canUndo; $('redo').disabled=value || !state.scene?.history.canRedo; }
async function loadLibrary() {
 const data=await api('/workspace/history'); state.library=data.scenes;
 $('library').innerHTML=data.scenes.length?data.scenes.map(item=>`<button class="library-item" data-open="${escape(item.id)}" aria-current="${state.scene?.id===item.id}">${escape(item.title)}<small>${item.objects} objects · ${item.connections} connections</small></button>`).join(''):'<p class="muted" style="padding:8px">Your imported diagrams will appear here.</p>';
}
async function loadAccountStatus() {
 try {
  const account=await api('/workspace/account');
  const modelName=formatModel(account.model);const effort=account.reasoningEffort;
  $('account').textContent=account.mode==='codex'?(modelName.replace(/^GPT-6 /,'')+(effort?' · '+titleCase(effort):'')):'Local';
  $('account').setAttribute('aria-label',account.label+(modelName?' using '+modelName:''));
  $('account').title=[account.label,modelName,effort&&titleCase(effort)+' reasoning'].filter(Boolean).join(' · ');
  $('composer-mode').textContent=account.mode==='codex'?'SceneLyr MCP':'Local commands';
 } catch {}
}
const titleCase=value=>String(value||'').replace(/(^|[-_ ])(\w)/g,(_,space,letter)=>(space?' ':'')+letter.toUpperCase());
const formatModel=value=>value?String(value).split('-').map((part,index)=>index===0?'GPT':index===1&&/^\d/.test(part)?part.toUpperCase():titleCase(part)).join('-').replace(/^GPT-(\d[^-]*)-/,'GPT-$1 '):'';
function updateEffortChoices(preferred) {
 const model=state.models.find(item=>item.id===$('model-select').value);const efforts=model?.efforts||[];
 $('effort-select').innerHTML=efforts.map(value=>`<option value="${escape(value)}">${escape(titleCase(value))}</option>`).join('')||'<option value="">Default</option>';
 const saved=preferred||recall('reasoningEffort');$('effort-select').value=efforts.includes(saved)?saved:(model?.defaultEffort||efforts[0]||'');$('effort-select').disabled=!efforts.length;
 remember('model',$('model-select').value);remember('reasoningEffort',$('effort-select').value);
}
async function loadModels() {
 try {
  const data=await api('/workspace/models');state.models=data.models||[];
  $('model-select').innerHTML=state.models.map(item=>`<option value="${escape(item.id)}">${escape(item.name)}</option>`).join('')||'<option value="">Codex default</option>';
  const saved=recall('model');const chosen=state.models.find(item=>item.id===saved)||state.models.find(item=>item.isDefault)||state.models[0];
  $('model-select').value=chosen?.id||'';updateEffortChoices();
 } catch {
  $('model-select').innerHTML='<option value="">Codex default</option>';$('model-select').disabled=true;$('effort-select').disabled=true;
 }
}
const agentSettings=()=>({model:$('model-select').value||null,effort:$('effort-select').value||null});
function setupSpeech() {
 const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;const button=$('voice');
 if(!SpeechRecognition){button.disabled=true;button.title='Speech input is unavailable in this browser';return;}
 const recognition=new SpeechRecognition();recognition.continuous=false;recognition.interimResults=true;recognition.lang=navigator.language||'en-US';
 let listening=false,base='';
 button.addEventListener('click',()=>{if(listening){recognition.stop();return;}base=$('command').value.trim();recognition.start();});
 recognition.onstart=()=>{listening=true;button.classList.add('listening');button.setAttribute('aria-label','Stop speech input');notice('Listening… Speak your SceneLyr request.');};
 recognition.onresult=event=>{let text='';for(let i=event.resultIndex;i<event.results.length;i++)text+=event.results[i][0].transcript;$('command').value=(base+' '+text).trim();};
 recognition.onerror=event=>notice(event.error==='not-allowed'?'Microphone access was not allowed. You can still type your request.':'Speech input stopped. You can continue typing.',true);
 recognition.onend=()=>{listening=false;button.classList.remove('listening');button.setAttribute('aria-label','Start speech input');if($('command').value.trim())notice('Speech added. Review it, then send to Codex.');};
}
async function clearPreview() {
 const old=state.preview; state.preview=null; $('pending-preview').hidden=true; $('pending-preview').replaceChildren();
 if(old) await api('/workspace/previews/'+encodeURIComponent(old.token),{method:'DELETE'}).catch(()=>{});
}
async function openScene(id) {
 const generation=++state.openGeneration;
 try {
  const scene=await api(sceneURL(id)); if(generation!==state.openGeneration)return;
  await clearPreview(); state.selected=recall('selection.'+id); renderScene(scene); notice('');
  history.replaceState(null,'','?scene='+encodeURIComponent(id)); remember('scene',id);
 } catch(e) { if(generation===state.openGeneration)error(e); }
}
function renderScene(data) {
 state.scene=data;
 if(!data.scene.nodes.some(n=>n.id===state.selected)&&!data.scene.edges.some(e=>e.id===state.selected))state.selected=null;
 $('empty').hidden=true; $('import-progress').hidden=true; $('canvas-section').hidden=false;
 $('hierarchy-section').hidden=false; $('asset-section').hidden=false;
 $('scene-title').textContent=data.title; document.title=data.title+' · SceneLyr';
 $('scene-path').textContent='Local workspace / '+data.id;
 $('scene-count').textContent=data.scene.nodes.length+data.scene.edges.length;
 $('canvas-summary').textContent=`${data.scene.nodes.length} objects · ${data.scene.edges.length} connections · review required`;
 $('save-status').textContent='Saved on this computer';
 $('exports').innerHTML=['json','svg','pptx','html'].map(kind=>`<a href="/ui/export/${encodeURIComponent(data.id)}/${kind}" download>${kind==='pptx'?'Editable PowerPoint':kind==='html'?'HTML Inspector':kind.toUpperCase()}</a>`).join('');
 // Only the deterministic Python renderer supplies this SVG; no user HTML is accepted.
 $('canvas').innerHTML=data.svg;
 for(const element of $('canvas').querySelectorAll('[data-scene-id],[data-edge-id]')) {
  const id=element.dataset.sceneId||element.dataset.edgeId;
  const item=data.scene.nodes.find(n=>n.id===id)||data.scene.edges.find(e=>e.id===id);
  element.setAttribute('tabindex','0'); element.setAttribute('role','button');
  element.setAttribute('aria-label',item.label||`${item.from} to ${item.to}`);
  element.dataset.review=String(needsReview(item));
  if(element.dataset.edgeId) {const path=element.querySelector('path'); if(path){const hit=path.cloneNode();hit.classList.add('edge-hit');hit.removeAttribute('marker-end');element.prepend(hit);}}
 }
 renderHierarchy(); renderAssets(); syncSelection(); zoom(); busy(false); loadLibrary().catch(error);
}
function needsReview(item) {return item.metadata?.requiresReview || item.metadata?.labelStatus==='unread' || item.metadata?.direction==='unknown';}
function renderHierarchy() {
 if(!state.scene)return;
 const query=$('filter').value.toLocaleLowerCase();
 const nodes=state.scene.scene.nodes.filter(n=>(n.label+' '+n.id).toLocaleLowerCase().includes(query));
 const edges=state.scene.scene.edges.filter(e=>(e.id+' '+(e.label||'')+' '+e.from+' '+e.to).toLocaleLowerCase().includes(query));
 const row=(item,type)=>`<button class="tree-row ${state.selected===item.id?'selected':''}" data-select="${escape(item.id)}" aria-pressed="${state.selected===item.id}"><span class="tree-icon" aria-hidden="true">${type==='edge'?'↗':item.metadata?.shape==='diamond'?'◇':'▢'}</span><span>${escape(item.label||(type==='edge'?item.from+' → '+item.to:item.id))}</span>${needsReview(item)?'<span class="review-dot" title="Review required">!</span>':''}</button>`;
 $('hierarchy').innerHTML=`<details class="hierarchy-group" open><summary>Objects · ${nodes.length}</summary>${nodes.map(n=>row(n,'node')).join('')||'<p class="muted">No matching objects.</p>'}</details><details class="hierarchy-group" open><summary>Connections · ${edges.length}</summary>${edges.map(e=>row(e,'edge')).join('')||'<p class="muted">No matching connections.</p>'}</details>`;
}
function renderAssets() {
 const nodes=state.scene.nodes; $('asset-count').textContent=nodes.length;
 $('assets').innerHTML=nodes.map(n=>`<button class="tree-row" data-select="${escape(n.id)}">▧ ${escape(n.label)}</button>`).join('');
 $('debug-assets').innerHTML='<p class="muted">Open to load detection images.</p>';
 if($('debug-details').open)loadDebug();
}
async function loadDebug() {
 if(!state.scene)return;const id=state.scene.id;
 try {const data=await api(sceneURL(id)+'/debug');if(state.scene?.id!==id)return;$('debug-assets').innerHTML=data.files.length?data.files.map(file=>`<a href="${escape(file.url)}" target="_blank" rel="noopener">${escape(file.name.replace(/[-_]/g,' '))}</a>`).join(''):'<p class="muted">No source detection stages for this scene.</p>';}catch(e){error(e);}
}
function select(id) {
 state.selected=id||null; remember('selection.'+state.scene.id,id||''); syncSelection();
}
function syncSelection() {
 for(const row of document.querySelectorAll('[data-select]')) {const selected=row.dataset.select===state.selected;row.classList.toggle('selected',selected);row.setAttribute('aria-pressed',String(selected));}
 for(const element of $('canvas').querySelectorAll('[data-scene-id],[data-edge-id]')) {const selected=(element.dataset.sceneId||element.dataset.edgeId)===state.selected;element.classList.toggle('selected',selected);element.setAttribute('aria-pressed',String(selected));}
 renderInspector();
}
const evidence = (label,value) => `<div><span>${escape(label)}</span><strong>${escape(value ?? 'Not measured')}</strong></div>`;
const imagePreview = (src,alt,hint='Open and zoom image') => `<button type="button" class="image-preview" data-image-src="${escape(src)}" data-image-alt="${escape(alt)}" aria-label="${escape(hint)}"><img class="source-crop" src="${escape(src)}" alt="${escape(alt)}"><span>${escape(hint)} <span aria-hidden="true">↗</span></span></button>`;
function sceneWarnings() {
 const metadata=state.scene.scene.metadata;
 return `<div class="inspector-section"><h3>Review Queue</h3><div class="warnings">${(metadata.warnings||[]).map(w=>`<p>! ${escape(w)}</p>`).join('')||'<p>Extraction still requires human review.</p>'}</div><p class="muted">${metadata.junctionDetectionProfile?.withheld?.length||0} ambiguous junctions withheld</p></div>`;
}
function renderInspector() {
 if(!state.scene)return;
 const data=state.scene; const node=data.nodes.find(n=>n.id===state.selected);const edge=data.scene.edges.find(e=>e.id===state.selected);
 let html='';
 if(node) {
  const m=node.metadata||{};
  html=`<span class="eyebrow">OBJECT / ${escape(m.shape||node.kind)}</span><h2 class="inspector-title">${escape(node.label)}</h2><span class="muted">${escape(node.id)}</span><label class="inspector-label" for="node-label">Label</label><input id="node-label" value="${escape(node.label)}" maxlength="500"><button class="primary" id="rename-node">Preview Rename</button><div class="inspector-section"><h3>Source Evidence</h3>${node.cropUrl?imagePreview(node.cropUrl+'?v='+data.revision.slice(0,8),'Original source crop of '+node.label,'Open crop and zoom'):'<p class="muted">No source crop. This object was added to the scene and now follows the imported diagram style.</p>'}<div class="evidence-grid">${evidence('Text confidence',m.ocrConfidence==null?null:Math.round(m.ocrConfidence*100)+'%')}${evidence('Label status',m.labelStatus||'Semantic')}${evidence('Detection',m.method||'User added')}${evidence('Source shape',m.shape||'Matched to scene')}</div>${needsReview(node)?'<div class="review-card"><strong>! Review Required</strong>Compare this label and shape with the original image.</div>':''}<div class="asset-links"><a href="${escape(node.recordUrl)}" target="_blank" rel="noopener">Object JSON</a><a href="${escape(node.layerUrl)}" target="_blank" rel="noopener">SVG Layer</a></div></div><div class="inspector-section"><h3>Semantic Actions</h3><button class="action" data-command="${escape('remove '+quote(node.id))}">Remove Object…</button></div><details><summary>Detection Details</summary><pre class="evidence-json">${escape(JSON.stringify(m,null,2))}</pre></details>`;
 } else if(edge) {
  const m=edge.metadata||{};const options=data.nodes.map(n=>`<option value="${escape(n.id)}">${escape(n.label)} (${escape(n.id)})</option>`).join('');
  html=`<span class="eyebrow">CONNECTION</span><h2 class="inspector-title">${escape(edge.label||edge.id)}</h2><p class="muted">${escape(edge.from)} → ${escape(edge.to)}</p><label class="inspector-label" for="edge-from">From</label><select id="edge-from">${options}</select><label class="inspector-label" for="edge-to">To</label><select id="edge-to">${options}</select><button class="primary" id="reconnect-edge">Preview Reconnection</button><div class="inspector-section"><h3>Direction Evidence</h3><div class="evidence-grid">${evidence('Direction',m.direction||'User defined')}${evidence('Detection',m.method||'Semantic')}${evidence('Confidence',m.confidence==null?null:String(m.confidence))}</div><div class="review-card"><strong>! Review Direction</strong>Inferred direction is evidence, not a guarantee.</div><details open><summary>Arrowhead & Junction Details</summary><pre class="evidence-json">${escape(JSON.stringify(m,null,2))}</pre></details></div><div class="inspector-section"><button class="action" data-command="${escape('reverse '+quote(edge.id))}">Reverse Direction…</button><button class="action" data-command="${escape('remove '+quote(edge.id))}">Remove Connection…</button></div>`;
 } else {
  const m=data.scene.metadata;
  html=`<span class="eyebrow">SCENE OVERVIEW</span><h2 class="inspector-title">${escape(data.title)}</h2><p class="muted">Select an object or connection to see its evidence.</p>${data.sourceUrl?imagePreview(data.sourceUrl,'Original diagram','Open original and zoom'):''}<div class="evidence-grid">${evidence('Objects',data.scene.nodes.length)}${evidence('Connections',data.scene.edges.length)}${evidence('OCR engine',m.ocrEngine||'Unavailable')}${evidence('Processing','Local')}</div><div class="inspector-section"><h3>Semantic Actions</h3><button class="action" data-command="redetect">Rerun Detection…</button><button class="action" data-command="inspect">Inspect Scene</button></div><details><summary>Detection Profiles</summary><pre class="evidence-json">${escape(JSON.stringify({arrowheads:m.arrowheadDetectionProfile,junctions:m.junctionDetectionProfile},null,2))}</pre></details>`;
 }
 $('inspector-content').innerHTML=html+sceneWarnings();
 if(edge) {$('edge-from').value=edge.from;$('edge-to').value=edge.to;}
}
function zoom(delta=0,fit=false) {
 if(fit) state.zoom=1;else state.zoom=Math.min(3,Math.max(.35,state.zoom+delta));
 const svg=$('canvas').querySelector('svg');
 if(svg){const available=Math.max(240,$('canvas').clientWidth-50);svg.style.width=(available*state.zoom)+'px';}
 $('zoom-level').textContent=Math.round(state.zoom*100)+'%';
}
async function sendCommand(message) {
 if(state.busy)return;
 if(!state.scene){notice('Import an image or open a recent scene before editing. Use Command Guide for examples.');return;}
 if(state.importing){notice('Wait for the current import to finish before editing.');return;}
 await clearPreview(); log(message,'user'); busy(true); notice('');
 const progress=setTimeout(()=>notice('Codex is interpreting your request and calling SceneLyr MCP tools…'),300);
 try {
  const id=state.scene.id;let response;
  try {
   response=await post(sceneURL(id)+'/commands',{message:message.replace(/[“”]/g,'"'),selected:state.selected,...agentSettings()});
  } catch(localError) {
   if(!String(localError.message).startsWith('This local command was not recognized.'))throw localError;
   notice('Codex is interpreting your request and may call SceneLyr tools…');
   response=await post(sceneURL(id)+'/agent',{message,selected:state.selected,...agentSettings()});
  }
  if(state.scene?.id!==id)return;
  if(response.type==='preview'){
   state.preview=response; const container=$('pending-preview');container.hidden=false;
   container.innerHTML=`<div class="preview-card"><small>Preview · ${escape(response.tool)}</small><p>${escape(response.summary)}</p><button class="primary" id="apply-preview">Apply Change</button><button id="discard-preview">Cancel</button><span class="muted">Undo available after applying</span></div>`;
   log(response.summary,'tool','Preview · '+response.tool);$('apply-preview').focus();
  } else if(response.type==='download') {
   log(response.summary);const a=document.createElement('a');a.href=response.url;a.download='';a.textContent='Download '+message.split(' ').pop().toUpperCase();$('timeline').lastElementChild.append(document.createElement('br'),a);a.click();
  } else if(response.type==='job'&&response.kind==='agent') {await pollAgent(response.job,id);}
  else if(response.type==='job') {log(response.summary);pollValidation(response.job);}
  else if(response.type==='agent') {if(response.scene)renderScene(response.scene);log(response.message,'tool',response.tools?.length?'Codex · '+response.tools.join(', '):'Codex');notice('Codex completed the request.');}
  else {if(response.scene)renderScene(response.scene);log(response.summary,'tool',response.tool);}
 }catch(e){error(e);}finally{clearTimeout(progress);busy(false);}
}
async function pollAgent(id,sceneId) {
 let shown=0;const panel=beginActivity();
 while(true){
  const job=await api('/workspace/jobs/'+encodeURIComponent(id));
  for(const activity of job.events.slice(shown))addActivity(panel,activity);
  shown=job.events.length;
  if(job.state==='failed'){panel.summary.textContent='Work stopped · '+panel.count+' steps';panel.details.open=true;throw new Error(job.error);}
  if(job.state==='complete'){
   const result=job.result;if(state.scene?.id!==sceneId)return;
   if(result.scene)renderScene(result.scene);
   panel.summary.textContent='Work completed · '+panel.count+' step'+(panel.count===1?'':'s');panel.details.open=false;
   log(result.message,'assistant',result.tools?.length?'Codex · '+result.tools.join(', '):'Codex');
   notice('Codex completed the request.');return;
  }
  await sleep(350);
 }
}
async function applyPreview() {
 if(!state.preview||state.busy)return;const preview=state.preview;const sceneId=state.scene.id;busy(true);$('apply-preview').disabled=true;
 notice(preview.tool==='redetect_arrows'?'Rerunning source detection locally…':'Applying semantic change…');
 try {
  const result=await post('/workspace/previews/'+encodeURIComponent(preview.token)+'/apply');
  if(state.scene?.id!==sceneId)return;
  state.preview=null;$('pending-preview').hidden=true;renderScene(result.scene);log(result.summary,'tool',result.tool);notice('Saved locally. Undo is available.');$('command').focus();
 }catch(e){error(e);await clearPreview();}finally{busy(false);}
}
function showStages(events) {
 const latest={};for(const event of events)latest[event.stage]=event;
 $('stages').innerHTML=Object.entries(stageNames).map(([key,label])=>{const e=latest[key];const status=e?.state||'waiting';return `<li data-state="${status}"><span>${escape(label)}</span><span>${status==='complete'?'✓ Done':status==='running'?'In progress':status==='unavailable'?'Unavailable':'Waiting'}</span></li>`;}).join('');
 const objects=latest.objects?.objects;
 if(objects!=null)$('partial-summary').textContent=`${objects} objects detected${latest.routes?.connections!=null?' · '+latest.routes.connections+' connections':''}. Results will open after saving.`;
}
async function importFile(file) {
 if(!file)return;if(state.importing){notice('An import is already running. Wait for it to finish.');return;}
 if(file.size>25*1024*1024||!file.size){error(new Error('Choose a nonempty image smaller than 25 MB.'));return;}
 if(!['image/png','image/jpeg','image/webp','image/bmp'].includes(file.type)){error(new Error('Choose a PNG, JPG, WebP or BMP image.'));return;}
 await clearPreview(); state.lastFile=file;state.importing=true;$('import-button').disabled=true;$('retry-import').hidden=true;
 if(state.sourceObjectUrl)URL.revokeObjectURL(state.sourceObjectUrl);state.sourceObjectUrl=URL.createObjectURL(file);$('upload-preview').src=state.sourceObjectUrl;
 $('empty').hidden=true;$('canvas-section').hidden=true;$('import-progress').hidden=false;$('import-title').textContent='Reading your diagram';
 showStages([{stage:'upload',state:'running'}]);notice('');log('Import '+file.name,'user');
 const form=new FormData();form.append('image',file);
 try {
  const result=await api('/workspace/imports',{method:'POST',body:form});state.importJob=result.job;remember('importJob',result.job);
  await pollImport(result.job);
 }catch(e){importFailed(e);}finally{state.importing=false;$('import-button').disabled=false;}
}
function importFailed(e){error(e);$('import-title').textContent='Import paused';$('retry-import').hidden=!state.lastFile;$('partial-summary').textContent='No completion was recorded. Retry this image or choose a different one.';}
async function pollImport(id) {
 let failures=0;
 while(true){
  let job;try{job=await api('/workspace/jobs/'+encodeURIComponent(id));failures=0;}catch(e){if(++failures<4){await sleep(1500);continue;}throw e;}
  showStages(job.events);
  if(job.partial.length){$('hierarchy-section').hidden=false;$('hierarchy').innerHTML=`<p class="muted">Import in progress · ${job.partial.length} objects</p>`+job.partial.map(n=>`<p class="tree-row">▢ ${escape(n.label)}</p>`).join('');}
  if(job.state==='complete'){remember('importJob','');state.importJob=null;state.importing=false;await openScene(job.scene_id);log('Imported and saved locally. Review the objects, text, and connections.','tool','import_pixels');return;}
  if(job.state==='failed'){remember('importJob','');state.importJob=null;throw new Error(job.error);}
  await sleep(350);
 }
}
async function validate() {
 $('validate').disabled=true;try{const response=await post('/workspace/validation');log(response.summary);await pollValidation(response.job);}catch(e){error(e);}finally{$('validate').disabled=false;}
}
async function pollValidation(id) {
 $('validate').disabled=true;notice('Release validation is running against the real image importer…');
 try {while(true){const job=await api('/workspace/jobs/'+encodeURIComponent(id));if(job.state==='failed')throw new Error(job.error);if(job.state==='complete'){const summary=`Release validation: ${job.summary.passed}/${job.summary.total} fixtures passed.`;notice(summary,!job.passed);log(summary);const link=document.createElement('a');link.href=job.reportUrl;link.target='_blank';link.rel='noopener';link.textContent='Open Validation Report';$('timeline').lastElementChild.append(document.createElement('br'),link);break;}await sleep(600);}}catch(e){error(e);}finally{$('validate').disabled=false;}
}
let sheetPane=null, sheetPlaceholder=null;
function closeSheet() {
 if(sheetPane){sheetPlaceholder.replaceWith(sheetPane);sheetPane=null;sheetPlaceholder=null;}
 $('sheet').close();
}
function togglePane(name) {
 const compact=name==='sidebar'?matchMedia('(max-width:760px)').matches:matchMedia('(max-width:1150px)').matches;
 if(compact){if(sheetPane)closeSheet();sheetPane=$(name);sheetPlaceholder=document.createComment(name);sheetPane.replaceWith(sheetPlaceholder);$('sheet-content').append(sheetPane);$('sheet-title').textContent=name==='sidebar'?'Library & Hierarchy':'Inspector';$('sheet').showModal();}
 else{$('workspace').classList.toggle('hidden-'+name);updatePaneButtons();zoom();}
}
function updatePaneButtons(){for(const name of ['sidebar','inspector'])$('toggle-'+name).setAttribute('aria-expanded',String(getComputedStyle($(name)).display!=='none'));}
function info(title, html){$('info-title').textContent=title;$('info-content').innerHTML=html;$('info-dialog').showModal();}
let imageZoom=1;
function setImageZoom(value,fit=false){
 const stage=$('image-stage'),image=$('viewer-image');
 if(fit)imageZoom=Math.min(1,(stage.clientWidth-48)/Math.max(1,image.naturalWidth),(stage.clientHeight-48)/Math.max(1,image.naturalHeight));
 else imageZoom=Math.min(5,Math.max(.25,value));
 image.style.width=(image.naturalWidth*imageZoom)+'px';image.style.maxWidth='none';
 $('image-zoom-level').textContent=fit?'Fit · '+Math.round(imageZoom*100)+'%':Math.round(imageZoom*100)+'%';
}
function openImageViewer(src,alt){
 if(sheetPane)closeSheet();const dialog=$('image-viewer'),image=$('viewer-image');$('image-viewer-title').textContent=alt||'Image preview';image.alt=alt||'Image preview';image.src=src;
 image.onload=()=>setImageZoom(1,true);dialog.showModal();
}
function resizePane(name,min,max,initial) {
 const handle=$(name+'-resizer');let width=Number(recall(name+'Width'))||initial;width=Math.min(max,Math.max(min,width));
 const set=value=>{width=Math.min(max,Math.max(min,value));document.documentElement.style.setProperty('--'+name+'-width',width+'px');handle.setAttribute('aria-valuenow',String(width));remember(name+'Width',width);zoom();};set(width);
 handle.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();set(e.key==='Home'?min:e.key==='End'?max:width+(e.key==='ArrowRight'?1:-1)*(name==='sidebar'?1:-1)*16);});
 handle.addEventListener('pointerdown',e=>{const start=e.clientX,previous=width;handle.setPointerCapture(e.pointerId);const move=ev=>set(previous+(ev.clientX-start)*(name==='sidebar'?1:-1));const end=()=>{handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',end);};handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',end);});
}
$('library').addEventListener('click',e=>{const button=e.target.closest('[data-open]');if(button){if(state.importing||state.busy){notice('Wait for the current operation to finish before switching scenes.');return;}closeSheet();openScene(button.dataset.open);}});
for(const id of ['hierarchy','assets'])$(id).addEventListener('click',e=>{const row=e.target.closest('[data-select]');if(row)select(row.dataset.select);});
$('hierarchy').addEventListener('keydown',e=>{if(!['ArrowDown','ArrowUp','Home','End'].includes(e.key))return;const rows=[...$('hierarchy').querySelectorAll('details[open] [data-select]')];const index=rows.indexOf(document.activeElement);if(index<0)return;e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?rows.length-1:Math.max(0,Math.min(rows.length-1,index+(e.key==='ArrowDown'?1:-1)));rows[next].focus();select(rows[next].dataset.select);});
$('canvas').addEventListener('click',e=>{const element=e.target.closest('[data-scene-id],[data-edge-id]');select(element?(element.dataset.sceneId||element.dataset.edgeId):null);});
$('canvas').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){const element=e.target.closest('[data-scene-id],[data-edge-id]');if(element){e.preventDefault();select(element.dataset.sceneId||element.dataset.edgeId);}}});
$('inspector-content').addEventListener('click',e=>{const button=e.target.closest('button');if(!button)return;if(button.dataset.imageSrc){openImageViewer(button.dataset.imageSrc,button.dataset.imageAlt);return;}let command=button.dataset.command;if(button.id==='rename-node')command='rename '+quote(state.selected)+' to '+quote($('node-label').value);if(button.id==='reconnect-edge')command='reconnect '+quote(state.selected)+' from '+quote($('edge-from').value)+' to '+quote($('edge-to').value);if(command){if(sheetPane)closeSheet();sendCommand(command);}});
$('filter').addEventListener('input',renderHierarchy);$('debug-details').addEventListener('toggle',()=>{if($('debug-details').open)loadDebug();});
$('pending-preview').addEventListener('click',e=>{if(e.target.id==='apply-preview')applyPreview();if(e.target.id==='discard-preview'){log('Preview cancelled. No scene change.');clearPreview();$('command').focus();}});
$('composer').addEventListener('submit',e=>{e.preventDefault();const value=$('command').value.trim();if(value){$('command').value='';resizeCommand();sendCommand(value);}});
$('command').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('composer').requestSubmit();}});
$('command').addEventListener('input',resizeCommand);
$('timeline').addEventListener('click',e=>{const suggestion=e.target.closest('[data-prompt]');if(suggestion){$('command').value=suggestion.dataset.prompt;resizeCommand();$('command').focus();}});
$('model-select').addEventListener('change',()=>updateEffortChoices());$('effort-select').addEventListener('change',()=>remember('reasoningEffort',$('effort-select').value));
for(const id of ['choose-image','import-button','attach'])$(id).addEventListener('click',()=>$('file').click());
$('file').addEventListener('change',()=>{const file=$('file').files[0];$('file').value='';importFile(file);});
$('retry-import').addEventListener('click',()=>importFile(state.lastFile));
for(const type of ['dragenter','dragover'])$('main').addEventListener(type,e=>{e.preventDefault();$('main').classList.add('drag-over');});
$('main').addEventListener('dragleave',e=>{if(!$('main').contains(e.relatedTarget))$('main').classList.remove('drag-over');});
$('main').addEventListener('drop',e=>{e.preventDefault();$('main').classList.remove('drag-over');importFile(e.dataTransfer.files[0]);});
document.addEventListener('paste',e=>{const item=[...e.clipboardData.items].find(item=>item.kind==='file'&&item.type.startsWith('image/'));if(item){e.preventDefault();importFile(item.getAsFile());}});
$('undo').addEventListener('click',()=>sendCommand('undo'));$('redo').addEventListener('click',()=>sendCommand('redo'));$('validate').addEventListener('click',validate);
$('zoom-in').addEventListener('click',()=>zoom(.15));$('zoom-out').addEventListener('click',()=>zoom(-.15));$('fit-canvas').addEventListener('click',()=>zoom(0,true));
$('review-toggle').addEventListener('click',()=>{state.overlay=!state.overlay;$('canvas').classList.toggle('review-overlay',state.overlay);$('review-toggle').setAttribute('aria-pressed',String(state.overlay));});
for(const name of ['sidebar','inspector'])$('toggle-'+name).addEventListener('click',()=>togglePane(name));
$('close-sheet').addEventListener('click',closeSheet);$('sheet').addEventListener('cancel',e=>{e.preventDefault();closeSheet();});$('close-info').addEventListener('click',()=>$('info-dialog').close());
$('close-image-viewer').addEventListener('click',()=>$('image-viewer').close());$('image-zoom-in').addEventListener('click',()=>setImageZoom(imageZoom+.25));$('image-zoom-out').addEventListener('click',()=>setImageZoom(imageZoom-.25));$('image-zoom-reset').addEventListener('click',()=>setImageZoom(1,true));
$('image-viewer').addEventListener('click',e=>{if(e.target===$('image-viewer'))$('image-viewer').close();});$('image-viewer').addEventListener('cancel',e=>{e.preventDefault();$('image-viewer').close();});
$('image-stage').addEventListener('wheel',e=>{if(!e.ctrlKey&&!e.metaKey)return;e.preventDefault();setImageZoom(imageZoom+(e.deltaY<0?.2:-.2));},{passive:false});
$('new-scene').addEventListener('click',()=>{if(state.importing||state.busy){notice('Wait for the current operation to finish.');return;}clearPreview();state.scene=null;state.selected=null;remember('scene','');history.replaceState(null,'','/');location.reload();});
$('account').addEventListener('click',async()=>{try{const account=await api('/workspace/account');const model=formatModel(account.model);info(account.label,`<p>${escape(account.message)}</p>${model?`<p><strong>${escape(model)}</strong>${account.reasoningEffort?' · '+escape(titleCase(account.reasoningEffort))+' reasoning':''}</p>`:''}<p>${escape(account.integration)}</p><p>No credentials are read by this workspace.</p>`);}catch(e){error(e);}});
$('command-help').addEventListener('click',()=>info('SceneLyr Commands','<p>Write a natural-language request for Codex, or use an exact local command for a faster deterministic edit. Codex receives the open scene and can call the configured SceneLyr MCP tools.</p><pre>Make this flow horizontal and give the steps realistic names\nrename selected to “Customer”\nadd “Cache”\nconnect “Customer” to “Cache”\nredetect\ninspect\nrender\nexport svg\nundo / redo\nvalidate</pre><p>Keyboard: Tab to move, Enter to select, arrow keys in the hierarchy or on pane dividers. ⌘/Ctrl Z previews undo; Shift adds redo. Escape closes sheets.</p>'));
document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='z'&&!['INPUT','TEXTAREA'].includes(document.activeElement.tagName)){e.preventDefault();if(state.scene)sendCommand(e.shiftKey?'redo':'undo');}});
window.addEventListener('resize',()=>{if(sheetPane)closeSheet();updatePaneButtons();zoom();});
function resizeCommand(){const input=$('command');input.style.height='auto';input.style.height=Math.min(150,input.scrollHeight)+'px';}
resizePane('sidebar',200,380,240);resizePane('inspector',260,440,300);updatePaneButtons();setupSpeech();resizeCommand();
(async()=>{try{await Promise.all([loadLibrary(),loadAccountStatus(),loadModels()]);const job=recall('importJob');if(job){state.importing=true;$('empty').hidden=true;$('import-progress').hidden=false;$('upload-preview').hidden=true;try{await pollImport(job);}catch(e){remember('importJob','');importFailed(e);}finally{state.importing=false;$('upload-preview').hidden=false;}}else{const requested=new URLSearchParams(location.search).get('scene')||recall('scene');if(requested)await openScene(requested);}}catch(e){error(e);}})();
