'use strict';
// Herramienta Páginas.

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
