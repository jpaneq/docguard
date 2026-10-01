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

Object.assign(Edit, {
  /** Botones de la barra de Formas. */
  graphButtons() {
    if (!this.info) return [];
    const cal = this.calibs?.[this.viewer.n];
    return [h('span', { class: 'sep' }),
      h('button', { title: 'Dibuja rectas y = m·x + n sobre un gráfico de esta página', onclick: () => this.eqLine() }, icon('line'), ' Recta por ecuación…'),
      cal ? h('button', { title: 'Vuelve a marcar las esquinas del gráfico', onclick: () => this.calibrate(false) }, 'Recalibrar ejes') : null];
  },
  eqLine() {
    if (!this.info) return;
    if (!this.calibs?.[this.viewer.n]) return this.calibrate(true);
    this.askLineEq();
  },
  calibrate(thenAsk) {
    if (this.tool !== 'shape') this.setTool('shape');
    this.graph = { n: this.viewer.n, pts: [], thenAsk };
    this.draw();
  },
  /** Marcas de calibración y ayuda mientras se calibra. */
  drawGraph() {
    if (this.graph && this.tool !== 'shape') this.graph = null;  // se cambió de herramienta
    const v = this.viewer, g = this.graph;
    const pts = g && g.n === v.n ? g.pts : (this.tool === 'shape' && this.calibs?.[v.n]) || [];
    for (const p of pts) {
      const [x, y] = p.v;
      const d = v.box([x - 4, y - 4, x + 4, y + 4], 'calib');
      Object.assign(d.style, { border: '2px solid #1a4fd6', borderRadius: '50%', pointerEvents: 'none', background: 'transparent' });
    }
    if (g) this.hint(g.pts.length === 0
      ? 'Recta por ecuación (1/2): haz clic en una esquina del gráfico de coordenadas conocidas, p. ej. el origen (0; 0). Ctrl + rueda para hacer zoom y afinar. Esc cancela.'
      : 'Recta por ecuación (2/2): ahora haz clic en la esquina opuesta del gráfico, p. ej. (1; 1). Esc cancela.');
  },
  async graphClick(e) {
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
    if (g.thenAsk) this.askLineEq();
    else toast('Ejes calibrados. Pulsa «Recta por ecuación…» para dibujar.', 'ok', [], 3000);
  },
  async askLineEq() {
    const n = this.viewer.n, cal = this.calibs?.[n];
    if (!cal) return;
    const s = await ask('Recta por ecuación',
      'Ecuación de la recta, p. ej. y = 0,5x + 0,3  ·  x = 0,35  (varias separadas por «;»)', this.lastEq || '');
    if (s == null || !s.trim()) return;
    this.lastEq = s;
    const [a, b] = cal;
    const xr = [Math.min(a.d[0], b.d[0]), Math.max(a.d[0], b.d[0])];
    const yr = [Math.min(a.d[1], b.d[1]), Math.max(a.d[1], b.d[1])];
    const toView = ([x, y]) => [a.v[0] + (x - a.d[0]) * (b.v[0] - a.v[0]) / (b.d[0] - a.d[0]),
                                a.v[1] + (y - a.d[1]) * (b.v[1] - a.v[1]) / (b.d[1] - a.d[1])];
    const sh = this.shape;
    for (const eq of s.split(';').map(x => x.trim()).filter(Boolean)) {
      let l;
      try { l = parseLineEq(eq); } catch { toast(`No entiendo «${eq}». Escribe por ejemplo y = 0,5x + 0,3 o x = 0,35.`, 'err'); continue; }
      const seg = clipLineEq(l, xr, yr);
      if (!seg) { toast(`«${eq}» no pasa por la zona del gráfico.`, 'err'); continue; }
      const p = seg.map(toView);
      const rect = [Math.min(p[0][0], p[1][0]), Math.min(p[0][1], p[1][1]), Math.max(p[0][0], p[1][0]), Math.max(p[0][1], p[1][1])];
      if (this.viewer.n !== n) break;
      await this.op('add_shape', { kind: 'line', rect, points: p, stroke: sh.stroke, fill: null, width: sh.width, dash: sh.dash }, 'Dibujando recta…');
    }
  },
});
