'use strict';
// Editar PDF: rectas por ecuación (y = m·x + n, x = c) sobre un gráfico del PDF.
// Se calibran los ejes con dos esquinas opuestas del gráfico y la recta se dibuja como
// una línea normal (se puede mover, cambiar de estilo, borrar y deshacer).

/** «y = 0,5x + 0,3», «0.8/1.8 x + 0.93/1.8», «x = 0,35» → {m, n} o {c} (recta vertical). */
function parseLineEq(src) {
  let s = src.toLowerCase().replace(/\s+/g, '').replace(/,/g, '.').replace(/[·×]/g, '*').replace(/[−–]/g, '-');
  const num = e => {
    if (!/^[0-9+\-*/().]+$/.test(e)) throw new Error();
    const v = Function(`return (${e});`)();
    if (!isFinite(v)) throw new Error();
    return v;
  };
  const vert = s.match(/^x=(.+)$/);
  if (vert) return { c: num(vert[1]) };
  s = s.replace(/^y=/, '');
  if (!/^[0-9x+\-*/().]+$/.test(s)) throw new Error();
  const e = s.replace(/([0-9.)])(?=[x(])/g, '$1*').replace(/x(?=[0-9.(x])/g, 'x*');
  const f = Function('x', `return (${e});`);
  const f0 = f(0), f1 = f(1), fh = f(0.5);
  if (![f0, f1, fh].every(isFinite) || Math.abs(fh - (f0 + f1) / 2) > 1e-9 * (1 + Math.abs(f0) + Math.abs(f1)))
    throw new Error('no lineal');
  return { m: f1 - f0, n: f0 };
}

/** Tramo de la recta dentro del rectángulo [x0, x1] × [y0, y1] (coordenadas del gráfico). */
function clipLineEq(l, [x0, x1], [y0, y1]) {
  if ('c' in l) return l.c >= x0 && l.c <= x1 ? [[l.c, y0], [l.c, y1]] : null;
  const pts = [];
  const add = (x, y) => {
    const ex = 1e-9 * (x1 - x0), ey = 1e-9 * (y1 - y0);
    if (x >= x0 - ex && x <= x1 + ex && y >= y0 - ey && y <= y1 + ey) pts.push([x, y]);
  };
  add(x0, l.m * x0 + l.n); add(x1, l.m * x1 + l.n);
  if (l.m) { add((y0 - l.n) / l.m, y0); add((y1 - l.n) / l.m, y1); }
  if (pts.length < 2) return null;
  pts.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const a = pts[0], b = pts[pts.length - 1];
  return Math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-12 ? [a, b] : null;
}

/** Número con hasta 4 decimales y coma decimal. */
const fmtNum = v => String(+(Math.abs(v) < 5e-5 ? 0 : v).toFixed(4)).replace('.', ',');

/** Ecuación de la recta que pasa por p y q (coordenadas del gráfico). */
function lineEqText([x1, y1], [x2, y2]) {
  if (Math.abs(x2 - x1) < 1e-12) return `x = ${fmtNum(x1)}`;
  const m = (y2 - y1) / (x2 - x1), n = y1 - m * x1;
  const ns = Math.abs(n) < 5e-5 ? '' : (n < 0 ? ` − ${fmtNum(-n)}` : ` + ${fmtNum(n)}`);
  return `y = ${fmtNum(m)}x${ns}`;
}

/** Corte de los segmentos a1-a2 y b1-b2 (o null). */
function segInter(a1, a2, b1, b2) {
  const rx = a2[0] - a1[0], ry = a2[1] - a1[1], sx = b2[0] - b1[0], sy = b2[1] - b1[1];
  const den = rx * sy - ry * sx;
  if (Math.abs(den) < 1e-9) return null;
  const qx = b1[0] - a1[0], qy = b1[1] - a1[1];
  const t = (qx * sy - qy * sx) / den, u = (qx * ry - qy * rx) / den;
  const e = 1e-6;
  return t >= -e && t <= 1 + e && u >= -e && u <= 1 + e ? [a1[0] + t * rx, a1[1] + t * ry] : null;
}

Object.assign(Edit, {
  /** Botones de la barra de Formas. */
  graphButtons() {
    if (!this.info) return [];
    const cal = this.calibs?.[this.viewer.n];
    const btn = (label, title, onclick, on = false) => h('button', { title, class: on ? 'on' : '', onclick }, label);
    return [h('span', { class: 'sep' }),
      h('button', { title: 'Dibuja rectas y = m·x + n sobre un gráfico de esta página', onclick: () => this.eqLine() }, icon('line'), ' Recta por ecuación…'),
      btn('Recta por dos puntos', 'Clic en dos puntos: se ajustan a intersecciones, extremos y rectas ya dibujadas', () => this.startTwo(), this.graph?.mode === 'two'),
      h('label', { class: 'inline', title: 'Recta por dos puntos: prolongarla hasta los bordes del gráfico en vez de dibujar solo el tramo' },
        h('input', { type: 'checkbox', checked: !!this.twoExtend, onchange: e => { this.twoExtend = e.target.checked; } }), 'Prolongar'),
      btn('Intersecciones', 'Muestra los cortes entre las líneas con sus coordenadas (clic en una para copiarla)', () => this.toggleInter(), !!this.showInter),
      cal ? btn('Recalibrar ejes', 'Vuelve a marcar las esquinas del gráfico', () => this.calibrate(null)) : null];
  },
  eqLine() {
    if (!this.info) return;
    if (!this.calibs?.[this.viewer.n]) return this.calibrate('eq');
    this.askLineEq();
  },
  startTwo() {
    if (!this.info) return;
    if (!this.calibs?.[this.viewer.n]) return this.calibrate('two');
    if (this.graph?.mode === 'two') { this.graph = null; return this.draw(); }  // pulsar otra vez: termina
    if (this.tool !== 'shape') this.setTool('shape');
    this.graph = { mode: 'two', n: this.viewer.n, pts: [] };
    this.draw();
  },
  toggleInter() {
    if (!this.info) return;
    if (!this.calibs?.[this.viewer.n]) { this.showInter = true; return this.calibrate(null); }
    this.showInter = !this.showInter;
    this.draw();
  },
  calibrate(then) {
    if (this.tool !== 'shape') this.setTool('shape');
    this.graph = { mode: 'calib', n: this.viewer.n, pts: [], then };
    this.draw();
  },
  /** Conversión entre la vista y las coordenadas del gráfico calibrado de la página n. */
  calX(n = this.viewer.n) {
    const cal = this.calibs?.[n];
    if (!cal) return null;
    const [a, b] = cal;
    const kx = (b.v[0] - a.v[0]) / (b.d[0] - a.d[0]), ky = (b.v[1] - a.v[1]) / (b.d[1] - a.d[1]);
    return {
      xr: [Math.min(a.d[0], b.d[0]), Math.max(a.d[0], b.d[0])],
      yr: [Math.min(a.d[1], b.d[1]), Math.max(a.d[1], b.d[1])],
      toView: ([x, y]) => [a.v[0] + (x - a.d[0]) * kx, a.v[1] + (y - a.d[1]) * ky],
      toData: ([x, y]) => [a.d[0] + (x - a.v[0]) / kx, a.d[1] + (y - a.v[1]) / ky],
    };
  },
  /** Líneas y flechas de la página, como segmentos en coordenadas de la vista. */
  pageSegs() {
    return (this.st?.annots || []).filter(a => a.type === 'Line' && a.points?.length >= 2)
      .map(a => [a.points[0], a.points[a.points.length - 1]]);
  },
  /** Cortes entre las líneas de la página que caen dentro del gráfico (vista). */
  intersections() {
    const X = this.calX(), segs = this.pageSegs(), out = [];
    if (!X) return out;
    const ex = 1e-6 * (X.xr[1] - X.xr[0]), ey = 1e-6 * (X.yr[1] - X.yr[0]);
    for (let i = 0; i < segs.length; i++) for (let j = i + 1; j < segs.length; j++) {
      const p = segInter(...segs[i], ...segs[j]);
      if (!p) continue;
      const [x, y] = X.toData(p);
      if (x < X.xr[0] - ex || x > X.xr[1] + ex || y < X.yr[0] - ey || y > X.yr[1] + ey) continue;
      if (!out.some(q => Math.hypot(q[0] - p[0], q[1] - p[1]) < 0.5)) out.push(p);
    }
    return out;
  },
  /** Ajusta p (vista) a la intersección, extremo o recta más cercana. */
  snap(p, free = false) {
    if (free) return { p, kind: null };
    const tol = 9 / this.viewer.zoom, segs = this.pageSegs();
    const near = (cands, kind) => {
      let best = null, bd = tol;
      for (const c of cands) { const d = Math.hypot(c[0] - p[0], c[1] - p[1]); if (d <= bd) { bd = d; best = c; } }
      return best && { p: best, kind };
    };
    const corners = (this.calibs?.[this.viewer.n] || []).map(c => c.v);
    const hit = near(this.intersections(), 'intersección') || near(segs.flat().concat(corners), 'extremo');
    if (hit) return hit;
    let best = null, bd = tol;
    for (const [a, b] of segs) {
      const dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy;
      if (!L) continue;
      const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L));
      const q = [a[0] + t * dx, a[1] + t * dy], d = Math.hypot(q[0] - p[0], q[1] - p[1]);
      if (d <= bd) { bd = d; best = q; }
    }
    return best ? { p: best, kind: 'recta' } : { p, kind: null };
  },
  /** Círculo de marca en el punto p (vista). */
  gdot(p, color, r = 4, filled = false) {
    const d = this.viewer.box([p[0] - r, p[1] - r, p[0] + r, p[1] + r], 'gdot');
    Object.assign(d.style, { border: `2px solid ${color}`, borderRadius: '50%', pointerEvents: 'none', boxSizing: 'border-box',
      background: filled ? color : 'transparent' });
    return d;
  },
  /** Marcas de calibración, intersecciones, puntos elegidos y ayuda. */
  drawGraph() {
    if (this.graph && this.tool !== 'shape') this.graph = null;  // se cambió de herramienta
    const v = this.viewer, g = this.graph, X = this.calX();
    if (g) $$('.bx.annot', v.ov).forEach(d => { d.style.pointerEvents = 'none'; });  // que los clics lleguen a la página
    const cpts = g?.mode === 'calib' && g.n === v.n ? g.pts : (this.tool === 'shape' && this.calibs?.[v.n]) || [];
    for (const p of cpts) this.gdot(p.v, '#1a4fd6');
    if (this.showInter && X && this.tool === 'shape') {
      for (const p of this.intersections()) {
        this.gdot(p, '#e63946', 4);
        const [x, y] = X.toData(p), txt = `(${fmtNum(x)}; ${fmtNum(y)})`;
        const lab = v.box([p[0] + 6, p[1] - 18, p[0] + 7, p[1] - 4], 'glabel');
        lab.textContent = txt;
        Object.assign(lab.style, { width: 'auto', height: 'auto', whiteSpace: 'nowrap', font: '11px system-ui, sans-serif', color: '#e63946',
          background: 'rgba(255,255,255,.88)', padding: '1px 4px', borderRadius: '4px', cursor: 'copy', pointerEvents: g ? 'none' : 'auto' });
        lab.title = 'Clic para copiar las coordenadas';
        lab.addEventListener('mousedown', e => {
          e.stopPropagation();
          navigator.clipboard?.writeText(`${fmtNum(x)}; ${fmtNum(y)}`).catch(() => {});
          toast(`Intersección ${txt} copiada.`, 'ok', [], 2500);
        });
      }
    }
    if (g?.mode === 'two' && g.n === v.n) {
      for (const p of g.pts) this.gdot(p, '#2a9d8f', 4, true);
      if (!v.ov._graphHover) {
        v.ov._graphHover = true;
        v.ov.addEventListener('mousemove', e => this.graphHover(e));
        v.ov.addEventListener('mouseleave', () => { this.hoverDot?.remove(); });
      }
    }
    if (!g) return;
    if (g.mode === 'two') {
      return this.hint(`Recta por dos puntos (${g.pts.length + 1}/2): clic en un punto. Se ajusta a intersecciones, extremos y rectas (Alt: sin ajuste). `
        + `${this.twoExtend ? 'Se prolonga hasta los bordes. ' : ''}Esc o el mismo botón para terminar.`);
    }
    this.hint(g.pts.length === 0
      ? 'Calibrar ejes (1/2): haz clic en una esquina del gráfico de coordenadas conocidas, p. ej. el origen (0; 0). Ctrl + rueda para hacer zoom y afinar. Esc cancela.'
      : 'Calibrar ejes (2/2): ahora haz clic en la esquina opuesta del gráfico, p. ej. (1; 1). Esc cancela.');
  },
  graphHover(e) {
    const g = this.graph, v = this.viewer;
    this.hoverDot?.remove();
    if (g?.mode !== 'two' || g.n !== v.n || e.currentTarget !== v.ov) return;
    const s = this.snap(v.pt(e), e.altKey);
    this.hoverDot = this.gdot(s.p, s.kind ? '#2a9d8f' : '#8a94a6', s.kind === 'intersección' ? 6 : 4);
    const X = this.calX();
    if (X) { const [x, y] = X.toData(s.p); this.hoverDot.title = `(${fmtNum(x)}; ${fmtNum(y)})`; }
  },
  async graphClick(e) {
    if (this.graph.mode === 'two') return this.twoClick(e);
    const v = this.viewer, g = this.graph;
    if (g.n !== v.n) { g.n = v.n; g.pts = []; }
    const p = v.pt(e);
    g.pts.push({ v: p, d: null });
    this.draw();
    const def = g.pts.length === 1 ? '0; 0' : '1; 1';
    let d = null;
    while (!d) {
      const s = await ask('Punto de referencia', 'Coordenadas de este punto en el gráfico (x; y)', def);
      if (s == null) { g.pts.pop(); this.draw(); return; }
      const parts = s.replace(/[()]/g, '').split(/\s*;\s*|\s+/).filter(Boolean).map(x => +x.replace(',', '.'));
      if (parts.length === 2 && parts.every(isFinite)) d = parts;
      else toast('Escribe las dos coordenadas separadas por «;», por ejemplo 0,5; 0,25', 'err');
    }
    g.pts[g.pts.length - 1].d = d;
    if (g.pts.length < 2) return this.draw();
    const [a, b] = g.pts;
    if (a.d[0] === b.d[0] || a.d[1] === b.d[1] || Math.abs(a.v[0] - b.v[0]) < 2 || Math.abs(a.v[1] - b.v[1]) < 2) {
      toast('Los dos puntos deben ser esquinas opuestas (distinta x y distinta y). Vuelve a marcar el segundo.', 'err');
      g.pts.pop(); return this.draw();
    }
    this.calibs = this.calibs || {};
    this.calibs[g.n] = g.pts;
    this.graph = null;
    this.draw();
    if (g.then === 'eq') this.askLineEq();
    else if (g.then === 'two') this.startTwo();
    else toast('Ejes calibrados.', 'ok', [], 2500);
  },
  async twoClick(e) {
    const v = this.viewer, g = this.graph, X = this.calX();
    if (!X) { this.graph = null; return this.calibrate('two'); }
    if (g.n !== v.n) { g.n = v.n; g.pts = []; }
    g.pts.push(this.snap(v.pt(e), e.altKey).p);
    if (g.pts.length < 2) return this.draw();
    const [p1, p2] = g.pts.map(X.toData);
    g.pts = [];
    if (Math.hypot(p2[0] - p1[0], p2[1] - p1[1]) < 1e-9) { toast('Los dos puntos son el mismo.', 'err'); return this.draw(); }
    let seg = [p1, p2];
    if (this.twoExtend) {
      const l = Math.abs(p2[0] - p1[0]) < 1e-12 ? { c: p1[0] } : { m: (p2[1] - p1[1]) / (p2[0] - p1[0]) };
      if ('m' in l) l.n = p1[1] - l.m * p1[0];
      seg = clipLineEq(l, X.xr, X.yr) || seg;
    }
    const p = seg.map(X.toView), sh = this.shape;
    const rect = [Math.min(p[0][0], p[1][0]), Math.min(p[0][1], p[1][1]), Math.max(p[0][0], p[1][0]), Math.max(p[0][1], p[1][1])];
    const ok = await this.op('add_shape', { kind: 'line', rect, points: p, stroke: sh.stroke, fill: null, width: sh.width, dash: sh.dash }, 'Dibujando recta…');
    if (!ok) return;
    const eq = lineEqText(p1, p2);
    toast(`Recta dibujada: ${eq}  ·  de (${fmtNum(p1[0])}; ${fmtNum(p1[1])}) a (${fmtNum(p2[0])}; ${fmtNum(p2[1])})`, 'ok',
      [{ label: 'Copiar ecuación', fn: () => navigator.clipboard?.writeText(eq).catch(() => {}) }], 8000);
  },
  /** Diálogo con una fila por recta (ecuación + color). Devuelve [{seg, color}] o null. */
  lineEqDialog(xr, yr) {
    const COLORS = ['#d62828', '#1a4fd6', '#2a9d8f', '#f4a261', '#7b2cbf', '#111111'];
    this.eqColor = this.eqColor || 0;
    const list = h('div', { style: 'display:flex;flex-direction:column;gap:6px;margin-top:8px' });
    const err = h('div', { style: 'color:#d62828;font-size:12px;min-height:16px;margin-top:6px' });
    const rows = [];
    const addRow = (focus = true) => {
      const eq = h('input', { placeholder: 'y = 0,5x + 0,3   ·   x = 0,35', style: 'flex:1;min-width:240px' });
      const color = h('input', { type: 'color', value: COLORS[this.eqColor++ % COLORS.length], title: 'Color de esta recta' });
      const row = { eq, color };
      const del = h('button', { title: 'Quitar esta recta', onclick: () => {
        if (rows.length === 1) { eq.value = ''; eq.focus(); return; }
        rows.splice(rows.indexOf(row), 1); row.el.remove(); rows[rows.length - 1].eq.focus();
      } }, '✕');
      row.el = h('div', { style: 'display:flex;gap:6px;align-items:center' }, eq, color, del);
      eq.addEventListener('input', () => { eq.style.borderColor = ''; err.textContent = ''; });
      eq.addEventListener('keydown', e => {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        if (e.metaKey || e.ctrlKey) return submit();
        const i = rows.indexOf(row);
        if (i < rows.length - 1) rows[i + 1].eq.focus();
        else if (eq.value.trim()) addRow();
        else submit();
      });
      rows.push(row); list.append(row.el);
      if (focus) eq.focus();
    };
    let submit;
    return new Promise(res => {
      const check = () => {
        const out = [];
        let bad = 0;
        for (const r of rows) {
          const s = r.eq.value.trim();
          if (!s) continue;
          let seg = null;
          try { seg = clipLineEq(parseLineEq(s), xr, yr); } catch { /* inválida */ }
          if (!seg) { bad++; r.eq.style.borderColor = '#d62828'; r.eq.title = 'No es una recta válida o no pasa por el gráfico'; }
          else { r.eq.style.borderColor = ''; r.eq.title = ''; out.push({ seg, color: r.color.value, eq: s }); }
        }
        if (bad) { err.textContent = bad === 1 ? 'Hay una recta que no se entiende o no pasa por el gráfico (en rojo).' : `Hay ${bad} rectas que no se entienden o no pasan por el gráfico (en rojo).`; return false; }
        if (!out.length) { err.textContent = 'Escribe al menos una recta.'; return false; }
        res(out);
        return true;
      };
      const close = modal({
        title: 'Rectas por ecuación', wide: true,
        body: h('div', {},
          h('div', { class: 'muted', style: 'font-size:12px' }, 'Una recta por línea: y = m·x + n o x = c (vertical). Intro pasa a la línea siguiente; Ctrl+Intro dibuja. Grosor y trazo: los de la barra de Formas.'),
          list,
          h('button', { style: 'margin-top:8px', onclick: () => addRow() }, '+ Añadir recta'),
          err),
        actions: [{ label: 'Cancelar', fn: () => res(null) }, { label: 'Dibujar', primary: true, fn: () => check() }],
        onclose: () => res(null),
      });
      submit = () => { if (check()) close(); };
      addRow();
    });
  },
  async askLineEq() {
    const n = this.viewer.n, X = this.calX(n);
    if (!X) return;
    const lines = await this.lineEqDialog(X.xr, X.yr);
    if (!lines) return;
    const toView = X.toView;
    const sh = this.shape;
    for (const { seg, color } of lines) {
      const p = seg.map(toView);
      const rect = [Math.min(p[0][0], p[1][0]), Math.min(p[0][1], p[1][1]), Math.max(p[0][0], p[1][0]), Math.max(p[0][1], p[1][1])];
      if (this.viewer.n !== n) break;
      await this.op('add_shape', { kind: 'line', rect, points: p, stroke: color, fill: null, width: sh.width, dash: sh.dash }, 'Dibujando recta…');
    }
  },
});
