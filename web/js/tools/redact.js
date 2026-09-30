'use strict';
// Herramienta Censurar.

/* ======================================================================
   CENSURAR
   ====================================================================== */

const Redact = {
  init() {
    this.root = $('#tool-redact');
    this.viewer = new ContViewer($('.viewer-host', this.root), { keepOverlays: true, firstClickActivates: false });
    this.viewer.onrender = () => this.draw();
    this.viewer.onpage = n => { if (!this.preview) this.ensureWords(n); };
    this.viewer.on('mousedown', e => this.down(e));
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
    // cambiar marcas o estilo invalida la vista previa
    $('[data-k=style]', this.root).addEventListener('change', () => { if (this.preview) { this.exitPreview(false); this.showPreview(); } });
    act('save', () => this.save());
    act('preview', () => this.showPreview());
    act('back', () => this.exitPreview());
    act('savepreview', () => saveResult(this.preview?.res));
    $$('[data-mode]', this.root).forEach(b => b.onclick = () => {
      $$('[data-mode]', this.root).forEach(x => x.classList.toggle('on', x === b));
      this.mode = b.dataset.mode;
    });
  },
  status(t) { $('.status', this.root).textContent = t; },
  async openFile(f) { const info = await run('Abriendo…', () => uploadFile(f)); if (info) this.loadInfo(info); },
  loadInfo(info) {
    if (info.encrypted || !info.pages.length) return toast('No se puede abrir: tiene contraseña o no es un PDF/imagen.', 'err');
    this.exitPreview(false);
    this.info = info; this.marks = {}; this.words = {};
    setCurrent(info);
    $('.doc-name', this.root).textContent = info.name;
    this.viewer.load(info);
    this.ensureWords(0);
    this.restoreMarks();
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
    if (!this.info) return;
    if (!this.preview) this.persist();
    const pages = v.pages ? v.pages.length : 1;
    for (let n = 0; n < pages; n++) {
      const ov = v.pageOv(n);
      if (!ov) continue;
      ov.replaceChildren();
      ov.classList.add('draw');
      if (this.preview) { ov.classList.remove('draw'); continue; }
      (this.marks[n] || []).forEach((g, gi) => g.forEach((r, ri) => {
        const isSel = this.selMark && this.selMark.n === n && this.selMark.gi === gi && this.selMark.ri === ri;
        const d = v.box(r, 'mark' + (isSel ? ' sel' : ''), ov);
        d.title = 'Clic para seleccionar; ✕ o Supr para quitar esta zona';
        d.addEventListener('mousedown', e => { e.stopPropagation(); this.selMark = { n, gi, ri }; this.draw(); });
        if (isSel) d.append(h('div', { class: 'x', title: 'Quitar esta zona', onmousedown: e => { e.stopPropagation(); this.removeMark(); } }, '✕'));
      }));
    }
  },
  /** Recupera las zonas marcadas la última vez en este mismo documento. */
  async restoreMarks() {
    const id = this.info.id;
    const r = await api('redact/marks/load', { id }).catch(() => null);
    if (!r || this.info?.id !== id || !r.marks || !Object.keys(r.marks).length) return;
    this.marks = {};
    for (const [n, groups] of Object.entries(r.marks)) this.marks[+n] = groups;
    if (r.style) $('[data-k=style]', this.root).value = r.style;
    this.restoring = true;
    this.draw();
    this.restoring = false;
    toast(`Se han recuperado ${this.count()} zona(s) marcadas la última vez en este documento.`, 'ok',
      [{ label: 'Descartarlas', fn: () => { this.marks = {}; this.draw(); } }], 8000);
  },
  persist() {
    if (!this.info || this.restoring) return;
    clearTimeout(this._pt);
    this._pt = setTimeout(() => api('redact/marks/save', { id: this.info.id, marks: this.marks, style: $('[data-k=style]', this.root).value }).catch(() => {}), 400);
  },
  collectMarks() {
    const marks = {};
    for (const [n, gs] of Object.entries(this.marks)) { const f = gs.flat(); if (f.length) marks[n] = f; }
    return marks;
  },
  /** Aplica la censura a una copia y la muestra en su lugar, en la misma página. */
  async showPreview() {
    if (!this.info) return;
    if (this.preview) return this.exitPreview();
    const marks = this.collectMarks();
    if (!Object.keys(marks).length) return toast('No hay nada marcado para censurar.', 'err');
    const r = await run('Preparando la vista previa…', () => api('redact/preview', { id: this.info.id, marks, style: $('[data-k=style]', this.root).value }));
    if (!r) return;
    this.preview = { info: r.info, res: { rid: r.rid, files: [{ name: r.info.name, size: r.info.size }] } };
    this.selMark = null;
    $('.preview-banner', this.root).hidden = false;
    $('[data-act=preview]', this.root).classList.add('on');
    $('[data-act=preview]', this.root).textContent = '✎ Volver a editar';
    this.viewer.swap(r.info);
    this.status('Vista previa. Comprueba que no se ve nada de lo tapado; vuelve a editar para cambiar zonas.');
  },
  exitPreview(swap = true) {
    if (!this.preview) return;
    api('close', { id: this.preview.info.id }).catch(() => {});
    this.preview = null;
    $('.preview-banner', this.root).hidden = true;
    $('[data-act=preview]', this.root).classList.remove('on');
    $('[data-act=preview]', this.root).textContent = '👁 Vista previa';
    if (swap && this.info) { this.viewer.swap(this.info); this.ensureWords(this.viewer.n); }
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
    if (e.button !== 0 || !this.info || this.preview) return;
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
    if (this.preview) return saveResult(this.preview.res);
    const marks = this.collectMarks();
    if (!Object.keys(marks).length) return toast('No hay nada marcado para censurar.', 'err');
    const res = await run('Censurando…', () => api('redact', { id: this.info.id, marks, style: $('[data-k=style]', this.root).value }));
    saveResult(res);
  },
};
