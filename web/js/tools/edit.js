'use strict';
// Herramienta Editar PDF.

/* ======================================================================
   EDITAR PDF (herramienta unificada, estilo Acrobat / Word)
   ====================================================================== */

/** Mayús, Ctrl o ⌘ pulsados: añadir a la selección en vez de sustituirla. */
const multi = e => e.shiftKey || e.ctrlKey || e.metaKey;

const ICON = {
  select: '<path d="M5 3l11 6.2-4.8 1.3-2.4 4.5z"/><path d="M11.2 10.5l3.8 5.5"/>',
  text: '<path d="M4 6V3.5h12V6M10 3.5v13M7.5 16.5h5"/>',
  image: '<rect x="2.5" y="4" width="15" height="12" rx="1.5"/><circle cx="7" cy="8.2" r="1.4"/><path d="M3.5 15l4.2-4.2 3 3 2-2 3.8 3.7"/>',
  table: '<rect x="2.5" y="4" width="15" height="12" rx="1"/><path d="M2.5 8.5h15M2.5 12.5h15M8 4v12M13 4v12"/>',
  shape: '<rect x="2.5" y="8" width="8" height="8" rx=".5"/><circle cx="13" cy="7" r="4.5"/>',
  annot: '<path d="M3 17h6M5.5 13.5l7.8-7.8 3 3-7.8 7.8H5.5z"/><path d="M11.8 7.2l3 3"/>',
  form: '<rect x="2.5" y="5" width="15" height="10" rx="1.2"/><path d="M5.5 10h6M14 8v4"/>',
  sign: '<path d="M2.5 15.5c2.5-.5 3.5-6.5 5.8-6.5 1.8 0 .7 4.6 2.7 4.6 1.5 0 1.9-2.8 3.1-2.8 1 0 1 1.6 2.4 1.6"/><path d="M2.5 18h15"/>',
  copy: '<rect x="6.5" y="6.5" width="10" height="11" rx="1.5"/><path d="M4 13.5V4.2c0-.7.5-1.2 1.2-1.2H13"/>',
  cut: '<circle cx="5.5" cy="15" r="2.3"/><circle cx="14.5" cy="15" r="2.3"/><path d="M7.2 13.3L15 3M12.8 13.3L5 3"/>',
  paste: '<rect x="3.5" y="4" width="13" height="14" rx="1.5"/><rect x="7" y="2.2" width="6" height="3.6" rx="1"/>',
  print: '<path d="M6 7V3.5h8V7"/><rect x="2.5" y="7" width="15" height="7" rx="1.5"/><rect x="6" y="11.5" width="8" height="5.5" rx=".8"/>',
  trash: '<path d="M3.5 5.5h13M8 5.5V3.5h4v2M5.5 5.5l.8 11.5h7.4l.8-11.5M8.5 8.5v6M11.5 8.5v6"/>',
  undo: '<path d="M7 5L3 9l4 4"/><path d="M3 9h9.5a4.5 4.5 0 010 9H9"/>',
  redo: '<path d="M13 5l4 4-4 4"/><path d="M17 9H7.5a4.5 4.5 0 000 9H11"/>',
  ocr: '<path d="M3 6.5V3h3.5M13.5 3H17v3.5M17 13.5V17h-3.5M6.5 17H3v-3.5"/><path d="M6.5 7.5h7M6.5 10h7M6.5 12.5h4.5"/>',
  rect: '<rect x="3" y="5" width="14" height="10" rx=".5"/>',
  ellipse: '<ellipse cx="10" cy="10" rx="7.5" ry="5.5"/>',
  line: '<path d="M3.5 16.5l13-13"/>',
  arrow: '<path d="M3.5 16.5l13-13M9.5 3.5h7v7"/>',
  highlight: '<rect x="2.5" y="7" width="15" height="6" rx="1" fill="currentColor" opacity=".35" stroke="none"/><path d="M4 10h12"/>',
  underline: '<path d="M6 3.5v6a4 4 0 008 0v-6M4.5 17h11"/>',
  strikeout: '<path d="M4 10h12M13.5 6c-.5-1.5-2-2.5-3.7-2.5-2 0-3.6 1.2-3.6 2.8M6.5 14c.5 1.5 2 2.5 3.7 2.5 2.1 0 3.8-1.2 3.8-2.9"/>',
  note: '<path d="M3.5 4h13v9h-7l-4 3.5V13h-2z"/>',
  freetext: '<rect x="2.5" y="4" width="15" height="12" rx="1"/><path d="M6.5 7.5h7M10 7.5v6"/>',
  ink: '<path d="M3 14c2-5 4-8 5.5-8s-.5 7 1.5 7 2.5-5 4-5 1.5 3 3 3"/>',
  bullet: '<circle cx="4.5" cy="5.5" r="1.3" fill="currentColor"/><circle cx="4.5" cy="10" r="1.3" fill="currentColor"/><circle cx="4.5" cy="14.5" r="1.3" fill="currentColor"/><path d="M8 5.5h9M8 10h9M8 14.5h9"/>',
  number: '<path d="M3.5 4l1-.6V7.5M3 11c.4-.8 2-.8 2 .2 0 .8-2 1.6-2 2.8h2.2M8 5.5h9M8 10h9M8 14.5h9"/>',
  letter: '<path d="M3 7.5l1.3-4 1.3 4M3.4 6.3h1.8M8 5.5h9M8 10h9M8 14.5h9"/><circle cx="4.3" cy="12.8" r="1.4"/>',
  nolist: '<path d="M4 5.5h13M4 10h13M4 14.5h9"/>',
  plus: '<path d="M10 4v12M4 10h12"/>',
  margin: '<rect x="4" y="2.5" width="12" height="15" rx="1"/><path d="M13.5 5c-1 2 1 3 0 5s1 3 0 5"/>',
  pages: '<rect x="2.5" y="3" width="5" height="6.5" rx="1"/><rect x="2.5" y="11" width="5" height="6.5" rx="1"/><path d="M10 4.5h7.5M10 8h5M10 12.5h7.5M10 16h5"/>',
  flatten: '<path d="M3 7l7-4 7 4-7 4z"/><path d="M3 11l7 4 7-4"/>',
  unwm: '<path d="M10 2.8c2.9 3.3 5 5.800 5 8.500a5 5 0 01-10 0c0-2.700 2.100-5.200 5-8.500z"/><path d="M3.500 3.500l13 13"/>',
};

function icon(name) {
  const s = document.createElement('span');
  s.className = 'svg';
  s.innerHTML = `<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${ICON[name] || ''}</svg>`;
  return s;
}
const ibtn = (name, title, onclick, on = false) =>
  h('button', { class: 'ib' + (on ? ' on' : ''), title, onclick, onmousedown: e => e.preventDefault() }, icon(name));

const Edit = {
  init() {
    this.root = $('#tool-edit');
    this.bar = $('.formatbar', this.root);
    this.statusEl = $('.status', this.root);
    $$('[data-i]', this.root).forEach(b => b.prepend(icon(b.dataset.i)));
    this.viewer = new ContViewer($('.viewer-host', this.root));
    this.viewer.onrender = () => this.draw();
    this.viewer.onpage = n => { if (this.inline) this.commitInline(); this.clearSel(false); this.st = null; this.refresh(); this.markThumb(n); };
    this.viewer.on('mousedown', e => this.down(e));
    this.viewer.on('mousemove', e => { this.mouse = { n: this.viewer.n, p: this.viewer.pt(e) }; });
    this.viewer.on('contextmenu', e => { if (e.target === this.viewer.ov) this.contextMenu(e); });
    this.side = $('.pages-side', this.root);
    makeResizable(this.side, 'right', 'edit-side', 120, 520);
    $('[data-act=pages]', this.root).onclick = () => this.toggleSide();
    this.tool = 'select'; this.sel = null; this.selSpans = new Set(); this.st = null;
    this.textOpts = { font: 'base:helv', size: 12, color: '#000000', bold: false, italic: false, list: 'none' };
    this.table = { rows: 3, cols: 3, header: true, stroke: '#000000', width: 1, size: 11, fill: '#e8e8e8' };
    this.shape = { kind: 'rect', stroke: '#d62828', fill: '#ffe066', filled: false, width: 2, dash: 'continua' };
    this.wordsCache = {};  // palabras por página, para seleccionar texto al resaltar
    this.ann = { kind: 'highlight', color: '#fff200', text: '' };
    this.widgetType = 'text'; this.sig = null; this.fonts = [];
    $$('[data-t]', this.root).forEach(b => b.onclick = () => this.setTool(b.dataset.t));
    const act = (a, f) => { $(`[data-act=${a}]`, this.root).onclick = f; };
    act('open', async () => { for (const f of await pickFiles(ACCEPT_DOCS, true)) await this.openFile(f); });
    act('undo', () => this.undo());
    act('redo', () => this.redo());
    act('copy', () => this.copyAny(false));
    act('cut', () => this.copyAny(true));
    act('paste', () => this.pasteAny());
    act('delete', () => this.deleteSel());
    act('ocr', () => this.ocrDialog());
    const find = $('[data-k=find]', this.root);
    find.addEventListener('keydown', e => {
      e.stopPropagation();
      if (e.key === 'Enter') { e.preventDefault(); if (find.value.trim() !== this.findTerm) this.find(find.value.trim()); else this.findStep(e.shiftKey ? -1 : 1); }
      if (e.key === 'Escape') { find.value = ''; this.find(''); find.blur(); }
    });
    act('findnext', () => this.findStep(1));
    act('findprev', () => this.findStep(-1));
    act('unwm', () => this.removeWatermarks());
    act('toword', async () => saveResult(await run('Convirtiendo a Word…', () => api('todocx', { ids: [this.info.id], mode: 'fiel' }))));
    act('export', async () => saveResult(await run('Preparando…', () => api('edit/export', { id: this.info.id }))));
    dropTarget(this.viewer.el, async fs => { for (const f of fs) await this.openFile(f); });
    document.addEventListener('keydown', e => this.key(e));
    document.addEventListener('mousedown', e => { if (this.menu && !this.menu.contains(e.target)) this.closeMenu(); });
    document.addEventListener('sigs-changed', () => { if (this.tool === 'sign') this.renderBar(); });
    // la lista de fuentes tarda ~0,3 s y bloquea el servidor: se pide un poco después para no retrasar
    // la primera página de un documento abierto al arrancar (solo hace falta para escribir texto)
    setTimeout(() => api('fonts').then(r => { this.fonts = r.fonts; this.renderBar(); }).catch(() => {}), 2500);
    this.draw();
  },

  /* ---- documento ---- */
  async openFile(f) {
    const info = await run('Abriendo…', () => uploadFile(f));
    if (info) this.loadInfo(info);
  },
  loadInfo(info) {
    if (info.encrypted) return toast('El PDF tiene contraseña: quítala primero en «Contraseña».', 'err');
    if (!info.pages.length) return toast('Solo se pueden editar PDFs e imágenes.', 'err');
    this.info = info; this.st = null; this.clearSel(false);
    this.calibs = {}; this.graph = null;  // rectas por ecuación (graphline.js)
    setCurrent(info);
    $('.doc-name', this.root).textContent = info.name;
    $('[data-act=export]', this.root).disabled = false;
    $('[data-act=toword]', this.root).disabled = false;
    $('[data-act=unwm]', this.root).disabled = false;
    this.viewer.load(info);
    this.outline = null;
    if (!this.side.hidden) this.renderSide();
    this.refresh().then(() => {
      if (this.st?.widgets.some(w => w.type === 'signature'))
        toast('Este PDF tiene firma digital: cualquier cambio la invalidará. Edita una copia y vuelve a firmar al final.', '', [], 9000);
    });
  },
  async refresh(rerender = false) {
    if (!this.info) return;
    const n = this.viewer.n;
    try { this.st = await api('edit/state', { id: this.info.id, n }); } catch (e) { return toast(e.message, 'err'); }
    this.st.n = n;
    $('[data-act=undo]', this.root).disabled = !this.st.can_undo;
    $('[data-act=redo]', this.root).disabled = !this.st.can_redo;
    if (rerender) this.viewer.refresh(); else this.draw();
  },
  async op(name, payload, busyMsg = 'Aplicando…', keepSel = false) {
    if (keepSel) this.lastSel = (this.st?.spans || []).filter(s => this.selSpans.has(s.i)).map(s => s.bbox);
    const r = await run(busyMsg, () => api('edit/' + name, { id: this.info.id, n: this.viewer.n, ...payload }));
    if (r === undefined) return false;
    if (r.message && /sustituta/.test(r.message)) toast('No se encontró la fuente original; se ha usado ' + r.message.replace(' (sustituta)', '') + '.', '', [], 4000);
    if (!keepSel) this.clearSel(false);
    this.wordsCache = {};
    await this.refresh(true);
    this.refreshThumb();
    if (!this.side.hidden && this.sideTab === 'comments') this.renderSide('comments');
    return true;
  },
  refreshThumb() {
    const t = $$('.tp img', this.side)[this.viewer.n];
    if (t) t.src = pageUrl(this.info.id, this.viewer.n, 0.5, Date.now());
  },
  async undo() {
    if (!this.info) return;
    await run('Deshaciendo…', () => api('edit/undo', { id: this.info.id }));
    this.clearSel(false); this.refresh(true);
  },
  async redo() {
    if (!this.info) return;
    await run('Rehaciendo…', () => api('edit/redo', { id: this.info.id }));
    this.clearSel(false); this.refresh(true);
  },

  /* ---- buscar ---- */
  async find(term) {
    this.findTerm = term;
    this.hits = [];
    this.hitIdx = -1;
    if (term && this.info) {
      const r = await run('Buscando…', () => api('search', { id: this.info.id, term }));
      for (const hit of r?.hits || []) for (const rect of hit.rects) this.hits.push({ n: hit.n, r: rect });
    }
    $('.findcount', this.root).textContent = term ? (this.hits.length ? '' : '0') : '';
    if (this.hits.length) this.findStep(1); else this.draw();
  },
  findStep(d) {
    if (!this.hits?.length) return;
    this.hitIdx = (this.hitIdx + d + this.hits.length) % this.hits.length;
    const hit = this.hits[this.hitIdx];
    $('.findcount', this.root).textContent = `${this.hitIdx + 1}/${this.hits.length}`;
    const v = this.viewer;
    if (v.n !== hit.n) v.go(hit.n);
    v.el.scrollTop = v.pages[hit.n].wrap.offsetTop + hit.r[1] * v.zoom - v.el.clientHeight / 3;
    this.draw();
  },

  /* ---- panel de miniaturas e índice ---- */
  toggleSide() {
    this.side.hidden = !this.side.hidden;
    $('[data-act=pages]', this.root).classList.toggle('on', !this.side.hidden);
    if (!this.side.hidden) this.renderSide();
    requestAnimationFrame(() => this.viewer.fitMode && this.viewer.fit());
  },
  async renderSide(tab = this.sideTab || 'thumbs') {
    this.sideTab = tab;
    const s = this.side;
    s.innerHTML = '';
    const tabs = h('div', { class: 'seg side-tabs' },
      h('button', { class: tab === 'thumbs' ? 'on' : '', onclick: () => this.renderSide('thumbs') }, 'Miniaturas'),
      h('button', { class: tab === 'toc' ? 'on' : '', onclick: () => this.renderSide('toc') }, 'Índice'),
      h('button', { class: tab === 'comments' ? 'on' : '', onclick: () => this.renderSide('comments') }, 'Comentarios'));
    s.append(tabs);
    if (!this.info) return;
    if (tab === 'thumbs') {
      const list = h('div', { class: 'thumb-list' });
      this.info.pages.forEach((sz, i) => {
        const img = h('img', { alt: '', loading: 'lazy', src: pageUrl(this.info.id, i, 0.5, this.viewer.v) });
        list.append(h('div', { class: 'tp' + (i === this.viewer.n ? ' on' : ''), onclick: () => this.viewer.go(i) }, img, h('span', {}, i + 1)));
      });
      s.append(list);
      list.querySelector('.tp.on')?.scrollIntoView({ block: 'nearest' });
    } else if (tab === 'comments') {
      let list = [];
      try { list = (await api('comments', { id: this.info.id })).comments; } catch (e) { /* sin lista */ }
      s.append(h('div', { style: 'padding:8px' }, h('button', { class: 'wide', onclick: () => { this.setTool('annot'); this.ann.kind = 'note'; this.draw(); } }, '＋ Añadir comentario')));
      if (!list.length) { s.append(h('p', { class: 'muted', style: 'padding:6px 12px' }, 'Aún no hay comentarios. Pulsa «Añadir comentario» y haz clic en la página donde quieras ponerlo.')); return; }
      list.forEach(c => s.append(h('div', { class: 'cm', onclick: () => this.gotoComment(c) },
        h('div', { class: 'cm-h' }, h('b', {}, c.author || 'Sin autor'), h('span', {}, `p. ${c.n + 1}` + (c.date ? ' · ' + c.date : ''))),
        h('p', {}, c.content || '(vacío)'),
        h('div', { class: 'cm-b' },
          h('button', { onclick: e => { e.stopPropagation(); this.editComment(c); } }, 'Editar'),
          h('button', { class: 'danger', onclick: async e => { e.stopPropagation(); this.viewer.n === c.n || await this.viewer.go(c.n); await this.op('delete_annot', { n: c.n, xref: c.xref }); } }, 'Borrar')))));
    } else {
      if (!this.outline) {
        try { this.outline = (await api('outline', { id: this.info.id })).toc; } catch (e) { this.outline = []; }
      }
      if (!this.outline.length) {
        s.append(h('p', { class: 'muted', style: 'padding:10px' }, 'Este documento no tiene índice (marcadores). Usa las miniaturas para moverte.'));
        return;
      }
      s.append(h('div', { class: 'toc' }, this.outline.map(([lvl, title, page]) =>
        h('div', { class: 'toc-i', style: `padding-left:${8 + (lvl - 1) * 14}px`, title, onclick: () => this.viewer.go(page - 1) }, title, h('small', {}, page)))));
    }
  },
  markThumb(n) {
    if (this.side.hidden || this.sideTab !== 'thumbs') return;
    $$('.tp', this.side).forEach((t, i) => t.classList.toggle('on', i === n));
    $('.tp.on', this.side)?.scrollIntoView({ block: 'nearest' });
  },

  /* ---- herramientas y selección ---- */
  setTool(t) {
    if (this.inline) this.commitInline();
    this.tool = t;
    $$('[data-t]', this.root).forEach(b => b.classList.toggle('on', b.dataset.t === t));
    this.clearSel(false);
    if (t === 'image') this.pickImage();
    this.draw();
  },
  clearSel(redraw = true) {
    this.sel = null; this.selSpans = new Set(); this.region = null;
    if (redraw) this.draw();
  },
  select(type, id) {
    this.selSpans = new Set();
    this.region = null;
    this.sel = { type, id };
    this.draw();
  },
  hint(t) { this.statusEl.textContent = t; },

  draw() {
    const v = this.viewer;
    v.clear();
    v.ov.className = 'ov tool-' + this.tool + (this.tool === 'annot' && ['highlight', 'underline', 'strikeout'].includes(this.ann.kind) ? ' markup' : '');
    this.renderBar();
    if (!this.info) { this.hint('Abre o arrastra un PDF o una imagen para editarlo.'); return; }
    const st = this.st;
    if (!st || st.n !== v.n) return;
    const t = this.tool;
    v.setSnap([...st.spans.map(x => ({ r: x.bbox, k: 's' + x.i })), ...st.images.map(x => ({ r: x.bbox, k: 'i' + x.xref })),
      ...st.annots.map(x => ({ r: x.bbox, k: 'a' + x.xref }))], st.size);
    // imágenes (movibles en la herramienta de selección)
    if (t === 'select') {
      for (const im of st.images) {
        const on = this.sel?.type === 'image' && this.sel.id === im.xref;
        const d = v.box(im.bbox, 'img' + (on ? ' sel' : ''));
        d.title = 'Imagen — arrastra para moverla, esquina para redimensionar, Supr para borrar';
        d.addEventListener('mousedown', e => { if (e.button === 0 && !on) { e.stopPropagation(); this.select('image', im.xref); } });
        if (on) v.transformable(d, im.bbox, r => this.op('move_image', { xref: im.xref, rect: r }, 'Moviendo…', false));
        d.addEventListener('contextmenu', e => { this.select('image', im.xref); this.contextMenu(e); });
      }
    }
    // textos
    if (t === 'select' || t === 'text') {
      for (const s of st.spans) {
        const d = v.box(s.bbox, 'span' + (this.selSpans.has(s.i) ? ' sel' : ''));
        d.dataset.i = s.i;
        d.title = `${s.font} · ${s.size} pt — doble clic para escribir; seleccionado, la esquina del marco cambia el tamaño`;
        d.addEventListener('mousedown', e => (t === 'text' ? (e.stopPropagation(), e.button === 0 && this.startInline(s, e)) : this.spanDown(e, s)));
        d.addEventListener('dblclick', e => { e.stopPropagation(); this.startInline(s, e); });
        d.addEventListener('contextmenu', e => { if (!this.selSpans.has(s.i)) { this.selSpans = new Set([s.i]); this.sel = { type: 'spans' }; this.draw(); } this.contextMenu(e, s); });
      }
    }
    // marco de la selección de texto, con tirador para cambiar el tamaño
    if (t === 'select' && this.selSpans.size && !this.inline) this.drawSpanFrame();
    // anotaciones y formas
    if (['select', 'shape', 'annot'].includes(t)) {
      const fixed = ['Highlight', 'Underline', 'StrikeOut', 'Squiggly'];
      for (const a of st.annots) {
        if (t === 'shape' && !['Square', 'Circle', 'Line', 'Ink', 'Polygon', 'PolyLine'].includes(a.type)) continue;
        const on = this.sel?.type === 'annot' && this.sel.id === a.xref;
        const d = v.box(a.bbox, 'annot' + (on ? ' sel' : ''));
        d.title = a.label + (a.content ? ': ' + a.content : '');
        d.addEventListener('mousedown', e => { if (e.button === 0) { e.stopPropagation(); if (!on) this.select('annot', a.xref); } });
        if (on && !fixed.includes(a.type)) {
          const done = r => this.op('move_annot', { xref: a.xref, rect: r }, 'Moviendo…').then(ok => ok && this.reselectAnnot(r));
          if (a.type === 'Line' && a.points) {  // líneas y flechas: se mueven enteras o por sus extremos
            v.transformable(d, a.bbox, done, { handles: 'none' });
            this.lineEnds(a);
          } else v.transformable(d, a.bbox, done, { handles: a.type === 'Text' ? 'none' : 'all' });
        }
        d.addEventListener('contextmenu', e => { this.select('annot', a.xref); this.contextMenu(e); });
      }
    }
    // campos de formulario: se rellenan directamente
    if (t === 'select' || t === 'form') this.drawWidgets(st);
    if (this.region && this.region.n === v.n) v.box(this.region.r, 'region');
    (this.hits || []).forEach((hit, i) => { if (hit.n === v.n) v.box(hit.r, 'hit' + (i === this.hitIdx ? ' cur' : '')); });
    this.hint({
      select: 'Clic: seleccionar (con ⌘/Ctrl o Mayús: añadir varios) · Doble clic en un texto: escribir (Intro = nueva línea) · Arrastrar: mover (guías de alineación; Alt las desactiva) · Esquina del marco: cambiar el tamaño · Arrastrar en vacío: seleccionar zona · ⌘C/⌘X/⌘V · Supr · Clic derecho: más opciones',
      text: 'Clic en la página para escribir texto nuevo, o en un texto existente para modificarlo. ⌘+Intro o clic fuera para fijarlo.',
      image: 'Arrastra en la página el recuadro donde colocar la imagen.',
      table: 'Arrastra el recuadro donde irá la tabla; después rellena las celdas (puedes pegar desde Excel o Word).',
      shape: 'Arrastra para dibujar la forma (con Mayús: líneas en ángulos de 15°, 45°, 90°…, y cuadrados o círculos). Clic en una forma para moverla o cambiar su tamaño con sus tiradores.',
      annot: ['highlight', 'underline', 'strikeout'].includes(this.ann.kind) ? 'Pulsa al principio del texto y arrastra hasta el final, como al seleccionar texto (también varias líneas). En páginas escaneadas sin texto, arrastra un recuadro (o pasa antes el OCR).' : this.ann.kind === 'note' ? 'Clic donde quieras el comentario; escribe el texto y guárdalo. Todos aparecen en la pestaña «Comentarios» del panel de la izquierda.' : this.ann.kind === 'ink' ? 'Dibuja sobre la página.' : 'Arrastra para dibujar el recuadro.',
      form: 'Arrastra para crear un campo del tipo elegido. Clic en la etiqueta de un campo para editarlo.',
      sign: 'Elige una firma y arrastra el recuadro donde colocarla, o usa «Al margen» para firmar todas las páginas.',
    }[t]);
    this.drawGraph();
  },

  /* ---- resaltar como en un lector de PDF: seleccionando el texto ---- */
  async pageWords(n) {
    if (!this.wordsCache[n]) this.wordsCache[n] = (await api('edit/words', { id: this.info.id, n })).words;
    return this.wordsCache[n];
  },
  nearestWord(words, [x, y]) {
    let best = 0, bd = Infinity;
    words.forEach((w, i) => {
      const [x0, y0, x1, y1] = w.bbox;
      const dx = x < x0 ? x0 - x : x > x1 ? x - x1 : 0;
      const dy = y < y0 ? y0 - y : y > y1 ? y - y1 : 0;
      const d = dx + dy * 4;  // mejor en la misma línea
      if (d < bd) { bd = d; best = i; }
    });
    return best;
  },
  /** Un recuadro por línea con las palabras de a a b (en orden de lectura). */
  lineRects(words, a, b) {
    const [lo, hi] = a <= b ? [a, b] : [b, a];
    const out = [], keys = [];
    for (let i = lo; i <= hi; i++) {
      const w = words[i], k = keys.indexOf(w.line);
      if (k < 0) { keys.push(w.line); out.push(w.bbox.slice()); }
      else { const r = out[k]; out[k] = [Math.min(r[0], w.bbox[0]), Math.min(r[1], w.bbox[1]), Math.max(r[2], w.bbox[2]), Math.max(r[3], w.bbox[3])]; }
    }
    return out;
  },
  async markupDown(e) {
    const v = this.viewer, { kind, color } = this.ann;
    const words = await this.pageWords(v.n).catch(() => []);
    if (!words.length) {  // página escaneada sin texto: se marca la zona que se dibuje
      const d = await v.drag(e);
      if (d.moved) this.op('add_markup', { kind, rects: [d.rect], color, area: true });
      return;
    }
    const p0 = v.pt(e), i0 = this.nearestWord(words, p0);
    let i1 = i0, moved = false;
    const layer = h('div', { class: 'mark-layer' });
    v.ov.append(layer);
    const paint = () => {
      layer.replaceChildren();
      for (const r of this.lineRects(words, i0, i1)) v.box(r, 'mark-preview ' + kind, layer).style.setProperty('--c', color);
    };
    paint();
    const mv = ev => {
      const p = v.pt(ev);
      if (Math.hypot(p[0] - p0[0], p[1] - p0[1]) > 3 / v.zoom) moved = true;
      i1 = this.nearestWord(words, p);
      paint();
    };
    window.addEventListener('mousemove', mv);
    window.addEventListener('mouseup', () => {
      window.removeEventListener('mousemove', mv);
      const rects = this.lineRects(words, i0, i1);
      layer.remove();
      if (moved || e.detail > 1) this.op('add_markup', { kind, rects, color });
    }, { once: true });
  },

  /* ---- propiedades de las formas ---- */
  dashSelect(value, onchange) {
    const sel = h('select', { title: 'Tipo de línea', onchange: e => onchange(e.target.value) },
      ...Object.entries({ continua: '── Continua', discontinua: '- - Discontinua', punteada: '··· Punteada', 'rayas-largas': '— — Rayas largas' })
        .map(([k, l]) => h('option', { value: k, selected: k === value }, l)));
    return sel;
  },
  shapeControls(a) {
    const s = a.style;
    const apply = changes => this.op('style_annot', { xref: a.xref, ...changes }, 'Aplicando…').then(ok => ok && this.select('annot', a.xref));
    const fillColor = h('input', { type: 'color', value: s.fill || '#ffe066', title: 'Color del relleno', disabled: !s.fill, onchange: e => apply({ fill: e.target.value }) });
    const canFill = !['Line', 'Ink', 'PolyLine'].includes(a.type);
    const ends = { '0,0': 'Sin flechas', '0,5': 'Flecha al final', '5,0': 'Flecha al principio', '5,5': 'Flechas en los dos extremos' };
    return [
      h('span', { class: 'blabel' }, 'Contorno'),
      h('input', { type: 'color', value: s.stroke || '#000000', title: 'Color del contorno', onchange: e => apply({ stroke: e.target.value }) }),
      h('input', { type: 'number', value: s.width, min: 0.5, max: 20, step: 0.5, class: 'num', title: 'Grosor', onchange: e => apply({ width: +e.target.value }) }),
      this.dashSelect(s.dash, dash => apply({ dash })),
      canFill ? h('label', { class: 'inline' }, h('input', { type: 'checkbox', checked: !!s.fill, onchange: e => apply({ fill: e.target.checked ? fillColor.value : null }) }), 'Relleno') : null,
      canFill ? fillColor : null,
      a.type === 'Line' ? h('select', { title: 'Flechas', onchange: e => apply({ ends: e.target.value.split(',').map(Number) }) },
        ...Object.entries(ends).map(([k, l]) => h('option', { value: k, selected: k === s.ends.map(v => (v ? 5 : 0)).join(',') }, l))) : null,
      h('label', { class: 'inline', title: 'Opacidad' }, 'Opacidad',
        h('input', { type: 'range', min: 10, max: 100, value: Math.round(s.opacity * 100), onchange: e => apply({ opacity: +e.target.value / 100 }) })),
      h('span', { class: 'sep' }),
      ibtn('copy', 'Copiar (⌘C)', () => this.copyAny()), ibtn('trash', 'Borrar', () => this.deleteSel()),
    ];
  },

  /** Extremos de una línea o flecha: se arrastran por separado (con Mayús, en ángulos de 15°). */
  lineEnds(a) {
    const v = this.viewer, z = v.zoom;
    a.points.forEach((pt, i) => {
      const hd = h('div', { class: 'line-end', title: 'Arrastra el extremo (Mayús: ángulos de 15°, 45°, 90°…)' });
      const place = q => Object.assign(hd.style, { left: q[0] * z - 7 + 'px', top: q[1] * z - 7 + 'px' });
      place(pt);
      v.ov.append(hd);
      hd.addEventListener('mousedown', e => {
        if (e.button !== 0) return;
        e.preventDefault(); e.stopPropagation();
        const fixed = a.points[1 - i];
        const NS = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(NS, 'svg');
        svg.setAttribute('style', 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible');
        const ln = document.createElementNS(NS, 'line');
        ln.setAttribute('stroke', '#2563d9'); ln.setAttribute('stroke-width', '2'); ln.setAttribute('stroke-dasharray', '5 3');
        ln.setAttribute('x1', fixed[0] * z); ln.setAttribute('y1', fixed[1] * z);
        svg.append(ln);
        v.ov.append(svg);
        let q = pt, moved = false;
        const mv = ev => {
          const p = v.pt(ev);
          let dx = p[0] - fixed[0], dy = p[1] - fixed[1];
          if (ev.shiftKey) [dx, dy] = snapAngle(dx, dy);
          q = [fixed[0] + dx, fixed[1] + dy];
          moved = true;
          place(q);
          ln.setAttribute('x2', q[0] * z); ln.setAttribute('y2', q[1] * z);
        };
        window.addEventListener('mousemove', mv);
        window.addEventListener('mouseup', () => {
          window.removeEventListener('mousemove', mv);
          svg.remove();
          if (!moved) return;
          const pts = (i === 0 ? [q, fixed] : [fixed, q]).map(p => p.map(c => Math.round(c * 100) / 100));
          this.op('set_line', { xref: a.xref, points: pts }, 'Cambiando la línea…').then(ok => ok && this.reselectAnnot(norm(pts[0], pts[1]), pts));
        }, { once: true });
      });
    });
  },
  /** Tras mover o cambiar una forma, vuelve a seleccionarla (algunas se rehacen con otra referencia). */
  reselectAnnot(rect, pts = null) {
    let best = null, bd = 1e9;
    for (const a of this.st?.annots || []) {
      const d = pts && a.points ? Math.hypot(a.points[0][0] - pts[0][0], a.points[0][1] - pts[0][1]) + Math.hypot(a.points[1][0] - pts[1][0], a.points[1][1] - pts[1][1])
        : a.bbox.reduce((acc, v, k) => acc + Math.abs(v - rect[k]), 0);
      if (d < bd) { bd = d; best = a; }
    }
    if (best && bd < 20) this.select('annot', best.xref);
  },
  drawWidgets(st) {
    const v = this.viewer;
    for (const w of st.widgets) {
      const on = this.sel?.type === 'widget' && this.sel.id === w.xref;
      const d = v.box(w.bbox, 'widget' + (on ? ' sel' : ''));
      if (w.type === 'signature') {
        d.classList.add('locked');
        d.title = 'Firma digital: no se puede mover ni borrar';
        d.append(h('div', { class: 'grip' }, '🔒 Firma digital'));
        d.addEventListener('mousedown', e => e.stopPropagation());
        continue;
      }
      const grip = h('div', { class: 'grip', title: 'Clic para editar el campo; arrastra para moverlo' }, w.name);
      grip.addEventListener('mousedown', e => { if (!on) { e.stopPropagation(); this.select('widget', w.xref); } });
      let ctl;
      const upd = value => this.fill(w.xref, value);
      if (w.type === 'text') { ctl = h('input', { value: w.value || '' }); ctl.addEventListener('change', () => upd(ctl.value)); }
      else if (w.type === 'checkbox' || w.type === 'radio') ctl = h('input', { type: 'checkbox', checked: !!w.value, onchange: () => upd(ctl.checked) });
      else if (w.type === 'combobox' || w.type === 'listbox') { ctl = h('select', { onchange: () => upd(ctl.value) }, w.options.map(o => h('option', {}, o))); ctl.value = w.value; }
      else ctl = h('span');
      ctl.addEventListener('mousedown', e => e.stopPropagation());
      d.append(grip, ctl);
      if (on) v.transformable(d, w.bbox, r => this.op('update_widget', { xref: w.xref, rect: r }), { grip });
    }
  },
  async fill(xref, value) {
    const r = await run('Guardando…', () => api('edit/update_widget', { id: this.info.id, n: this.viewer.n, xref, value }));
    if (r !== undefined) { await this.refresh(); this.viewer.refresh(); }
  },

  /* ---- barra de formato contextual ---- */
  fontSelect(value, auto = null) {
    const s = h('select', { class: 'fsel' },
      auto ? h('option', { value: 'auto' }, auto) : null,
      this.fonts.map(f => h('option', { value: f.key }, f.label)));
    s.value = value;
    return s;
  },
  textControls(o, onchange, { lists = false, auto = null } = {}) {
    const font = this.fontSelect(o.font, auto);
    const size = h('input', { type: 'number', value: o.size, min: 3, max: 200, step: 0.5, class: 'num', title: 'Tamaño' });
    const color = h('input', { type: 'color', value: o.color, title: 'Color' });
    const tog = (label, key, title) => {
      const b = h('button', { class: 'ib txt' + (o[key] ? ' on' : ''), title, onmousedown: e => e.preventDefault(),
        onclick: () => { o[key] = !o[key]; b.classList.toggle('on', o[key]); onchange(); } }, label);
      return b;
    };
    font.onchange = () => { o.font = font.value; onchange(); };
    size.onchange = () => { o.size = +size.value; onchange(); };
    color.onchange = () => { o.color = color.value; onchange(); };
    const parts = [font, size, color, tog(h('b', {}, 'B'), 'bold', 'Negrita'), tog(h('i', {}, 'I'), 'italic', 'Cursiva')];
    if (lists) {
      parts.push(h('span', { class: 'sep' }));
      for (const [k, ic, t] of [['none', 'nolist', 'Sin lista'], ['bullet', 'bullet', 'Viñetas'], ['number', 'number', 'Lista numerada'], ['letter', 'letter', 'Lista con letras']]) {
        parts.push(ibtn(ic, t, () => { o.list = k; if (this.inline?.isNew) this.applyList(this.inline.el, true); this.renderBar(); this.inline?.el.focus(); }, o.list === k));
      }
    }
    return parts;
  },
  renderBar() {
    const b = this.bar;
    b.innerHTML = '';
    const add = (...xs) => b.append(...xs.flat().filter(x => x != null && x !== false));  // sin «null» sueltos
    const label = t => h('span', { class: 'blabel' }, t);
    const t = this.tool;
    const sel = this.st?.spans.filter(s => this.selSpans.has(s.i)) || [];
    if (this.inline?.isNew || t === 'text') {
      add(label('Texto'), ...this.textControls(this.textOpts, async () => {
        if (this.inline?.isNew) { await this.styleNew(this.inline.el); this.inline.el.focus(); }
      }, { lists: true }));
      if (this.inline?.isNew) add(h('span', { class: 'grow' }), h('button', { class: 'primary', onmousedown: e => e.preventDefault(), onclick: () => this.commitInline() }, 'Fijar texto'));
      return;
    }
    if (sel.length) {
      const s0 = sel[0];
      const o = { font: 'auto', size: s0.size, color: s0.color, bold: s0.bold, italic: s0.italic };
      const apply = () => this.op('format_spans', { indices: sel.map(s => s.i), font: o.font, size: o.size, color: o.color, bold: o.bold, italic: o.italic }, 'Aplicando…', true)
        .then(ok => ok && this.reselectMoved(sel.length, 0, 0));
      add(label(sel.length > 1 ? `${sel.length} textos` : 'Texto'), ...this.textControls(o, apply, { auto: `Original (${s0.font})` }),
        h('span', { class: 'sep' }),
        sel.length === 1 ? h('button', { onclick: () => this.startInline(s0) }, 'Escribir') : null,
        ibtn('copy', 'Copiar', () => this.copyAny()), ibtn('trash', 'Borrar', () => this.deleteSel()));
      return;
    }
    if (this.sel?.type === 'image') {
      add(label('Imagen'), h('span', { class: 'muted' }, 'Arrastra para mover · esquina para redimensionar'),
        h('span', { class: 'sep' }), ibtn('copy', 'Copiar como imagen', () => this.copyAny()), ibtn('trash', 'Borrar imagen', () => this.deleteSel()));
      return;
    }
    if (this.sel?.type === 'annot') {
      const a = this.st.annots.find(x => x.xref === this.sel.id);
      if (a?.style) { add(label(a.label), ...this.shapeControls(a)); return; }
      add(label(a?.label || 'Anotación'), a?.content ? h('span', { class: 'muted' }, a.content.slice(0, 60)) : null,
        a && (a.type === 'Text' || a.content) ? h('button', { onclick: () => this.editComment({ n: this.viewer.n, xref: a.xref, content: a.content, author: '' }) }, 'Editar comentario…') : null,
        h('span', { class: 'sep' }), ibtn('trash', 'Borrar', () => this.deleteSel()));
      return;
    }
    if (this.sel?.type === 'widget') {
      const w = this.st.widgets.find(x => x.xref === this.sel.id);
      if (!w) return;
      const name = h('input', { value: w.name, class: 'mid', title: 'Nombre del campo' });
      name.onchange = () => this.op('update_widget', { xref: w.xref, name: name.value });
      add(label('Campo'), name,
        ['combobox', 'listbox'].includes(w.type) ? h('button', {
          onclick: async () => {
            const s = await ask('Opciones', 'Una opción por línea', w.options.join('\n'), { textarea: true });
            if (s != null) this.op('update_widget', { xref: w.xref, options: s.split('\n').map(x => x.trim()).filter(Boolean) });
          },
        }, 'Opciones…') : null,
        ibtn('trash', 'Borrar campo', () => this.deleteSel()));
      return;
    }
    if (this.region) {
      add(label('Zona'), h('span', { class: 'muted' }, 'Zona seleccionada'),
        h('button', { onclick: () => this.copyAny() }, 'Copiar'),
        h('button', { onclick: () => this.copyAny(false, true) }, 'Copiar como captura'));
      return;
    }
    if (t === 'table') {
      const tb = this.table, num = (k, min, max, title) => h('input', { type: 'number', value: tb[k], min, max, class: 'num', title, onchange: e => { tb[k] = Math.min(max, Math.max(min, +e.target.value || min)); } });
      add(label('Tabla'), h('span', { class: 'muted' }, 'Filas'), num('rows', 1, 40, 'Filas'), h('span', { class: 'muted' }, 'Columnas'), num('cols', 1, 12, 'Columnas'),
        h('label', { class: 'inline' }, h('input', { type: 'checkbox', checked: tb.header, onchange: e => { tb.header = e.target.checked; } }), 'Cabecera'),
        h('input', { type: 'color', value: tb.fill, title: 'Color de la cabecera', onchange: e => { tb.fill = e.target.value; } }),
        h('span', { class: 'sep' }), label('Borde'), h('input', { type: 'color', value: tb.stroke, onchange: e => { tb.stroke = e.target.value; } }),
        h('input', { type: 'number', value: tb.width, min: 0.25, max: 6, step: 0.25, class: 'num', title: 'Grosor del borde', onchange: e => { tb.width = +e.target.value; } }),
        h('span', { class: 'muted' }, 'Texto'), num('size', 6, 36, 'Tamaño del texto'));
      return;
    }
    if (t === 'shape') {
      const sh = this.shape;
      add(label('Forma'), ...['rect', 'ellipse', 'line', 'arrow'].map(k =>
        ibtn(k, { rect: 'Rectángulo', ellipse: 'Elipse', line: 'Línea', arrow: 'Flecha' }[k], () => { sh.kind = k; this.renderBar(); }, sh.kind === k)),
      h('span', { class: 'sep' }), label('Borde'), h('input', { type: 'color', value: sh.stroke, onchange: e => { sh.stroke = e.target.value; } }),
      h('input', { type: 'number', value: sh.width, min: 0.5, max: 20, step: 0.5, class: 'num', title: 'Grosor', onchange: e => { sh.width = +e.target.value; } }),
      h('label', { class: 'inline' }, h('input', { type: 'checkbox', checked: sh.filled, onchange: e => { sh.filled = e.target.checked; } }), 'Relleno'),
      h('input', { type: 'color', value: sh.fill, onchange: e => { sh.fill = e.target.value; } }),
      this.dashSelect(sh.dash, v => { sh.dash = v; }), ...this.graphButtons());
      return;
    }
    if (t === 'annot') {
      const a = this.ann;
      const kinds = { highlight: 'Resaltar (fosforito)', underline: 'Subrayar', strikeout: 'Tachar', note: 'Comentario', freetext: 'Cuadro de texto', ink: 'Dibujo a mano' };
      const neon = { '#fff200': 'Amarillo flúor', '#39ff14': 'Verde flúor', '#ff3fa4': 'Rosa flúor', '#ff9a1f': 'Naranja flúor', '#1ee3ff': 'Azul flúor', '#c86bff': 'Lila flúor' };
      add(label('Anotar'), ...Object.entries(kinds).map(([k, l]) => ibtn(k, l, () => { a.kind = k; this.draw(); }, a.kind === k)),
        h('span', { class: 'sep' }),
        ...Object.entries(neon).map(([c, t]) => h('button', { class: 'swatch' + (a.color === c ? ' on' : ''), title: t, style: `--c:${c}`, onmousedown: e => e.preventDefault(), onclick: () => { a.color = c; this.renderBar(); } })),
        h('input', { type: 'color', value: a.color, title: 'Otro color', onchange: e => { a.color = e.target.value; this.renderBar(); } }),
        ['freetext'].includes(a.kind) ? h('input', { class: 'mid', placeholder: 'Texto de la nota', value: a.text, oninput: e => { a.text = e.target.value; } }) : null);
      return;
    }
    if (t === 'form') {
      const types = { text: 'Texto', checkbox: 'Casilla', radio: 'Opción', combobox: 'Desplegable', listbox: 'Lista' };
      add(label('Nuevo campo'), ...Object.entries(types).map(([k, l]) =>
        h('button', { class: this.widgetType === k ? 'on' : '', onclick: () => { this.widgetType = k; this.renderBar(); } }, l)),
      h('span', { class: 'grow' }), ibtn('flatten', 'Aplanar formulario y anotaciones', async () => {
        if (await confirmBox('Aplanar', 'Los campos y anotaciones pasarán a ser contenido fijo. ¿Continuar?', 'Aplanar')) this.op('flatten', {});
      }));
      return;
    }
    if (t === 'sign') {
      const g = h('div', { class: 'sig-gallery inline' });
      for (const it of Sigs.items) {
        g.append(h('div', { class: 'sig-item' + (it.id === this.sig ? ' sel' : ''), title: 'Usar esta firma', onclick: () => { this.sig = it.id; this.renderBar(); } },
          h('img', { src: Sigs.src(it) })));
      }
      add(label('Firma'), g, ibtn('plus', 'Nueva firma', async () => { const id = await Sigs.create(); if (id) { this.sig = id; this.renderBar(); } }),
        h('span', { class: 'sep' }), h('button', { onclick: () => this.marginDialog() }, icon('margin'), ' Al margen (todas las páginas)…'),
        this.sig ? ibtn('trash', 'Borrar la firma guardada', async () => {
          if (await confirmBox('Borrar firma', '¿Borrar esta firma guardada?', 'Borrar')) { await api('sigimg/delete', { id: this.sig }); this.sig = null; Sigs.load(); }
        }) : null);
      return;
    }
    if (t === 'image') {
      add(label('Imagen'), h('button', { onclick: () => this.pickImage() }, 'Elegir imagen…'),
        h('span', { class: 'muted' }, this.pendingImage ? 'Arrastra en la página dónde colocarla.' : ''));
      return;
    }
    add(h('span', { class: 'muted' }, this.info ? 'Selecciona algo en la página para ver sus opciones.' : ''));
  },

  /** Busca las marcas de agua del documento, las enseña y, si se acepta, las quita (con deshacer). */
  async removeWatermarks() {
    const r = await run('Buscando marcas de agua…', () => api('watermarks', { id: this.info.id }));
    if (!r) return;
    if (!r.found.length) {
      return toast('No se ha encontrado ninguna marca de agua que se pueda quitar (texto en diagonal, contenido marcado como marca de agua o anotación de marca de agua).', '', [], 7000);
    }
    const items = r.found.slice(0, 12).map(f => h('li', {}, `Página ${f.n + 1}: ${f.kind}${f.text ? ` «${f.text}»` : ''}`));
    if (r.found.length > 12) items.push(h('li', {}, `… y ${r.found.length - 12} más`));
    const ok = await new Promise(res => modal({
      title: 'Quitar marca de agua',
      body: h('div', {}, h('p', {}, 'Se quitará solo esto; el resto del documento no cambia:'), h('ul', {}, items),
        h('p', { class: 'muted' }, 'Puedes deshacerlo con ⌘Z. Si es el borrador de un documento oficial, la copia sin marca sigue sin ser la versión definitiva.')),
      actions: [{ label: 'Cancelar', fn: () => res(false) }, { label: 'Quitar', primary: true, fn: () => res(true) }],
      onclose: () => res(false),
    }));
    if (ok && await this.op('remove_watermarks', {}, 'Quitando marca de agua…')) {
      toast(r.found.length === 1 ? 'Marca de agua quitada. ⌘Z para deshacer.' : `${r.found.length} marcas de agua quitadas. ⌘Z para deshacer.`, 'ok', [], 5000);
    }
  },

  /* ---- teclado ---- */
  key(e) {
    if (!this.root.classList.contains('active')) return;
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'f') { e.preventDefault(); const f = $('[data-k=find]', this.root); f.focus(); f.select(); return; }
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
    if (typing) return;
    const mod = e.metaKey || e.ctrlKey, k = e.key.toLowerCase();
    if (mod && k === 'z') { e.preventDefault(); return e.shiftKey ? this.redo() : this.undo(); }
    if (mod && k === 'y') { e.preventDefault(); return this.redo(); }
    if (mod && ['c', 'x', 'v'].includes(k) && this.info) {
      e.preventDefault();
      return k === 'v' ? this.pasteAny() : this.copyAny(k === 'x');
    }
    if (!mod && !e.altKey) {
      const tools = { v: 'select', t: 'text', r: 'shape', h: 'annot' };
      if (tools[k]) { e.preventDefault(); return this.setTool(tools[k]); }
    }
    const has = this.selSpans.size || this.sel;
    if ((e.key === 'Delete' || e.key === 'Backspace') && has) { e.preventDefault(); return this.deleteSel(); }
    if (e.key === 'Escape') { this.closeMenu(); if (this.graph) { this.graph = null; this.draw(); } if (has || this.region) this.clearSel(); }
    const arrows = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (this.selSpans.size && arrows[e.key]) {
      e.preventDefault();
      const m = e.shiftKey ? 10 : 1;
      this.moveSel(arrows[e.key][0] * m, arrows[e.key][1] * m);
    }
  },
  deleteSel() {
    if (this.selSpans.size) { const indices = [...this.selSpans]; return this.op('delete_spans', { indices }); }
    if (!this.sel) return;
    const { type, id } = this.sel;
    if (type === 'image') return this.op('delete_image', { xref: id });
    if (type === 'annot') return this.op('delete_annot', { xref: id });
    if (type === 'widget') return this.op('delete_widget', { xref: id });
  },

  /* ---- menú contextual ---- */
  contextMenu(e, span) {
    e.preventDefault();
    e.stopPropagation();
    if (!this.info) return;
    this.closeMenu();
    const has = this.selSpans.size || this.sel || this.region;
    const item = (label, key, fn, enabled = true) => h('div', {
      class: 'mi' + (enabled ? '' : ' off'), onclick: () => { if (!enabled) return; this.closeMenu(); fn(); },
    }, h('span', {}, label), h('small', {}, key || ''));
    const clip = !!this.clipKind;
    const m = h('div', { class: 'ctxmenu', style: `left:${e.clientX}px;top:${e.clientY}px` },
      span && this.selSpans.size === 1 ? item('Escribir en este texto', 'doble clic', () => this.startInline(span, e)) : null,
      item('Copiar', '⌘C', () => this.copyAny(), !!has),
      item('Cortar', '⌘X', () => this.copyAny(true), !!(this.selSpans.size || this.sel)),
      item('Pegar aquí', '⌘V', () => this.pasteAny()),
      item('Pegar como captura', '', () => this.pasteAny(true), clip && this.clipKind === 'region'),
      item('Copiar zona como captura', '', () => this.copyAny(false, true), !!(this.region || this.selSpans.size || this.sel?.type === 'image')),
      h('div', { class: 'msep' }),
      item('Eliminar', 'Supr', () => this.deleteSel(), !!(this.selSpans.size || this.sel)),
      item('Añadir texto aquí', 'T', () => { this.setTool('text'); const p = this.viewer.pt(e); this.newInline(p[0], p[1]); }));
    document.body.append(m);
    const r = m.getBoundingClientRect();
    if (r.right > innerWidth) m.style.left = innerWidth - r.width - 8 + 'px';
    if (r.bottom > innerHeight) m.style.top = innerHeight - r.height - 8 + 'px';
    this.menu = m;
    this.mouse = { n: this.viewer.n, p: this.viewer.pt(e) };
  },
  closeMenu() { this.menu?.remove(); this.menu = null; },

  /* ---- ratón en zona vacía ---- */
  async down(e) {
    if (e.button !== 0 || e.target !== this.viewer.ov || !this.info) return;
    this.closeMenu();
    if (!this.st || this.st.n !== this.viewer.n) return;  // la página aún se está cargando
    const v = this.viewer, t = this.tool;
    if (this.inline) { this.commitInline(); return; }
    if (this.graph) return this.graphClick(e);
    if (t === 'text') { const [x, y] = v.pt(e); this.newInline(x, y); return; }
    if (t === 'annot' && ['highlight', 'underline', 'strikeout'].includes(this.ann.kind)) return this.markupDown(e);
    if (t === 'annot' && this.ann.kind === 'note') {
      const [x, y] = v.pt(e);
      return this.addComment(x, y);
    }
    const d = await v.drag(e, { ink: t === 'annot' && this.ann.kind === 'ink', shape: t === 'shape' ? this.shape.kind : null });
    if (t === 'select') {
      if (!d.moved) { this.clearSel(); return; }
      const hit = (this.st?.spans || []).filter(s => inter(s.bbox, d.rect)).map(s => s.i);
      this.selSpans = new Set(multi(e) ? [...this.selSpans, ...hit] : hit);
      this.sel = hit.length ? { type: 'spans' } : null;
      this.region = { n: v.n, r: d.rect };  // la zona se puede copiar como captura aunque tenga texto
      if (hit.length) this.region.withSpans = true;
      this.draw();
      return;
    }
    if (!d.moved) return;
    if (t === 'image') {
      if (!this.pendingImage) return this.pickImage();
      const data = this.pendingImage;
      this.pendingImage = null;
      await this.op('insert_image', { rect: d.rect, data });
      return this.setTool('select');
    }
    if (t === 'table') {
      const cells = await this.tableDialog(this.table.rows, this.table.cols);
      if (!cells) return this.draw();
      const tb = this.table;
      await this.op('add_table', { rect: d.rect, cells, size: tb.size, stroke: tb.stroke, width: tb.width, header: tb.header, fill: tb.fill, color: this.textOpts.color });
      return this.setTool('select');
    }
    if (t === 'shape') {
      const sh = this.shape;
      return this.op('add_shape', { kind: sh.kind, rect: d.rect, points: [d.points[0], d.points[d.points.length - 1]], stroke: sh.stroke, fill: sh.filled ? sh.fill : null, width: sh.width, dash: sh.dash });
    }
    if (t === 'annot') {
      if (this.ann.kind === 'ink') return this.op('add_ink', { strokes: [d.points], color: this.ann.color });
      return this.op('add_annot', { kind: this.ann.kind, rect: d.rect, text: this.ann.text, color: this.ann.color });
    }
    if (t === 'form') {
      const ty = this.widgetType;
      const count = (this.st?.widgets.length || 0) + 1;
      const name = await ask('Nuevo campo', 'Nombre del campo', ty === 'radio' ? 'grupo1' : `${ty}${count}`);
      if (!name) return;
      let options = null;
      if (ty === 'combobox' || ty === 'listbox') {
        const s = await ask('Opciones', 'Escribe las opciones, una por línea', 'Opción 1\nOpción 2', { textarea: true });
        if (s == null) return;
        options = s.split('\n').map(x => x.trim()).filter(Boolean);
      }
      return this.op('add_widget', { type: ty, rect: d.rect, name, options });
    }
    if (t === 'sign') {
      if (!this.sig) return toast('Elige o crea primero una firma en la barra de arriba.', 'err');
      const ratio = await Sigs.ratio(this.sig);
      let [x0, y0, x1, y1] = d.rect;
      const w = x1 - x0, hh = y1 - y0;
      if (w / hh > ratio) { const nw = hh * ratio; x0 += (w - nw) / 2; x1 = x0 + nw; } else { const nh = w / ratio; y0 += (hh - nh) / 2; y1 = y0 + nh; }
      const r = await run('Colocando firma…', () => api('sigimg/place', { id: this.info.id, n: v.n, sig: this.sig, rect: [x0, y0, x1, y1] }));
      if (r !== undefined) this.refresh(true);
    }
  },
  async pickImage() {
    const [f] = await pickFiles('image/*');
    if (!f) { if (this.tool === 'image' && !this.pendingImage) this.setTool('select'); return; }
    this.pendingImage = await fileToB64(f);
    this.renderBar();
    this.hint('Arrastra en la página el recuadro donde colocar la imagen.');
  },

  /* ---- mover textos y escritura directa ---- */
  spanDown(e, s) {
    if (e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    this.closeMenu();
    if (this.inline) { this.commitInline(); return; }
    const wasOnly = this.selSpans.has(s.i) && this.selSpans.size === 1;
    if (multi(e)) { this.selSpans.has(s.i) ? this.selSpans.delete(s.i) : this.selSpans.add(s.i); }
    else if (!this.selSpans.has(s.i)) this.selSpans = new Set([s.i]);
    this.sel = this.selSpans.size ? { type: 'spans' } : null;
    this.region = null;
    this.draw();
    if (!this.selSpans.has(s.i)) return;
    const v = this.viewer, p0 = v.pt(e);
    const boxes = $$('.bx.span.sel', v.ov);
    const mine = this.st.spans.filter(x => this.selSpans.has(x.i)).map(x => x.bbox);
    const box0 = mine.reduce((a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])]);
    let dx = 0, dy = 0, moved = false;
    const mv = ev => {
      const p = v.pt(ev);
      dx = p[0] - p0[0]; dy = p[1] - p0[1];
      if (Math.abs(dx) + Math.abs(dy) > 4 / v.zoom) moved = true;
      if (moved && !ev.altKey) {  // guías de alineación con el resto de textos e imágenes
        const sn = v.snap([box0[0] + dx, box0[1] + dy, box0[2] + dx, box0[3] + dy], { skip: t => t.k[0] === 's' && this.selSpans.has(+t.k.slice(1)) });
        dx += sn.dx; dy += sn.dy;
      } else v.clearGuides();
      if (moved) boxes.forEach(b => { b.style.transform = `translate(${dx * v.zoom}px, ${dy * v.zoom}px)`; });
    };
    window.addEventListener('mousemove', mv);
    window.addEventListener('mouseup', ev => {
      window.removeEventListener('mousemove', mv);
      v.clearGuides();
      if (moved) this.moveSel(dx, dy);
      else if (wasOnly && !multi(e)) this.startInline(s, ev);
    }, { once: true });
  },
  /** Marco alrededor de los textos seleccionados; su esquina cambia el tamaño (letra e interlineado). */
  drawSpanFrame() {
    const sel = this.st.spans.filter(s => this.selSpans.has(s.i));
    if (!sel.length) return;
    const u = sel.map(s => s.bbox).reduce((a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])]);
    const v = this.viewer, pad = 2;
    const fr = v.box([u[0] - pad, u[1] - pad, u[2] + pad, u[3] + pad], 'span-frame');
    const handle = h('div', { class: 'handle', title: 'Arrastra para cambiar el tamaño del texto' });
    fr.append(handle);
    handle.addEventListener('mousedown', e => this.scaleDrag(e, sel, u, fr));
  },
  scaleDrag(e, sel, u, fr) {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    const v = this.viewer, p0 = v.pt(e), z = v.zoom, pad = 2;
    const w = u[2] - u[0], hh = u[3] - u[1], diag2 = w * w + hh * hh;
    const boxes = $$('.bx.span.sel', v.ov);
    const label = h('div', { class: 'scale-label' });
    fr.append(label);
    let f = 1;
    const mv = ev => {
      const p = v.pt(ev);
      f = clamp(1 + ((p[0] - p0[0]) * w + (p[1] - p0[1]) * hh) / diag2, 0.2, 8);  // a lo largo de la diagonal
      v.place(fr, [u[0] - pad, u[1] - pad, u[0] + w * f + pad, u[1] + hh * f + pad]);
      boxes.forEach(b => {
        b.style.transformOrigin = `${u[0] * z - parseFloat(b.style.left)}px ${u[1] * z - parseFloat(b.style.top)}px`;
        b.style.transform = `scale(${f})`;
      });
      const sizes = [...new Set(sel.map(s => Math.round(s.size * f * 10) / 10))];
      label.textContent = `${sizes.length === 1 ? sizes[0] + ' pt' : Math.round(f * 100) + ' %'}`;
    };
    window.addEventListener('mousemove', mv);
    window.addEventListener('mouseup', async () => {
      window.removeEventListener('mousemove', mv);
      if (Math.abs(f - 1) < 0.02) { this.draw(); return; }
      const ok = await this.op('scale_spans', { indices: sel.map(s => s.i), factor: Math.round(f * 1000) / 1000, anchor: u.slice(0, 2) },
        'Cambiando el tamaño…', true);
      if (ok) this.reselectScaled(u, f);
    }, { once: true });
  },
  reselectScaled(u, f) {
    const found = new Set();
    for (const b of this.lastSel || []) {
      const r = [u[0] + (b[0] - u[0]) * f, u[1] + (b[1] - u[1]) * f];
      let best = null, bd = 1e9;
      for (const s of this.st.spans) {
        const d = Math.abs(s.bbox[0] - r[0]) + Math.abs(s.bbox[1] - r[1]);
        if (d < bd) { bd = d; best = s; }
      }
      if (best && bd < 8 * Math.max(1, f)) found.add(best.i);
    }
    this.selSpans = found;
    this.sel = found.size ? { type: 'spans' } : null;
    this.draw();
  },
  async moveSel(dx, dy) {
    const indices = [...this.selSpans];
    const ok = await this.op('move_spans', { indices, dx: Math.round(dx * 100) / 100, dy: Math.round(dy * 100) / 100 }, 'Moviendo…', true);
    if (ok) this.reselectMoved(indices.length, dx, dy);
  },
  reselectMoved(count, dx, dy) {
    const moved = (this.lastSel || []).map(b => [b[0] + dx, b[1] + dy]);
    const found = new Set();
    for (const r of moved) {
      let best = null, bd = 1e9;
      for (const s of this.st.spans) {
        const d = Math.abs(s.bbox[0] - r[0]) + Math.abs(s.bbox[1] - r[1]);
        if (d < bd) { bd = d; best = s; }
      }
      if (best && bd < 8) found.add(best.i);
    }
    this.selSpans = found;
    this.sel = found.size ? { type: 'spans' } : null;
    this.draw();
  },
  async startInline(s, ev) {
    if (this.inline) this.commitInline();
    const v = this.viewer, z = v.zoom;
    const [x0, y0, x1, y1] = s.bbox;
    const fam = await cssFont(`/api/font?id=${this.info.id}&n=${v.n}&name=${encodeURIComponent(s.rawfont)}&t=${TOKEN}`, s.font, s.flags);
    const el = h('div', { class: 'inline-edit', contentEditable: 'true', spellcheck: false });
    el.textContent = s.text;
    const lh = this.lineHeight(s);
    Object.assign(el.style, {
      left: x0 * z + 'px', top: (y0 - (lh - (y1 - y0)) / 2) * z + 'px', minWidth: (x1 - x0) * z + 'px', minHeight: lh * z + 'px',
      lineHeight: lh * z + 'px', fontSize: s.size * z + 'px', fontFamily: fam, color: s.color,
      fontWeight: s.bold ? 'bold' : 'normal', fontStyle: s.italic ? 'italic' : 'normal',
      background: pageColorAt(v, x0 - 1.5, y0 + (y1 - y0) / 2),
    });
    v.ov.append(el);
    this.inline = { el, s };
    el.focus();
    const r = ev && document.caretRangeFromPoint ? document.caretRangeFromPoint(ev.clientX, ev.clientY) : null;
    const sel = window.getSelection();
    if (r && el.contains(r.startContainer)) { sel.removeAllRanges(); sel.addRange(r); }
    else { const rg = document.createRange(); rg.selectNodeContents(el); rg.collapse(false); sel.removeAllRanges(); sel.addRange(rg); }
    el.addEventListener('keydown', e => {
      e.stopPropagation();
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); this.commitInline(); return; }
      if (e.key === 'Enter') { e.preventDefault(); document.execCommand('insertLineBreak'); return; }
      if (e.key === 'Escape') { e.preventDefault(); this.cancelInline(); }
    });
    el.addEventListener('paste', e => {  // pegar solo texto, sin formato
      e.preventDefault();
      document.execCommand('insertText', false, e.clipboardData.getData('text/plain'));
    });
    el.addEventListener('mousedown', e => e.stopPropagation());
    this.hint('Escribe sobre el texto. Intro = nueva línea (el texto de debajo baja) · ⌘+Intro o clic fuera para guardar · Esc cancela.');
  },
  /** Interlineado junto a un texto (distancia a la línea de debajo), como en el servidor. */
  lineHeight(s) {
    let best = null;
    for (const o of this.st?.spans || []) {
      if (o === s || o.bbox[0] > s.bbox[2] || o.bbox[2] < s.bbox[0]) continue;
      const d = o.bbox[1] - s.bbox[1];
      if (d > s.size * 0.9 && d < s.size * 2.5 && (best === null || d < best)) best = d;
    }
    return best || s.size * 1.25;
  },
  cancelInline() {
    this.inline?.el.remove();
    this.inline = null;
    this.renderBar();
  },
  commitInline() {
    const it = this.inline;
    if (!it) return;
    this.inline = null;
    if (it.isNew) {
      const lines = it.el.value.split('\n').filter(l => this.textOpts.list === 'none' || this.splitLine(l).body.trim());
      const text = lines.join('\n').replace(/\s+$/, '');
      it.el.remove();
      if (text.trim()) this.op('add_text', { x: it.x, y: it.y, text, ...this.textOpts });
      else this.renderBar();
      return;
    }
    const text = it.el.innerText.replace(/\u00a0/g, ' ').replace(/\n+$/, '');
    if (text === it.s.text) { it.el.remove(); this.renderBar(); return; }
    this.op('replace_text', { i: it.s.i, text: text.trim() ? text : '' }).then(() => it.el.remove());
  },

  /* ---- texto nuevo (con listas) ---- */
  async styleNew(el) {
    const o = this.textOpts, z = this.viewer.zoom;
    Object.assign(el.style, {
      fontSize: o.size * z + 'px', lineHeight: '1.2', color: o.color, fontFamily: await fontForKey(o.font),
      fontWeight: o.bold ? 'bold' : 'normal', fontStyle: o.italic ? 'italic' : 'normal',
    });
    this.autosize(el);
  },
  autosize(el) { el.style.height = 'auto'; el.style.height = el.scrollHeight + 'px'; },
  listPrefix(mode, level, n) {
    const letter = k => String.fromCharCode(96 + ((k - 1) % 26) + 1);
    const roman = k => ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x', 'xi', 'xii'][(k - 1) % 12];
    if (mode === 'bullet') return ['•', '–', '·'][level % 3];
    if (mode === 'number') return [`${n}.`, `${letter(n)})`, `${roman(n)}.`][level % 3];
    if (mode === 'letter') return [`${letter(n)})`, `${n}.`, `${roman(n)}.`][level % 3];
    return '';
  },
  splitLine(line) {
    const m = line.match(/^((?: {4})*)(?:(?:•|–|·|\d+\.|[a-z]\)|[ivx]+\.) )?(.*)$/);
    return { level: m[1].length / 4, body: m[2] };
  },
  applyList(el, keepCaret = false) {
    const mode = this.textOpts.list;
    const pos = el.selectionStart;
    const before = el.value.slice(0, pos).split('\n');
    const caretLine = before.length - 1, caretCol = before[before.length - 1].length;
    const lines = el.value.split('\n');
    const counters = [];
    let caretShift = 0;
    const out = lines.map((line, i) => {
      const { level, body } = this.splitLine(line);
      if (mode === 'none') {
        if (i === caretLine) caretShift = (level * 4 + body.length) - line.length;
        return '    '.repeat(level) + body;
      }
      counters.length = level + 1;
      counters[level] = (counters[level] || 0) + 1;
      const nl = '    '.repeat(level) + this.listPrefix(mode, level, counters[level]) + ' ' + body;
      if (i === caretLine) caretShift = nl.length - line.length;
      return nl;
    });
    el.value = out.join('\n');
    if (keepCaret) {
      const lineStart = out.slice(0, caretLine).reduce((a, l) => a + l.length + 1, 0);
      const p = lineStart + Math.max(0, Math.min(out[caretLine].length, caretCol + caretShift));
      el.setSelectionRange(p, p);
    }
    this.autosize(el);
  },
  listKey(e, el) {
    if (this.textOpts.list === 'none') return false;
    const pos = el.selectionStart;
    const lineStart = el.value.lastIndexOf('\n', pos - 1) + 1;
    let lineEnd = el.value.indexOf('\n', pos);
    if (lineEnd < 0) lineEnd = el.value.length;
    const { level, body } = this.splitLine(el.value.slice(lineStart, lineEnd));
    if (e.key === 'Enter' && !e.metaKey && !e.ctrlKey) {
      e.preventDefault();
      if (!body.trim()) {
        if (!level) {
          el.value = (el.value.slice(0, Math.max(0, lineStart - 1)) + el.value.slice(lineEnd)).replace(/\n$/, '');
          this.commitInline();
          return true;
        }
        const nl = '    '.repeat(level - 1);
        el.value = el.value.slice(0, lineStart) + nl + el.value.slice(lineEnd);
        el.setSelectionRange(lineStart + nl.length, lineStart + nl.length);
      } else {
        const ind = '    '.repeat(level);
        el.value = el.value.slice(0, pos) + '\n' + ind + el.value.slice(pos);
        el.setSelectionRange(pos + 1 + ind.length, pos + 1 + ind.length);
      }
      this.applyList(el, true);
      return true;
    }
    if (e.key === 'Tab') {
      e.preventDefault();
      const nl = e.shiftKey ? '    '.repeat(Math.max(0, level - 1)) + body : '    '.repeat(level + 1) + body;
      el.value = el.value.slice(0, lineStart) + nl + el.value.slice(lineEnd);
      el.setSelectionRange(lineStart + nl.length, lineStart + nl.length);
      this.applyList(el, true);
      return true;
    }
    return false;
  },
  async newInline(x, y) {
    if (this.inline) this.commitInline();
    const v = this.viewer, z = v.zoom;
    const el = h('textarea', { class: 'inline-edit new', spellcheck: false, wrap: 'off', rows: 1 });
    Object.assign(el.style, { left: x * z + 'px', top: (y - this.textOpts.size * 0.1) * z + 'px', width: Math.max(80, (v.size[0] - x - 8) * z) + 'px' });
    await this.styleNew(el);
    v.ov.append(el);
    this.inline = { el, isNew: true, x, y };
    if (this.textOpts.list !== 'none') this.applyList(el, true);
    el.addEventListener('keydown', e => {
      e.stopPropagation();
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); this.commitInline(); return; }
      if (e.key === 'Escape') { e.preventDefault(); this.cancelInline(); return; }
      this.listKey(e, el);
    });
    el.addEventListener('input', () => this.autosize(el));
    el.addEventListener('mousedown', e => e.stopPropagation());
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
    this.renderBar();
  },

  /* ---- portapapeles ---- */
  async copyAny(cut = false, asImage = false) {
    if (!this.info) return;
    const n = this.viewer.n;
    if (this.selSpans.size && !asImage) {
      const indices = [...this.selSpans];
      const r = await run('Copiando…', () => api('edit/copy_spans', { id: this.info.id, n, indices }));
      if (!r) return;
      this.clipKind = 'spans';
      this.clipAnchor = this.st.spans.filter(s => this.selSpans.has(s.i)).reduce((a, s) => [Math.min(a[0], s.bbox[0]), Math.min(a[1], s.bbox[1])], [1e9, 1e9]);
      navigator.clipboard?.writeText(r.text).catch(() => {});
      if (cut) await this.op('delete_spans', { indices });
      toast(cut ? 'Cortado. Pega con ⌘V donde tengas el ratón.' : 'Copiado. Pega con ⌘V donde tengas el ratón.', 'ok', [], 2500);
      this.saveClip(); this._clipAt = Date.now();
      return;
    }
    // campos de formulario y formas: se copian como objetos (se pegan editables)
    const obj = this.sel?.type === 'widget' ? 'widget' : (this.sel?.type === 'annot' && this.st.annots.find(x => x.xref === this.sel.id)?.style ? 'annot' : null);
    if (obj && !asImage) {
      const r = await run('Copiando…', () => api('edit/copy_object', { id: this.info.id, n, kind: obj, xref: this.sel.id }));
      if (!r) return;
      this.clipKind = 'object';
      this.clipObj = r;
      this.clipAnchor = r.rect;
      if (cut) await this.op(obj === 'widget' ? 'delete_widget' : 'delete_annot', { xref: this.sel.id });
      toast(`${obj === 'widget' ? (cut ? 'Campo cortado' : 'Campo copiado') : (cut ? 'Forma cortada' : 'Forma copiada')}. Pega con ⌘V donde tengas el ratón (también en otra página).`, 'ok', [], 3000);
      this.saveClip(); this._clipAt = Date.now();
      return;
    }
    // zona: la seleccionada, la de los textos seleccionados o la de la imagen seleccionada
    let rect = this.region?.r;
    if (!rect && this.selSpans.size) rect = this.st.spans.filter(s => this.selSpans.has(s.i)).map(s => s.bbox).reduce((a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])]);
    if (!rect && this.sel?.type === 'image') rect = this.st.images.find(i => i.xref === this.sel.id)?.bbox;
    if (!rect && this.sel?.type === 'annot') rect = this.st.annots.find(i => i.xref === this.sel.id)?.bbox;
    if (!rect) return toast('Selecciona un texto, una imagen o arrastra en una zona vacía para seleccionar un área.', '', [], 3500);
    const r = await run('Copiando…', () => api('edit/copy', { id: this.info.id, n, rect }));
    if (!r) return;
    this.clip = r;
    this.clipKind = 'region';
    this.clipAsImage = asImage || !r.text;
    this.clipAnchor = rect;
    try {
      const blob = await (await fetch('data:image/png;base64,' + r.png)).blob();
      const items = { 'image/png': blob };
      if (r.text) items['text/plain'] = new Blob([r.text], { type: 'text/plain' });
      await navigator.clipboard.write([new ClipboardItem(items)]);
    } catch (e) { /* portapapeles del sistema no disponible: se usa el interno */ }
    if (cut) {
      if (this.sel?.type === 'image') await this.op('delete_image', { xref: this.sel.id });
      else if (this.sel?.type === 'annot') await this.op('delete_annot', { xref: this.sel.id });
    }
    toast(this.clipAsImage ? 'Copiado como captura. Pega con ⌘V donde tengas el ratón.' : 'Zona copiada. Pega con ⌘V donde tengas el ratón.', 'ok', [], 2500);
    this.saveClip(); this._clipAt = Date.now();
  },
  /** Lo copiado se comparte entre ventanas de DocGuard (el contenido está en el servidor). */
  saveClip() {
    try { localStorage.setItem('dg_clip', JSON.stringify({ clipKind: this.clipKind, clipObj: this.clipObj, clipAnchor: this.clipAnchor, clipAsImage: this.clipAsImage, at: Date.now() })); } catch (e) { /* sin almacenamiento */ }
  },
  loadClip() {
    try {
      const c = JSON.parse(localStorage.getItem('dg_clip') || 'null');
      if (c && (!this._clipAt || c.at > this._clipAt)) { Object.assign(this, c); this._clipAt = c.at; if (c.clipKind === 'region') this.clip = true; }
    } catch (e) { /* sin almacenamiento */ }
  },
  async pasteAny(asImage = false) {
    if (!this.info) return;
    this.loadClip();
    const v = this.viewer;
    const at = this.mouse && this.mouse.n === v.n ? this.mouse.p : null;
    if (this.clipKind === 'spans') {
      const [x, y] = at || [this.clipAnchor[0] + 12, this.clipAnchor[1] + 12];
      return this.op('paste_spans', { x, y }, 'Pegando…');
    }
    if (this.clipKind === 'object' && this.clipObj) {
      const o = this.clipObj;
      const [x, y] = at || [this.clipAnchor[0] + 15, this.clipAnchor[1] + 15];
      const ok = await this.op('paste_object', { spec: o, x, y }, 'Pegando…');
      if (!ok) return;
      const w = o.rect[2] - o.rect[0], hh = o.rect[3] - o.rect[1];
      if (o.kind === 'widget') {  // se selecciona lo pegado para poder moverlo enseguida
        const nw = this.st.widgets.reduce((b, x2) => (!b || Math.abs(x2.bbox[0] - x) + Math.abs(x2.bbox[1] - y) < Math.abs(b.bbox[0] - x) + Math.abs(b.bbox[1] - y) ? x2 : b), null);
        if (nw) this.select('widget', nw.xref);
      } else this.reselectAnnot([x, y, x + w, y + hh]);
      return;
    }
    if (this.clipKind === 'region' && this.clip) {
      const [x, y] = at || [this.clipAnchor[0] + 20, this.clipAnchor[1] + 20];
      return this.op('paste', { x, y, mode: asImage || this.clipAsImage ? 'image' : 'auto' }, 'Pegando…');
    }
    try {
      const items = await navigator.clipboard.read();
      const [W, H] = v.size;
      for (const it of items) {
        const t = it.types.find(t => t.startsWith('image/'));
        if (t) {
          const blob = await it.getType(t);
          const data = await fileToB64(blob);
          const dim = await new Promise(res => { const im = new Image(); im.onload = () => res([im.width, im.height]); im.src = URL.createObjectURL(blob); });
          const w = Math.min(W * 0.5, dim[0] * 0.75), hh = w * dim[1] / dim[0];
          const [x, y] = at || [(W - w) / 2, (H - hh) / 2];
          return this.op('insert_image', { rect: [x, y, x + w, y + hh], data });
        }
      }
      const text = await navigator.clipboard.readText();
      if (text) { const [x, y] = at || [W * 0.1, H * 0.1]; return this.op('add_text', { x, y, text, ...this.textOpts }); }
      toast('No hay nada que pegar.', '');
    } catch (e) {
      toast('No hay nada copiado todavía. Selecciona texto, una imagen o una zona y pulsa ⌘C.', '', [], 4000);
    }
  },

  /* ---- Comentarios (notas con autor y fecha, visibles en Acrobat y otros lectores) ---- */
  commentDialog(title, { text = '', author = '' } = {}) {
    return new Promise(resolve => {
      const ta = h('textarea', { rows: 5, placeholder: 'Escribe tu comentario…' }, text);
      const au = h('input', { value: author, placeholder: 'Tu nombre' });
      let done = false;
      const finish = v => { if (!done) { done = true; resolve(v); } };
      modal({
        title, onclose: () => finish(null),
        body: h('div', {}, h('label', {}, 'Comentario', ta), h('label', {}, 'Autor', au)),
        actions: [{ label: 'Cancelar', fn: () => finish(null) }, { label: 'Guardar', primary: true, fn: () => { if (!ta.value.trim()) return false; finish({ text: ta.value.trim(), author: au.value.trim() }); } }],
      });
      setTimeout(() => ta.focus(), 50);
    });
  },
  async addComment(x, y) {
    let author = '';
    try { author = localStorage.getItem('dg_author') || ''; } catch (e) { /* sin almacenamiento */ }
    const r = await this.commentDialog('Nuevo comentario', { author });
    if (!r) return;
    try { localStorage.setItem('dg_author', r.author); } catch (e) { /* sin almacenamiento */ }
    await this.op('add_annot', { kind: 'note', rect: [x, y, x + 20, y + 20], text: r.text, author: r.author, color: this.ann.color });
  },
  async editComment(c) {
    const r = await this.commentDialog('Editar comentario', { text: c.content, author: c.author });
    if (!r) return;
    if (this.viewer.n !== c.n) await this.viewer.go(c.n);
    await this.op('edit_comment', { n: c.n, xref: c.xref, text: r.text });
  },
  gotoComment(c) {
    this.setTool('select');
    this.viewer.go(c.n);
    setTimeout(() => this.select('annot', c.xref), 500);
  },

  /* ---- Tabla: rellenar las celdas (se puede pegar desde Excel o Word) ---- */
  tableDialog(rows, cols) {
    return new Promise(resolve => {
      const inputs = [];
      const grid = h('div', { class: 'tbl-grid', style: `grid-template-columns: repeat(${cols}, minmax(90px, 1fr))` });
      for (let i = 0; i < rows; i++) {
        inputs.push([]);
        for (let j = 0; j < cols; j++) {
          const inp = h('input', { placeholder: i === 0 ? `Columna ${j + 1}` : '' });
          inp.addEventListener('paste', e => {  // varias celdas separadas por tabuladores y saltos de línea
            const txt = e.clipboardData.getData('text');
            if (!/[\t\n]/.test(txt)) return;
            e.preventDefault();
            txt.replace(/\r/g, '').replace(/\n$/, '').split('\n').forEach((line, di) => line.split('\t').forEach((v, dj) => { if (inputs[i + di]?.[j + dj]) inputs[i + di][j + dj].value = v; }));
          });
          inp.addEventListener('keydown', e => {
            const mv = { ArrowDown: [1, 0], ArrowUp: [-1, 0], Enter: [1, 0] }[e.key];
            if (mv && !e.shiftKey) { e.preventDefault(); inputs[i + mv[0]]?.[j + mv[1]]?.focus(); }
          });
          inputs[i].push(inp);
          grid.append(inp);
        }
      }
      let done = false;
      const finish = v => { if (!done) { done = true; resolve(v); } };
      modal({
        title: `Tabla de ${rows} × ${cols}`,
        body: h('div', {}, h('p', { class: 'muted' }, 'Escribe el contenido de cada celda. Tab pasa a la siguiente; Intro baja; se puede pegar un bloque copiado de Excel o Word. La primera fila es la cabecera.'), grid),
        onclose: () => finish(null),
        actions: [{ label: 'Cancelar', fn: () => finish(null) }, { label: 'Insertar tabla', primary: true, fn: () => finish(inputs.map(r => r.map(i => i.value))) }],
      });
      setTimeout(() => inputs[0][0].focus(), 50);
    });
  },

  /* ---- OCR y firma al margen ---- */
  async ocrDialog() {
    if (!this.info) return toast('Abre primero un documento.', 'err');
    const mode = h('select', {}, h('option', { value: 'editable' }, 'Convertir en texto editable'),
      h('option', { value: 'invisible' }, 'Solo hacerlo seleccionable (mantiene el aspecto)'));
    const scope = h('select', {}, h('option', { value: 'page' }, 'Esta página'), h('option', { value: 'all' }, 'Todas las páginas'));
    modal({
      title: 'Reconocer texto (OCR)',
      body: h('div', {}, h('p', { class: 'muted' }, 'Para documentos escaneados o fotos. «Editable» sustituye la imagen del texto por texto real que puedes cambiar. «Seleccionable» añade una capa invisible para buscar y copiar sin cambiar el aspecto.'),
        h('label', {}, 'Qué hacer', mode), h('label', {}, 'Páginas', scope)),
      actions: [{ label: 'Cancelar' }, {
        label: 'Reconocer', primary: true, fn: async () => {
          const pages = scope.value === 'all' ? this.info.pages.map((_, i) => i) : [this.viewer.n];
          busy(true, 'Reconociendo texto…');
          try {
            for (let k = 0; k < pages.length; k++) {
              busyText(`Reconociendo texto… página ${pages[k] + 1} (${k + 1} de ${pages.length})`);
              await api('edit/ocr', { id: this.info.id, n: pages[k], pages: [pages[k]], mode: mode.value });
            }
            toast('Texto reconocido. ' + (mode.value === 'editable' ? 'Ya puedes editarlo.' : 'Ya se puede seleccionar y buscar.'), 'ok');
          } catch (e) { toast(e.message, 'err'); } finally { busy(false); }
          this.setTool('select');
          this.refresh(true);
        },
      }],
    });
  },
  marginDialog() {
    if (!this.sig) return toast('Elige o crea primero una firma.', 'err');
    const side = h('select', {},
      h('option', { value: 'derecha' }, 'Margen derecho (vertical)'), h('option', { value: 'izquierda' }, 'Margen izquierdo (vertical)'),
      h('option', { value: 'pie-derecha' }, 'Pie de página, a la derecha'), h('option', { value: 'pie-centro' }, 'Pie de página, centrada'),
      h('option', { value: 'pie-izquierda' }, 'Pie de página, a la izquierda'));
    const length = h('input', { type: 'range', min: 10, max: 45, value: 22 });
    const pages = h('select', { onchange: () => { ranges.hidden = pages.value !== 'ranges'; } },
      h('option', { value: 'all' }, 'Todas las páginas'), h('option', { value: 'ranges' }, 'Solo algunas…'));
    const ranges = h('input', { placeholder: 'Ej.: 1-3, 5', hidden: true });
    modal({
      title: 'Firmar al margen',
      body: h('div', {}, h('p', { class: 'muted' }, 'Coloca tu firma en el margen de varias páginas de una vez, como en los contratos.'),
        h('label', {}, 'Posición', side), h('label', {}, 'Tamaño', length), h('label', {}, 'Páginas', pages), ranges),
      actions: [{ label: 'Cancelar' }, {
        label: 'Firmar', primary: true, fn: async () => {
          const r = await run('Firmando las páginas…', () => api('sigimg/margin', {
            id: this.info.id, sig: this.sig, side: side.value, length: +length.value, ranges: pages.value === 'ranges' ? ranges.value : '',
          }));
          if (r) { toast(r.message, 'ok'); this.refresh(true); }
        },
      }],
    });
  },
};
