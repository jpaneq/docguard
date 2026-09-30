'use strict';
// Herramienta Comparar versiones: dos PDFs lado a lado con los cambios marcados.

const Compare = {
  init() {
    this.root = $('#tool-compare');
    this.va = new ContViewer($('[data-role=a]', this.root), { keepOverlays: true, firstClickActivates: false });
    this.vb = new ContViewer($('[data-role=b]', this.root), { keepOverlays: true, firstClickActivates: false });
    this.va.onrender = () => this.draw();
    this.vb.onrender = () => this.draw();
    this.a = null; this.b = null; this.res = null;
    const act = (a, f) => { $(`[data-act=${a}]`, this.root).onclick = f; };
    act('opena', async () => { const [f] = await pickFiles(ACCEPT_PDF); if (f) this.open('a', f); });
    act('openb', async () => { const [f] = await pickFiles(ACCEPT_PDF); if (f) this.open('b', f); });
    act('run', () => this.run());
    dropTarget(this.va.el, f => this.open('a', f[0]));
    dropTarget(this.vb.el, f => this.open('b', f[0]));
    // desplazamiento sincronizado
    let lock = false;
    const sync = (from, to) => from.el.addEventListener('scroll', () => {
      if (lock || !$('[data-k=sync]', this.root).checked || !to.info) return;
      lock = true;
      const k = from.el.scrollTop / Math.max(1, from.el.scrollHeight - from.el.clientHeight);
      to.el.scrollTop = k * (to.el.scrollHeight - to.el.clientHeight);
      requestAnimationFrame(() => { lock = false; });
    });
    sync(this.va, this.vb);
    sync(this.vb, this.va);
    makeResizable($('.cmp-list', this.root), 'left', 'cmp', 220, 600);
  },
  loadInfo(info) { this.set('a', info); },
  async open(side, f) {
    const info = await run('Abriendo…', () => uploadFile(f));
    if (info) this.set(side, info);
  },
  set(side, info) {
    if (info.encrypted || !info.pages.length) return toast('No se puede abrir: tiene contraseña o no es un PDF.', 'err');
    this[side] = info;
    this.res = null;
    $(`[data-role=n${side}]`, this.root).textContent = info.name;
    (side === 'a' ? this.va : this.vb).load(info);
    this.renderList();
    if (this.a && this.b) this.run();
  },
  async run() {
    if (!this.a || !this.b) return toast('Abre el documento original y la nueva versión.', 'err');
    const r = await run('Comparando…', () => api('compare', { a: this.a.id, b: this.b.id }));
    if (!r) return;
    this.res = r;
    $('[data-role=summary]', this.root).textContent = r.no_text
      ? 'Uno de los documentos no tiene texto (¿escaneado?). Pásale OCR en Editar y vuelve a comparar.'
      : `${r.changes.length} cambio(s) · ${r.similarity}% igual · ${r.pages[0]} y ${r.pages[1]} páginas`;
    this.draw();
    this.renderList();
  },
  draw() {
    for (const [v, marks, cls] of [[this.va, this.res?.marks_a, 'del'], [this.vb, this.res?.marks_b, 'add']]) {
      if (!v.pages) continue;
      v.pages.forEach((p, n) => {
        p.ov.replaceChildren();
        for (const m of (marks && marks[n]) || []) v.box(m.r, `dmark ${cls}`, p.ov);
      });
    }
  },
  renderList() {
    const box = $('.cmp-list', this.root);
    box.innerHTML = '';
    box.append(h('h3', {}, 'Cambios'));
    if (!this.res) { box.append(h('p', { class: 'muted' }, 'Abre las dos versiones y pulsa «Comparar».')); return; }
    if (!this.res.changes.length) { box.append(h('p', {}, '✔ No hay diferencias de texto entre las dos versiones.')); return; }
    this.res.changes.forEach(c => box.append(h('div', { class: 'chg', onclick: () => this.goto(c) },
      h('div', { class: 't' }, `${c.type} · pág. ${c.page_a + 1} → ${c.page_b + 1}`),
      c.old ? h('del', {}, c.old) : null, c.old && c.new ? ' → ' : null, c.new ? h('ins', {}, c.new) : null)));
  },
  goto(c) {
    const show = (v, n, marks) => {
      const m = (marks[n] || [])[0];
      v.go(n);
      if (m) v.el.scrollTop = v.pages[n].wrap.offsetTop + m.r[1] * v.zoom - v.el.clientHeight / 3;
    };
    const s = $('[data-k=sync]', this.root);
    const was = s.checked;
    s.checked = false;
    show(this.va, c.page_a, this.res.marks_a);
    show(this.vb, c.page_b, this.res.marks_b);
    setTimeout(() => { s.checked = was; }, 300);
  },
};
