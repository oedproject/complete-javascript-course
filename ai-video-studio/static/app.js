'use strict';

const $ = sel => document.querySelector(sel);
const STYLE_PRESETS = {
  'Sinematik': 'cinematic film still, dramatic lighting, shallow depth of field, highly detailed',
  'Anime': 'anime style, vibrant colors, detailed background, studio quality',
  'Gerçekçi': 'photorealistic, 35mm photo, natural light, sharp focus',
  'Suluboya': 'watercolor painting, soft edges, paper texture',
  '3D': '3d render, pixar style, soft global illumination',
  'Çizgi roman': 'comic book style, bold ink lines, halftone shading',
};
const EFFECT_LABELS = {
  auto: 'Otomatik', zoom_in: 'Yakınlaş', zoom_out: 'Uzaklaş', pan_left: 'Sola kaydır',
  pan_right: 'Sağa kaydır', pan_up: 'Yukarı kaydır', pan_down: 'Aşağı kaydır', static: 'Sabit',
};
const MODE_HELP = {
  fast: 'Karelere kamera hareketi ve geçiş eklenir. Saniyeler içinde biter.',
  ai: 'Her kare AI ile gerçekten hareketlenir (LTX-Video). M2 16 GB’de klip başına birkaç dakika sürer; ilk seferde ~25 GB model indirilir.',
};

let status = null;
let project = null;
const sceneJobs = {}; // sahne id -> iş id
let jobsCache = [];
let pollTimer = null;
let saveTimer = null;

// ---------------------------------------------------------------- API
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: opts.body && !(opts.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {},
    ...opts,
    body: opts.body && !(opts.body instanceof FormData) ? JSON.stringify(opts.body) : opts.body,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

function toast(msg, isError = false) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'toast' + (isError ? ' error' : '');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add('hidden'), isError ? 8000 : 3000);
}

const fileUrl = rel => (rel ? `/files/${project.id}/${rel}` : '');

// ---------------------------------------------------------------- kaydetme
function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(save, 500);
}

async function save() {
  clearTimeout(saveTimer);
  saveTimer = null;
  if (!project) return;
  const payload = {
    title: project.title, idea: project.idea, style: project.style, negative: project.negative,
    aspect: project.aspect, image_model: project.image_model, translate: project.translate,
    video: project.video,
    scenes: project.scenes.map(s => ({
      id: s.id, prompt: s.prompt, caption: s.caption, effect: s.effect, motion: s.motion, seed: s.seed,
    })),
  };
  try {
    const p = await api(`/api/projects/${project.id}`, { method: 'PUT', body: payload });
    mergeServer(p);
    refreshProjectList();
  } catch (e) {
    toast('Kaydedilemedi: ' + e.message, true);
  }
}

// Sunucudaki yeni kare/klip bilgilerini, kullanıcının yazdıklarını bozmadan al
function mergeServer(p) {
  const byId = Object.fromEntries(p.scenes.map(s => [s.id, s]));
  for (const s of project.scenes) {
    const srv = byId[s.id];
    if (!srv) continue;
    for (const k of ['image', 'clip', 'clip_key', 'used_prompt']) s[k] = srv[k];
    // yeni kare geldiyse onu üreten seed'i göster
    if (srv.image !== s._lastImage) s.seed = srv.seed;
    s._lastImage = srv.image;
  }
  // Sahne sayısı tutmuyorsa (ör. başka sekmede değişti) tamamen yenile
  if (p.scenes.length !== project.scenes.length) {
    project = p;
    project.scenes.forEach(s => (s._lastImage = s.image));
    renderAll();
    return;
  }
  for (const k of ['output', 'output_duration', 'music', 'music_name']) project[k] = p[k];
  project.scenes.forEach(s => updateSceneCard(s));
  renderOutput();
  renderMusic();
}

// ---------------------------------------------------------------- projeler
let listSeq = 0;
async function refreshProjectList() {
  const seq = ++listSeq;
  const list = await api('/api/projects');
  if (seq !== listSeq) return list; // daha yeni bir istek var; eski cevabı çizme
  const sel = $('#projectSelect');
  sel.innerHTML = '';
  for (const p of list) {
    const o = document.createElement('option');
    o.value = p.id;
    o.textContent = `${p.title} (${p.scenes} sahne)`;
    sel.appendChild(o);
  }
  if (project) sel.value = project.id;
  return list;
}

async function openProject(id) {
  if (saveTimer) await save();
  project = await api(`/api/projects/${id}`);
  project.scenes.forEach(s => (s._lastImage = s.image));
  localStorage.setItem('studio:last', id);
  renderAll();
  refreshProjectList();
  pollJobs();
}

async function newProject() {
  if (saveTimer) await save();
  const p = await api('/api/projects', { method: 'POST', body: { title: 'Yeni proje' } });
  await openProject(p.id);
  $('#idea').focus();
}

// ---------------------------------------------------------------- çizim
function renderAll() {
  $('#title').value = project.title;
  $('#idea').value = project.idea || '';
  $('#style').value = project.style || '';
  $('#negative').value = project.negative || '';
  $('#translate').checked = !!project.translate;
  $('#imageModel').value = project.image_model;
  setSeg('#aspect', project.aspect);
  const v = project.video;
  setSeg('#mode', v.mode);
  $('#seconds').value = v.seconds;
  $('#fade').value = v.fade;
  $('#resolution').value = v.resolution;
  $('#captions').checked = !!v.captions;
  $('#aiSeconds').value = v.ai_seconds;
  $('#aiSteps').value = v.ai_steps;
  $('#aiQuality').value = v.ai_quality;
  renderMode();
  renderScenes();
  renderOutput();
  renderMusic();
}

function setSeg(sel, value) {
  document.querySelectorAll(`${sel} button`).forEach(b => b.classList.toggle('active', b.dataset.v === value));
}

function renderMode() {
  const ai = project.video.mode === 'ai';
  document.querySelectorAll('.ai-only').forEach(el => el.classList.toggle('hidden', !ai));
  document.querySelectorAll('.fast-only').forEach(el => el.classList.toggle('hidden', ai));
  $('#modeHelp').textContent = MODE_HELP[project.video.mode];
}

function renderScenes() {
  const wrap = $('#scenes');
  wrap.innerHTML = '';
  wrap.className = 'scenes aspect-' + project.aspect.replace(':', '-');
  project.scenes.forEach((s, i) => wrap.appendChild(buildSceneCard(s, i)));
  $('#sceneCount').textContent = `(${project.scenes.length})`;
}

function buildSceneCard(scene, index) {
  const el = $('#sceneTpl').content.firstElementChild.cloneNode(true);
  el.dataset.id = scene.id;
  el.querySelector('.scene-no').textContent = `Sahne ${index + 1}`;
  const prompt = el.querySelector('.prompt');
  const caption = el.querySelector('.caption');
  const motion = el.querySelector('.motion');
  const seed = el.querySelector('.seed');
  const effect = el.querySelector('.effect');
  for (const e of ['auto', ...status.effects]) {
    const o = document.createElement('option');
    o.value = e;
    o.textContent = EFFECT_LABELS[e] || e;
    effect.appendChild(o);
  }
  prompt.value = scene.prompt;
  caption.value = scene.caption || '';
  motion.value = scene.motion || '';
  seed.value = scene.seed ?? '';
  effect.value = scene.effect || 'auto';

  prompt.addEventListener('input', () => { scene.prompt = prompt.value; scheduleSave(); });
  caption.addEventListener('input', () => { scene.caption = caption.value; scheduleSave(); });
  motion.addEventListener('input', () => { scene.motion = motion.value; scheduleSave(); });
  effect.addEventListener('change', () => { scene.effect = effect.value; scheduleSave(); });
  seed.addEventListener('input', () => {
    const n = parseInt(seed.value, 10);
    scene.seed = Number.isFinite(n) ? n : null;
    scheduleSave();
  });

  el.querySelector('.gen').addEventListener('click', () => genScene(scene, true));
  el.querySelector('.same').addEventListener('click', () => genScene(scene, false));
  el.querySelector('.upload').addEventListener('change', e => uploadImage(scene, e.target.files[0]));
  el.querySelector('.up').addEventListener('click', () => moveScene(scene, -1));
  el.querySelector('.down').addEventListener('click', () => moveScene(scene, 1));
  el.querySelector('.dup').addEventListener('click', () => duplicateScene(scene));
  el.querySelector('.del').addEventListener('click', () => deleteScene(scene));
  updateSceneCard(scene, el);
  return el;
}

function updateSceneCard(scene, el) {
  el = el || document.querySelector(`.scene[data-id="${scene.id}"]`);
  if (!el) return;
  const img = el.querySelector('img');
  const url = fileUrl(scene.image);
  if (img.getAttribute('src') !== url) img.setAttribute('src', url);
  el.classList.toggle('has-image', !!scene.image);
  el.querySelector('.gen').textContent = scene.image ? 'Yeniden üret' : 'Kare üret';
  el.querySelector('.same').classList.toggle('hidden', !scene.image);
  el.querySelector('.clip-badge').classList.toggle('hidden', !scene.clip);
  const seed = el.querySelector('.seed');
  if (document.activeElement !== seed) seed.value = scene.seed ?? '';
  el.querySelector('.used-prompt').textContent = scene.used_prompt ? 'Modele giden istem: ' + scene.used_prompt : '';

  const job = jobsCache.find(j => j.id === sceneJobs[scene.id]);
  const busy = job && (job.status === 'queued' || job.status === 'running');
  el.classList.toggle('is-busy', !!busy);
  if (busy) {
    el.querySelector('.busy-msg').textContent =
      job.status === 'queued' ? 'Sırada bekliyor…' : `${job.message} ${Math.round(job.progress * 100)}%`;
  }
}

function renderOutput() {
  const card = $('#outputCard');
  if (!project.output) { card.classList.add('hidden'); return; }
  card.classList.remove('hidden');
  const url = fileUrl(project.output);
  const v = $('#outputVideo');
  if (v.getAttribute('src') !== url) v.setAttribute('src', url);
  $('#outputDownload').href = url;
  $('#outputDownload').setAttribute('download', `${project.title || 'video'}.mp4`);
  $('#outputInfo').textContent = project.output_duration ? `${project.output_duration} saniye` : '';
}

function renderMusic() {
  $('#musicName').textContent = project.music_name || (project.music ? 'Müzik ekli' : 'Müzik yok');
  $('#musicRemove').classList.toggle('hidden', !project.music);
}

// ---------------------------------------------------------------- sahne işlemleri
function splitIdea() {
  const text = $('#idea').value.trim();
  if (!text) { toast('Önce bir fikir yaz.'); return; }
  let parts = text.split(/\n+/).map(s => s.trim()).filter(Boolean);
  if (parts.length === 1) parts = text.split(/(?<=[.!?])\s+/).map(s => s.trim()).filter(Boolean);
  const hasImages = project.scenes.some(s => s.image);
  if (hasImages && !confirm(`Mevcut sahneler silinip ${parts.length} yeni sahne oluşturulsun mu?`)) return;
  project.scenes = parts.map(p => ({ id: undefined, prompt: p, caption: '', effect: 'auto', motion: '', seed: null }));
  saveAndReload();
}

async function saveAndReload() {
  await save();
  project = await api(`/api/projects/${project.id}`);
  project.scenes.forEach(s => (s._lastImage = s.image));
  renderAll();
}

function addScene() {
  project.scenes.push({ id: undefined, prompt: '', caption: '', effect: 'auto', motion: '', seed: null });
  saveAndReload().then(() => {
    const cards = document.querySelectorAll('.scene .prompt');
    cards[cards.length - 1]?.focus();
  });
}

function moveScene(scene, dir) {
  const i = project.scenes.indexOf(scene);
  const j = i + dir;
  if (j < 0 || j >= project.scenes.length) return;
  [project.scenes[i], project.scenes[j]] = [project.scenes[j], project.scenes[i]];
  renderScenes();
  scheduleSave();
}

function duplicateScene(scene) {
  const i = project.scenes.indexOf(scene);
  project.scenes.splice(i + 1, 0, { ...scene, id: undefined, image: null, clip: null });
  saveAndReload();
}

function deleteScene(scene) {
  if (project.scenes.length === 1) { toast('En az bir sahne olmalı.'); return; }
  if (scene.image && !confirm('Bu sahne ve karesi silinsin mi?')) return;
  project.scenes = project.scenes.filter(s => s !== scene);
  renderScenes();
  save();
}

async function genScene(scene, newSeed) {
  if (!scene.prompt.trim()) { toast('Önce bu sahnede ne görmek istediğini yaz.'); return; }
  await save();
  try {
    const job = await api(`/api/projects/${project.id}/scenes/${scene.id}/image`, {
      method: 'POST', body: { new_seed: newSeed },
    });
    sceneJobs[scene.id] = job.id;
    jobsCache.push(job);
    updateSceneCard(scene);
    pollJobs();
  } catch (e) { toast(e.message, true); }
}

async function genMany(onlyMissing) {
  await save();
  const targets = project.scenes.filter(s => s.prompt.trim() && (!onlyMissing || !s.image));
  if (!targets.length) { toast(onlyMissing ? 'Eksik kare yok.' : 'İstemi olan sahne yok.'); return; }
  if (!onlyMissing && !confirm(`${targets.length} kare yeniden üretilsin mi?`)) return;
  // Her sahne ayrı iş: kartlarda tek tek ilerleme görünür
  for (const s of targets) {
    const job = await api(`/api/projects/${project.id}/scenes/${s.id}/image`, {
      method: 'POST', body: { new_seed: true },
    });
    sceneJobs[s.id] = job.id;
    jobsCache.push(job);
    updateSceneCard(s);
  }
  pollJobs();
}

async function uploadImage(scene, file) {
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const p = await api(`/api/projects/${project.id}/scenes/${scene.id}/upload`, { method: 'POST', body: fd });
    mergeServer(p);
    toast('Görsel yüklendi.');
  } catch (e) { toast(e.message, true); }
}

async function renderVideo() {
  await save();
  if (!project.scenes.some(s => s.image || s.prompt.trim())) {
    toast('Önce en az bir sahneye istem yaz.'); return;
  }
  try {
    const job = await api(`/api/projects/${project.id}/render`, { method: 'POST' });
    jobsCache.push(job);
    pollJobs();
    toast(project.scenes.some(s => !s.image && s.prompt.trim())
      ? 'Eksik kareler önce üretilecek, sonra video birleştirilecek.' : 'Video hazırlanıyor…');
  } catch (e) { toast(e.message, true); }
}

// ---------------------------------------------------------------- iş takibi
async function pollJobs() {
  clearTimeout(pollTimer);
  if (!project) return;
  try {
    const before = Object.fromEntries(jobsCache.map(j => [j.id, j.status]));
    jobsCache = await api(`/api/jobs?project=${project.id}`);
    let changed = false;
    for (const j of jobsCache) {
      const was = before[j.id];
      const finished = ['done', 'error', 'cancelled'].includes(j.status);
      if (finished && was && !['done', 'error', 'cancelled'].includes(was)) {
        changed = true;
        if (j.status === 'error') toast(`${j.label}: ${j.error}`, true);
        if (j.status === 'done' && j.kind === 'render') toast('Video hazır! 🎉');
      }
    }
    if (changed) mergeServer(await api(`/api/projects/${project.id}`));
    project.scenes.forEach(s => updateSceneCard(s));
    renderJobBar();
    const active = jobsCache.some(j => j.status === 'queued' || j.status === 'running');
    pollTimer = setTimeout(pollJobs, active ? 800 : 4000);
  } catch {
    pollTimer = setTimeout(pollJobs, 3000);
  }
}

function renderJobBar() {
  const active = jobsCache.filter(j => j.status === 'queued' || j.status === 'running');
  const bar = $('#jobbar');
  const renderBusy = active.some(j => j.kind === 'render');
  $('#render').disabled = renderBusy;
  $('#render').textContent = renderBusy ? '⏳ Video hazırlanıyor…' : '🎬 Videoyu oluştur';
  if (!active.length) { bar.classList.add('hidden'); return; }
  const cur = active.find(j => j.status === 'running') || active[0];
  bar.classList.remove('hidden');
  $('#jobLabel').textContent = cur.label + ':';
  $('#jobMsg').textContent = cur.message;
  $('#jobProgress').style.width = Math.round(cur.progress * 100) + '%';
  $('#jobQueue').textContent = active.length > 1 ? `+${active.length - 1} sırada` : '';
  $('#jobCancel').onclick = async () => {
    for (const j of active) await api(`/api/jobs/${j.id}/cancel`, { method: 'POST' });
    toast('İptal edildi.');
    pollJobs();
  };
}

// ---------------------------------------------------------------- bağlama
function bindInputs() {
  const bind = (sel, key, parse = v => v, target = () => project) => {
    const el = $(sel);
    const ev = el.type === 'checkbox' || el.tagName === 'SELECT' ? 'change' : 'input';
    el.addEventListener(ev, () => {
      const value = el.type === 'checkbox' ? el.checked : parse(el.value);
      if (value === undefined || Number.isNaN(value)) return;
      target()[key] = value;
      scheduleSave();
    });
  };
  const num = v => (v === '' ? undefined : parseFloat(v));
  const vid = () => project.video;
  bind('#title', 'title');
  bind('#idea', 'idea');
  bind('#style', 'style');
  bind('#negative', 'negative');
  bind('#translate', 'translate');
  bind('#imageModel', 'image_model');
  bind('#seconds', 'seconds', num, vid);
  bind('#fade', 'fade', num, vid);
  bind('#resolution', 'resolution', v => v, vid);
  bind('#captions', 'captions', v => v, vid);
  bind('#aiSeconds', 'ai_seconds', num, vid);
  bind('#aiSteps', 'ai_steps', v => (v === '' ? undefined : parseInt(v, 10)), vid);
  bind('#aiQuality', 'ai_quality', v => v, vid);

  document.querySelectorAll('#aspect button').forEach(b => b.addEventListener('click', () => {
    if (project.aspect === b.dataset.v) return;
    if (project.scenes.some(s => s.image) &&
        !confirm('Format değişirse yeni kareler bu formatta üretilir. Mevcut kareler kırpılarak kullanılır. Devam?')) return;
    project.aspect = b.dataset.v;
    setSeg('#aspect', project.aspect);
    renderScenes();
    scheduleSave();
  }));
  document.querySelectorAll('#mode button').forEach(b => b.addEventListener('click', () => {
    project.video.mode = b.dataset.v;
    setSeg('#mode', project.video.mode);
    renderMode();
    scheduleSave();
  }));

  const presets = $('#stylePresets');
  for (const [name, value] of Object.entries(STYLE_PRESETS)) {
    const btn = document.createElement('button');
    btn.textContent = name;
    btn.addEventListener('click', () => { project.style = value; $('#style').value = value; scheduleSave(); });
    presets.appendChild(btn);
  }

  $('#splitIdea').addEventListener('click', splitIdea);
  $('#addScene').addEventListener('click', addScene);
  $('#genMissing').addEventListener('click', () => genMany(true));
  $('#genAll').addEventListener('click', () => genMany(false));
  $('#render').addEventListener('click', renderVideo);
  $('#newProject').addEventListener('click', newProject);
  $('#projectSelect').addEventListener('change', e => openProject(e.target.value));
  $('#deleteProject').addEventListener('click', async () => {
    if (!confirm(`"${project.title}" projesi ve tüm dosyaları silinsin mi?`)) return;
    clearTimeout(saveTimer); saveTimer = null;
    await api(`/api/projects/${project.id}`, { method: 'DELETE' });
    project = null;
    const list = await refreshProjectList();
    if (list.length) openProject(list[0].id); else newProject();
  });
  $('#musicFile').addEventListener('change', async e => {
    const f = e.target.files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append('file', f);
    try { mergeServer(await api(`/api/projects/${project.id}/music`, { method: 'POST', body: fd })); }
    catch (err) { toast(err.message, true); }
    e.target.value = '';
  });
  $('#musicRemove').addEventListener('click', async () => {
    mergeServer(await api(`/api/projects/${project.id}/music`, { method: 'DELETE' }));
  });
  window.addEventListener('beforeunload', () => { if (saveTimer) save(); });
}

async function init() {
  status = await api('/api/status');
  const chip = $('#statusChip');
  if (status.mock) {
    chip.textContent = 'Test modu (AI yok)';
    $('#mockBanner').classList.remove('hidden');
  } else {
    chip.textContent = status.device === 'mps' ? 'Apple GPU (MPS) hazır' : `Cihaz: ${status.device}`;
    chip.classList.add('ok');
  }
  const im = $('#imageModel');
  for (const [k, label] of Object.entries(status.image_models)) {
    const o = document.createElement('option');
    o.value = k; o.textContent = label; im.appendChild(o);
  }
  const res = $('#resolution');
  for (const r of status.resolutions) {
    const o = document.createElement('option');
    o.value = r; o.textContent = r; res.appendChild(o);
  }
  bindInputs();
  const list = await refreshProjectList();
  const last = localStorage.getItem('studio:last');
  if (list.some(p => p.id === last)) await openProject(last);
  else if (list.length) await openProject(list[0].id);
  else await newProject();
}

init().catch(e => toast('Başlatılamadı: ' + e.message, true));
