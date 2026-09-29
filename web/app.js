'use strict';

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
  for (const k of kids.flat()) if (k != null && k !== false) el.append(k instanceof Node ? k : String(k));
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

/* ======================================================================
   Visor de páginas
   ====================================================================== */

class Viewer {
  constructor(host) {
    this.el = h('div', { class: 'viewer' }, this.empty = h('div', { class: 'empty' }, 'Abre o arrastra aquí un documento'));
    this.wrap = h('div', { class: 'page-wrap', style: 'display:none' }, this.img = h('img', { alt: '' }), this.ov = h('div', { class: 'ov' }));
    this.el.append(this.wrap);
    const b = (t, f, title) => h('button', { onclick: f, title }, t);
    this.bar = h('div', { class: 'vbar', style: 'display:none' },
      b('◀', () => this.go(this.n - 1), 'Página anterior'), this.lbl = h('span'), b('▶', () => this.go(this.n + 1), 'Página siguiente'),
      b('−', () => this.setZoom(this.zoom / 1.2), 'Alejar'), b('+', () => this.setZoom(this.zoom * 1.2), 'Acercar'),
      b('Ajustar', () => this.fit(), 'Ajustar al ancho'));
    host.append(this.el, this.bar);
    this.info = null; this.n = 0; this.zoom = 1; this.v = 0; this.fitMode = true;
    this.onpage = null; this.onrender = null;
    new ResizeObserver(() => { if (this.info && this.fitMode) this.fit(); }).observe(this.el);
  }
  load(info) {
    this.info = info; this.n = 0; this.v++;
    this.empty.style.display = 'none'; this.wrap.style.display = ''; this.bar.style.display = '';
    this.fit();
  }
  get size() { return this.info.pages[this.n]; }
  fit() {
    if (!this.info) return;
    const w = this.el.clientWidth - 40;
    if (w <= 0) return;
    this.fitMode = true;
    this.zoom = clamp(w / this.size[0], 0.2, 2.2);
    this.render();
  }
  setZoom(z) { this.fitMode = false; this.zoom = clamp(z, 0.2, 5); this.render(); }
  go(n) {
    if (!this.info) return;
    n = clamp(n, 0, this.info.pages.length - 1);
    if (n === this.n) return;
    this.n = n;
    this.el.scrollTop = 0;
    this.fitMode ? this.fit() : this.render();
    this.onpage?.(n);
  }
  refresh() { this.v++; this.render(); }
  render() {
    if (!this.info) return;
    const [w, hh] = this.size;
    this.wrap.style.width = w * this.zoom + 'px';
    this.wrap.style.height = hh * this.zoom + 'px';
    const z = (this.zoom * (window.devicePixelRatio || 1)).toFixed(3);
    this.img.src = pageUrl(this.info.id, this.n, z, this.v);
    this.lbl.textContent = `${this.n + 1} / ${this.info.pages.length}`;
    this.onrender?.();
  }
  pt(e) {
    const r = this.wrap.getBoundingClientRect();
    return [(e.clientX - r.left) / this.zoom, (e.clientY - r.top) / this.zoom];
  }
  place(d, r) {
    const z = this.zoom;
    Object.assign(d.style, { left: r[0] * z + 'px', top: r[1] * z + 'px', width: (r[2] - r[0]) * z + 'px', height: (r[3] - r[1]) * z + 'px' });
  }
  box(rect, cls, parent = this.ov) {
    const d = h('div', { class: 'bx ' + cls });
    this.place(d, rect);
    parent.append(d);
    return d;
  }
  clear() { this.ov.innerHTML = ''; }
  /** Arrastre del ratón desde el evento e. Devuelve {rect, points, moved}. */
  drag(e, { ink = false, show = true } = {}) {
    return new Promise(res => {
      const p0 = this.pt(e);
      const pts = [p0];
      let el = null, line = null;
      if (ink) {
        el = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        el.setAttribute('style', 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none');
        line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
        line.setAttribute('fill', 'none'); line.setAttribute('stroke', '#1a4fd6'); line.setAttribute('stroke-width', '2');
        el.append(line);
        this.ov.append(el);
      } else if (show) {
        el = h('div', { class: 'drag-box' });
        this.ov.append(el);
      }
      const mv = ev => {
        const p = this.pt(ev);
        pts.push(p);
        if (ink) line.setAttribute('points', pts.map(q => `${q[0] * this.zoom},${q[1] * this.zoom}`).join(' '));
        else if (el) this.place(el, norm(p0, p));
      };
      const up = ev => {
        window.removeEventListener('mousemove', mv);
        el?.remove();
        const p = this.pt(ev);
        const rect = norm(p0, p);
        res({ rect, points: pts, moved: (rect[2] - rect[0]) + (rect[3] - rect[1]) > 3 });
      };
      window.addEventListener('mousemove', mv);
      window.addEventListener('mouseup', up, { once: true });
    });
  }
  /** Hace que el cuadro el se pueda mover (arrastrando) y redimensionar (esquina). */
  transformable(el, rect, onDone, { keepRatio = false, grip = null } = {}) {
    const handle = h('div', { class: 'handle' });
    el.append(handle);
    const start = (e, mode) => {
      if (e.button !== 0) return;
      e.preventDefault(); e.stopPropagation();
      const p0 = this.pt(e);
      let r = rect.slice();
      const ratio = (rect[2] - rect[0]) / (rect[3] - rect[1]);
      const mv = ev => {
        const p = this.pt(ev), dx = p[0] - p0[0], dy = p[1] - p0[1];
        if (mode === 'move') r = [rect[0] + dx, rect[1] + dy, rect[2] + dx, rect[3] + dy];
        else {
          let w = Math.max(8, rect[2] - rect[0] + dx), hh = Math.max(8, rect[3] - rect[1] + dy);
          if (keepRatio) hh = w / ratio;
          r = [rect[0], rect[1], rect[0] + w, rect[1] + hh];
        }
        this.place(el, r);
      };
      window.addEventListener('mousemove', mv);
      window.addEventListener('mouseup', () => {
        window.removeEventListener('mousemove', mv);
        if (r.some((v, i) => Math.abs(v - rect[i]) > 0.5)) onDone(r.map(v => Math.round(v * 100) / 100));
      }, { once: true });
    };
    handle.addEventListener('mousedown', e => start(e, 'resize'));
    (grip || el).addEventListener('mousedown', e => { if (e.target !== handle) start(e, 'move'); });
  }
}

/* ======================================================================
   Fuentes y color para la edición directa
   ====================================================================== */

const FONT_CACHE = {};

function fallbackFamily(name, flags = 0) {
  const n = (name || '').toLowerCase();
  if (/cour|mono/.test(n)) return '"Courier New", Courier, monospace';
  if (/times|roman|tiro/.test(n)) return '"Times New Roman", Times, serif';
  if (/georgia/.test(n)) return 'Georgia, serif';
  if (/garamond/.test(n)) return 'Garamond, "Times New Roman", serif';
  if (/cambria/.test(n)) return 'Cambria, Georgia, serif';
  if (/calibri/.test(n)) return 'Calibri, Carlito, Arial, sans-serif';
  if (/verdana/.test(n)) return 'Verdana, sans-serif';
  if (/tahoma/.test(n)) return 'Tahoma, sans-serif';
  if (/trebuchet/.test(n)) return '"Trebuchet MS", sans-serif';
  if (/arial|helv|helvetica/.test(n)) return 'Arial, Helvetica, sans-serif';
  return flags & 4 ? '"Times New Roman", serif' : 'Arial, Helvetica, sans-serif';
}

/** Carga (una vez) una fuente del servidor y devuelve la pila CSS a usar. */
async function cssFont(url, name, flags) {
  const fb = fallbackFamily(name, flags);
  if (!url) return fb;
  if (!(url in FONT_CACHE)) {
    const fam = 'dg' + Object.keys(FONT_CACHE).length;
    FONT_CACHE[url] = new FontFace(fam, `url(${url})`).load()
      .then(f => { document.fonts.add(f); return fam; }).catch(() => null);
  }
  const fam = await FONT_CACHE[url];
  return fam ? `"${fam}", ${fb}` : fb;
}

function fontForKey(key) {
  if (key.startsWith('sys:')) return cssFont(`/api/font?key=${encodeURIComponent(key)}&t=${TOKEN}`, key, 0);
  return Promise.resolve(fallbackFamily(key.slice(5)));
}

/** Color de la página junto a un punto (para tapar el texto original mientras se edita). */
function pageColorAt(viewer, x, y) {
  try {
    const img = viewer.img;
    if (!viewer._cv || viewer._cvSrc !== img.src) {
      const c = document.createElement('canvas');
      c.width = img.naturalWidth; c.height = img.naturalHeight;
      c.getContext('2d').drawImage(img, 0, 0);
      viewer._cv = c; viewer._cvSrc = img.src;
    }
    const k = img.naturalWidth / viewer.size[0];
    const d = viewer._cv.getContext('2d').getImageData(clamp(Math.round(x * k), 0, img.naturalWidth - 1),
      clamp(Math.round(y * k), 0, img.naturalHeight - 1), 1, 1).data;
    return `rgb(${d[0]},${d[1]},${d[2]})`;
  } catch (e) { return '#fff'; }
}

/* ======================================================================
   Listas de archivos
   ====================================================================== */

class FileList {
  constructor(el, { multiple = true, accept = '', onchange = null, onselect = null, hint = null } = {}) {
    Object.assign(this, { el, multiple, accept, onchange, onselect });
    this.items = []; this.cur = 0;
    this.hint = hint || (multiple ? 'Arrastra aquí los archivos o' : 'Arrastra aquí el archivo o');
    dropTarget(el, files => this.add(files));
    this.render();
  }
  async add(files) {
    if (!files.length) return;
    if (!this.multiple) files = files.slice(0, 1);
    const infos = [];
    busy(true, 'Abriendo…');
    try {
      for (const f of files) {
        try { infos.push(await uploadFile(f)); } catch (e) { toast(e.message, 'err'); }
      }
    } finally { busy(false); }
    this.items = this.multiple ? this.items.concat(infos) : infos;
    if (!this.multiple || this.items.length === infos.length) this.cur = 0;
    this.render();
    this.onchange?.(this.items);
    if (infos.length) this.onselect?.(this.items[this.cur]);
  }
  setItems(items) { this.items = items; this.cur = 0; this.render(); this.onchange?.(items); this.onselect?.(items[0]); }
  get current() { return this.items[this.cur]; }
  get ids() { return this.items.map(i => i.id); }
  render() {
    this.el.innerHTML = '';
    this.items.forEach((it, i) => {
      const row = h('div', { class: 'file' + (this.onselect && i === this.cur ? ' cur' : ''), draggable: true, title: it.name },
        h('span', { class: 'n' }, it.name), h('small', {}, kb(it.size)),
        this.multiple && h('button', { title: 'Subir', onclick: e => { e.stopPropagation(); this.move(i, i - 1); } }, '↑'),
        this.multiple && h('button', { title: 'Bajar', onclick: e => { e.stopPropagation(); this.move(i, i + 1); } }, '↓'),
        h('button', { title: 'Quitar', onclick: e => { e.stopPropagation(); this.remove(i); } }, '✕'));
      row.addEventListener('click', () => { if (this.onselect) { this.cur = i; this.render(); this.onselect(it); } });
      row.addEventListener('dragstart', e => e.dataTransfer.setData('text/x-idx', i));
      row.addEventListener('dragover', e => { if (e.dataTransfer.types.includes('text/x-idx')) e.preventDefault(); });
      row.addEventListener('drop', e => {
        const from = e.dataTransfer.getData('text/x-idx');
        if (from !== '') { e.preventDefault(); e.stopPropagation(); this.move(+from, i); }
      });
      this.el.append(row);
    });
    this.el.append(h('div', { class: 'hint' }, this.hint + ' ',
      h('button', { onclick: async () => this.add(await pickFiles(this.accept, this.multiple)) }, this.multiple ? 'Añadir archivos…' : 'Elegir archivo…')));
  }
  move(i, j) {
    if (j < 0 || j >= this.items.length || i === j) return;
    const [it] = this.items.splice(i, 1);
    this.items.splice(j, 0, it);
    this.cur = j;
    this.render();
    this.onchange?.(this.items);
  }
  remove(i) {
    const [it] = this.items.splice(i, 1);
    api('close', { id: it.id }).catch(() => {});
    this.cur = clamp(this.cur, 0, Math.max(0, this.items.length - 1));
    this.render();
    this.onchange?.(this.items);
    if (this.items.length) this.onselect?.(this.current); else this.onselect?.(null);
  }
}

/* ======================================================================
   Firmas manuscritas (compartido entre Editar y Firma digital)
   ====================================================================== */

const Sigs = {
  items: [],
  async load() {
    try { this.items = (await api('sigimgs')).items; } catch (e) { this.items = []; }
    document.dispatchEvent(new Event('sigs-changed'));
    return this.items;
  },
  src(it) { return 'data:image/png;base64,' + it.png; },
  ratio(id) {
    return new Promise(res => {
      const it = this.items.find(s => s.id === id);
      if (!it) return res(3);
      const im = new Image();
      im.onload = () => res(im.width / im.height);
      im.src = this.src(it);
    });
  },
  /** Ventana para dibujar o subir una firma. Devuelve el id guardado. */
  create() {
    return new Promise(res => {
      const cv = h('canvas', { class: 'sig-canvas', width: 520, height: 200 });
      const ctx = cv.getContext('2d');
      ctx.lineWidth = 3; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = '#1a3fa8';
      let drawing = false, drawn = false, upload = null;
      const pos = e => { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * cv.width / r.width, (e.clientY - r.top) * cv.height / r.height]; };
      cv.addEventListener('pointerdown', e => { drawing = true; drawn = true; upload = null; ctx.beginPath(); ctx.moveTo(...pos(e)); cv.setPointerCapture(e.pointerId); });
      cv.addEventListener('pointermove', e => { if (drawing) { ctx.lineTo(...pos(e)); ctx.stroke(); } });
      cv.addEventListener('pointerup', () => { drawing = false; });
      const color = h('select', { onchange: () => { ctx.strokeStyle = color.value; } },
        h('option', { value: '#1a3fa8' }, 'Azul'), h('option', { value: '#111111' }, 'Negro'));
      const white = h('input', { type: 'checkbox', checked: true });
      const body = h('div', {},
        h('p', { class: 'muted' }, 'Dibuja tu firma con el ratón o el trackpad, o sube una imagen (foto o escaneo).'),
        cv,
        h('div', { class: 'row' }, 'Color', color,
          h('button', { onclick: () => { ctx.clearRect(0, 0, cv.width, cv.height); drawn = false; upload = null; } }, 'Borrar'),
          h('button', {
            onclick: async () => {
              const [f] = await pickFiles('image/*');
              if (!f) return;
              upload = await fileToB64(f);
              const im = new Image();
              im.onload = () => {
                ctx.clearRect(0, 0, cv.width, cv.height);
                const s = Math.min(cv.width / im.width, cv.height / im.height);
                ctx.drawImage(im, (cv.width - im.width * s) / 2, (cv.height - im.height * s) / 2, im.width * s, im.height * s);
              };
              im.src = 'data:image/*;base64,' + upload;
            },
          }, 'Subir imagen…')),
        h('label', { class: 'inline' }, white, 'Quitar el fondo blanco (para imágenes escaneadas)'));
      modal({
        title: 'Nueva firma manuscrita', body,
        actions: [{ label: 'Cancelar', fn: () => res(null) }, {
          label: 'Guardar firma', primary: true, fn: async () => {
            if (!drawn && !upload) { toast('Dibuja o sube una firma.', 'err'); return false; }
            const png = upload || cv.toDataURL('image/png').split(',')[1];
            const r = await run('Guardando…', () => api('sigimg/save', { png, remove_white: !!upload && white.checked }));
            if (!r) return false;
            await this.load();
            res(r.id);
          },
        }],
      });
    });
  },
  /** Galería con selección. onpick(id) */
  gallery(selected, onpick) {
    const g = h('div', { class: 'sig-gallery' });
    for (const it of this.items) {
      g.append(h('div', { class: 'sig-item' + (it.id === selected ? ' sel' : ''), onclick: () => onpick(it.id), title: 'Usar esta firma' },
        h('img', { src: this.src(it) }),
        h('button', {
          title: 'Borrar', onclick: async e => {
            e.stopPropagation();
            if (await confirmBox('Borrar firma', '¿Borrar esta firma guardada?', 'Borrar')) {
              await api('sigimg/delete', { id: it.id });
              await this.load();
              if (it.id === selected) onpick(null);
            }
          },
        }, '✕')));
    }
    if (!this.items.length) g.append(h('small', {}, 'Aún no tienes firmas guardadas.'));
    return g;
  },
};

/* ======================================================================
   EDITAR PDF
   ====================================================================== */

const Edit = {
  init() {
    this.root = $('#tool-edit');
    this.props = $('.props', this.root);
    this.viewer = new Viewer($('.viewer-host', this.root));
    this.viewer.onrender = () => this.draw();
    this.viewer.onpage = () => { this.sel = null; this.refresh(); };
    this.viewer.ov.addEventListener('mousedown', e => this.down(e));
    this.mode = 'text'; this.sel = null; this.point = null; this.st = null;
    this.annotKind = 'highlight'; this.color = '#ffd400'; this.widgetType = 'text'; this.sig = null;
    this.textOpts = { font: 'base:helv', size: 12, color: '#000000', bold: false, italic: false };
    this.fonts = [];
    dropTarget(this.viewer.el, f => this.openFile(f[0]));
    $('[data-act=open]', this.root).onclick = async () => { const [f] = await pickFiles(ACCEPT_DOCS); if (f) this.openFile(f); };
    $('[data-act=undo]', this.root).onclick = () => this.undo();
    $('[data-act=ocr]', this.root).onclick = () => this.ocrDialog();
    this.shape = { kind: 'rect', stroke: '#d62828', fill: '#ffe066', filled: false, width: 2 };
    document.addEventListener('paste', e => this.onPaste(e));
    document.addEventListener('copy', e => { if (this.root.classList.contains('active') && this.mode === 'select' && this.region && !document.activeElement.isContentEditable && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) { e.preventDefault(); this.copyRegion(); } });
    $('[data-act=export]', this.root).onclick = async () => saveResult(await run('Preparando…', () => api('edit/export', { id: this.info.id })));
    $$('[data-mode]', this.root).forEach(b => b.onclick = () => {
      $$('[data-mode]', this.root).forEach(x => x.classList.toggle('on', x === b));
      if (this.inline) this.commitInline();
      this.mode = b.dataset.mode; this.sel = null; this.point = null; this.selSpans = new Set(); this.draw();
    });
    document.addEventListener('keydown', e => {
      if (!this.root.classList.contains('active') || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)
        || document.activeElement.isContentEditable) return;
      if ((e.metaKey || e.ctrlKey) && e.key === 'z') { e.preventDefault(); this.undo(); }
      const hasSel = this.mode === 'text' ? this.selSpans?.size > 0 : this.sel != null;
      if ((e.key === 'Delete' || e.key === 'Backspace') && hasSel) { e.preventDefault(); this.deleteSel(); }
      if (e.key === 'Escape' && this.mode === 'text' && hasSel) { this.selSpans = new Set(); this.draw(); }
      const arrows = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
      if (this.mode === 'text' && hasSel && arrows[e.key]) {
        e.preventDefault();
        const k = e.shiftKey ? 10 : 1;
        this.moveSel(arrows[e.key][0] * k, arrows[e.key][1] * k);
      }
    });
    document.addEventListener('sigs-changed', () => { if (this.mode === 'handsign') this.draw(); });
    api('fonts').then(r => { this.fonts = r.fonts; }).catch(() => {});
    this.draw();
  },
  async openFile(f) {
    const info = await run('Abriendo…', () => uploadFile(f));
    if (info) this.loadInfo(info);
  },
  loadInfo(info) {
    if (info.encrypted) return toast('El PDF tiene contraseña: quítala primero en «Contraseña».', 'err');
    if (!info.pages.length) return toast('Solo se pueden editar PDFs e imágenes.', 'err');
    this.info = info; this.sel = null; this.st = null;
    setCurrent(info);
    $('.doc-name', this.root).textContent = info.name;
    $('[data-act=export]', this.root).disabled = false;
    this.viewer.load(info);
    this.refresh();
  },
  async refresh(rerender = false) {
    if (!this.info) return;
    const n = this.viewer.n;
    try { this.st = await api('edit/state', { id: this.info.id, n }); } catch (e) { return toast(e.message, 'err'); }
    this.st.n = n;
    $('[data-act=undo]', this.root).disabled = !this.st.can_undo;
    if (rerender) this.viewer.refresh(); else this.draw();
  },
  async op(name, payload, busyMsg = 'Aplicando…', keepSel = false) {
    if (keepSel) this.lastSel = (this.st?.spans || []).filter(s => this.selSpans?.has(s.i)).map(s => s.bbox);
    const r = await run(busyMsg, () => api('edit/' + name, { id: this.info.id, n: this.viewer.n, ...payload }));
    if (r === undefined) return false;
    if (r.message && /sustituta/.test(r.message)) toast('No se encontró la fuente original; se ha usado ' + r.message.replace(' (sustituta)', '') + '.', '', [], 4000);
    this.sel = null;
    if (!keepSel) this.selSpans = new Set();
    await this.refresh(true);
    return true;
  },
  async undo() {
    if (!this.info) return;
    await run('Deshaciendo…', () => api('edit/undo', { id: this.info.id }));
    this.sel = null;
    this.refresh(true);
  },
  deleteSel() {
    if (this.mode === 'text') { const indices = [...this.selSpans]; this.selSpans = new Set(); return this.op('delete_spans', { indices }); }
    if (this.mode === 'image') this.op('delete_image', { xref: this.sel });
    else if (this.mode === 'annot' || this.mode === 'shapes') this.op('delete_annot', { xref: this.sel });
    else if (this.mode === 'forms') this.op('delete_widget', { xref: this.sel });
  },

  /* ---- dibujo de la capa y del panel ---- */
  draw() {
    const v = this.viewer;
    v.clear();
    v.ov.classList.toggle('draw', ['addtext', 'annot', 'forms', 'handsign', 'shapes', 'select'].includes(this.mode) || (this.mode === 'image' && this.pendingImage));
    this.props.innerHTML = '';
    if (!this.info) {
      this.props.append(h('p', { class: 'muted' }, 'Abre un PDF para editarlo: cambiar textos respetando la fuente, añadir texto, mover o borrar imágenes, anotar, crear y rellenar formularios y firmar a mano.'));
      return;
    }
    const st = this.st;
    if (!st || st.n !== v.n) return;
    this['draw_' + this.mode]?.(st);
  },

  fontSelect(value, withAuto = null) {
    const opts = [];
    if (withAuto) opts.push(h('option', { value: 'auto' }, `Automática: ${withAuto}`));
    for (const f of this.fonts) opts.push(h('option', { value: f.key }, f.label));
    const s = h('select', {}, opts);
    s.value = value;
    return s;
  },

  draw_text(st) {
    const v = this.viewer;
    this.selSpans = this.selSpans || new Set();
    for (const s of st.spans) {
      const d = v.box(s.bbox, 'span' + (this.selSpans.has(s.i) ? ' sel' : ''));
      d.dataset.i = s.i;
      d.title = `${s.font} · ${s.size} pt — doble clic para escribir`;
      d.addEventListener('mousedown', e => this.spanDown(e, s));
      d.addEventListener('dblclick', e => { e.stopPropagation(); this.startInline(s, e); });
    }
    const sel = st.spans.filter(x => this.selSpans.has(x.i));
    if (!sel.length) {
      this.props.append(h('h3', {}, 'Editar texto'),
        h('p', { class: 'muted' }, st.spans.length ? 'Escribe directamente sobre el PDF:' : 'Esta página no tiene texto editable (puede ser un escaneo). Usa «Añadir texto» o «Censurar» con OCR.'),
        st.spans.length && h('ul', { class: 'help' },
          h('li', {}, h('b', {}, 'Doble clic'), ' en un texto para escribir en él (Intro guarda, Esc cancela).'),
          h('li', {}, h('b', {}, 'Clic'), ' para seleccionar; ', h('b', {}, 'arrastra'), ' para moverlo.'),
          h('li', {}, h('b', {}, 'Arrastra en una zona vacía'), ' para seleccionar varios textos; Mayús+clic añade o quita.'),
          h('li', {}, h('b', {}, 'Supr'), ' borra la selección; las ', h('b', {}, 'flechas'), ' la desplazan (Mayús = 10 pt).')));
      return;
    }
    if (sel.length > 1) {
      this.props.append(h('h3', {}, `${sel.length} textos seleccionados`),
        h('p', { class: 'muted' }, 'Arrástralos para moverlos juntos o pulsa Supr para borrarlos.'),
        h('button', { class: 'wide danger', onclick: () => this.deleteSel() }, 'Borrar selección'));
      return;
    }
    const s = sel[0];
    const font = this.fontSelect('auto', s.font);
    const size = h('input', { type: 'number', value: s.size, step: 0.5, min: 3, class: 'num' });
    const color = h('input', { type: 'color', value: s.color });
    const bold = h('input', { type: 'checkbox', checked: s.bold });
    const italic = h('input', { type: 'checkbox', checked: s.italic });
    this.props.append(h('h3', {}, 'Texto seleccionado'),
      h('p', { class: 'sel-text' }, s.text),
      h('button', { class: 'primary wide', onclick: () => this.startInline(s) }, 'Escribir en el PDF'),
      h('h3', {}, 'Formato'),
      h('label', {}, 'Fuente', font),
      h('div', { class: 'row' }, 'Tamaño', size, 'Color', color),
      h('div', { class: 'row' }, h('label', { class: 'inline' }, bold, 'Negrita'), h('label', { class: 'inline' }, italic, 'Cursiva')),
      h('small', {}, `Original: ${s.font}, ${s.size} pt`),
      h('button', {
        class: 'wide', onclick: () => this.op('replace_text', {
          i: s.i, text: s.text, font: font.value, size: +size.value, color: color.value, bold: bold.checked, italic: italic.checked,
        }),
      }, 'Aplicar formato'),
      h('button', { class: 'wide danger', onclick: () => this.deleteSel() }, 'Borrar texto'));
  },

  /* ---- selección, movimiento y escritura directa ---- */
  spanDown(e, s) {
    if (e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    if (this.inline) { this.commitInline(); return; }
    const wasOnly = this.selSpans.has(s.i) && this.selSpans.size === 1;
    if (e.shiftKey) { this.selSpans.has(s.i) ? this.selSpans.delete(s.i) : this.selSpans.add(s.i); }
    else if (!this.selSpans.has(s.i)) this.selSpans = new Set([s.i]);
    this.draw();
    if (!this.selSpans.has(s.i)) return;
    const v = this.viewer, p0 = v.pt(e);
    const boxes = $$('.bx.span.sel', v.ov);
    let dx = 0, dy = 0, moved = false;
    const mv = ev => {
      const p = v.pt(ev);
      dx = p[0] - p0[0]; dy = p[1] - p0[1];
      if (Math.abs(dx) + Math.abs(dy) > 2 / v.zoom * 2) moved = true;
      if (moved) boxes.forEach(b => { b.style.transform = `translate(${dx * v.zoom}px, ${dy * v.zoom}px)`; });
    };
    window.addEventListener('mousemove', mv);
    window.addEventListener('mouseup', ev => {
      window.removeEventListener('mousemove', mv);
      if (moved) this.moveSel(dx, dy);
      else if (wasOnly && !e.shiftKey) this.startInline(s, ev);
    }, { once: true });
  },
  async moveSel(dx, dy) {
    const indices = [...this.selSpans];
    const ok = await this.op('move_spans', { indices, dx: Math.round(dx * 100) / 100, dy: Math.round(dy * 100) / 100 }, 'Moviendo…', true);
    if (ok) this.reselectMoved(indices.length, dx, dy);
  },
  /** Tras mover, vuelve a seleccionar los textos en su nueva posición. */
  reselectMoved(count, dx, dy) {
    const prev = this.lastSel || [];
    const moved = prev.map(b => [b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy]);
    const found = new Set();
    for (const r of moved) {
      let best = null, bd = 1e9;
      for (const s of this.st.spans) {
        const d = Math.abs(s.bbox[0] - r[0]) + Math.abs(s.bbox[1] - r[1]);
        if (d < bd) { bd = d; best = s; }
      }
      if (best && bd < 6) found.add(best.i);
    }
    this.selSpans = found;
    this.draw();
  },
  async startInline(s, ev) {
    if (this.inline) this.commitInline();
    const v = this.viewer, z = v.zoom;
    const [x0, y0, x1, y1] = s.bbox;
    const fam = await cssFont(`/api/font?id=${this.info.id}&n=${v.n}&name=${encodeURIComponent(s.rawfont)}&t=${TOKEN}`, s.font, s.flags);
    const el = h('div', { class: 'inline-edit', contentEditable: 'true', spellcheck: false });
    el.textContent = s.text;
    Object.assign(el.style, {
      left: x0 * z + 'px', top: y0 * z + 'px', minWidth: (x1 - x0) * z + 'px', height: (y1 - y0) * z + 'px',
      lineHeight: (y1 - y0) * z + 'px', fontSize: s.size * z + 'px', fontFamily: fam, color: s.color,
      fontWeight: s.bold ? 'bold' : 'normal', fontStyle: s.italic ? 'italic' : 'normal',
      background: pageColorAt(v, x0 - 1.5, y0 + (y1 - y0) / 2),
    });
    v.ov.append(el);
    this.inline = { el, s };
    el.focus();
    const r = ev && document.caretRangeFromPoint ? document.caretRangeFromPoint(ev.clientX, ev.clientY) : null;
    const sel = window.getSelection();
    if (r && el.contains(r.startContainer)) { sel.removeAllRanges(); sel.addRange(r); }
    else { const rg = document.createRange(); rg.selectNodeContents(el); rg.collapse(false); sel.removeAllRanges(); sel.addRange(rg); }
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); this.commitInline(); }
      if (e.key === 'Escape') { e.preventDefault(); this.cancelInline(); }
      e.stopPropagation();
    });
    el.addEventListener('mousedown', e => e.stopPropagation());
  },
  cancelInline() {
    this.inline?.el.remove();
    this.inline = null;
  },
  commitInline() {
    const it = this.inline;
    if (!it) return;
    this.inline = null;
    const text = it.el.innerText.replace(/\n+/g, it.isNew ? '\n' : ' ').replace(/\u00a0/g, ' ');
    if (it.isNew) {
      it.el.remove();
      if (text.trim()) this.op('add_text', { x: it.x, y: it.y, text: text.replace(/\n$/, ''), ...this.textOpts });
      return;
    }
    if (text === it.s.text) { it.el.remove(); return; }
    this.op('replace_text', { i: it.s.i, text: text.trim() ? text : '' }).then(() => it.el.remove());
  },

  draw_addtext() {
    const o = this.textOpts;
    const font = this.fontSelect(o.font);
    const size = h('input', { type: 'number', value: o.size, min: 3, step: 0.5, class: 'num' });
    const color = h('input', { type: 'color', value: o.color });
    const bold = h('input', { type: 'checkbox', checked: o.bold });
    const italic = h('input', { type: 'checkbox', checked: o.italic });
    const save = async () => {
      Object.assign(o, { font: font.value, size: +size.value, color: color.value, bold: bold.checked, italic: italic.checked });
      if (this.inline?.isNew) { await this.styleNew(this.inline.el); this.inline.el.focus(); }
    };
    [font, size, color, bold, italic].forEach(el => el.addEventListener('change', save));
    this.props.append(h('h3', {}, 'Añadir texto'),
      h('p', { class: 'muted' }, 'Haz clic en la página y escribe directamente. Intro = nueva línea; haz clic fuera o pulsa Ctrl/⌘+Intro para fijarlo; Esc cancela.'),
      h('label', {}, 'Fuente', font),
      h('div', { class: 'row' }, 'Tamaño', size, 'Color', color),
      h('div', { class: 'row' }, h('label', { class: 'inline' }, bold, 'Negrita'), h('label', { class: 'inline' }, italic, 'Cursiva')),
      this.inline?.isNew && h('button', { class: 'primary wide', onclick: () => this.commitInline() }, 'Fijar texto'));
  },
  async styleNew(el) {
    const o = this.textOpts, z = this.viewer.zoom;
    Object.assign(el.style, {
      fontSize: o.size * z + 'px', lineHeight: '1.2', color: o.color, fontFamily: await fontForKey(o.font),
      fontWeight: o.bold ? 'bold' : 'normal', fontStyle: o.italic ? 'italic' : 'normal',
    });
  },
  async newInline(x, y) {
    const v = this.viewer, z = v.zoom;
    const el = h('div', { class: 'inline-edit new', contentEditable: 'true', spellcheck: false });
    Object.assign(el.style, { left: x * z + 'px', top: (y - this.textOpts.size * 0.1) * z + 'px', minWidth: '20px' });
    await this.styleNew(el);
    v.ov.append(el);
    this.inline = { el, isNew: true, x, y };
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); this.commitInline(); }
      if (e.key === 'Escape') { e.preventDefault(); this.cancelInline(); this.draw(); }
      e.stopPropagation();
    });
    el.addEventListener('mousedown', e => e.stopPropagation());
    el.focus();
    this.draw_addtext_refresh();
  },
  draw_addtext_refresh() { this.props.innerHTML = ''; this.draw_addtext(); },

  draw_image(st) {
    const v = this.viewer;
    for (const im of st.images) {
      const d = v.box(im.bbox, 'img' + (this.sel === im.xref ? ' sel' : ''));
      d.addEventListener('mousedown', () => { if (this.sel !== im.xref) { this.sel = im.xref; this.draw(); } });
      v.transformable(d, im.bbox, r => this.op('move_image', { xref: im.xref, rect: r }, 'Moviendo…'));
    }
    this.props.append(h('h3', {}, 'Imágenes'),
      h('p', { class: 'muted' }, 'Arrastra una imagen para moverla o su esquina para cambiar el tamaño.'),
      h('button', {
        class: 'wide', onclick: async () => {
          const [f] = await pickFiles('image/png,image/jpeg,image/*');
          if (!f) return;
          this.pendingImage = await fileToB64(f);
          toast('Arrastra en la página el recuadro donde colocar la imagen.', '', [], 4000);
          this.draw();
        },
      }, 'Insertar imagen…'));
    if (this.pendingImage) this.props.append(h('p', {}, 'Dibuja el recuadro en la página… ', h('button', { onclick: () => { this.pendingImage = null; this.draw(); } }, 'Cancelar')));
    if (this.sel != null && st.images.some(i => i.xref === this.sel)) {
      this.props.append(h('button', { class: 'wide danger', onclick: () => this.deleteSel() }, 'Eliminar imagen seleccionada'));
    }
    if (!st.images.length) this.props.append(h('small', {}, 'Esta página no tiene imágenes.'));
  },

  annotBoxes(st, onlyShapes = false) {
    const v = this.viewer;
    const fixed = ['Highlight', 'Underline', 'StrikeOut', 'Squiggly'];
    for (const a of st.annots) {
      if (onlyShapes && !['Square', 'Circle', 'Line', 'Ink', 'Polygon', 'PolyLine'].includes(a.type)) continue;
      const d = v.box(a.bbox, 'annot' + (this.sel === a.xref ? ' sel' : ''));
      d.title = a.label + (a.content ? ': ' + a.content : '') + (fixed.includes(a.type) ? '' : ' — arrastra para mover');
      d.addEventListener('mousedown', e => { e.stopPropagation(); if (this.sel !== a.xref) { this.sel = a.xref; this.draw(); } });
      if (!fixed.includes(a.type)) v.transformable(d, a.bbox, r => this.op('move_annot', { xref: a.xref, rect: r }, 'Moviendo…'));
    }
  },

  draw_annot(st) {
    this.annotBoxes(st);
    const kinds = { highlight: 'Resaltar texto', underline: 'Subrayar texto', strikeout: 'Tachar texto', note: 'Nota adhesiva',
      freetext: 'Cuadro de texto', rect: 'Rectángulo', circle: 'Elipse', ink: 'Dibujo a mano alzada' };
    const kind = h('select', { onchange: () => { this.annotKind = kind.value; this.draw(); } },
      Object.entries(kinds).map(([k, l]) => h('option', { value: k }, l)));
    kind.value = this.annotKind;
    const color = h('input', { type: 'color', value: this.color, onchange: () => { this.color = color.value; } });
    this.annotText = this.annotText || '';
    const txt = h('textarea', { rows: 2, placeholder: 'Texto de la nota o del cuadro', oninput: () => { this.annotText = txt.value; } }, this.annotText);
    const help = ['highlight', 'underline', 'strikeout'].includes(this.annotKind) ? 'Arrastra sobre el texto.'
      : this.annotKind === 'note' ? 'Haz clic donde quieras la nota.' : this.annotKind === 'ink' ? 'Dibuja sobre la página.' : 'Arrastra para dibujar el recuadro.';
    this.props.append(h('h3', {}, 'Anotar'), h('label', {}, 'Herramienta', kind), h('div', { class: 'row' }, 'Color', color),
      ['note', 'freetext'].includes(this.annotKind) && txt, h('p', { class: 'muted' }, help));
    const a = st.annots.find(x => x.xref === this.sel);
    if (a) this.props.append(h('h3', {}, 'Seleccionada'), h('p', {}, a.label + (a.content ? ` — ${a.content}` : '')),
      h('button', { class: 'wide danger', onclick: () => this.deleteSel() }, 'Eliminar anotación'));
    if (st.annots.length) this.props.append(h('small', {}, 'Haz clic en una anotación (recuadro naranja) para seleccionarla.'));
  },

  draw_shapes(st) {
    this.annotBoxes(st, true);
    const sh = this.shape;
    const kinds = { rect: 'Rectángulo', ellipse: 'Elipse', line: 'Línea', arrow: 'Flecha' };
    const kind = h('select', { onchange: () => { sh.kind = kind.value; } }, Object.entries(kinds).map(([k, l]) => h('option', { value: k }, l)));
    kind.value = sh.kind;
    const stroke = h('input', { type: 'color', value: sh.stroke, onchange: () => { sh.stroke = stroke.value; } });
    const filled = h('input', { type: 'checkbox', checked: sh.filled, onchange: () => { sh.filled = filled.checked; } });
    const fill = h('input', { type: 'color', value: sh.fill, onchange: () => { sh.fill = fill.value; } });
    const width = h('input', { type: 'number', value: sh.width, min: 0.5, max: 20, step: 0.5, class: 'num', onchange: () => { sh.width = +width.value; } });
    this.props.append(h('h3', {}, 'Formas'),
      h('p', { class: 'muted' }, 'Elige la forma y arrástrala sobre la página. Después puedes moverla, cambiar su tamaño (esquina) o borrarla (Supr).'),
      h('label', {}, 'Forma', kind),
      h('div', { class: 'row' }, 'Borde', stroke, 'Grosor', width),
      h('div', { class: 'row' }, h('label', { class: 'inline' }, filled, 'Relleno'), fill));
    const a = st.annots.find(x => x.xref === this.sel);
    if (a) this.props.append(h('button', { class: 'wide danger', onclick: () => this.deleteSel() }, 'Eliminar forma seleccionada'));
  },

  draw_select() {
    const v = this.viewer;
    if (this.region && this.region.n === v.n) v.box(this.region.r, 'region');
    const c = this.clip;
    this.props.append(h('h3', {}, 'Seleccionar, copiar y pegar'),
      h('p', { class: 'muted' }, 'Arrastra para seleccionar una zona. «Copiar» la guarda (también en el portapapeles del sistema como imagen y texto). Para pegarla, haz clic donde quieras y pulsa «Pegar» o ⌘/Ctrl+V: se pega tal cual, con su texto y calidad originales, en esta u otra página.'),
      h('button', { class: 'primary wide', disabled: !this.region, onclick: () => this.copyRegion() }, 'Copiar zona seleccionada'),
      h('button', { class: 'wide', disabled: !c, onclick: () => this.pasteHere() }, c ? 'Pegar' + (this.point ? ' en el punto marcado' : ' (haz clic donde pegar)') : 'Pegar (primero copia una zona)'),
      h('small', {}, 'También puedes pegar aquí imágenes o texto copiados de otras aplicaciones.'));
    if (this.point && this.point.n === v.n) v.box([this.point.p[0], this.point.p[1], this.point.p[0], this.point.p[1]], 'point');
  },
  async copyRegion() {
    if (!this.region) return;
    const r = await run('Copiando…', () => api('edit/copy', { id: this.info.id, n: this.region.n, rect: this.region.r }));
    if (!r) return;
    this.clip = r;
    try {
      const blob = await (await fetch('data:image/png;base64,' + r.png)).blob();
      const items = { 'image/png': blob };
      if (r.text) items['text/plain'] = new Blob([r.text], { type: 'text/plain' });
      await navigator.clipboard.write([new ClipboardItem(items)]);
      toast('Zona copiada (también en el portapapeles del sistema).', 'ok', [], 3000);
    } catch (e) {
      toast('Zona copiada para pegar en DocGuard.', 'ok', [], 3000);
    }
    this.draw();
  },
  async pasteHere() {
    if (!this.clip) return;
    const p = this.point && this.point.n === this.viewer.n ? this.point.p : [this.region?.r[0] + 20 || 40, this.region?.r[1] + 20 || 40];
    await this.op('paste', { x: p[0], y: p[1] }, 'Pegando…');
    this.point = null;
  },
  async onPaste(e) {
    if (!this.root.classList.contains('active') || !this.info) return;
    if (document.activeElement.isContentEditable || /INPUT|TEXTAREA/.test(document.activeElement.tagName)) return;
    const items = [...(e.clipboardData?.items || [])];
    const img = items.find(i => i.type.startsWith('image/'));
    const p = this.point && this.point.n === this.viewer.n ? this.point.p : null;
    e.preventDefault();
    if (this.mode === 'select' && this.clip && (!img || this.clipFresh())) return this.pasteHere();
    const [W, H] = this.viewer.size;
    if (img) {
      const file = img.getAsFile();
      const data = await fileToB64(file);
      const dim = await new Promise(res => { const im = new Image(); im.onload = () => res([im.width, im.height]); im.src = URL.createObjectURL(file); });
      const w = Math.min(W * 0.5, dim[0] * 0.75), hh = w * dim[1] / dim[0];
      const [x, y] = p || [(W - w) / 2, (H - hh) / 2];
      return this.op('insert_image', { rect: [x, y, x + w, y + hh], data });
    }
    const text = e.clipboardData.getData('text/plain');
    if (text) {
      const [x, y] = p || [W * 0.1, H * 0.1];
      return this.op('add_text', { x, y, text, ...this.textOpts });
    }
  },
  clipFresh() { return true; },

  async ocrDialog() {
    if (!this.info) return toast('Abre primero un documento.', 'err');
    const mode = h('select', {}, h('option', { value: 'editable' }, 'Convertir en texto editable'),
      h('option', { value: 'invisible' }, 'Solo hacerlo seleccionable (mantiene el aspecto)'));
    const scope = h('select', {}, h('option', { value: 'page' }, 'Esta página'), h('option', { value: 'all' }, 'Todas las páginas'));
    modal({
      title: 'Reconocer texto (OCR)',
      body: h('div', {}, h('p', { class: 'muted' }, 'Para documentos escaneados o fotos. «Editable» sustituye la imagen del texto por texto real que puedes cambiar (con una fuente estándar). «Seleccionable» añade una capa invisible para buscar y copiar sin cambiar el aspecto.'),
        h('label', {}, 'Qué hacer', mode), h('label', {}, 'Páginas', scope)),
      actions: [{ label: 'Cancelar' }, {
        label: 'Reconocer', primary: true, fn: async () => {
          const pages = scope.value === 'all' ? this.info.pages.map((_, i) => i) : [this.viewer.n];
          busy(true, 'Reconociendo texto…');
          try {
            for (let k = 0; k < pages.length; k++) {
              busyText(`Reconociendo texto… página ${pages[k] + 1} (${k + 1} de ${pages.length})`);
              await api('edit/ocr', { id: this.info.id, n: pages[k], pages: [pages[k]], mode: mode.value });
            }
            toast('Texto reconocido. ' + (mode.value === 'editable' ? 'Ya puedes editarlo con «Editar texto».' : 'Ya se puede seleccionar y buscar.'), 'ok');
          } catch (e) { toast(e.message, 'err'); } finally { busy(false); }
          document.querySelector('#tool-edit [data-mode=text]').click();
          this.refresh(true);
        },
      }],
    });
  },

  draw_forms(st) {
    const v = this.viewer;
    for (const w of st.widgets) {
      const d = v.box(w.bbox, 'widget' + (this.sel === w.xref ? ' sel' : ''));
      const grip = h('div', { class: 'grip', title: 'Clic para editar el campo; arrastra para moverlo' }, w.name);
      grip.addEventListener('click', () => { this.sel = w.xref; this.draw(); });
      let ctl;
      const upd = value => this.fill(w.xref, value);
      if (w.type === 'text') {
        ctl = h('input', { value: w.value || '' });
        ctl.addEventListener('change', () => upd(ctl.value));
      } else if (w.type === 'checkbox' || w.type === 'radio') {
        ctl = h('input', { type: 'checkbox', checked: !!w.value, onchange: () => upd(ctl.checked) });
      } else if (w.type === 'combobox' || w.type === 'listbox') {
        ctl = h('select', { onchange: () => upd(ctl.value) }, w.options.map(o => h('option', {}, o)));
        ctl.value = w.value;
      } else ctl = h('span');
      ctl.addEventListener('mousedown', e => e.stopPropagation());
      d.append(grip, ctl);
      v.transformable(d, w.bbox, r => this.op('update_widget', { xref: w.xref, rect: r }), { grip });
      d.querySelector('.handle').style.display = this.sel === w.xref ? '' : 'none';
    }
    const types = { text: 'Texto', checkbox: 'Casilla', radio: 'Botón de opción', combobox: 'Desplegable', listbox: 'Lista' };
    const type = h('select', { onchange: () => { this.widgetType = type.value; } }, Object.entries(types).map(([k, l]) => h('option', { value: k }, l)));
    type.value = this.widgetType;
    this.props.append(h('h3', {}, 'Formularios'),
      h('p', { class: 'muted' }, 'Rellena los campos directamente sobre la página. Para crear uno nuevo, elige el tipo y arrástralo en la página.'),
      h('label', {}, 'Tipo de campo nuevo', type),
      h('small', {}, 'Los botones de opción con el mismo nombre forman un grupo.'));
    const w = st.widgets.find(x => x.xref === this.sel);
    if (w) {
      const name = h('input', { value: w.name });
      const opts = h('textarea', { rows: 3 }, w.options.join('\n'));
      this.props.append(h('h3', {}, 'Campo seleccionado'), h('label', {}, 'Nombre', name),
        ['combobox', 'listbox'].includes(w.type) && h('label', {}, 'Opciones (una por línea)', opts),
        h('button', {
          class: 'primary wide', onclick: () => this.op('update_widget', {
            xref: w.xref, name: name.value,
            options: ['combobox', 'listbox'].includes(w.type) ? opts.value.split('\n').map(s => s.trim()).filter(Boolean) : null,
          }),
        }, 'Guardar cambios'),
        h('button', { class: 'wide danger', onclick: () => this.deleteSel() }, 'Eliminar campo'));
    }
    this.props.append(h('h3', {}, 'Todo el documento'),
      h('button', {
        class: 'wide', onclick: async () => {
          if (await confirmBox('Aplanar formulario', 'Los campos y anotaciones pasarán a ser contenido fijo y ya no se podrán editar. ¿Continuar?', 'Aplanar')) this.op('flatten', {});
        },
      }, 'Aplanar formulario y anotaciones'));
  },
  async fill(xref, value) {
    const r = await run('Guardando…', () => api('edit/update_widget', { id: this.info.id, n: this.viewer.n, xref, value }));
    if (r !== undefined) { await this.refresh(); this.viewer.refresh(); }
  },

  draw_handsign() {
    this.props.append(h('h3', {}, 'Firma manuscrita'),
      h('p', { class: 'muted' }, 'Elige una firma y arrastra en la página el recuadro donde colocarla. Es una firma visual; para una firma con validez legal usa «Firma digital».'),
      Sigs.gallery(this.sig, id => { this.sig = id; this.draw(); }),
      h('button', { class: 'wide', onclick: async () => { const id = await Sigs.create(); if (id) { this.sig = id; this.draw(); } } }, 'Nueva firma…'));
    const side = h('select', {},
      h('option', { value: 'derecha' }, 'Margen derecho (vertical)'), h('option', { value: 'izquierda' }, 'Margen izquierdo (vertical)'),
      h('option', { value: 'pie-derecha' }, 'Pie de página, a la derecha'), h('option', { value: 'pie-centro' }, 'Pie de página, centrada'),
      h('option', { value: 'pie-izquierda' }, 'Pie de página, a la izquierda'));
    const length = h('input', { type: 'range', min: 10, max: 45, value: 22 });
    const pages = h('select', { onchange: () => { ranges.hidden = pages.value !== 'ranges'; } },
      h('option', { value: 'all' }, 'Todas las páginas'), h('option', { value: 'ranges' }, 'Solo algunas…'));
    const ranges = h('input', { placeholder: 'Ej.: 1-3, 5', hidden: true });
    this.props.append(h('h3', {}, 'Firmar al margen'),
      h('p', { class: 'muted' }, 'Firma todas las páginas de una vez en el margen, como se hace con los contratos.'),
      h('label', {}, 'Posición', side), h('label', {}, 'Tamaño', length), h('label', {}, 'Páginas', pages), ranges,
      h('button', {
        class: 'primary wide', onclick: async () => {
          if (!this.sig) return toast('Elige o crea primero una firma.', 'err');
          const r = await run('Firmando las páginas…', () => api('sigimg/margin', {
            id: this.info.id, sig: this.sig, side: side.value, length: +length.value, ranges: pages.value === 'ranges' ? ranges.value : '',
          }));
          if (r) { toast(r.message, 'ok'); this.refresh(true); }
        },
      }, 'Firmar al margen'));
  },

  /* ---- ratón sobre la página ---- */
  async down(e) {
    if (e.button !== 0 || e.target !== this.viewer.ov || !this.info) return;
    const v = this.viewer, m = this.mode;
    if (this.inline) { this.commitInline(); return; }
    if (m === 'text') {
      const d = await v.drag(e);
      if (!d.moved) { if (this.selSpans?.size) { this.selSpans = new Set(); this.draw(); } return; }
      const hit = this.st.spans.filter(s => inter(s.bbox, d.rect)).map(s => s.i);
      this.selSpans = new Set(e.shiftKey ? [...this.selSpans, ...hit] : hit);
      this.draw();
      return;
    }
    if (m === 'image' && !this.pendingImage) { if (this.sel != null) { this.sel = null; this.draw(); } return; }
    if (m === 'addtext') { const [x, y] = v.pt(e); this.newInline(x, y); return; }
    if (m === 'annot' && this.annotKind === 'note') {
      const [x, y] = v.pt(e);
      return this.op('add_annot', { kind: 'note', rect: [x, y, x + 20, y + 20], text: this.annotText || 'Nota', color: this.color });
    }
    const d = await v.drag(e, { ink: m === 'annot' && this.annotKind === 'ink' });
    if (!d.moved && m !== 'select') { if (this.sel != null) { this.sel = null; this.draw(); } return; }
    if (m === 'image') {
      const data = this.pendingImage;
      this.pendingImage = null;
      return this.op('insert_image', { rect: d.rect, data });
    }
    if (m === 'annot') {
      if (this.annotKind === 'ink') return this.op('add_ink', { strokes: [d.points], color: this.color });
      return this.op('add_annot', { kind: this.annotKind, rect: d.rect, text: this.annotText, color: this.color });
    }
    if (m === 'select') {
      if (!d.moved) { this.point = { n: v.n, p: d.rect.slice(0, 2) }; this.draw(); return; }
      this.region = { n: v.n, r: d.rect };
      this.point = null;
      this.draw();
      return;
    }
    if (m === 'shapes') {
      const sh = this.shape;
      const pts = [d.points[0], d.points[d.points.length - 1]];
      return this.op('add_shape', { kind: sh.kind, rect: d.rect, points: pts, stroke: sh.stroke, fill: sh.filled ? sh.fill : null, width: sh.width });
    }
    if (m === 'forms') {
      const t = this.widgetType;
      const count = (this.st?.widgets.length || 0) + 1;
      const name = await ask('Nuevo campo', 'Nombre del campo', t === 'radio' ? 'grupo1' : `${t}${count}`);
      if (!name) return;
      let options = null;
      if (t === 'combobox' || t === 'listbox') {
        const s = await ask('Opciones', 'Escribe las opciones, una por línea', 'Opción 1\nOpción 2', { textarea: true });
        if (s == null) return;
        options = s.split('\n').map(x => x.trim()).filter(Boolean);
      }
      return this.op('add_widget', { type: t, rect: d.rect, name, options });
    }
    if (m === 'handsign') {
      if (!this.sig) return toast('Elige o crea primero una firma en el panel de la derecha.', 'err');
      const ratio = await Sigs.ratio(this.sig);
      let [x0, y0, x1, y1] = d.rect;
      const w = x1 - x0, hh = y1 - y0;
      if (w / hh > ratio) { const nw = hh * ratio; x0 += (w - nw) / 2; x1 = x0 + nw; } else { const nh = w / ratio; y0 += (hh - nh) / 2; y1 = y0 + nh; }
      const r = await run('Colocando firma…', () => api('sigimg/place', { id: this.info.id, n: v.n, sig: this.sig, rect: [x0, y0, x1, y1] }));
      if (r !== undefined) this.refresh(true);
    }
  },
};

/* ======================================================================
   MARCA DE AGUA
   ====================================================================== */

const Wm = {
  init() {
    this.root = $('#tool-watermark');
    this.img = $('.preview-img img', this.root);
    this.n = 0;
    this.files = new FileList($('[data-role=files]', this.root), {
      accept: ACCEPT_DOCS, onselect: info => { this.n = 0; if (info) setCurrent(info); this.preview(); },
      onchange: () => this.preview(),
    });
    dropTarget($('.preview', this.root), f => this.files.add(f));
    $$('input,select', this.root).forEach(el => el.addEventListener('input', () => { this.outputs(); this.schedule(); }));
    $('[data-act=prev]', this.root).onclick = () => { this.n = Math.max(0, this.n - 1); this.preview(); };
    $('[data-act=next]', this.root).onclick = () => { this.n = Math.min(this.pages() - 1, this.n + 1); this.preview(); };
    $('[data-act=export]', this.root).onclick = () => this.export();
    $('[data-k=preset]', this.root).onchange = e => this.applyPreset(e.target.value);
    $('[data-act=preset-save]', this.root).onclick = () => this.savePreset();
    $('[data-act=preset-del]', this.root).onclick = () => this.deletePreset();
    this.k('qr').addEventListener('change', () => { $('[data-role=qr]', this.root).hidden = !this.k('qr').checked; });
    this.hideData = {};
    this.hov = $('.hide-ov', this.root);
    this.img.addEventListener('load', () => this.placeOverlay());
    new ResizeObserver(() => this.placeOverlay()).observe($('.preview-img', this.root));
    this.hov.addEventListener('mousedown', e => this.hideDown(e));
    this.k('autohide').addEventListener('change', () => { this.ensureHide(); this.renderHide(); this.schedule(); });
    document.addEventListener('keydown', e => {
      if (!this.root.classList.contains('active') || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
      if ((e.key === 'Delete' || e.key === 'Backspace') && this.hsel) { e.preventDefault(); this.removeHide(this.hsel); }
    });
    const qrMode = () => {
      $('[data-role=qrweb]', this.root).hidden = this.k('qr_mode').value !== 'web';
      try { localStorage.setItem('dg_qr_base', this.k('qr_base').value); localStorage.setItem('dg_qr_mode', this.k('qr_mode').value); } catch (e) { /* sin almacenamiento */ }
    };
    try {
      this.k('qr_base').value = localStorage.getItem('dg_qr_base') || '';
      this.k('qr_mode').value = localStorage.getItem('dg_qr_mode') || 'vcard';
    } catch (e) { /* sin almacenamiento */ }
    this.k('qr_mode').addEventListener('change', qrMode);
    this.k('qr_base').addEventListener('change', qrMode);
    qrMode();
    this.k('level').addEventListener('change', () => { this.k('strike').disabled = this.k('level').value === 'basica'; });
    $('[data-act=check]', this.root).onclick = () => this.check();
    $('[data-act=registry]', this.root).onclick = () => this.registry();
    new ResizeObserver(() => this.schedule()).observe($('.preview-img', this.root));
    this.outputs();
    this.loadPresets();
  },
  loadInfo(info) { this.files.setItems([info]); },
  k(name) { return $(`[data-k=${name}]`, this.root); },
  pages() { return Math.max(1, this.files.current?.pages.length || 1); },
  outputs() { $$('input[type=range]', this.root).forEach(r => { r.parentElement.querySelector('output').textContent = r.value; }); },
  params() {
    const p = {};
    for (const k of ['text', 'angle', 'size', 'gap_x', 'gap_y', 'opacity', 'color', 'level']) p[k] = this.k(k).value;
    for (const k of ['hardened', 'strike', 'mark']) p[k] = this.k(k).checked;
    p.autohide = this.k('autohide').checked;
    const cur = this.files.current;
    p.hide_page = cur ? this.activeRects(cur.id, this.n).map(x => x.r) : [];
    p.hide = {};
    for (const [id, pages] of Object.entries(this.hideData)) {
      p.hide[id] = {};
      for (const n of Object.keys(pages)) p.hide[id][n] = this.activeRects(id, +n).map(x => x.r);
    }
    p.qr = { enabled: this.k('qr').checked, recipient: this.k('qr_recipient').value, purpose: this.k('qr_purpose').value,
      size: +this.k('qr_size').value, pos: this.k('qr_pos').value, mode: this.k('qr_mode').value, base_url: this.k('qr_base').value };
    return p;
  },
  schedule() { clearTimeout(this.t); this.t = setTimeout(() => this.preview(), 150); },
  async preview() {
    const cur = this.files.current;
    const box = $('.preview-img', this.root);
    box.classList.toggle('has', !!cur);
    $('.pager', this.root).style.visibility = cur && this.pages() > 1 ? '' : 'hidden';
    $('.pager span', this.root).textContent = `${this.n + 1} / ${this.pages()}`;
    if (!cur) { this.renderHide(); return; }
    if (this.ensureHide()) return;  // se volverá a llamar al terminar la detección
    this.renderHide();
    const maxw = Math.round(Math.min(1400, (box.clientWidth - 32) * (window.devicePixelRatio || 1)));
    const seq = (this.seq = (this.seq || 0) + 1);
    try {
      const blob = await api('wm/preview', { id: cur.id, n: this.n, params: this.params(), maxw: Math.max(300, maxw) });
      if (seq !== this.seq) return;
      if (this.url) URL.revokeObjectURL(this.url);
      this.url = URL.createObjectURL(blob);
      this.img.src = this.url;
    } catch (e) { toast(e.message, 'err'); }
  },
  async export() {
    if (!this.files.items.length) return toast('Abre primero algún documento.', 'err');
    const fmt = $('input[name=wmfmt]:checked', this.root).value;
    const w = this.k('width').value.trim(), hh = this.k('height').value.trim();
    if ((w && !(+w > 0)) || (hh && !(+hh > 0))) return toast('El tamaño debe ser un número de píxeles.', 'err');
    const res = await run('Aplicando la marca de agua…', () => api('wm/export', {
      ids: this.files.ids, params: this.params(), fmt, width: w || null, height: hh || null,
    }));
    saveResult(res);
  },
  /* ---- ocultar datos del documento de identidad ---- */
  hidePage(id, n) { return this.hideData[id]?.[n]; },
  ensureHide() {
    const cur = this.files.current;
    if (!cur || !this.k('autohide').checked) return false;
    const pg = this.hidePage(cur.id, this.n);
    if (pg) return false;
    (this.hideData[cur.id] = this.hideData[cur.id] || {})[this.n] = { loading: true, items: [], manual: [] };
    const n = this.n;
    busy(true, 'Buscando datos que ocultar…');
    api('idfields', { id: cur.id, n }).then(r => {
      this.hideData[cur.id][n] = { doc: r.doc, items: r.items.map(it => ({ ...it, on: true })), manual: [] };
      if (r.items.length) toast(`${r.doc === 'pasaporte' ? 'Pasaporte' : r.doc === 'dni' ? 'DNI' : 'Documento'}: ${r.items.length} dato(s) que conviene ocultar. Revísalos en la vista previa.`, 'ok', [], 5000);
    }).catch(e => { toast(e.message, 'err'); this.hideData[cur.id][n] = { items: [], manual: [] }; })
      .finally(() => { busy(false); this.preview(); });
    return true;
  },
  activeRects(id, n) {
    const pg = this.hidePage(id, n);
    if (!pg || pg.loading) return [];
    const out = [];
    if (this.k('autohide').checked) pg.items.forEach((it, ii) => { if (it.on) it.rects.forEach((r, ri) => out.push({ r, key: [ii, ri] })); });
    pg.manual.forEach((r, mi) => out.push({ r, key: ['m', mi] }));
    return out;
  },
  renderHide() {
    const list = $('[data-role=hidelist]', this.root);
    list.innerHTML = '';
    this.hov.innerHTML = '';
    const cur = this.files.current;
    const pg = cur && this.hidePage(cur.id, this.n);
    if (pg && !pg.loading && this.k('autohide').checked) {
      if (!pg.items.length) list.append(h('small', {}, 'No se han detectado datos de DNI/pasaporte en esta página.'));
      pg.items.forEach(it => {
        const cb = h('input', { type: 'checkbox', checked: it.on, onchange: () => { it.on = cb.checked; this.renderHide(); this.schedule(); } });
        list.append(h('div', {}, h('label', { class: 'inline' }, cb, it.label), it.text ? h('div', { class: 'ex' }, it.text.slice(0, 60)) : null));
      });
    }
    if (!cur) return;
    for (const a of this.activeRects(cur.id, this.n)) {
      const [x0, y0, x1, y1] = a.r;
      const isSel = this.hsel && this.hsel.join() === a.key.join();
      const d = h('div', { class: 'hbox' + (isSel ? ' sel' : ''), style: `left:${x0 * 100}%;top:${y0 * 100}%;width:${(x1 - x0) * 100}%;height:${(y1 - y0) * 100}%` });
      d.addEventListener('mousedown', e => { e.stopPropagation(); this.hsel = a.key; this.renderHide(); });
      if (isSel) d.append(h('div', { class: 'x', title: 'Quitar esta zona', onmousedown: e => { e.stopPropagation(); this.removeHide(a.key); } }, '✕'));
      this.hov.append(d);
    }
  },
  removeHide(key) {
    const cur = this.files.current;
    const pg = this.hidePage(cur.id, this.n);
    if (key[0] === 'm') pg.manual.splice(key[1], 1);
    else {
      const it = pg.items[key[0]];
      it.rects.splice(key[1], 1);
      if (!it.rects.length) it.on = false;
    }
    this.hsel = null;
    this.renderHide();
    this.schedule();
  },
  placeOverlay() {
    const box = $('.preview-img', this.root);
    const b = box.getBoundingClientRect(), r = this.img.getBoundingClientRect();
    Object.assign(this.hov.style, { left: r.left - b.left + box.scrollLeft + 'px', top: r.top - b.top + box.scrollTop + 'px', width: r.width + 'px', height: r.height + 'px' });
  },
  hideDown(e) {
    const cur = this.files.current;
    if (!cur || e.button !== 0) return;
    this.hsel = null;
    const R = this.hov.getBoundingClientRect();
    const pt = ev => [clamp((ev.clientX - R.left) / R.width, 0, 1), clamp((ev.clientY - R.top) / R.height, 0, 1)];
    const p0 = pt(e);
    const box = h('div', { class: 'drag-box' });
    this.hov.append(box);
    const mv = ev => { const r = norm(p0, pt(ev)); Object.assign(box.style, { left: r[0] * 100 + '%', top: r[1] * 100 + '%', width: (r[2] - r[0]) * 100 + '%', height: (r[3] - r[1]) * 100 + '%' }); };
    window.addEventListener('mousemove', mv);
    window.addEventListener('mouseup', ev => {
      window.removeEventListener('mousemove', mv);
      box.remove();
      const r = norm(p0, pt(ev));
      if ((r[2] - r[0]) * R.width < 6 || (r[3] - r[1]) * R.height < 6) { this.renderHide(); return; }
      const d = this.hideData[cur.id] = this.hideData[cur.id] || {};
      d[this.n] = d[this.n] || { items: [], manual: [] };
      d[this.n].manual.push(r);
      this.renderHide();
      this.schedule();
    }, { once: true });
  },

  async check() {
    const [f] = await pickFiles(ACCEPT_DOCS);
    if (!f) return;
    const r = await run('Buscando la marca invisible…', async () => {
      const info = await uploadFile(f);
      try { return await api('wm/check', { id: info.id }); } finally { api('close', { id: info.id }).catch(() => {}); }
    });
    if (!r) return;
    const body = r.found.length ? h('div', {}, r.found.map(x => h('div', { class: 'sig-result' },
      h('div', {}, h('b', { class: 'ok' }, `✔ Marca encontrada: ${x.ref}`), x.page > 1 ? ` (página ${x.page})` : ''),
      x.record ? h('div', { class: 'kv' },
        h('b', {}, 'Entregado a'), h('span', {}, x.record.destinatario || '—'),
        h('b', {}, 'Finalidad'), h('span', {}, x.record.finalidad || '—'),
        h('b', {}, 'Fecha'), h('span', {}, x.record.fecha),
        h('b', {}, 'Texto'), h('span', {}, x.record.texto || '—'),
        h('b', {}, 'Archivo'), h('span', {}, x.record.archivo || '—'))
        : h('p', { class: 'muted' }, 'Esta referencia no está en el historial de este equipo (quizá se marcó en otro).'))))
      : h('p', {}, 'No se ha encontrado ninguna marca invisible de DocGuard. Puede que no la tenga, o que la imagen se haya recortado, girado o regenerado por completo.');
    modal({ title: 'Comprobar marca invisible', body, actions: [{ label: 'Cerrar', primary: true }] });
  },
  async registry() {
    const r = await run('Cargando…', () => api('wm/registry'));
    if (!r) return;
    const body = r.items.length ? h('table', { class: 'reg' },
      h('tr', {}, h('th', {}, 'Fecha'), h('th', {}, 'Ref.'), h('th', {}, 'Entregado a'), h('th', {}, 'Finalidad'), h('th', {}, 'Archivo')),
      r.items.map(x => h('tr', {}, h('td', {}, x.fecha), h('td', {}, x.ref), h('td', {}, x.destinatario || '—'),
        h('td', {}, x.finalidad || '—'), h('td', {}, x.archivo))))
      : h('p', {}, 'Todavía no has entregado documentos con marca de rastreo o QR.');
    modal({ title: 'Historial de entregas', body, actions: [{ label: 'Cerrar', primary: true }], wide: true });
  },
  settings() {
    return { ...this.params(), fmt: $('input[name=wmfmt]:checked', this.root).value, width: this.k('width').value, height: this.k('height').value };
  },
  async loadPresets() {
    try { this.presets = (await api('presets')).presets; } catch (e) { this.presets = {}; }
    const sel = this.k('preset');
    const cur = sel.value;
    sel.innerHTML = '';
    sel.append(h('option', { value: '' }, '—'), ...Object.keys(this.presets).sort().map(n => h('option', { value: n }, n)));
    sel.value = cur in this.presets ? cur : '';
  },
  applyPreset(name) {
    const p = this.presets[name];
    if (!p) return;
    for (const k of ['text', 'angle', 'size', 'gap_x', 'gap_y', 'opacity', 'width', 'height']) if (p[k] != null) this.k(k).value = p[k];
    if (p.color) this.k('color').value = Array.isArray(p.color) ? '#' + p.color.map(c => (+c).toString(16).padStart(2, '0')).join('') : p.color;
    this.k('hardened').checked = p.hardened !== false;
    if (p.level) this.k('level').value = p.level;
    for (const k of ['strike', 'mark']) if (p[k] != null) this.k(k).checked = p[k];
    if (p.qr) {
      this.k('qr').checked = !!p.qr.enabled;
      $('[data-role=qr]', this.root).hidden = !p.qr.enabled;
      this.k('qr_recipient').value = p.qr.recipient || '';
      this.k('qr_purpose').value = p.qr.purpose || '';
      if (p.qr.size) this.k('qr_size').value = p.qr.size;
      if (p.qr.pos) this.k('qr_pos').value = p.qr.pos;
      if (p.qr.mode) { this.k('qr_mode').value = p.qr.mode; this.k('qr_mode').dispatchEvent(new Event('change')); }
      if (p.qr.base_url) this.k('qr_base').value = p.qr.base_url;
    }
    const f = $(`input[name=wmfmt][value=${(p.fmt || 'pdf').toLowerCase()}]`, this.root);
    if (f) f.checked = true;
    this.outputs();
    this.preview();
  },
  async savePreset() {
    const name = await ask('Guardar plantilla', 'Nombre de la plantilla', this.k('preset').value);
    if (!name) return;
    this.presets[name] = this.settings();
    await run('Guardando…', () => api('presets/save', { presets: this.presets }));
    await this.loadPresets();
    this.k('preset').value = name;
  },
  async deletePreset() {
    const name = this.k('preset').value;
    if (!name || !(await confirmBox('Borrar plantilla', `¿Borrar la plantilla «${name}»?`, 'Borrar'))) return;
    delete this.presets[name];
    await api('presets/save', { presets: this.presets });
    this.loadPresets();
  },
};

/* ======================================================================
   CENSURAR
   ====================================================================== */

const Redact = {
  init() {
    this.root = $('#tool-redact');
    this.viewer = new Viewer($('.viewer-host', this.root));
    this.viewer.onrender = () => this.draw();
    this.viewer.onpage = n => this.ensureWords(n);
    this.viewer.ov.addEventListener('mousedown', e => this.down(e));
    this.viewer.ov.classList.add('draw');
    this.mode = 'text'; this.marks = {}; this.words = {};
    dropTarget(this.viewer.el, f => this.openFile(f[0]));
    const act = (a, f) => { $(`[data-act=${a}]`, this.root).onclick = f; };
    act('open', async () => { const [f] = await pickFiles(ACCEPT_DOCS); if (f) this.openFile(f); });
    act('search', () => this.search());
    $('[data-k=term]', this.root).addEventListener('keydown', e => { if (e.key === 'Enter') this.search(); });
    act('detect', () => this.detect());
    act('ocr', () => this.ocrAll(true));
    act('undo', () => { (this.marks[this.viewer.n] || []).pop(); this.selMark = null; this.draw(); });
    document.addEventListener('keydown', e => {
      if (!this.root.classList.contains('active') || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
      if ((e.key === 'Delete' || e.key === 'Backspace') && this.selMark) { e.preventDefault(); this.removeMark(); }
      if (e.key === 'Escape' && this.selMark) { this.selMark = null; this.draw(); }
    });
    act('clear', () => { delete this.marks[this.viewer.n]; this.draw(); });
    act('save', () => this.save());
    $$('[data-mode]', this.root).forEach(b => b.onclick = () => {
      $$('[data-mode]', this.root).forEach(x => x.classList.toggle('on', x === b));
      this.mode = b.dataset.mode;
    });
  },
  status(t) { $('.status', this.root).textContent = t; },
  async openFile(f) { const info = await run('Abriendo…', () => uploadFile(f)); if (info) this.loadInfo(info); },
  loadInfo(info) {
    if (info.encrypted || !info.pages.length) return toast('No se puede abrir: tiene contraseña o no es un PDF/imagen.', 'err');
    this.info = info; this.marks = {}; this.words = {};
    setCurrent(info);
    $('.doc-name', this.root).textContent = info.name;
    this.viewer.load(info);
    this.ensureWords(0);
  },
  async ensureWords(n) {
    if (!this.words[n]) {
      try { this.words[n] = await api('words', { id: this.info.id, n }); } catch (e) { return toast(e.message, 'err'); }
    }
    const w = this.words[n];
    this.status(`Página ${n + 1}: ${w.source === 'pdf' ? 'texto seleccionable' : w.source === 'ocr' ? 'texto reconocido por OCR' : 'sin texto (usa OCR o «Área libre»)'} · ${this.count()} zonas marcadas en total`);
    return w;
  },
  count() { return Object.values(this.marks).reduce((a, g) => a + g.reduce((b, x) => b + x.length, 0), 0); },
  draw() {
    const v = this.viewer;
    v.clear();
    (this.marks[v.n] || []).forEach((g, gi) => g.forEach((r, ri) => {
      const isSel = this.selMark && this.selMark.n === v.n && this.selMark.gi === gi && this.selMark.ri === ri;
      const d = v.box(r, 'mark' + (isSel ? ' sel' : ''));
      d.title = 'Clic para seleccionar; ✕ o Supr para quitar esta zona';
      d.addEventListener('mousedown', e => { e.stopPropagation(); this.selMark = { n: v.n, gi, ri }; this.draw(); });
      if (isSel) d.append(h('div', { class: 'x', title: 'Quitar esta zona', onmousedown: e => { e.stopPropagation(); this.removeMark(); } }, '✕'));
    }));
  },
  removeMark() {
    const m = this.selMark;
    if (!m) return;
    const groups = this.marks[m.n];
    groups[m.gi].splice(m.ri, 1);
    if (!groups[m.gi].length) groups.splice(m.gi, 1);
    this.selMark = null;
    this.draw();
    this.ensureWords(this.viewer.n);
  },
  add(n, rects) { (this.marks[n] = this.marks[n] || []).push(rects); },
  async down(e) {
    if (e.button !== 0 || !this.info) return;
    if (this.selMark) { this.selMark = null; this.draw(); }
    const d = await this.viewer.drag(e);
    if (!d.moved) return;
    const n = this.viewer.n;
    if (this.mode === 'area') this.add(n, [d.rect]);
    else {
      let w = await this.ensureWords(n);
      if (w && w.source === 'none') {
        const pages = await api('pages_without_text', { id: this.info.id });
        if (pages.ocr_available && await confirmBox('Página escaneada', 'Esta página no tiene texto. ¿Reconocerlo con OCR? Tarda unos segundos.', 'Reconocer')) {
          await this.ocrPages([n]);
          w = await this.ensureWords(n);
        }
      }
      const hits = (w?.words || []).filter(x => inter(x.bbox, d.rect)).map(x => x.bbox);
      if (!hits.length) return toast('No hay texto en esa zona. Usa «Área libre» para tapar cualquier zona.', '');
      this.add(n, hits);
    }
    this.draw();
    this.ensureWords(n);
  },
  async ocrPages(pages) {
    busy(true, 'Reconociendo texto…');
    try {
      for (let k = 0; k < pages.length; k++) {
        busyText(`Reconociendo texto… página ${pages[k] + 1} (${k + 1} de ${pages.length})`);
        await api('ocr', { id: this.info.id, n: pages[k] });
        delete this.words[pages[k]];
      }
    } catch (e) { toast(e.message, 'err'); } finally { busy(false); }
  },
  async ocrAll(explicit) {
    if (!this.info) return;
    const r = await api('pages_without_text', { id: this.info.id });
    if (!r.pages.length) { if (explicit) toast('Todas las páginas ya tienen texto seleccionable.'); return true; }
    if (!r.ocr_available) { toast('El OCR no está disponible en esta instalación.', 'err'); return false; }
    if (!explicit && !await confirmBox('Páginas escaneadas', `${r.pages.length} página(s) no tienen texto. ¿Reconocerlo con OCR antes de buscar?`, 'Reconocer')) return false;
    await this.ocrPages(r.pages);
    this.ensureWords(this.viewer.n);
    if (explicit) toast('OCR terminado.', 'ok');
    return true;
  },
  async search() {
    const term = $('[data-k=term]', this.root).value.trim();
    if (!this.info || !term) return;
    const r = await run('Buscando…', () => api('search', { id: this.info.id, term }));
    if (!r) return;
    let c = 0;
    for (const hit of r.hits) { this.add(hit.n, hit.rects); c += hit.rects.length; }
    toast(`${c} coincidencia(s) marcadas.`, c ? 'ok' : '');
    this.draw(); this.ensureWords(this.viewer.n);
  },
  async detect() {
    if (!this.info) return;
    await this.ocrAll(false);
    const r = await run('Buscando datos sensibles…', () => api('detect', { id: this.info.id }));
    if (!r) return;
    const kinds = Object.entries(r.found);
    if (!kinds.length) return toast('No se han encontrado datos sensibles.');
    const checks = {};
    const body = h('div', { class: 'check-list' }, kinds.map(([k, items]) => {
      checks[k] = h('input', { type: 'checkbox', checked: k !== 'Fecha' });
      const ex = [...new Set(items.map(i => i.text))].slice(0, 4).join(' · ');
      return h('div', {}, h('label', { class: 'inline' }, checks[k], `${k} (${items.length})`), h('div', { class: 'ex' }, ex));
    }));
    modal({
      title: 'Datos sensibles encontrados', body,
      actions: [{ label: 'Cancelar' }, {
        label: 'Marcar seleccionados', primary: true, fn: () => {
          let c = 0;
          for (const [k, items] of kinds) if (checks[k].checked) for (const it of items) { this.add(it.n, it.rects); c++; }
          this.draw(); this.ensureWords(this.viewer.n);
          toast(`${c} dato(s) marcados. Revisa todas las páginas antes de guardar.`, 'ok');
        },
      }],
    });
  },
  async save() {
    if (!this.info) return;
    const marks = {};
    for (const [n, gs] of Object.entries(this.marks)) { const f = gs.flat(); if (f.length) marks[n] = f; }
    if (!Object.keys(marks).length) return toast('No hay nada marcado para censurar.', 'err');
    const res = await run('Censurando…', () => api('redact', { id: this.info.id, marks, style: $('[data-k=style]', this.root).value }));
    saveResult(res);
  },
};

/* ======================================================================
   FIRMA DIGITAL
   ====================================================================== */

const Sign = {
  init() {
    this.root = $('#tool-sign');
    this.viewer = new Viewer($('.viewer-host', this.root));
    this.viewer.onrender = () => this.draw();
    this.viewer.ov.classList.add('draw');
    this.viewer.ov.addEventListener('mousedown', e => this.down(e));
    this.rect = null; this.p12 = null;
    dropTarget(this.viewer.el, f => this.openFile(f[0]));
    const act = (a, f) => { $(`[data-act=${a}]`, this.root).onclick = f; };
    const k = n => $(`[data-k=${n}]`, this.root);
    this.k = k;
    act('open', async () => { const [f] = await pickFiles(ACCEPT_PDF); if (f) this.openFile(f); });
    act('cert', async () => {
      const [f] = await pickFiles('');
      if (!f) return;
      this.p12 = await fileToB64(f);
      $('.cert-name', this.root).textContent = f.name;
      $('.cert-info', this.root).innerHTML = '';
    });
    act('certinfo', () => this.certInfo());
    act('newsig', async () => { const id = await Sigs.create(); if (id) this.fillSigs(id); });
    act('sign', () => this.sign());
    act('verify', () => this.verify());
    k('tsa').onchange = () => { k('tsa_custom').hidden = k('tsa').value !== 'custom'; };
    this.source = 'file';
    $$('[data-src]', this.root).forEach(b => b.onclick = () => {
      this.source = b.dataset.src;
      $$('[data-src]', this.root).forEach(x => x.classList.toggle('on', x === b));
      $$('[data-pane]', this.root).forEach(p => { p.hidden = p.dataset.pane !== this.source; });
      if (this.source === 'card' && !this.modulesLoaded) this.loadModules();
    });
    k('module').onchange = () => { k('module_custom').hidden = k('module').value !== 'custom'; };
    act('p11list', () => this.listCards());
    act('p11login', () => this.login());
    this.card = { state: 'off' };
    k('p11cert').onchange = () => { if (this.card.state === 'ok') this.setCard('found', this.card.text); };
    setInterval(() => this.poll(), 4000);
    k('visible').onchange = () => this.draw();
    document.addEventListener('sigs-changed', () => this.fillSigs());
  },
  async loadModules() {
    this.modulesLoaded = true;
    const r = await run('Buscando módulos…', () => api('p11/modules'));
    const s = this.k('module');
    s.innerHTML = '';
    for (const m of r?.modules || []) s.append(h('option', { value: m }, m.split(/[\\/]/).pop() + ' — ' + m));
    s.append(h('option', { value: 'custom' }, 'Otro (indicar ruta)…'));
    if (!r?.modules.length) {
      s.value = 'custom';
      this.k('module_custom').hidden = false;
      toast('No se ha encontrado el módulo del DNIe ni OpenSC. Instálalo (ver ayuda) o indica su ruta.', 'err', [], 9000);
    }
  },
  module() { return this.k('module').value === 'custom' ? this.k('module_custom').value.trim() : this.k('module').value; },
  /** Indicador del DNIe: off (gris), found (ámbar, falta PIN), ok (verde, conectado). */
  setCard(state, text) {
    this.card = { state, text };
    const labels = { off: 'Sin tarjeta', found: 'Tarjeta detectada — introduce el PIN', ok: 'DNIe conectado' };
    for (const el of $$('.card-status')) {
      el.className = el.className.replace(/\b(off|found|ok)\b/g, '').trim() + ' ' + state;
      const t = el.querySelector('.txt');
      if (el.classList.contains('nav-card')) {
        el.hidden = state === 'off';
        t.textContent = state === 'ok' ? `DNIe conectado · ${text}` : 'Tarjeta detectada';
      } else t.textContent = state === 'ok' ? `✔ DNIe conectado correctamente · ${text}` : (text && state === 'found' ? `${labels.found} (${text})` : labels[state]);
    }
  },
  async poll() {
    if (this.source !== 'card' && this.card.state === 'off') return;
    const module = this.module();
    if (!module || this.polling) return;
    this.polling = true;
    try {
      const r = await api('p11/list', { module });
      const present = r.tokens.some(t => t.certs.length);
      if (!present && this.card.state !== 'off') {
        this.setCard('off');
        this.k('pin').value = '';
        toast('Se ha retirado la tarjeta.', '');
      } else if (present && this.card.state === 'off') {
        this.fillCerts(r.tokens);
        this.setCard('found', r.tokens[0].token);
      }
    } catch (e) { /* lector no disponible: se ignora en el sondeo */ } finally { this.polling = false; }
  },
  fillCerts(tokens) {
    const s = this.k('p11cert');
    const cur = s.value;
    s.innerHTML = '';
    for (const t of tokens) for (const c of t.certs) {
      s.append(h('option', { value: JSON.stringify({ token: t.token, id: c.id }) },
        `${c.signing ? '✍ ' : ''}${c.subject} · ${c.label} (${t.token}, caduca ${c.valid_to})`));
    }
    if ([...s.options].some(o => o.value === cur)) s.value = cur;
    return s.options.length;
  },
  async login() {
    const c = this.k('p11cert').value;
    if (!c) return toast('Detecta primero la tarjeta.', 'err');
    if (!this.k('pin').value) return toast('Escribe el PIN.', 'err');
    const { token, id } = JSON.parse(c);
    const r = await run('Verificando el PIN…', () => api('p11/login', { module: this.module(), token, cert_id: id, pin: this.k('pin').value }));
    if (!r) { this.k('pin').value = ''; return; }
    this.setCard('ok', r.subject);
    toast(`DNIe conectado: ${r.subject}`, 'ok');
  },
  async listCards() {
    const module = this.module();
    if (!module) return toast('Indica el módulo PKCS#11.', 'err');
    const r = await run('Leyendo la tarjeta…', () => api('p11/list', { module }));
    if (!r) return;
    if (!this.fillCerts(r.tokens)) {
      this.k('p11cert').append(h('option', { value: '' }, 'No hay tarjeta o certificados'));
      this.setCard('off');
      toast('No se ha encontrado ninguna tarjeta con certificados. ¿Está bien insertada en el lector?', 'err');
    } else {
      if (this.card.state !== 'ok') this.setCard('found', r.tokens[0].token);
      toast(`Tarjeta detectada: ${r.tokens.map(t => t.token).join(', ')}`, 'ok');
    }
  },
  fillSigs(select) {
    const s = this.k('sig');
    const cur = select ?? s.value;
    s.innerHTML = '';
    s.append(h('option', { value: '' }, 'Sin imagen'), ...Sigs.items.map((it, i) => h('option', { value: it.id }, `Firma ${i + 1}`)));
    s.value = Sigs.items.some(i => i.id === cur) ? cur : '';
  },
  async openFile(f) { const info = await run('Abriendo…', () => uploadFile(f)); if (info) this.loadInfo(info); },
  loadInfo(info) {
    if (!info.pages.length) return toast('Solo se pueden firmar PDFs o imágenes (se convierten a PDF).', 'err');
    if (info.encrypted) return toast('Quita primero la contraseña del PDF.', 'err');
    this.info = info; this.rect = null;
    setCurrent(info);
    $('.doc-name', this.root).textContent = info.name;
    this.viewer.load(info);
  },
  draw() {
    const v = this.viewer;
    v.clear();
    if (this.rect && this.rect.n === v.n && this.k('visible').checked) v.box(this.rect.r, 'sigbox');
  },
  async down(e) {
    if (e.button !== 0 || !this.info || !this.k('visible').checked) return;
    const d = await this.viewer.drag(e);
    if (d.moved) { this.rect = { n: this.viewer.n, r: d.rect }; this.draw(); }
  },
  async certInfo() {
    if (!this.p12) return toast('Elige primero el archivo del certificado.', 'err');
    const r = await run('Comprobando…', () => api('certinfo', { p12: this.p12, password: this.k('password').value }));
    if (!r) return;
    $('.cert-info', this.root).replaceChildren(h('div', { class: 'kv' },
      h('b', {}, 'Titular'), h('span', {}, r.subject), h('b', {}, 'Emisor'), h('span', {}, r.issuer),
      h('b', {}, 'Válido'), h('span', {}, `${r.valid_from} – ${r.valid_to}`)));
  },
  async sign() {
    if (!this.info) return toast('Abre primero un PDF.', 'err');
    let cred;
    if (this.source === 'card') {
      const c = this.k('p11cert').value;
      if (!c) return toast('Detecta la tarjeta y elige un certificado.', 'err');
      if (!this.k('pin').value) return toast('Escribe el PIN de la tarjeta.', 'err');
      const { token, id } = JSON.parse(c);
      cred = { source: 'card', module: this.module(), token, cert_id: id, pin: this.k('pin').value };
    } else {
      if (!this.p12) return toast('Elige el certificado (.p12 / .pfx).', 'err');
      cred = { source: 'file', p12: this.p12, password: this.k('password').value };
    }
    const visible = this.k('visible').checked;
    if (visible && !this.rect) return toast('Arrastra en la página el recuadro donde irá la firma (o desmarca «Firma visible»).', 'err');
    const tsa = this.k('tsa').value === 'custom' ? this.k('tsa_custom').value.trim() : this.k('tsa').value;
    const res = await run('Firmando…', () => api('sign', {
      id: this.info.id, ...cred,
      n: visible ? this.rect.n : null, rect: visible ? this.rect.r : null, sig: visible ? this.k('sig').value : '',
      reason: this.k('reason').value, location: this.k('location').value, contact: this.k('contact').value, tsa,
    }));
    if (this.source === 'card' && !res && this.card.state === 'ok') this.setCard('found', this.card.text);
    saveResult(res);
  },
  async verify() {
    if (!this.info) return toast('Abre primero un PDF.', 'err');
    const r = await run('Verificando…', () => api('verify', { id: this.info.id }));
    if (!r) return;
    const body = h('div', {}, r.signatures.length ? r.signatures.map(s => h('div', { class: 'sig-result' },
      h('div', {}, h('b', {}, s.field), ' — ', s.signer),
      h('div', { class: 'muted' }, `Emisor: ${s.issuer}${s.time ? ' · ' + s.time : ''}${s.reason ? ' · Motivo: ' + s.reason : ''}`),
      h('div', {}, s.intact && s.valid ? h('b', { class: 'ok' }, '✔ Firma íntegra: el documento no ha cambiado desde la firma')
        : h('b', { class: 'bad' }, '✘ Firma NO válida o documento alterado')),
      h('div', { class: 'muted' }, s.trusted ? 'Certificado de confianza.' : 'Certificado no verificado contra una autoridad de confianza de este equipo (normal con certificados propios o si falta la cadena).'),
      s.modified_after ? h('div', { class: 'muted' }, 'Hay cambios posteriores a esta firma (otras firmas o anotaciones).') : null,
    )) : h('p', {}, 'Este PDF no tiene firmas digitales.'));
    modal({ title: 'Firmas del documento', body, actions: [{ label: 'Cerrar', primary: true }] });
  },
};

/* ======================================================================
   PÁGINAS
   ====================================================================== */

const Pages = {
  init() {
    this.root = $('#tool-pages');
    this.grid = $('.thumbs', this.root);
    this.items = [];
    dropTarget(this.grid, f => this.openFile(f[0]));
    const act = (a, f) => { $(`[data-act=${a}]`, this.root).onclick = f; };
    act('open', async () => { const [f] = await pickFiles(ACCEPT_DOCS); if (f) this.openFile(f); });
    act('all', () => { const all = this.items.every(i => i.sel); this.items.forEach(i => { i.sel = !all; }); this.render(); });
    act('rotl', () => this.rotate(-90));
    act('rotr', () => this.rotate(90));
    act('del', () => {
      const keep = this.items.filter(i => !i.sel);
      if (!keep.length) return toast('No puedes eliminar todas las páginas.', 'err');
      this.items = keep; this.render();
    });
    act('save', () => this.save('one', this.items, 'editado'));
    act('extract', () => {
      const s = this.items.filter(i => i.sel);
      if (!s.length) return toast('Selecciona alguna página (clic en la miniatura).', 'err');
      this.save('one', s, 'extracto');
    });
    act('each', () => this.save('each', this.items));
    act('ranges', async () => {
      const r = await ask('Dividir por rangos', 'Rangos según el orden actual (ej.: 1-3, 4-6, 7-)', '');
      if (r) this.save('ranges', this.items, '', r);
    });
  },
  async openFile(f) { const info = await run('Abriendo…', () => uploadFile(f)); if (info) this.loadInfo(info); },
  loadInfo(info) {
    if (info.encrypted || !info.pages.length) return toast('No se puede abrir: tiene contraseña o no es un PDF.', 'err');
    this.info = info;
    this.v = (this.v || 0) + 1;
    setCurrent(info);
    this.items = info.pages.map((_, i) => ({ idx: i, rot: 0, sel: false }));
    $('.doc-name', this.root).textContent = `${info.name} (${info.pages.length} págs.)`;
    this.render();
  },
  rotate(d) {
    const s = this.items.filter(i => i.sel);
    if (!s.length) return toast('Selecciona las páginas a girar, o usa el botón ↻ de cada miniatura.', 'err');
    s.forEach(i => { i.rot = (i.rot + d + 360) % 360; });
    this.render();
  },
  render() {
    this.grid.innerHTML = '';
    this.items.forEach((it, k) => {
      const img = h('img', { src: pageUrl(this.info.id, it.idx, 0.35, this.v), style: `transform:rotate(${it.rot}deg)`, draggable: false });
      const card = h('div', { class: 'thumb' + (it.sel ? ' sel' : ''), draggable: true },
        h('div', { class: 'ti' }, img),
        h('div', { class: 'tl' }, h('span', {}, `${k + 1}${it.idx !== k ? ` (orig. ${it.idx + 1})` : ''}`),
          h('span', {},
            h('button', { title: 'Girar', onclick: e => { e.stopPropagation(); it.rot = (it.rot + 90) % 360; this.render(); } }, '↻'),
            h('button', { title: 'Eliminar', onclick: e => { e.stopPropagation(); if (this.items.length > 1) { this.items.splice(k, 1); this.render(); } } }, '✕'))));
      card.onclick = () => { it.sel = !it.sel; card.classList.toggle('sel', it.sel); };
      card.addEventListener('dragstart', e => e.dataTransfer.setData('text/x-page', k));
      card.addEventListener('dragover', e => { if (e.dataTransfer.types.includes('text/x-page')) { e.preventDefault(); card.classList.add('dragover'); } });
      card.addEventListener('dragleave', () => card.classList.remove('dragover'));
      card.addEventListener('drop', e => {
        const from = e.dataTransfer.getData('text/x-page');
        if (from === '') return;
        e.preventDefault(); e.stopPropagation();
        const [m] = this.items.splice(+from, 1);
        this.items.splice(k, 0, m);
        this.render();
      });
      this.grid.append(card);
    });
  },
  async save(mode, items, suffix = 'editado', ranges = '') {
    if (!this.info) return toast('Abre primero un PDF.', 'err');
    const res = await run('Guardando…', () => api('pages/save', { id: this.info.id, items: items.map(i => [i.idx, i.rot]), mode, suffix, ranges }));
    saveResult(res);
  },
};

/* ======================================================================
   CONTRASEÑA, CONVERTIR, LIMPIAR, UNIR
   ====================================================================== */

const Protect = {
  init() {
    this.root = $('#tool-protect');
    this.files = new FileList($('[data-role=files]', this.root), {
      multiple: false, accept: ACCEPT_DOCS, onselect: info => { if (info) setCurrent(info); },
    });
    const k = n => $(`[data-k=${n}]`, this.root);
    $('[data-act=protect]', this.root).onclick = async () => {
      const f = this.files.current;
      if (!f) return toast('Elige primero un archivo.', 'err');
      if (!k('pw1').value) return toast('Escribe una contraseña.', 'err');
      if (k('pw1').value !== k('pw2').value) return toast('Las contraseñas no coinciden.', 'err');
      saveResult(await run('Cifrando…', () => api('encrypt', {
        id: f.id, user_pw: k('pw1').value, owner_pw: k('owner').value, print: k('print').checked, copy: k('copy').checked, edit: k('edit').checked,
      })));
    };
    $('[data-act=unprotect]', this.root).onclick = async () => {
      const f = this.files.current;
      if (!f) return toast('Elige primero un archivo.', 'err');
      saveResult(await run('Quitando la contraseña…', () => api('decrypt', { id: f.id, password: k('pwrm').value })));
    };
  },
  loadInfo(info) { this.files.setItems([info]); },
};

function batchTool(id, accept, handlers) {
  const root = $('#' + id);
  const files = new FileList($('[data-role=files]', root), { accept });
  for (const [act, fn] of Object.entries(handlers)) {
    $(`[data-act=${act}]`, root).onclick = async () => {
      if (!files.items.length) return toast('Añade algún archivo a la lista.', 'err');
      saveResult(await run('Procesando…', () => fn(files, root)));
    };
  }
  return { files, loadInfo: info => files.setItems([info]) };
}

/* ======================================================================
   Navegación
   ====================================================================== */

const TOOLS = {};

/** Al entrar en una herramienta, abre en ella el documento actual (con sus cambios). */
function syncTool(name) {
  const t = TOOLS[name];
  if (!CURRENT || !t) return;
  const same = t.info?.id === CURRENT.id;
  if (name === 'edit') { if (same) t.refresh(true); else t.loadInfo(CURRENT); }
  else if (name === 'redact') { if (same) { t.words = {}; t.viewer.refresh(); t.ensureWords(t.viewer.n); } else t.loadInfo(CURRENT); }
  else if (name === 'sign') { if (same) t.viewer.refresh(); else t.loadInfo(CURRENT); }
  else if (name === 'pages') { if (same) { t.v++; t.render(); } else t.loadInfo(CURRENT); }
  else if (name === 'watermark' || name === 'protect') {
    const fl = t.files;
    const i = fl.items.findIndex(x => x.id === CURRENT.id);
    if (i >= 0) { fl.cur = i; fl.render(); }
    else if (fl.items.length <= 1) { fl.items = [CURRENT]; fl.cur = 0; fl.render(); }
    else { fl.items.unshift(CURRENT); fl.cur = 0; fl.render(); }
    if (name === 'watermark') { t.n = 0; t.preview(); }
  } else if (t.files && !t.files.items.length) { t.files.items = [CURRENT]; t.files.render(); }
}

function showTool(name) {
  syncTool(name);
  $$('.nav button').forEach(b => b.classList.toggle('active', b.dataset.tool === name));
  $$('.tool').forEach(s => s.classList.toggle('active', s.id === 'tool-' + name));
  requestAnimationFrame(() => TOOLS[name]?.viewer?.fit());
  if (name === 'watermark') Wm.schedule();
}

function init() {
  Edit.init(); Wm.init(); Redact.init(); Sign.init(); Pages.init(); Protect.init();
  Object.assign(TOOLS, { edit: Edit, watermark: Wm, redact: Redact, sign: Sign, pages: Pages, protect: Protect });
  $('.cd-close').onclick = clearCurrent;
  TOOLS.convert = batchTool('tool-convert', ACCEPT_DOCS, {
    compress: (f, r) => api('compress', { ids: f.ids, level: $('[data-k=level]', r).value }),
    toimages: (f, r) => api('toimages', { ids: f.ids, fmt: $('[data-k=fmt]', r).value, dpi: +$('[data-k=dpi]', r).value }),
    topdf: f => api('topdf', { ids: f.ids }),
  });
  TOOLS.sanitize = batchTool('tool-sanitize', '', { clean: f => api('sanitize', { ids: f.ids }) });
  TOOLS.merge = batchTool('tool-merge', ACCEPT_DOCS, { merge: f => api('merge', { ids: f.ids }) });
  $$('.nav button').forEach(b => b.onclick = () => showTool(b.dataset.tool));
  Sigs.load();
}

init();
