'use strict';
// Herramienta Unir PDFs: vista de lista de archivos y vista de páginas (cuadrícula)
// con reordenación libre e inserción de documentos en cualquier punto.

const DOC_COLORS = ['#2563d9', '#e0822b', '#1f9d55', '#b83280', '#7c3aed', '#0e9aa7', '#c53030', '#8a6d1f'];

const Merge = {
  init() {
    this.root = $('#tool-merge');
    this.view = 'list';
    this.pages = null;       // [{id, idx, rot}] cuando se ha tocado la cuadrícula; null = orden de la lista
    this.files = new FileList($('[data-role=files]', this.root), {
      accept: ACCEPT_DOCS, onchange: () => this.syncFromList(),
    });
    $$('[data-view]', this.root).forEach(b => b.onclick = () => this.setView(b.dataset.view));
    $('[data-act=add]', this.root).onclick = async () => this.insertFiles(await pickFiles(ACCEPT_DOCS, true), null);
    $('[data-act=merge]', this.root).onclick = () => this.merge();
    $('[data-act=reset]', this.root).onclick = () => { this.pages = null; this.render(); };
    dropTarget($('[data-pane=grid]', this.root), f => this.insertFiles(f, null));
  },
  loadInfo(info) { this.files.setItems([info]); },

  color(id) {
    const i = this.files.items.findIndex(f => f.id === id);
    return DOC_COLORS[(i < 0 ? 0 : i) % DOC_COLORS.length];
  },
  docOf(id) { return this.files.items.find(f => f.id === id); },
  /** Páginas en el orden actual (las de la lista si no se ha reordenado a mano). */
  currentPages() {
    if (this.pages) return this.pages;
    return this.files.items.flatMap(f => (f.pages.length ? f.pages : [[0, 0]]).map((_, idx) => ({ id: f.id, idx, rot: 0 })));
  },
  syncFromList() {
    if (this.pages) {
      const ids = new Set(this.files.items.map(f => f.id));
      this.pages = this.pages.filter(p => ids.has(p.id));
      // documentos añadidos desde la lista: sus páginas van al final
      for (const f of this.files.items) {
        if (!this.pages.some(p => p.id === f.id)) f.pages.forEach((_, idx) => this.pages.push({ id: f.id, idx, rot: 0 }));
      }
    }
    this.render();
  },
  setView(v) {
    this.view = v;
    $$('[data-view]', this.root).forEach(b => b.classList.toggle('on', b.dataset.view === v));
    $$('[data-pane]', this.root).forEach(p => { p.hidden = p.dataset.pane !== v; });
    this.render();
  },
  /** Sube archivos y los inserta en la posición pos de la cuadrícula (null = al final). */
  async insertFiles(files, pos) {
    if (!files.length) return;
    const infos = [];
    busy(true, 'Abriendo…');
    try {
      for (const f of files) {
        try { infos.push(await uploadFile(f)); } catch (e) { toast(e.message, 'err'); }
      }
    } finally { busy(false); }
    const bad = infos.filter(i => !i.pages.length || i.encrypted);
    if (bad.length) toast(`No se pueden unir: ${bad.map(b => b.name).join(', ')} (con contraseña o formato no admitido).`, 'err');
    const ok = infos.filter(i => i.pages.length && !i.encrypted);
    if (!ok.length) return;
    if (pos !== null || this.pages) {
      const cur = this.currentPages().slice();
      const add = ok.flatMap(i => i.pages.map((_, idx) => ({ id: i.id, idx, rot: 0 })));
      cur.splice(pos === null ? cur.length : pos, 0, ...add);
      this.pages = cur;
    }
    this.files.items.push(...ok);
    this.files.render();
    this.render();
    toast(`${ok.length} documento(s) añadido(s)${pos !== null ? ` en la posición ${pos + 1}` : ''}.`, 'ok', [], 2500);
  },
  render() {
    const pages = this.currentPages();
    $('[data-role=count]', this.root).textContent = this.files.items.length
      ? `${this.files.items.length} documento(s) · ${pages.length} página(s)` : '';
    $('[data-act=reset]', this.root).hidden = !this.pages;
    if (this.view !== 'grid') return;
    const grid = $('[data-pane=grid]', this.root);
    grid.innerHTML = '';
    if (!pages.length) {
      grid.append(h('div', { class: 'empty' }, 'Añade o arrastra aquí PDFs o imágenes para ver sus páginas.'));
      return;
    }
    // leyenda de documentos
    grid.append(h('div', { class: 'merge-legend' }, this.files.items.map(f =>
      h('span', { class: 'lg' }, h('i', { style: `background:${this.color(f.id)}` }), f.name))));
    const wrap = h('div', { class: 'merge-pages' });
    const slot = pos => {
      const b = h('button', { class: 'ins', title: 'Insertar aquí un PDF o una imagen' }, '+');
      b.onclick = async () => this.insertFiles(await pickFiles(ACCEPT_DOCS, true), pos);
      b.addEventListener('dragover', e => { if (e.dataTransfer.types.includes('Files') || e.dataTransfer.types.includes('text/x-mp')) { e.preventDefault(); b.classList.add('over'); } });
      b.addEventListener('dragleave', () => b.classList.remove('over'));
      b.addEventListener('drop', e => {
        e.preventDefault(); e.stopPropagation(); b.classList.remove('over');
        if (e.dataTransfer.files.length) return this.insertFiles([...e.dataTransfer.files], pos);
        const from = e.dataTransfer.getData('text/x-mp');
        if (from !== '') this.movePage(+from, pos);
      });
      return b;
    };
    pages.forEach((p, k) => {
      wrap.append(slot(k));
      const doc = this.docOf(p.id);
      const col = this.color(p.id);
      const card = h('div', { class: 'mp', draggable: true, style: `--dc:${col}`, title: `${doc?.name || ''} — página ${p.idx + 1}` },
        h('div', { class: 'mp-img' }, h('img', { src: pageUrl(p.id, p.idx, 0.3), style: `transform:rotate(${p.rot}deg)`, draggable: false, loading: 'lazy' })),
        h('div', { class: 'mp-foot' },
          h('span', { class: 'mp-n' }, k + 1),
          h('span', { class: 'mp-doc' }, `${(doc?.name || '').replace(/\.[^.]+$/, '').slice(0, 14)} · p${p.idx + 1}`),
          h('span', {},
            h('button', { title: 'Girar', onclick: () => { this.edit(); this.pages[k].rot = (this.pages[k].rot + 90) % 360; this.render(); } }, '↻'),
            h('button', { title: 'Quitar esta página', onclick: () => { this.edit(); this.pages.splice(k, 1); this.render(); } }, '✕'))));
      card.addEventListener('dragstart', e => e.dataTransfer.setData('text/x-mp', k));
      card.addEventListener('dragover', e => { if (e.dataTransfer.types.includes('text/x-mp')) { e.preventDefault(); card.classList.add('over'); } });
      card.addEventListener('dragleave', () => card.classList.remove('over'));
      card.addEventListener('drop', e => {
        const from = e.dataTransfer.getData('text/x-mp');
        if (from === '') return;
        e.preventDefault(); e.stopPropagation();
        this.movePage(+from, k);
      });
      wrap.append(card);
    });
    wrap.append(slot(pages.length));
    grid.append(wrap);
  },
  edit() { if (!this.pages) this.pages = this.currentPages().map(p => ({ ...p })); },
  movePage(from, to) {
    this.edit();
    const [p] = this.pages.splice(from, 1);
    this.pages.splice(to > from ? to - 1 : to, 0, p);
    this.render();
  },
  async merge() {
    const pages = this.currentPages();
    if (!pages.length) return toast('Añade algún documento.', 'err');
    if (!this.pages && this.files.items.length < 2) return toast('Añade al menos dos documentos (o reordena páginas en «Ver páginas»).', 'err');
    saveResult(await run('Uniendo…', () => this.pages
      ? api('merge_pages', { items: pages.map(p => [p.id, p.idx, p.rot]) })
      : api('merge', { ids: this.files.ids })));
  },
};
