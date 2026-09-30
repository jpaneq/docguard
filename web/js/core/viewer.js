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
  }
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
    this.pages[n].wrap.scrollIntoView({ block: 'start' });
    this.el.scrollTop -= 10;
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
    this.pages.forEach((p, i) => {
      const [w, hh] = this.info.pages[i];
      p.wrap.style.width = w * this.zoom + 'px';
      p.wrap.style.height = hh * this.zoom + 'px';
      p.v = -1;
    });
    this.lbl.textContent = `${this.n + 1} / ${this.pages.length}`;
    this.loadVisible();
    this.onrender?.();
  }
  loadVisible() {
    const top = this.el.scrollTop - 900, bottom = this.el.scrollTop + this.el.clientHeight + 900;
    const z = (this.zoom * (window.devicePixelRatio || 1)).toFixed(3);
    this.pages.forEach((p, i) => {
      const y0 = p.wrap.offsetTop, y1 = y0 + p.wrap.offsetHeight;
      if (y1 >= top && y0 <= bottom && p.v !== this.v) { p.img.src = pageUrl(this.info.id, i, z, this.v); p.v = this.v; }
    });
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
