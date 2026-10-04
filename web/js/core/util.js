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
  if ((r.headers.get('Content-Type') || '').includes('json')) return r.json();
  const b = await r.blob();
  b.headers = r.headers;
  return b;
}

async function uploadFile(file) {
  const r = await fetch('/api/open', {
    method: 'POST', headers: { 'X-Token': TOKEN, 'X-Filename': encodeURIComponent(file.name) }, body: file,
  });
  const j = await r.json();
  if (!r.ok) throw new Error(`${file.name}: ${j.error}`);
  return unlockInfo(j);
}

/** Si el PDF tiene contraseña, la pide (hasta acertar o cancelar) y devuelve el documento ya abierto. */
async function unlockInfo(info) {
  if (!info?.encrypted || info.kind !== 'pdf') return info;
  const hidden = busyCount;  // el indicador de carga taparía la pregunta
  if (hidden) $('#busy').classList.remove('on');
  try {
    let label = `«${info.name}» está protegido. Escribe su contraseña:`;
    for (;;) {
      const pw = await ask('PDF con contraseña', label, '', { password: true });
      if (pw === null) return info;
      try { return await api('unlock', { id: info.id, password: pw }); } catch (e) { label = 'Contraseña incorrecta. Vuelve a intentarlo:'; }
    }
  } finally { if (hidden) $('#busy').classList.toggle('on', busyCount > 0); }
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

function modal({ title, body, actions = [], wide = false, onclose = null }) {
  const bg = h('div', { class: 'modal-bg' });
  let closed = false;
  const close = () => { bg.remove(); if (!closed) { closed = true; onclose?.(); } };
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
    setTimeout(() => inp.focus(), 50);
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

/** Guarda el resultado. `actions` = botones extra del aviso: {label, fn(rutas guardadas o null)}. */
/** Imprime el documento tal como está ahora (con las ediciones). En Windows y en el navegador el PDF se
 *  carga en un marco invisible y se abre el diálogo de impresión del sistema (impresión vectorial, con
 *  impresora, copias y páginas). En la ventana nativa de Mac se abre en Vista Previa para imprimirlo. */
function printDoc(info) {
  if (!info?.id) return toast('Abre primero un documento.', 'err');
  if (info.encrypted) return toast('El PDF tiene contraseña: quítala primero en «Contraseña».', 'err');
  if (window.pywebview?.api?.print_pdf && /Mac/.test(navigator.platform)) return window.pywebview.api.print_pdf(info.id);
  let f = $('#print-frame');
  if (!f) {
    f = h('iframe', { id: 'print-frame', title: 'Impresión', style: 'position:fixed;right:0;bottom:0;width:1px;height:1px;border:0;opacity:0;pointer-events:none' });
    document.body.append(f);
  }
  toast('Preparando la impresión…', '', [], 2000);
  f.onload = () => setTimeout(() => {
    try { f.contentWindow.focus(); f.contentWindow.print(); } catch (e) { toast('No se pudo abrir la impresión: ' + e.message, 'err'); }
  }, 300);
  f.src = `/api/pdf?id=${encodeURIComponent(info.id)}&t=${TOKEN}&v=${Date.now()}`;
}

/** ⌘P / Ctrl+P: imprime el documento que se está viendo (y no la pantalla de DocGuard). */
document.addEventListener('keydown', e => {
  if (!(e.metaKey || e.ctrlKey) || e.shiftKey || e.altKey || e.key.toLowerCase() !== 'p') return;
  e.preventDefault();
  const tool = $('.tool.active')?.id;
  if (tool === 'tool-redact') return toast('En Censurar las marcas aún no se han aplicado: guarda el PDF censurado y imprime ese.', 'err', [], 6000);
  const reading = typeof Library !== 'undefined' && !$('#tool-library .reader')?.hidden && Library.reading;
  printDoc((tool === 'tool-library' && reading) || (tool === 'tool-edit' && Edit.info) || CURRENT);
});

async function saveResult(res, notes = [], actions = []) {
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
      toast('No se ha guardado.', '', [{ label: 'Guardar…', fn: () => saveResult(res, notes, actions) }]);
      return null;
    }
    const names = paths.map(p => p.split(/[\\/]/).pop());
    toast(`Guardado: ${names.slice(0, 3).join(', ')}${names.length > 3 ? '…' : ''}${extra ? ' · ' + extra : ''}`, 'ok',
      [{ label: 'Mostrar', fn: () => window.pywebview.api.reveal(paths[0]) }, ...actions.map(a => ({ label: a.label, fn: () => a.fn(paths) })), ...cont],
      9000);
    return paths;
  }
  const a = h('a', { href: `/api/result?rid=${res.rid}&t=${TOKEN}`, download: res.files.length === 1 ? res.files[0].name : 'docguard.zip' });
  document.body.append(a);
  a.click();
  a.remove();
  toast(`Descargado${res.files.length > 1 ? ` (${res.files.length} archivos en un .zip)` : ''}${extra ? ' · ' + extra : ''}`, 'ok',
    [...actions.map(x => ({ label: x.label, fn: () => x.fn(null) })), ...cont], 9000);
  return true;
}

/** Copia un texto al portapapeles (también dentro de la ventana nativa). */
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch (e) { /* sin permiso: método clásico */ }
  const ta = h('textarea', { style: 'position:fixed;left:-9999px;top:0' }, text);
  document.body.append(ta);
  ta.select();
  let ok = false;
  try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
  ta.remove();
  return ok;
}

/** Abre un correo nuevo en el programa de correo con asunto y texto (no lo envía). */
function composeMail(subject, body) {
  const url = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  if (window.pywebview?.api?.compose) return window.pywebview.api.compose(url);
  window.location.href = url;
}

const CONTINUE_TOOLS = { watermark: 'Marca de agua (proteger)', edit: 'Editar PDF', redact: 'Censurar', sign: 'Firma digital',
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
  if (typeof Tabs !== 'undefined') Tabs.add(info);
  const box = $('.current-doc');
  box.hidden = false;
  $('.cd-name', box).textContent = info.name;
  box.title = info.name;
  updateTitle();
}

function clearCurrent() {
  CURRENT = null;
  $('.current-doc').hidden = true;
  updateTitle();
}

/** Título de la ventana (y de la barra de tareas): el documento que se está viendo. */
function updateTitle(name = CURRENT?.name) {
  document.title = name ? `${name} — DocGuard` : 'DocGuard';
  window.pywebview?.api?.set_title?.(name || '');
}
window.addEventListener('pywebviewready', () => updateTitle());  // en Windows la API llega tras cargar

/* ======================================================================
   Paneles con anchura ajustable
   ====================================================================== */

/** Añade un tirador al borde (edge: 'right' o 'left') para cambiar la anchura del panel. */
function makeResizable(panel, edge, key, min = 150, max = 700, onresize = null) {
  try { const w = +localStorage.getItem('dg_w_' + key); if (w) panel.style.width = w + 'px'; } catch (e) { /* sin almacenamiento */ }
  // separador entre el panel y el resto (así no se desplaza con el contenido del panel)
  const grip = h('div', { class: 'splitter', title: 'Arrastra para cambiar el tamaño' });
  if (edge === 'right') panel.after(grip); else panel.before(grip);
  new MutationObserver(() => { grip.hidden = panel.hidden; }).observe(panel, { attributes: true, attributeFilter: ['hidden'] });
  grip.hidden = panel.hidden;
  grip.addEventListener('mousedown', e => {
    e.preventDefault();
    const x0 = e.clientX, w0 = panel.getBoundingClientRect().width;
    document.body.classList.add('resizing');
    const mv = ev => {
      const w = clamp(w0 + (edge === 'right' ? ev.clientX - x0 : x0 - ev.clientX), min, max);
      panel.style.width = w + 'px';
      onresize?.(w);
    };
    window.addEventListener('mousemove', mv);
    window.addEventListener('mouseup', () => {
      window.removeEventListener('mousemove', mv);
      document.body.classList.remove('resizing');
      try { localStorage.setItem('dg_w_' + key, Math.round(panel.getBoundingClientRect().width)); } catch (err) { /* sin almacenamiento */ }
      onresize?.(panel.getBoundingClientRect().width, true);
    }, { once: true });
  });
}
