'use strict';
// Utilidades comunes: API local, avisos, ventanas, archivos, resultados y documento actual.

/* ======================================================================
   Utilidades
   ====================================================================== */

const TOKEN = new URLSearchParams(location.search).get('t') || '';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const norm = (a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1])];
const inter = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
const kb = n => n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.round(n / 1024) + ' KB';

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'class') el.className = v;
    else if (k === 'style') el.style.cssText = v;
    else if (k in el && k !== 'list') el[k] = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false && k !== undefined) el.append(k instanceof Node ? k : String(k));
  return el;
}

async function api(op, payload) {
  const r = await fetch('/api/' + op, {
    method: 'POST', headers: { 'X-Token': TOKEN, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  });
  if (!r.ok) {
    let m = 'Error ' + r.status;
    try { m = (await r.json()).error; } catch (e) { /* sin detalle */ }
    throw new Error(m);
  }
  return (r.headers.get('Content-Type') || '').includes('json') ? r.json() : r.blob();
}

async function uploadFile(file) {
  const r = await fetch('/api/open', {
    method: 'POST', headers: { 'X-Token': TOKEN, 'X-Filename': encodeURIComponent(file.name) }, body: file,
  });
  const j = await r.json();
  if (!r.ok) throw new Error(`${file.name}: ${j.error}`);
  return j;
}

// En la ventana nativa de macOS solo cuentan los tipos MIME (las extensiones se ignoran).
const ACCEPT_DOCS = 'application/pdf,.pdf,image/*';
const ACCEPT_PDF = 'application/pdf,.pdf';

const pageUrl = (id, n, zoom, v = 0) => `/api/page?id=${id}&n=${n}&zoom=${zoom}&t=${TOKEN}&v=${v}`;

function toast(msg, kind = '', actions = [], ms = 6000) {
  const t = h('div', { class: 'toast ' + kind }, msg,
    actions.map(a => h('button', { onclick: () => { a.fn(); t.remove(); } }, a.label)));
  $('#toasts').append(t);
  setTimeout(() => t.remove(), ms + actions.length * 4000);
}

let busyCount = 0;
function busy(on, text = '') {
  busyCount += on ? 1 : -1;
  $('#busy').classList.toggle('on', busyCount > 0);
  if (on) $('.busy-text').textContent = text;
}
function busyText(text) { $('.busy-text').textContent = text; }

/** Ejecuta fn con el indicador de carga; los errores se muestran y devuelve undefined. */
async function run(text, fn) {
  busy(true, text);
  try { return await fn(); } catch (e) { toast(e.message, 'err'); return undefined; } finally { busy(false); }
}

function modal({ title, body, actions = [], wide = false }) {
  const bg = h('div', { class: 'modal-bg' });
  const close = () => bg.remove();
  const box = h('div', { class: 'modal', style: wide ? 'min-width:560px' : '' }, title && h('h2', {}, title), body,
    h('div', { class: 'actions' }, actions.map(a => h('button', {
      class: a.primary ? 'primary' : (a.danger ? 'danger' : ''),
      onclick: async () => { if ((await a.fn?.()) !== false) close(); },
    }, a.label))));
  bg.append(box);
  bg.addEventListener('mousedown', e => { if (e.target === bg) close(); });
  document.body.append(bg);
  box.querySelector('input,select,textarea')?.focus();
  return close;
}

function ask(title, label, value = '', { password = false, textarea = false } = {}) {
  return new Promise(res => {
    const inp = textarea ? h('textarea', { rows: 4 }, value) : h('input', { value, type: password ? 'password' : 'text' });
    let done = false;
    const finish = v => { if (!done) { done = true; res(v); } };
    const close = modal({
      title, body: h('label', {}, label, inp),
      actions: [{ label: 'Cancelar', fn: () => finish(null) }, { label: 'Aceptar', primary: true, fn: () => finish(inp.value) }],
    });
    inp.addEventListener('keydown', e => { if (e.key === 'Enter' && !textarea) { finish(inp.value); close(); } });
  });
}

function confirmBox(title, text, okLabel = 'Aceptar') {
  return new Promise(res => modal({
    title, body: h('p', {}, text),
    actions: [{ label: 'Cancelar', fn: () => res(false) }, { label: okLabel, primary: true, fn: () => res(true) }],
  }));
}

function pickFiles(accept = '', multiple = false) {
  return new Promise(res => {
    const inp = h('input', { type: 'file', accept, multiple, style: 'display:none' });
    inp.addEventListener('change', () => { res([...inp.files]); inp.remove(); });
    document.body.append(inp);
    inp.click();
  });
}

const fileToB64 = f => new Promise((res, rej) => {
  const r = new FileReader();
  r.onload = () => res(r.result.split(',')[1]);
  r.onerror = rej;
  r.readAsDataURL(f);
});

function dropTarget(el, cb) {
  el.addEventListener('dragover', e => {
    if (!e.dataTransfer.types.includes('Files')) return;
    e.preventDefault();
    el.classList.add('dropping');
  });
  el.addEventListener('dragleave', () => el.classList.remove('dropping'));
  el.addEventListener('drop', e => {
    el.classList.remove('dropping');
    if (!e.dataTransfer.files.length) return;
    e.preventDefault();
    e.stopPropagation();
    cb([...e.dataTransfer.files]);
  });
}
window.addEventListener('dragover', e => e.preventDefault());
window.addEventListener('drop', e => e.preventDefault());

/* ---- resultados: guardar y continuar en otra herramienta ---- */

async function saveResult(res, notes = []) {
  if (!res || !res.rid) {
    if (res?.errors?.length) toast('Errores:\n' + res.errors.join('\n'), 'err');
    return;
  }
  const single = res.files.length === 1 && res.files[0].name.toLowerCase().endsWith('.pdf');
  const cont = single ? [{ label: 'Seguir con este archivo…', fn: () => continueIn(res) }] : [];
  const extra = [...notes, ...(res.notes || [])].join(' · ');
  if (res.errors?.length) toast('Errores:\n' + res.errors.join('\n'), 'err');
  if (window.pywebview?.api?.save_result) {
    const paths = await window.pywebview.api.save_result(res.rid);
    if (!paths) {
      toast('No se ha guardado.', '', [{ label: 'Guardar…', fn: () => saveResult(res, notes) }]);
      return;
    }
    const names = paths.map(p => p.split(/[\\/]/).pop());
    toast(`Guardado: ${names.slice(0, 3).join(', ')}${names.length > 3 ? '…' : ''}${extra ? ' · ' + extra : ''}`, 'ok',
      [{ label: 'Mostrar', fn: () => window.pywebview.api.reveal(paths[0]) }, ...cont], 9000);
  } else {
    const a = h('a', { href: `/api/result?rid=${res.rid}&t=${TOKEN}`, download: res.files.length === 1 ? res.files[0].name : 'docguard.zip' });
    document.body.append(a);
    a.click();
    a.remove();
    toast(`Descargado${res.files.length > 1 ? ` (${res.files.length} archivos en un .zip)` : ''}${extra ? ' · ' + extra : ''}`, 'ok', cont, 9000);
  }
}

const CONTINUE_TOOLS = { edit: 'Editar PDF', watermark: 'Marca de agua', redact: 'Censurar', sign: 'Firma digital',
  pages: 'Páginas', protect: 'Contraseña' };

function continueIn(res) {
  const close = modal({
    title: 'Seguir trabajando con ' + res.files[0].name,
    body: h('div', { class: 'row' }, Object.entries(CONTINUE_TOOLS).map(([k, label]) => h('button', {
      onclick: async () => {
        close();
        const info = await run('Abriendo…', () => api('open_result', { rid: res.rid }));
        if (info) { showTool(k); TOOLS[k].loadInfo(info); }
      },
    }, label))),
    actions: [{ label: 'Cerrar' }],
  });
}

/* ======================================================================
   Documento actual (compartido entre herramientas)
   ====================================================================== */

let CURRENT = null;

function setCurrent(info) {
  if (!info || !info.pages?.length) return;
  CURRENT = info;
  const box = $('.current-doc');
  box.hidden = false;
  $('.cd-name', box).textContent = info.name;
  box.title = info.name;
}

function clearCurrent() {
  CURRENT = null;
  $('.current-doc').hidden = true;
}
