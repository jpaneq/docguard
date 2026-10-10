'use strict';
// Regla para Editar PDF (al estilo de la regla de Windows Ink): franja semitransparente con milímetros
// y centímetros a escala real, transportador en el centro con el ángulo, y trazado de líneas a lo largo
// de sus bordes.
//
//   · Mover: arrastrar la regla.               · Girar: rueda encima, o ← / → (Mayús: 15°),
//   · Ángulo exacto: clic en el transportador     o arrastrar el transportador.
//     (doble clic: 0°).                         · Trazar: arrastrar junto a un borde (fuera de la regla).
//   · Esc: ocultarla.
//
// La posición se guarda respecto a una página (puntos del PDF) para que siga al documento al desplazarse
// y al hacer zoom; el largo de la regla es fijo en pantalla y las marcas se ajustan al zoom.

const Ruler = {
  H: 70,            // alto de la franja (px de pantalla)
  SNAP: 26,         // distancia al borde (px) en la que un arrastre traza una línea pegada a la regla
  MM: 72 / 25.4,    // puntos del PDF por milímetro
  visible: false,
  angle: 0,         // grados, sentido de las agujas del reloj (como en pantalla)
  pos: null,        // { n, x, y }: centro, en puntos de la página n

  attach(edit) {
    this.edit = edit;
    this.v = edit.viewer;
    const prev = this.v.onrender;
    this.v.onrender = () => { prev?.(); if (this.visible) this.layout(); };
    this.v.el.addEventListener('mousedown', e => this.edgeDown(e), true);   // antes que Editar
    this.v.el.addEventListener('mousemove', e => this.edgeHover(e));
    document.addEventListener('keydown', e => this.key(e), true);
    new ResizeObserver(() => { if (this.visible) this.layout(true); }).observe(this.v.el);
  },

  toggle() { this.visible ? this.hide() : this.show(); },

  show() {
    if (!this.edit.info) return toast('Abre primero un documento.', 'err');
    const v = this.v, n = v.n, wrap = v.pages[n]?.wrap;
    if (!wrap) return;
    if (!this.pos || !v.pages[this.pos.n]) {  // en el centro de lo que se está viendo
      const cx = v.el.scrollLeft + v.el.clientWidth / 2, cy = v.el.scrollTop + v.el.clientHeight / 2;
      this.pos = { n, x: (cx - wrap.offsetLeft) / v.zoom, y: (cy - wrap.offsetTop) / v.zoom };
    }
    if (!this.el) this.build();
    v.el.append(this.el, this.guide);
    this.visible = true;
    this.layout(true);
    $('[data-act=ruler]', this.edit.root)?.classList.add('on');
    this.edit.hint('Regla: arrástrala para moverla · rueda o ← / → para girar (Mayús: 15°) · clic en el ángulo para escribirlo · arrastra junto a un borde para trazar una línea · Esc la oculta');
  },

  hide() {
    this.visible = false;
    this.el?.remove();
    this.guide?.remove();
    $('[data-act=ruler]', this.edit.root)?.classList.remove('on');
    this.edit.draw();
  },

  build() {
    const NS = 'http://www.w3.org/2000/svg';
    this.el = h('div', { class: 'ruler' });
    this.svg = document.createElementNS(NS, 'svg');
    this.svg.classList.add('ruler-svg');
    this.dial = h('div', { class: 'ruler-dial', title: 'Clic: escribir el ángulo · doble clic: 0° · arrastrar: girar' });
    this.el.append(this.svg, this.dial);
    this.guide = document.createElementNS(NS, 'svg');  // línea que se está trazando
    this.guide.classList.add('ruler-guide');
    // mover arrastrando la franja
    this.el.addEventListener('mousedown', e => {
      if (e.button !== 0 || e.target.closest('.ruler-dial')) return;
      e.preventDefault(); e.stopPropagation();
      const v = this.v, c0 = this.center(), x0 = e.clientX, y0 = e.clientY;
      const move = ev => this.setCenter(c0.x + ev.clientX - x0, c0.y + ev.clientY - y0);
      const up = () => { document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up); };
      document.addEventListener('mousemove', move);
      document.addEventListener('mouseup', up);
      v.el.focus?.();
    });
    // girar con la rueda (1° por paso; con Mayús, 15°)
    this.el.addEventListener('wheel', e => {
      if (e.ctrlKey) return;  // Ctrl + rueda sigue siendo el zoom
      e.preventDefault();
      this.rotate((e.deltaY > 0 ? 1 : -1) * (e.shiftKey ? 15 : 1));
    }, { passive: false });
    this.el.addEventListener('mouseenter', () => { this.hot = true; });
    this.el.addEventListener('mouseleave', () => { this.hot = false; });
    // transportador: arrastrar gira; clic escribe el ángulo; doble clic, 0°
    this.dial.addEventListener('mousedown', e => {
      if (e.button !== 0) return;
      e.preventDefault(); e.stopPropagation();
      const r = this.dial.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const a0 = Math.atan2(e.clientY - cy, e.clientX - cx) * 180 / Math.PI, start = this.angle;
      let moved = false;
      const move = ev => {
        const a = Math.atan2(ev.clientY - cy, ev.clientX - cx) * 180 / Math.PI;
        if (Math.hypot(ev.clientX - e.clientX, ev.clientY - e.clientY) > 3) moved = true;
        if (moved) this.setAngle(Math.round(start + a - a0));
      };
      const up = () => {
        document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up);
        if (!moved) { clearTimeout(this._click); this._click = setTimeout(() => this.askAngle(), 250); }
      };
      document.addEventListener('mousemove', move);
      document.addEventListener('mouseup', up);
    });
    this.dial.addEventListener('dblclick', e => { e.stopPropagation(); clearTimeout(this._click); this.setAngle(0); });
  },

  /** Largo en pantalla y marcas (se rehace al cambiar el zoom o el tamaño del visor). */
  draw() {
    const v = this.v, L = this.L, H = this.H, mm = this.MM * v.zoom;  // px por milímetro
    this.svg.setAttribute('width', L); this.svg.setAttribute('height', H);
    this.svg.setAttribute('viewBox', `0 0 ${L} ${H}`);
    const parts = [`<rect x="0" y="0" width="${L}" height="${H}" rx="6" class="rb"/>`];
    const every = mm >= 4 ? 1 : mm >= 1.6 ? 5 : 10;  // si el zoom es pequeño, no se dibujan todos los mm
    const count = Math.floor(L / mm);
    for (let i = 0; i <= count; i += every) {
      const x = (i * mm).toFixed(2), cm = i % 10 === 0, half = i % 5 === 0;
      const len = cm ? 16 : half ? 11 : 6;
      parts.push(`<line x1="${x}" y1="0" x2="${x}" y2="${len}" class="${cm ? 'tk tk-cm' : 'tk'}"/>`,
        `<line x1="${x}" y1="${H}" x2="${x}" y2="${H - len}" class="${cm ? 'tk tk-cm' : 'tk'}"/>`);
      if (cm && i > 0 && x < L - 8) parts.push(`<text x="${x}" y="30" class="tl">${i / 10}</text>`);
    }
    this.svg.innerHTML = parts.join('');
  },

  /** Coloca la regla según su página y el zoom. `redraw`: rehacer también las marcas. */
  layout(redraw) {
    const v = this.v, p = v.pages[this.pos.n];
    if (!p) return this.hide();
    const L = Math.round(Math.min(1300, Math.max(320, v.el.clientWidth * 0.8)));
    if (redraw || L !== this.L || v.zoom !== this._z) { this.L = L; this._z = v.zoom; this.draw(); }
    const cx = p.wrap.offsetLeft + this.pos.x * v.zoom, cy = p.wrap.offsetTop + this.pos.y * v.zoom;
    Object.assign(this.el.style, { width: L + 'px', height: this.H + 'px', left: cx - L / 2 + 'px', top: cy - this.H / 2 + 'px',
      transform: `rotate(${this.angle}deg)` });
    this.dial.style.transform = `translate(-50%, -50%) rotate(${-this.angle}deg)`;  // el número siempre derecho
    this.renderDial();
  },

  renderDial() {
    const a = ((this.angle % 180) + 180) % 180;  // 0–179°, como en la imagen de referencia
    const ticks = [];
    for (let k = 0; k < 36; k++) {
      const t = k * 10 * Math.PI / 180, r1 = 25, r2 = k % 9 === 0 ? 20 : 22.5;
      ticks.push(`<line x1="${30 + r1 * Math.cos(t)}" y1="${30 + r1 * Math.sin(t)}" x2="${30 + r2 * Math.cos(t)}" y2="${30 + r2 * Math.sin(t)}" class="dt"/>`);
    }
    const ra = this.angle * Math.PI / 180;  // marcas rojas: orientación de la regla
    for (const s of [0, Math.PI]) {
      ticks.push(`<line x1="${30 + 26 * Math.cos(ra + s)}" y1="${30 + 26 * Math.sin(ra + s)}" x2="${30 + 18 * Math.cos(ra + s)}" y2="${30 + 18 * Math.sin(ra + s)}" class="dr"/>`);
    }
    this.dial.innerHTML = `<svg width="60" height="60" viewBox="0 0 60 60"><circle cx="30" cy="30" r="28" class="dc"/>${ticks.join('')}</svg><b>${Math.round(a)}°</b>`;
  },

  /** Centro de la regla en coordenadas del contenido del visor (px). */
  center() {
    const v = this.v, p = v.pages[this.pos.n];
    return { x: p.wrap.offsetLeft + this.pos.x * v.zoom, y: p.wrap.offsetTop + this.pos.y * v.zoom };
  },
  setCenter(cx, cy) {
    const v = this.v;
    // se guarda respecto a la página más cercana al nuevo centro (para que siga al documento)
    let n = this.pos.n, best = Infinity;
    v.pages.forEach((p, i) => {
      const t = p.wrap.offsetTop, b = t + p.wrap.offsetHeight, d = cy < t ? t - cy : cy > b ? cy - b : 0;
      if (d < best) { best = d; n = i; }
    });
    const w = v.pages[n].wrap;
    this.pos = { n, x: (cx - w.offsetLeft) / v.zoom, y: (cy - w.offsetTop) / v.zoom };
    this.layout();
  },
  rotate(d) { this.setAngle(this.angle + d); },
  setAngle(a) { this.angle = ((Math.round(a) % 360) + 360) % 360; this.layout(); },

  async askAngle() {
    const s = await ask('Ángulo de la regla', 'Grados (0 a 359; p. ej. 45 o -30)', String(((this.angle % 180) + 180) % 180));
    if (s == null) return;
    const a = parseFloat(String(s).replace(',', '.'));
    if (!Number.isFinite(a)) return toast('Escribe un número de grados, por ejemplo 45.', 'err');
    this.setAngle(a);
  },

  key(e) {
    if (!this.visible || !this.edit.root.classList.contains('active')) return;
    const a = document.activeElement;
    if (/INPUT|TEXTAREA|SELECT/.test(a?.tagName) || a?.isContentEditable || $('.modal-bg')) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); return this.hide(); }
    // ← / → giran la regla cuando el ratón está encima (si no, siguen pasando de página o moviendo texto)
    if (this.hot && (e.key === 'ArrowLeft' || e.key === 'ArrowRight') && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault(); e.stopPropagation();
      this.rotate((e.key === 'ArrowRight' ? 1 : -1) * (e.shiftKey ? 15 : 1));
    }
    // un número con el ratón encima: escribir el ángulo directamente
    if (this.hot && /^[0-9-]$/.test(e.key) && !e.ctrlKey && !e.metaKey) {
      e.preventDefault(); e.stopPropagation();
      this.askAngleFrom(e.key);
    }
  },
  async askAngleFrom(first) {
    const s = await ask('Ángulo de la regla', 'Grados (0 a 359; p. ej. 45 o -30)', first);
    if (s == null) return;
    const a = parseFloat(String(s).replace(',', '.'));
    if (Number.isFinite(a)) this.setAngle(a); else toast('Escribe un número de grados, por ejemplo 45.', 'err');
  },

  /* ---- trazar líneas a lo largo de la regla ---- */

  /** Punto del contenido del visor (px) bajo el ratón. */
  contentPt(e) {
    const r = this.v.el.getBoundingClientRect();
    return { x: e.clientX - r.left + this.v.el.scrollLeft, y: e.clientY - r.top + this.v.el.scrollTop };
  },
  /** Si el punto está junto a un borde de la regla: { s: lado ±1, t: posición a lo largo }. */
  near(P) {
    const C = this.center(), a = this.angle * Math.PI / 180;
    const ux = Math.cos(a), uy = Math.sin(a), nx = -uy, ny = ux;
    const dx = P.x - C.x, dy = P.y - C.y, t = dx * ux + dy * uy, d = dx * nx + dy * ny;
    if (Math.abs(t) > this.L / 2) return null;
    const ad = Math.abs(d) - this.H / 2;
    return ad >= -4 && ad <= this.SNAP ? { s: Math.sign(d) || 1, t } : null;
  },
  edgePoint(s, t) {
    const C = this.center(), a = this.angle * Math.PI / 180, ux = Math.cos(a), uy = Math.sin(a);
    const half = this.L / 2, tt = Math.max(-half, Math.min(half, t));
    return { x: C.x + ux * tt - uy * s * this.H / 2, y: C.y + uy * tt + ux * s * this.H / 2 };
  },
  edgeHover(e) {
    if (!this.visible || e.buttons) return;
    const onEdge = !e.target.closest('.ruler') && this.near(this.contentPt(e));
    this.v.el.classList.toggle('ruler-edge', !!onEdge);
  },
  edgeDown(e) {
    if (!this.visible || e.button !== 0 || e.target.closest('.ruler') || !this.edit.info) return;
    const hit = this.near(this.contentPt(e));
    if (!hit) return;
    e.preventDefault(); e.stopPropagation();  // que Editar no empiece a seleccionar ni a dibujar otra cosa
    const v = this.v, s = hit.s, t0 = hit.t;
    // la línea se guarda en la página donde empieza
    const P0 = this.edgePoint(s, t0);
    let n = 0;
    v.pages.forEach((p, i) => { if (P0.y >= p.wrap.offsetTop) n = i; });
    const wrap = v.pages[n].wrap, z = v.zoom;
    const toPage = P => [(P.x - wrap.offsetLeft) / z, (P.y - wrap.offsetTop) / z];
    let t1 = t0;
    const show = () => {
      const A = this.edgePoint(s, t0), B = this.edgePoint(s, t1), sh = this.edit.shape;
      const len = Math.abs(t1 - t0) / z / this.MM / 10;  // cm
      Object.assign(this.guide.style, { left: '0px', top: '0px', width: v.el.scrollWidth + 'px', height: v.el.scrollHeight + 'px' });
      this.guide.innerHTML = `<line x1="${A.x}" y1="${A.y}" x2="${B.x}" y2="${B.y}" stroke="${sh.stroke}" stroke-width="${Math.max(1, sh.width * z)}" stroke-linecap="round"/>`
        + `<text x="${B.x + 10}" y="${B.y - 10}" class="rg-len">${len.toFixed(1).replace('.', ',')} cm</text>`;
    };
    const move = ev => {
      const P = this.contentPt(ev), C = this.center(), a = this.angle * Math.PI / 180;
      t1 = (P.x - C.x) * Math.cos(a) + (P.y - C.y) * Math.sin(a);
      show();
    };
    const up = async () => {
      document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up);
      this.guide.innerHTML = '';
      if (Math.abs(t1 - t0) < 3) return;
      const pa = toPage(this.edgePoint(s, t0)), pb = toPage(this.edgePoint(s, t1)), sh = this.edit.shape;
      const rect = [Math.min(pa[0], pb[0]), Math.min(pa[1], pb[1]), Math.max(pa[0], pb[0]), Math.max(pa[1], pb[1])];
      if (v.n !== n) v.setActive(n);
      await this.edit.op('add_shape', { kind: 'line', rect, points: [pa, pb], stroke: sh.stroke, fill: null, width: sh.width, dash: sh.dash }, 'Dibujando línea…');
    };
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
    show();
  },
};
