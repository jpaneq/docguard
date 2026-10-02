'use strict';
// Visor de páginas (una a una y continuo) y utilidades de fuentes para la edición directa.

/* ======================================================================
   Visor de páginas
   ====================================================================== */

class Viewer {
  constructor(host) {
    this.el = h('div', { class: 'viewer' }, this.empty = h('div', { class: 'empty' }, 'Abre o arrastra aquí un documento'));
    this._wrap = h('div', { class: 'page-wrap', style: 'display:none' }, this._img = h('img', { alt: '' }), this._ov = h('div', { class: 'ov' }));
    this.el.append(this._wrap);
    const b = (t, f, title) => h('button', { onclick: f, title }, t);
    this.bar = h('div', { class: 'vbar', style: 'display:none' },
      b('◀', () => this.go(this.n - 1), 'Página anterior'), this.lbl = h('span'), b('▶', () => this.go(this.n + 1), 'Página siguiente'),
      b('−', () => this.setZoom(this.zoom / 1.2), 'Alejar'), b('+', () => this.setZoom(this.zoom * 1.2), 'Acercar'),
      b('Ajustar', () => this.fit(), 'Ajustar al ancho'));
    host.append(this.el, this.bar);
    this.info = null; this.n = 0; this.zoom = 1; this.v = 0; this.fitMode = true;
    this.onpage = null; this.onrender = null;
    new ResizeObserver(() => { if (this.info && this.fitMode) this.fit(); }).observe(this.el);
    // Ctrl + rueda (o pellizco en el trackpad): zoom manteniendo fijo el punto bajo el ratón.
    // Mientras se gira, la página se amplía al momento (imagen estirada); al parar se pide nítida.
    let wheelZoom = null;
    this.el.addEventListener('wheel', e => {
      if (!e.ctrlKey || !this.info) return;
      e.preventDefault();
      if (!wheelZoom) {
        const r = this.el.getBoundingClientRect();
        const cx = e.clientX - r.left, cy = e.clientY - r.top;
        wheelZoom = { z: this.zoom, old: this.zoom, cx, cy, x: cx + this.el.scrollLeft, y: cy + this.el.scrollTop };
        this.el.classList.add('zooming');
      }
      const w = wheelZoom;
      w.z = clamp(w.z * Math.exp(-clamp(e.deltaY, -100, 100) / 400), 0.2, 5);
      this.previewZoom(w.z);
      const k = this.zoom / w.old;
      this.el.scrollLeft = w.x * k - w.cx;
      this.el.scrollTop = w.y * k - w.cy;
      clearTimeout(w.t);
      w.t = setTimeout(() => {
        wheelZoom = null;
        this.el.classList.remove('zooming');
        this.render();
      }, 90);
    }, { passive: false });
  }
  /** Vista previa del zoom: solo cambia el tamaño de las páginas, sin pedir imágenes nuevas. */
  previewZoom(z) {
    this.fitMode = false;
    this.zoom = clamp(z, 0.2, 5);
    const wraps = this.pages ? this.pages.map((p, i) => [p.wrap, this.info.pages[i]]) : [[this._wrap, this.size]];
    for (const [w, sz] of wraps) this.sizeWrap(w, sz);
  }
  /** Tamaño de una página en píxeles reales de pantalla (enteros): la imagen se pide justo a ese
   *  tamaño para que el navegador no la reescale y el texto se vea nítido. */
  pageGeom([pw, ph]) {
    const d = window.devicePixelRatio || 1, W = Math.max(1, Math.round(pw * this.zoom * d));
    return { w: W / d, h: Math.round(ph * this.zoom * d) / d, z: (W / pw).toFixed(6) };
  }
  sizeWrap(wrap, sz) { const g = this.pageGeom(sz); wrap.style.width = g.w + 'px'; wrap.style.height = g.h + 'px'; return g; }
  /** Con muchos píxeles, PNG de compresión rápida (sin pérdida: misma imagen, se genera antes). */
  fmt() { return this.zoom * (window.devicePixelRatio || 1) >= 1.5 ? '&fmt=fast' : ''; }
  pageOv(i) { return i === this.n ? this._ov : null; }
  get wrap() { return this._wrap; }
  get img() { return this._img; }
  get ov() { return this._ov; }
  /** Escucha eventos del lienzo de la página (en el visor continuo, de todas). */
  on(type, fn) { this._ov.addEventListener(type, fn); }
  load(info) {
    this.info = info; this.n = 0; this.v++;
    this.empty.style.display = 'none'; this._wrap.style.display = ''; this.bar.style.display = '';
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
    const g = this.sizeWrap(this.wrap, this.size);
    this.img.src = pageUrl(this.info.id, this.n, g.z, this.v) + this.fmt();
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
  /** Arrastre del ratón desde el evento e. Devuelve {rect, points, moved}.
   *  shape: 'line'/'arrow' (vista previa de línea; con Mayús, ángulos de 15°) o
   *  'rect'/'ellipse' (con Mayús, cuadrado o círculo). */
  drag(e, { ink = false, show = true, shape = null } = {}) {
    return new Promise(res => {
      const p0 = this.pt(e);
      const pts = [p0];
      const isLine = shape === 'line' || shape === 'arrow';
      let el = null, line = null, last = p0, shift = e.shiftKey;
      if (ink || isLine) {
        el = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        el.setAttribute('style', 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible');
        line = document.createElementNS('http://www.w3.org/2000/svg', isLine ? 'line' : 'polyline');
        line.setAttribute('fill', 'none'); line.setAttribute('stroke', isLine ? '#d62828' : '#1a4fd6'); line.setAttribute('stroke-width', '2');
        el.append(line);
        this.ov.append(el);
      } else if (show) {
        el = h('div', { class: 'drag-box' + (shape === 'ellipse' ? ' ellipse' : '') });
        this.ov.append(el);
      }
      const end = () => {
        const dx = last[0] - p0[0], dy = last[1] - p0[1];
        if (!shift) return last;
        if (isLine) { const [sx, sy] = snapAngle(dx, dy); return [p0[0] + sx, p0[1] + sy]; }
        if (shape === 'rect' || shape === 'ellipse') {
          const side = Math.max(Math.abs(dx), Math.abs(dy));
          return [p0[0] + Math.sign(dx || 1) * side, p0[1] + Math.sign(dy || 1) * side];
        }
        return last;
      };
      const paint = () => {
        const p = end();
        if (isLine) {
          const z = this.zoom;
          line.setAttribute('x1', p0[0] * z); line.setAttribute('y1', p0[1] * z);
          line.setAttribute('x2', p[0] * z); line.setAttribute('y2', p[1] * z);
        } else if (ink) line.setAttribute('points', pts.map(q => `${q[0] * this.zoom},${q[1] * this.zoom}`).join(' '));
        else if (el) this.place(el, norm(p0, p));
      };
      const mv = ev => { last = this.pt(ev); shift = ev.shiftKey; pts.push(last); paint(); };
      const key = ev => { if (ev.key === 'Shift') { shift = ev.type === 'keydown'; paint(); } };
      const up = ev => {
        window.removeEventListener('mousemove', mv);
        window.removeEventListener('keydown', key);
        window.removeEventListener('keyup', key);
        el?.remove();
        last = this.pt(ev);
        shift = ev.shiftKey;
        const p = end();
        const rect = norm(p0, p);
        res({ rect, points: isLine ? [p0, p] : pts, moved: (rect[2] - rect[0]) + (rect[3] - rect[1]) > 3 });
      };
      window.addEventListener('mousemove', mv);
      window.addEventListener('keydown', key);
      window.addEventListener('keyup', key);
      window.addEventListener('mouseup', up, { once: true });
    });
  }
  /** Hace que el cuadro el se pueda mover (arrastrando) y redimensionar.
   *  handles: 'corner' (esquina inferior derecha), 'all' (esquinas y lados) o 'none' (solo mover).
   *  Con Mayús: al mover, en pasos de 15°; en una esquina, se mantiene la proporción. */
  transformable(el, rect, onDone, { keepRatio = false, grip = null, handles = 'corner' } = {}) {
    const dirs = handles === 'all' ? ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'] : handles === 'none' ? [] : ['se'];
    const start = (e, mode) => {
      if (e.button !== 0) return;
      e.preventDefault(); e.stopPropagation();
      const p0 = this.pt(e);
      let r = rect.slice();
      const w0 = rect[2] - rect[0], h0 = rect[3] - rect[1];
      const mv = ev => {
        const p = this.pt(ev);
        let dx = p[0] - p0[0], dy = p[1] - p0[1];
        if (mode === 'move') {
          if (ev.shiftKey) [dx, dy] = snapAngle(dx, dy);
          r = [rect[0] + dx, rect[1] + dy, rect[2] + dx, rect[3] + dy];
        } else {
          let [x0, y0, x1, y1] = rect;
          if (mode.includes('w')) x0 = Math.min(rect[0] + dx, rect[2] - 6);
          if (mode.includes('e')) x1 = Math.max(rect[2] + dx, rect[0] + 6);
          if (mode.includes('n')) y0 = Math.min(rect[1] + dy, rect[3] - 6);
          if (mode.includes('s')) y1 = Math.max(rect[3] + dy, rect[1] + 6);
          if ((keepRatio || ev.shiftKey) && mode.length === 2 && w0 > 0 && h0 > 0) {
            const fx = (x1 - x0) / w0, fy = (y1 - y0) / h0;
            const f = Math.abs(fx - 1) > Math.abs(fy - 1) ? fx : fy;  // la esquina contraria queda fija
            if (mode.includes('w')) x0 = rect[2] - w0 * f; else x1 = rect[0] + w0 * f;
            if (mode.includes('n')) y0 = rect[3] - h0 * f; else y1 = rect[1] + h0 * f;
          }
          r = [x0, y0, x1, y1];
        }
        this.place(el, r);
      };
      window.addEventListener('mousemove', mv);
      window.addEventListener('mouseup', () => {
        window.removeEventListener('mousemove', mv);
        if (r.some((v, i) => Math.abs(v - rect[i]) > 0.5)) onDone(r.map(v => Math.round(v * 100) / 100));
      }, { once: true });
    };
    for (const dir of dirs) {
      const hd = h('div', { class: 'handle' + (handles === 'all' ? ' h-' + dir : ''), title: 'Arrastra para cambiar el tamaño (Mayús: mantener la proporción)' });
      el.append(hd);
      hd.addEventListener('mousedown', e => start(e, dir));
    }
    (grip || el).addEventListener('mousedown', e => { if (!e.target.classList.contains('handle')) start(e, 'move'); });
  }
}

/** Con Mayús: la dirección se redondea a múltiplos de 15° (0°, 15°, 30°, 45°, 90°…). */
function snapAngle(dx, dy, step = 15) {
  const len = Math.hypot(dx, dy);
  if (!len) return [0, 0];
  const k = step * Math.PI / 180;
  const a = Math.round(Math.atan2(dy, dx) / k) * k;
  const r = v => Math.abs(v) < 1e-9 ? 0 : v;
  return [r(Math.cos(a) * len), r(Math.sin(a) * len)];
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

/** Visor con todas las páginas seguidas (desplazamiento con la rueda). La página
 *  activa es la que ocupa el centro de la vista o la última en la que se ha hecho clic. */
class ContViewer extends Viewer {
  /** keepOverlays: las marcas de cada página se conservan al cambiar de página (Censurar, Firma).
   *  firstClickActivates: el primer clic en otra página solo la activa (Editar). */
  constructor(host, { keepOverlays = false, firstClickActivates = true } = {}) {
    super(host);
    this.keepOverlays = keepOverlays;
    this.firstClickActivates = firstClickActivates;
    this._wrap.remove();
    this.stack = h('div', { class: 'stack' });
    this.el.append(this.stack);
    this.pages = [];
    this.handlers = [];
    let raf = 0;
    this.el.addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; this.onScroll(); }); });
  }
  get wrap() { return this.pages[this.n]?.wrap || this._wrap; }
  get img() { return this.pages[this.n]?.img || this._img; }
  get ov() { return this.pages[this.n]?.ov || this._ov; }
  on(type, fn) {
    this.handlers.push([type, fn]);
    this.pages.forEach((p, i) => this.bind(p, i, type, fn));
  }
  bind(p, i, type, fn) {
    p.ov.addEventListener(type, e => {
      if (i !== this.n) {
        this.setActive(i);
        if (this.firstClickActivates && (type === 'mousedown' || type === 'contextmenu')) { e.preventDefault(); return; }
      }
      fn(e);
    }, true);
  }
  load(info) {
    this.info = info; this.n = 0; this.v++;
    this.empty.style.display = 'none'; this.bar.style.display = '';
    this.stack.innerHTML = '';
    this.pages = info.pages.map((sz, i) => {
      const img = h('img', { alt: '', draggable: false });
      const ov = h('div', { class: 'ov' });
      const wrap = h('div', { class: 'page-wrap' }, img, ov);
      wrap.dataset.page = i + 1;
      this.stack.append(wrap);
      const p = { wrap, img, ov, v: -1 };
      this.handlers.forEach(([t, f]) => this.bind(p, i, t, f));
      return p;
    });
    this.el.scrollTop = 0;
    this.fit();
  }
  /** Cambia el documento mostrado manteniendo la página y el desplazamiento (vista previa). */
  swap(info) {
    const n = this.n, fit = this.fitMode, z = this.zoom;
    const off = this.pages[n] ? this.el.scrollTop - this.pages[n].wrap.offsetTop : 0;
    this.load(info);
    if (!fit) { this.zoom = z; this.fitMode = false; this.render(); }
    const restore = () => { if (this.pages[n]) this.el.scrollTop = this.pages[n].wrap.offsetTop + off; this.loadVisible(); };
    restore();
    requestAnimationFrame(() => { restore(); requestAnimationFrame(restore); });
    this.n = -1;
    this.setActive(n);
  }
  get size() { return this.info.pages[this.n]; }
  fit() {
    if (!this.info) return;
    const w = this.el.clientWidth - 40;
    if (w <= 0) return;
    this.fitMode = true;
    this.zoom = clamp(w / Math.max(...this.info.pages.map(p => p[0])), 0.2, 2.2);
    this.render();
  }
  setZoom(z) {
    const p = this.pages[this.n];
    const off = p ? this.el.scrollTop - p.wrap.offsetTop : 0, old = this.zoom;
    this.fitMode = false; this.zoom = clamp(z, 0.2, 5); this.render();
    if (p) this.el.scrollTop = p.wrap.offsetTop + off * this.zoom / old;
  }
  go(n) {
    if (!this.info) return;
    n = clamp(n, 0, this.pages.length - 1);
    // solo se desplaza el visor (scrollIntoView movería también la ventana)
    this.el.scrollTop = this.pages[n].wrap.offsetTop - 10;
    this.setActive(n);
  }
  pageOv(i) { return this.pages[i]?.ov || null; }
  setActive(n) {
    if (n === this.n) return;
    if (!this.keepOverlays) this.pages[this.n]?.ov.replaceChildren();
    this.n = n;
    this.lbl.textContent = `${n + 1} / ${this.pages.length}`;
    this.onpage?.(n);
  }
  refresh() { this.v++; this.render(); }
  render() {
    if (!this.info) return;
    this.pages.forEach((p, i) => { this.sizeWrap(p.wrap, this.info.pages[i]); p.v = -1; });
    this.lbl.textContent = `${this.n + 1} / ${this.pages.length}`;
    this.loadVisible();
    this.onrender?.();
  }
  loadVisible() {
    const top = this.el.scrollTop - 900, bottom = this.el.scrollTop + this.el.clientHeight + 900;
    const fmt = this.fmt();
    // primero la página que se está mirando y luego las más cercanas (el servidor las genera de una en una)
    const mid = this.el.scrollTop + this.el.clientHeight / 2;
    this.pages.map((p, i) => ({ p, i, y0: p.wrap.offsetTop, y1: p.wrap.offsetTop + p.wrap.offsetHeight }))
      .filter(({ p, y0, y1 }) => y1 >= top && y0 <= bottom && p.v !== this.v)
      .sort((a, b) => Math.max(0, a.y0 - mid, mid - a.y1) - Math.max(0, b.y0 - mid, mid - b.y1))
      .forEach(({ p, i }) => { p.img.src = pageUrl(this.info.id, i, this.pageGeom(this.info.pages[i]).z, this.v) + fmt; p.v = this.v; });
  }
  onScroll() {
    if (!this.info) return;
    this.loadVisible();
    const mid = this.el.scrollTop + this.el.clientHeight * 0.4;
    let best = this.n;
    this.pages.forEach((p, i) => { if (p.wrap.offsetTop <= mid) best = i; });
    if (best !== this.n) this.setActive(best);
  }
}
