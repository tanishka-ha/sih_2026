const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

let currentAppId = 'APP-2026-8891';
let currentDocKey = 'p8891_income';
let activeFlagId = null;
let auditLog = [
  {time:'21:42:08', event:'Verification completed', detail:'APP-2026-8891 · 5 documents · ranked findings generated', hash:'', tone:'green'},
  {time:'21:42:11', event:'Finding inspected', detail:'Income amount region opened · 3 corroborating integrity signals', hash:'', tone:'blue'},
  {time:'21:42:17', event:'Cross-application match', detail:'INC-7842-2024 linked to APP-2026-9014', hash:'', tone:'red'}
];

const BAND = {
  high:{label:'Needs review', cls:'high'},
  medium:{label:'Needs review', cls:'medium'},
  clear:{label:'No findings', cls:'clear'},
  unreadable:{label:'Re-upload requested', cls:'neutral'},
  pending:{label:'Awaiting verification', cls:'pending'}
};

const VIEW_META = {
  queue:['Review queue','Ranked evidence for a human reviewer — never an automatic rejection.'],
  detail:['Application','One bundle · one evidence trail · one human decision.'],
  cross:['Across applications','See relationships that disappear when each review desk works alone.'],
  evidence:['Evidence map','Connect fields, sources and reasons behind every surfaced relationship.'],
  documents:['Documents','Inspect source material and reading quality without leaving the console.'],
  audit:['Audit trail','Every reviewer action becomes a traceable, hash-linked event.'],
  metrics:['Performance','Measured extraction results from the controlled ground-truth corpus.']
};

let pendingFiles = [];
let uploadedPreviews = new Map();
const API_BASE = window.SCHOLARGUARD_API_BASE || localStorage.getItem('sg-api-base') || '';


const appById = id => APPLICATIONS.find(a => a.id === id);

function renderQueue(filter='all'){
  const rows = APPLICATIONS.filter(a => filter==='all' || a.band===filter);
  const count = b => APPLICATIONS.filter(a=>a.band===b).length;
  $('#queueCounts').innerHTML = [
    [APPLICATIONS.length,'Applications today','Review worklist'],
    [count('high')+count('medium'),'Need human review','Ranked evidence'],
    [1,'Cross-application match','Duplicate certificate'],
    [count('unreadable'),'Re-upload required','No blind guesses']
  ].map(([n,t,chip])=>`<div class="summary-card"><b>${n}</b><span>${t}</span><div class="summary-chip">${chip}</div></div>`).join('');
  $('#navOpenCount').textContent = count('high')+count('medium');
  $('#queueRows').innerHTML = rows.map(a=>{
    const severity = a.band==='high' ? 'HIGH' : a.band==='medium' ? 'MEDIUM' : a.band==='clear' ? 'CLEAR' : a.band==='pending' ? 'PENDING' : 'RE-UPLOAD';
    const state = a.band==='high' ? 'Human review' : a.band==='medium' ? 'Human review' : a.band==='clear' ? 'All checks passed' : a.band==='pending' ? 'Awaiting verification' : 'Action required';
    return `<button class="q-row band-${a.band}" data-app="${a.id}">
      <span class="q-band"><i></i><span><strong>${severity}</strong><small>${BAND[a.band].label}</small></span></span>
      <span class="q-who"><b>${a.name}</b><small>${a.id} · ${a.institution}</small></span>
      <span class="q-reason"><b>${a.headline}</b><small>${a.readable||'Evidence available in case view'}</small></span>
      <span><span class="badge ${BAND[a.band].cls}">${state}</span></span>
      <span class="q-open">Review case <b>→</b></span>
    </button>`;
  }).join('');
  $$('#queueRows .q-row').forEach(el=>el.onclick=()=>openApplication(el.dataset.app));
}

function paperMarkup(key){
  const p = PAPERS[key];
  if(!p) return '<div class="paper-empty">No page image for this document in the demo dataset.</div>';
  const rows = p.rows.map(r=>`<div class="paper-line"><span>${r[0]}</span><strong class="${r[2]||''}">${r[1]}</strong></div>`).join('');
  const boxes = (p.boxes||[]).map(b=>`<button class="bbox ${b.kind==='neutral'?'bbox-neutral':''}" data-box="${b.id}" data-flag="${b.flagId}" style="left:${b.x*100}%;top:${b.y*100}%;width:${b.w*100}%;height:${b.h*100}%"><span>${b.label}</span></button>`).join('');
  return `<div class="paper ${p.degraded?'degraded':''}">
    <div class="paper-header"><div class="seal">GOVT.<br/>CERT</div><div><b>${p.title}</b><span>${p.sub}</span></div><div class="tiny-code">${p.code}</div></div>
    ${rows}<div class="paper-footer"><span>Scanned submission</span><span>Authorised Officer</span></div>${boxes}
  </div>`;
}

function showDoc(key, app){
  currentDocKey = key;
  const d = app.docs.find(x=>x.key===key);
  const p = PAPERS[key];
  $('#viewerTitle').textContent = d?.name || p?.title || 'Document';
  $('#viewerMeta').textContent = d ? `${d.meta} · character confidence ${d.conf}% · structure checks enabled` : '';
  if(d?.previewUrl){
    $('#documentCanvas').innerHTML = `<div class="uploaded-document"><img src="${d.previewUrl}" alt="${d.name}"><div class="uploaded-document-meta"><span>Uploaded source</span><b>${d.name}</b><small>${d.meta}</small></div></div>`;
  } else if(d?.type==='pdf' && !p){
    $('#documentCanvas').innerHTML = `<div class="pdf-placeholder"><div class="drop-icon">PDF</div><b>${d.name}</b><span>${d.meta}</span><small>PDF preview is handed to the verification service in the integrated build.</small></div>`;
  } else {
    $('#documentCanvas').innerHTML = paperMarkup(key);
  }
  $$('#documentCanvas .bbox').forEach(b=>b.onclick=()=>selectFlag(b.dataset.flag));
  $$('.doc-item').forEach(el=>el.classList.toggle('active',el.dataset.doc===key));
  if(activeFlagId) $(`#documentCanvas .bbox[data-flag="${activeFlagId}"]`)?.classList.add('is-active');
}

function selectFlag(flagId){
  const app = appById(currentAppId); const flag = app?.flags.find(f=>f.id===flagId); if(!flag) return;
  activeFlagId = flagId;
  if(flag.docKey!==currentDocKey) showDoc(flag.docKey,app);
  $$('.flag').forEach(el=>el.classList.toggle('is-active',el.dataset.flag===flagId));
  $$('#documentCanvas .bbox').forEach(b=>b.classList.toggle('is-active',b.dataset.flag===flagId));
  $(`#documentCanvas .bbox[data-flag="${flagId}"]`)?.scrollIntoView({block:'nearest',behavior:'smooth'});
  pushAudit('Finding inspected', `${flag.title} · evidence region opened`, 'blue');
}

function renderDetailHero(app){
  const severityBadge = `<span class="badge ${BAND[app.band].cls}">${BAND[app.band].label}</span>`;
  const open = app.flags?.length || 0;
  const read = app.docs?.length ? app.docs.filter(d=>d.state!=='unread').length : 0;
  $('#detailHero').innerHTML = `
    <div class="hero-card hero-main"><div class="app-id">${app.id}</div><h2>${app.name}</h2><p>${app.institution}</p><div class="hero-status">${severityBadge}<button class="primary" id="detailDecision">Record decision</button></div><div class="reason-line"><span class="hero-mini-label">Primary review reason</span><div>${app.headline}</div></div></div>
    <div class="hero-card"><span class="hero-mini-label">Open findings</span><strong class="hero-mini-value">${open}</strong><span class="mini-note">${open ? 'Ranked by reviewer attention' : 'All checks agree'}</span></div>
    <div class="hero-card"><span class="hero-mini-label">Readability</span><strong class="hero-mini-value">${read}/${app.docs?.length||0}</strong><span class="mini-note">${app.readable}</span></div>`;
  $('#detailDecision').onclick=()=>openDecisionModal();
}

function openApplication(id){
  const app = appById(id); if(!app) return;
  currentAppId = id; activeFlagId = null;
  renderDetailHero(app);
  $('#docCountChip').textContent = `${app.docs.length} file${app.docs.length===1?'':'s'}`;
  $('#docList').innerHTML = app.docs.length ? app.docs.map(d=>`<div class="doc-item" data-doc="${d.key}"><div class="doc-left"><div class="file-icon">${d.icon}</div><div><div class="doc-name">${d.name}</div><div class="doc-meta">${d.meta} · ${d.conf}% OCR</div></div></div><span class="doc-state ${d.state==='ok'?'ok':d.state==='unread'?'unread':'warn'}">${d.state==='ok'?'✓ Ready':d.state==='unread'?'↺ Re-upload':'! Review'}</span></div>`).join('') : '<div class="empty-note">Documents not included in this demo case.</div>';
  $$('.doc-item').forEach(el=>el.onclick=()=>showDoc(el.dataset.doc,app));

  $('#flagCount').textContent = app.flags.length;
  if(app.flags.length){
    $('#flagList').innerHTML = app.flags.map(f=>`<div class="flag ${f.kind==='medium'?'medium':''} ${f.kind==='neutral'?'neutral':''}" data-flag="${f.id}"><div class="flag-head"><div class="flag-sev">${f.sev}</div><div><div class="flag-title">${f.title}</div><div class="flag-sub">${f.sub}</div></div></div><div class="flag-foot"><button>${f.action==='cross'?'Compare both applications':f.action==='evidence'?'Open evidence map':'Show the region'}</button><span class="confidence">${f.basis}</span></div></div>`).join('');
    $$('.flag').forEach(el=>el.onclick=()=>selectFlag(el.dataset.flag));
    $$('.flag-foot button').forEach((b,i)=>{ b.onclick=e=>{e.stopPropagation(); const f=app.flags[i]; if(f.action==='cross') goto('cross'); else if(f.action==='evidence') goto('evidence'); else selectFlag(f.id); }; });
  } else if(app.cleared){
    $('#flagList').innerHTML = `<div class="cleared-head"><b>Nothing here needs your attention</b><p>Every check ran and agreed. The reasoning remains inspectable.</p></div>${app.cleared.map(c=>`<div class="cleared-row"><span>${c[0]}</span><b>${c[1]}</b></div>`).join('')}`;
  } else $('#flagList').innerHTML = '<div class="empty-note">No findings in this demo case.</div>';

  if(app.docs.length) showDoc(app.docs[0].key,app);
  goto('detail');
}

function renderCross(){
  const d=DUPLICATE_CASE;
  const side=s=>`<div class="cross-card"><div class="cross-card-head"><div><b>${s.name}</b><span>${s.appId}</span></div><div class="cross-inst">${s.institution}<i>${s.reviewer}</i></div></div><div class="cross-paper">${paperMarkup(s.paper)}</div><div class="cross-meta">Submitted ${s.submitted}</div></div>`;
  $('#crossPair').innerHTML = side(d.left)+`<div class="cross-link"><div class="cross-link-line"></div><div class="cross-link-chip"><span>${d.sharedLabel}</span><b>${d.sharedValue}</b></div><div class="cross-link-line"></div></div>`+side(d.right);
  $('#crossTable').innerHTML = d.comparison.map(r=>`<div class="ct-row ${r[3]}" data-shared="${r[0]}"><span class="ct-field">${r[0]}</span><span class="ct-val">${r[1]}</span><span class="ct-mark">${r[3]==='same'?'identical':'differs'}</span><span class="ct-val">${r[2]}</span></div>`).join('');
}

function renderDocGrid(){
  const app=appById(currentAppId);
  $('#docGrid').innerHTML = (app.docs||[]).map(d=>`<div class="doc-tile"><div class="file-icon">${d.icon}</div><h3>${d.name}</h3><p>${d.meta} · character confidence ${d.conf}%</p><div class="tile-status"><span class="quality ${d.state==='unread'?'quality-blue':''}">${d.state==='unread'?'Needs re-upload':'Readable'}</span><span class="mini-note">Original source</span></div></div>`).join('') || '<div class="empty-note">No documents in the selected demo dataset.</div>';
}

function goto(view){
  $$('.view').forEach(v=>v.classList.remove('active-view'));
  $(`#${view}-view`)?.classList.add('active-view');
  $$('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
  const meta=VIEW_META[view]||VIEW_META.queue;
  $('#pageTitle').textContent=meta[0]; $('#pageSub').textContent=meta[1];
  if(view==='documents') renderDocGrid();
  if(view==='audit') renderAudit();
  window.scrollTo({top:0});
}

function openModal(id){const el=$(`#${id}`); el?.classList.add('open');el?.setAttribute('aria-hidden','false')}
function closeModal(id){const el=$(`#${id}`); el?.classList.remove('open');el?.setAttribute('aria-hidden','true')}
function openDecisionModal(){
  const app=appById(currentAppId); if(!app) return;
  $('#decisionSummary').innerHTML=`<div><span>Application</span><b>${app.id}</b></div><div><span>Priority</span><b>${BAND[app.band].label}</b></div><div><span>Open findings</span><b>${app.flags.length}</b></div>`;
  openModal('decisionModal');
}

async function sha256Hex(text){
  const data=new TextEncoder().encode(text);
  const digest=await crypto.subtle.digest('SHA-256',data);
  return Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,'0')).join('');
}

async function rebuildAuditHashes(){
  let previous='GENESIS';
  for(let i=auditLog.length-1;i>=0;i--){
    const a=auditLog[i];
    a.hash=await sha256Hex(`${previous}|${a.time}|${a.event}|${a.detail}`);
    previous=a.hash;
  }
  renderAudit();
}

async function pushAudit(event,detail,tone='green'){
  const now=new Date();
  const time=now.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
  const previous=auditLog[0]?.hash || 'GENESIS';
  const hash=await sha256Hex(`${previous}|${time}|${event}|${detail}`);
  auditLog.unshift({time,event,detail,hash,tone});
  renderAudit();
}
function renderAudit(){
  $('#auditCount').textContent=auditLog.length;
  $('#auditList').innerHTML=auditLog.map(a=>`<div class="audit-entry"><div class="audit-time">${a.time}</div><div class="audit-event"><b>${a.event}</b><span>${a.detail}</span><span class="audit-pill">SHA-256 chained</span></div><div class="audit-hash" title="${a.hash}">${a.hash ? `${a.hash.slice(0,10)}…${a.hash.slice(-6)}` : 'calculating…'}</div></div>`).join('');
}

function exportReport(){
  const app=appById(currentAppId);
  const payload={application_id:app.id, applicant:app.name, status:app.status, flags:app.flags.map(f=>({id:f.id,severity:f.sev,title:f.title,basis:f.basis})), generated_at:new Date().toISOString()};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`${app.id}-results.json`;a.click();URL.revokeObjectURL(a.href);
  pushAudit('Audit report exported',`${app.id} · machine-readable results.json`,`blue`);
  showToast('results.json exported for the selected application');
}

function formatBytes(bytes){
  if(bytes < 1024) return `${bytes} B`;
  const units=['KB','MB','GB']; let n=bytes/1024, i=0;
  while(n>=1024 && i<units.length-1){n/=1024;i++;}
  return `${n.toFixed(n>=10?0:1)} ${units[i]}`;
}

function isAllowedFile(file){
  return /^(application\/pdf|image\/(png|jpeg))$/i.test(file.type) || /\.(pdf|png|jpe?g)$/i.test(file.name);
}

function renderSelectedFiles(){
  const root=$('#selectedFiles'); const btn=$('#runUpload');
  if(!root || !btn) return;
  btn.disabled = pendingFiles.length===0;
  if(!pendingFiles.length){ root.innerHTML=''; return; }
  root.innerHTML=pendingFiles.map((f,i)=>`<div class="selected-file"><span class="file-kind">${f.type==='application/pdf'?'PDF':'IMG'}</span><div><b>${f.name}</b><small>${formatBytes(f.size)}</small></div><button type="button" class="remove-file" data-index="${i}" aria-label="Remove ${f.name}">×</button></div>`).join('');
  $$('.remove-file',root).forEach(b=>b.onclick=()=>{pendingFiles.splice(Number(b.dataset.index),1); renderSelectedFiles();});
}

function makeUploadedApplication(files){
  const id=`LOCAL-${new Date().toISOString().slice(0,10).replace(/-/g,'')}-${String(Date.now()).slice(-4)}`;
  const docs=[];
  let remaining=files.length;
  files.forEach((file,idx)=>{
    const type=file.type==='application/pdf' || /\.pdf$/i.test(file.name) ? 'pdf':'image';
    const ext=(file.name.split('.').pop()||'file').toUpperCase();
    const doc={key:`${id}-${idx}`, name:file.name, icon:type==='pdf'?'PDF':ext==='PNG'?'PNG':'JPG', meta:`Uploaded · ${formatBytes(file.size)}`, conf:'—', state:'ok', type};
    if(type==='image'){
      const reader=new FileReader();
      reader.onload=e=>{
        doc.previewUrl=e.target.result;
        uploadedPreviews.set(doc.key,e.target.result);
        if(currentAppId===id && currentDocKey===doc.key) showDoc(doc.key,app);
      };
      reader.readAsDataURL(file);
    }
    docs.push(doc);
    remaining--;
  });
  const app={id,name:'New application',institution:'Local browser upload',band:'pending',status:'Awaiting verification',headline:'Documents uploaded — waiting for verification engine',readable:`${files.length} document${files.length===1?'':'s'} uploaded locally`,docs,flags:[]};
  APPLICATIONS.unshift(app);
  return app;
}

async function verifyBundleWithApi(app, files){
  if(!API_BASE) return null;
  const form=new FormData();
  form.append('application_id',app.id);
  files.forEach(f=>form.append('documents',f,f.name));
  const res=await fetch(`${API_BASE.replace(/\/$/,'')}/api/applications/verify`,{method:'POST',body:form});
  if(!res.ok) throw new Error(`Verification API returned ${res.status}`);
  return await res.json();
}

function mergeApiResult(app,result){
  if(!result || typeof result!=='object') return;
  if(Array.isArray(result.documents)) app.docs=result.documents;
  if(Array.isArray(result.flags)) app.flags=result.flags;
  if(result.band) app.band=result.band;
  if(result.status) app.status=result.status;
  if(result.headline) app.headline=result.headline;
  if(result.readable) app.readable=result.readable;
}

function handleFiles(fileList){
  const incoming=Array.from(fileList||[]);
  const valid=incoming.filter(isAllowedFile);
  const rejected=incoming.length-valid.length;
  pendingFiles=[...pendingFiles,...valid].slice(0,20);
  renderSelectedFiles();
  $('#uploadHint').textContent=rejected ? `${rejected} unsupported file${rejected===1?'':'s'} skipped. Use PDF, PNG or JPEG.` : 'Files stay in this browser until the verification API is connected.';
}

function toggleTheme(){
  const dark=document.documentElement.classList.toggle('dark');
  localStorage.setItem('sg-theme',dark?'dark':'light');
  $('#themeToggle').textContent=dark?'☀':'☾';
  showToast(dark?'Dark theme enabled':'Bright theme enabled');
}

function showToast(msg){const t=$('#toast');t.textContent=msg;t.classList.add('show');clearTimeout(window.__toast);window.__toast=setTimeout(()=>t.classList.remove('show'),2400)}

$$('.nav-item').forEach(btn=>btn.onclick=()=>goto(btn.dataset.view));
$$('#queueFilters button').forEach(btn=>btn.onclick=()=>{ $$('#queueFilters button').forEach(b=>b.classList.remove('on'));btn.classList.add('on');renderQueue(btn.dataset.filter)});

$('#newApplication').onclick=()=>openModal('newAppModal');
$('#helpBtn').onclick=()=>openModal('helpModal');
$('#themeToggle').onclick=toggleTheme;
$('#mobileMenu').onclick=()=>$('.sidebar')?.classList.toggle('mobile-open');
$('#settingsBtn').onclick=()=>showToast('Settings are intentionally minimal in this judging prototype');
$('#fitBtn').onclick=()=>showToast('Fit to page');
$('#zoomBtn').onclick=()=>showToast('Zoom control reserved for PDF viewer integration');

$$('[data-close]').forEach(btn=>btn.onclick=()=>closeModal(btn.dataset.close));
$$('.modal-backdrop').forEach(m=>m.addEventListener('click',e=>{if(e.target===m) closeModal(m.id)}));
document.addEventListener('keydown',e=>{if(e.key==='Escape') $$('.modal-backdrop.open').forEach(m=>closeModal(m.id))});

$$('.decision-btn').forEach(btn=>btn.onclick=()=>{
  const app=appById(currentAppId); if(!app) return;
  const outcome=btn.dataset.outcome;
  app.status=outcome==='cleared'?'Cleared':outcome==='correction'?'Correction requested':'Escalated for verification';
  const tone=outcome==='escalated'?'red':outcome==='correction'?'blue':'green';
  pushAudit('Reviewer decision',`${app.id} · ${app.status}`,tone);
  closeModal('decisionModal');
  renderQueue();
  renderDetailHero(app);
  showToast(`Decision recorded: ${app.status}`);
});

$('#loadDemoCase').onclick=()=>{
  closeModal('newAppModal');
  openApplication('APP-2026-8891');
  showToast('Demo bundle loaded · sample verification results ready');
  pushAudit('Demo bundle loaded','APP-2026-8891 · 5 documents · local prototype','blue');
};

const fileInput=$('#applicationFiles');
const dropzone=$('#dropzone');
$('#chooseFiles').onclick=()=>fileInput?.click();
fileInput?.addEventListener('change',e=>handleFiles(e.target.files));
dropzone?.addEventListener('dragover',e=>{e.preventDefault();dropzone.classList.add('dragover');});
dropzone?.addEventListener('dragleave',()=>dropzone.classList.remove('dragover'));
dropzone?.addEventListener('drop',e=>{e.preventDefault();dropzone.classList.remove('dragover');handleFiles(e.dataTransfer.files);});
$('#runUpload').onclick=async()=>{
  if(!pendingFiles.length) return;
  const files=[...pendingFiles];
  const app=makeUploadedApplication(files);
  pendingFiles=[]; renderSelectedFiles(); closeModal('newAppModal'); openApplication(app.id); renderQueue();
  pushAudit('Application uploaded',`${app.id} · ${files.length} source documents selected locally`,'blue');
  if(API_BASE){
    showToast('Uploading bundle to verification engine…');
    try{
      const result=await verifyBundleWithApi(app,files);
      mergeApiResult(app,result); renderQueue(); openApplication(app.id); showToast('Verification results received');
      pushAudit('Verification completed',`${app.id} · response received from verification API`,'green');
    }catch(err){
      app.headline='Upload complete — verification API unavailable';
      app.readable='Files remain local; no decision was made';
      renderQueue(); openApplication(app.id);
      showToast('Verification API connection failed — no decision made');
      pushAudit('Verification unavailable',`${app.id} · ${err.message}`,'red');
    }
  } else {
    showToast('Bundle added locally · awaiting verification API');
  }
};

$('#clearAudit').onclick=()=>{auditLog=[];renderAudit();showToast('Demo audit log reset')};

// Add an export button without crowding the main navigation.
const metricsPanel=$('#metrics-view .section-title');
const exportBtn=document.createElement('button');exportBtn.className='secondary';exportBtn.textContent='Export results.json';exportBtn.onclick=exportReport;metricsPanel.appendChild(exportBtn);

const savedTheme=localStorage.getItem('sg-theme');
if(savedTheme==='dark'){document.documentElement.classList.add('dark');$('#themeToggle').textContent='☀'}
const statusText=$('.status-pill'); if(statusText){statusText.innerHTML=`<span class="status-dot green"></span>${API_BASE?'Verification API connected':'Frontend console ready'}`}

renderQueue();renderCross();openApplication('APP-2026-8891');goto('queue'); void rebuildAuditHashes();
