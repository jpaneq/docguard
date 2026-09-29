'use strict';
// Herramienta Censurar.

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
    if (!w) return null;
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
