'use strict';
// Herramienta Visor PDF: varios PDFs a la vez, búsqueda en todos (⌘F) y lector
// que se abre por encima al pinchar en una página.

const Library = {
  init() {
    this.root = $('#tool-library');
    this.docs = [];          // infos de los documentos abiertos
    this.res = null;         // resultados de la última búsqueda
    this.term = '';
    const act = (a, f) => { $(`[data-act=${a}]`, this.root).onclick = f; };
    act('add', async () => this.add(await pickFiles(ACCEPT_DOCS, true)));
    act('clear', () => { this.docs.forEach(d => api('close', { id: d.id }).catch(() => {})); this.docs = []; this.res = null; this.render(); });
    act('rclose', () => this.closeReader());
    act('rnext', () => this.step(1));
    act('rprev', () => this.step(-1));
    act('rprint', () => printDoc(this.reading));
    act('redit', () => { const d = this.reading; this.closeReader(); showTool('edit'); Edit.loadInfo(d); });
    dropTarget($('.lib-list', this.root), f => this.add(f));
    const term = $('[data-k=term]', this.root);
    term.addEventListener('keydown', e => {
      e.stopPropagation();
      if (e.key === 'Enter') this.search(term.value.trim());
      if (e.key === 'Escape') { term.value = ''; this.search(''); }
    });
    $('[data-k=only]', this.root).onchange = () => this.render();
    document.addEventListener('keydown', e => {
      if (!this.root.classList.contains('active')) return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'f') { e.preventDefault(); term.focus(); term.select(); }
      if (e.key === 'Escape' && !$('.reader', this.root).hidden) this.closeReader();
      if (!$('.reader', this.root).hidden && e.key === 'Enter' && document.activeElement === document.body) this.step(e.shiftKey ? -1 : 1);
      // ⌘Z / ⇧⌘Z en el lector: deshacer / rehacer (p. ej. un giro)
      if (!$('.reader', this.root).hidden && (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z' && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) {
        e.preventDefault();
        this.undoRedo(e.shiftKey ? 'redo' : 'undo');
      }
    });
    act('rrotl', () => this.rotate(-90));
    act('rrotr', () => this.rotate(90));
    this.viewer = new ContViewer($('.reader-host', this.root), { keepOverlays: true, firstClickActivates: false });
    this.viewer.fitPage = true;  // «Ajustar» muestra la hoja entera
    this.viewer.onrender = () => { this.drawHits(); this.textLayers(); };
    this.viewer.el.addEventListener('scroll', () => { clearTimeout(this._tl); this._tl = setTimeout(() => this.textLayers(), 120); });
    makeResizable($('.lib-results', this.root), 'left', 'lib', 220, 620);
  },
  loadInfo(info) { if (!this.docs.some(d => d.id === info.id)) { this.docs.push(info); this.render(); } },
  /** Abre un documento directamente en el lector, con la hoja entera (doble clic, «Abrir con…», «Añadir» de un archivo). */
  async openDoc(info) {
    info = await unlockInfo(info);
    if (!info?.pages?.length || info.encrypted) return toast(`${info?.name || 'El archivo'}: no se puede mostrar (con contraseña o formato no admitido).`, 'err');
    this.loadInfo(info);
    setCurrent(info);
    this.openReader(this.docs.find(d => d.id === info.id) || info, 0);
  },

  async add(files) {
    if (!files.length) return;
    const before = this.docs.length;
    busy(true, 'Abriendo…');
    try {
      for (const f of files) {
        try {
          const info = await uploadFile(f);
          if (!info.pages.length || info.encrypted) toast(`${info.name}: no se puede mostrar (con contraseña o formato no admitido).`, 'err');
          else this.docs.push(info);
        } catch (e) { toast(e.message, 'err'); }
      }
    } finally { busy(false); }
    this.render();
    if (this.term) this.search(this.term);
    if (files.length === 1 && this.docs.length > before) this.openDoc(this.docs[this.docs.length - 1]);  // uno solo: se abre ya
  },
  hitsOf(id) { return this.res?.docs.find(d => d.id === id); },

  render() {
    const list = $('.lib-list', this.root);
    list.innerHTML = '';
    const pages = this.docs.reduce((a, d) => a + d.pages.length, 0);
    $('[data-role=count]', this.root).textContent = this.docs.length ? `${this.docs.length} PDF · ${pages} páginas` : '';
    if (!this.docs.length) {
      list.append(h('div', { class: 'empty' }, 'Añade o arrastra aquí varios PDFs. Con ⌘F buscas en todos a la vez; pincha en una página para leer ese PDF.'));
      this.renderResults();
      return;
    }
    const only = $('[data-k=only]', this.root).checked && this.res;
    for (const d of this.docs) {
      const hd = this.hitsOf(d.id);
      const hitPages = new Map((hd?.pages || []).map(p => [p.n, p.rects.length]));
      const count = [...hitPages.values()].reduce((a, b) => a + b, 0);
      if (only && !count) continue;
      const strip = h('div', { class: 'lib-strip' });
      d.pages.forEach((_, n) => {
        if (only && !hitPages.has(n)) return;
        const c = hitPages.get(n);
        strip.append(h('div', { class: 'lib-page' + (c ? ' hit' : ''), title: `Página ${n + 1}`, onclick: () => this.openReader(d, n) },
          h('img', { src: pageUrl(d.id, n, 0.25), loading: 'lazy', alt: '' }), c ? h('span', { class: 'hc' }, c) : null, h('div', {}, n + 1)));
      });
      list.append(h('div', { class: 'lib-doc' + (this.res && !count ? ' nohit' : '') },
        h('div', { class: 'lib-head' }, h('b', { title: d.name }, d.name), h('small', {}, `${d.pages.length} pág.`),
          count ? h('span', { class: 'badge' }, `${count} coincidencia(s)`) : null,
          hd?.no_text ? h('small', { class: 'muted', title: 'Pásale OCR en Editar para poder buscar' }, 'sin texto (escaneado)') : null,
          h('button', { title: 'Leer', onclick: () => this.openReader(d, hitPages.size ? [...hitPages.keys()][0] : 0) }, 'Leer'),
          h('button', { title: 'Quitar de la lista', onclick: () => { this.docs = this.docs.filter(x => x !== d); api('close', { id: d.id }).catch(() => {}); this.render(); } }, '✕')),
        strip));
    }
    this.renderResults();
  },
  renderResults() {
    const box = $('.lib-results', this.root);
    box.innerHTML = '';
    box.append(h('h3', {}, 'Resultados'));
    $('.findcount', this.root).textContent = this.res ? `${this.res.total}` : '';
    if (!this.res) { box.append(h('p', { class: 'muted' }, 'Escribe un término y pulsa Intro. Se busca en todos los PDFs abiertos.')); return; }
    if (!this.res.total) { box.append(h('p', {}, `No se ha encontrado «${this.term}».`)); return; }
    const esc = t => t.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
    const re = new RegExp(this.term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    for (const hd of this.res.docs) {
      if (!hd.pages.length) continue;
      const d = this.docs.find(x => x.id === hd.id);
      if (!d) continue;
      box.append(h('div', { class: 'res-doc' }, `${d.name} (${hd.pages.reduce((a, p) => a + p.rects.length, 0)})`));
      for (const p of hd.pages) {
        const el = h('div', { class: 'res', onclick: () => this.openReader(d, p.n) }, h('b', {}, `Pág. ${p.n + 1} · `));
        const span = h('span');
        span.innerHTML = esc(p.snippet).replace(re, m => `<mark>${m}</mark>`);
        el.append(span);
        box.append(el);
      }
    }
  },
  async search(term) {
    this.term = term;
    if (!term || !this.docs.length) { this.res = null; this.render(); return; }
    this.res = await run('Buscando en todos los PDFs…', () => api('search_many', { ids: this.docs.map(d => d.id), term }));
    this.render();
    if (!$('.reader', this.root).hidden) { this.readerHits(); this.drawHits(); }
  },

  /* ---- lector ---- */
  openReader(d, n) {
    this.reading = d;
    const r = $('.reader', this.root);
    r.hidden = false;
    $('.reader-name', this.root).textContent = d.name;
    updateTitle(d.name);
    this.viewer.load(d);
    this.showSignatures(d);
    this.readerHits();
    requestAnimationFrame(() => {
      this.viewer.fit();
      this.viewer.go(n);
      const k = this.hits.findIndex(x => x.n === n);
      if (k >= 0) this.showHit(k); else this.drawHits();
    });
  },
  closeReader() { $('.reader', this.root).hidden = true; this.reading = null; updateTitle(); },
  /** Franja con el estado de cada firma digital: verde si todo está bien, naranja si hay avisos, rojo si no vale.
   *  Primero se verifica sin conexión (rápido) y luego se consulta en línea si el certificado está revocado. */
  async showSignatures(d) {
    const box = $('.sig-banner', this.root);
    box.hidden = true;
    box.replaceChildren();
    if (d.kind !== 'pdf' || d.encrypted) return;
    const paint = (sigs, checking) => {
      if (this.reading !== d) return;
      box.hidden = !sigs.length;
      const n = sigs.length;
      box.replaceChildren(...sigs.map((s, i) => {
        const st = { ok: '✔ Firma válida', aviso: '⚠ Firma válida con avisos', mal: '✘ Firma NO válida' }[s.level];
        const list = h('ul', { hidden: s.level === 'ok' }, s.notes.map(t => h('li', { class: t.k }, t.t)));
        return h('div', { class: 'sig-row ' + s.level, title: 'Ver detalles', onclick: () => { list.hidden = !list.hidden; } },
          h('span', { class: 'st' }, st), ` · ${n > 1 ? `Firma ${i + 1} de ${n} · ` : ''}${s.name}${s.time ? ' · ' + s.time : ''}`,
          checking ? h('span', { class: 'chk' }, ' · comprobando revocación…') : null, list);
      }));
    };
    let sigs;
    try { sigs = (await api('verify', { id: d.id })).signatures; } catch (e) { return; }
    if (!sigs.length) return;
    paint(sigs, true);
    try { sigs = (await api('verify', { id: d.id, online: true })).signatures; } catch (e) { /* sin conexión */ }
    paint(sigs, false);
  },
  readerHits() {
    const hd = this.reading && this.hitsOf(this.reading.id);
    this.hits = (hd?.pages || []).flatMap(p => p.rects.map(r => ({ n: p.n, r })));
    this.hitIdx = -1;
    $('.reader-count', this.root).textContent = this.hits.length ? `${this.hits.length} coincidencia(s)` : '';
  },
  showHit(k) {
    this.hitIdx = k;
    const hit = this.hits[k];
    const v = this.viewer;
    v.go(hit.n);
    v.el.scrollTop = v.pages[hit.n].wrap.offsetTop + hit.r[1] * v.zoom - v.el.clientHeight / 3;
    $('.reader-count', this.root).textContent = `${k + 1} / ${this.hits.length}`;
    this.drawHits();
  },
  /** ▲ ▼: con una búsqueda, coincidencia anterior / siguiente; sin búsqueda, página anterior / siguiente. */
  step(d) {
    if (this.hits?.length) this.showHit((this.hitIdx + d + this.hits.length) % this.hits.length);
    else this.viewer.go(this.viewer.n + d);
  },
  /** Gira todas las páginas del documento que se está leyendo (cambio real del PDF, con deshacer):
   *  así se imprime, se copia el texto y se guarda ya girado. */
  async rotate(deg) {
    const d = this.reading;
    if (!d) return;
    const r = await run('Girando…', () => api('edit/rotate', { id: d.id, deg }));
    if (r !== undefined) this.reloadReading();
  },
  async undoRedo(what) {
    const d = this.reading;
    if (!d) return;
    const r = await run(what === 'undo' ? 'Deshaciendo…' : 'Rehaciendo…', () => api('edit/' + what, { id: d.id }));
    if (r !== undefined) this.reloadReading();
  },
  /** Vuelve a cargar el documento del lector tras cambiarlo (tamaños de página nuevos), en la misma página. */
  async reloadReading() {
    const d = this.reading, n = this.viewer.n;
    const info = await api('info', { id: d.id }).catch(() => null);
    if (!info) return;
    // el mismo documento puede estar abierto en Editar, en las pestañas o como documento actual
    for (const o of new Set([d, CURRENT, typeof Edit !== 'undefined' ? Edit.info : null, ...this.docs])) {
      if (o && o.id === d.id) Object.assign(o, info);
    }
    this.viewer.load(d);
    requestAnimationFrame(() => { this.viewer.fit(); this.viewer.go(n); });
    if (typeof Tabs !== 'undefined') Tabs.refresh();
  },
  /** Capa de texto invisible sobre las páginas del lector, para seleccionar y copiar (⌘C) como en un
   *  lector de PDF. Se crea para las páginas cercanas a la vista y se escala con el zoom. */
  textLayers() {
    const v = this.viewer, d = this.reading;
    if (!v.pages || !d) return;
    const top = v.el.scrollTop - 600, bottom = v.el.scrollTop + v.el.clientHeight + 600;
    v.pages.forEach((p, i) => {
      const [pw, ph] = v.info.pages[i];
      let tl = $('.textlayer', p.wrap);
      if (tl) { tl.style.transform = `scale(${p.wrap.clientWidth / pw})`; return; }
      const y0 = p.wrap.offsetTop, y1 = y0 + p.wrap.offsetHeight;
      if (y1 < top || y0 > bottom) return;
      tl = h('div', { class: 'textlayer' });
      Object.assign(tl.style, { width: pw + 'px', height: ph + 'px', transform: `scale(${p.wrap.clientWidth / pw})` });
      p.wrap.append(tl);
      api('edit/words', { id: d.id, n: i }).then(r => { if (this.reading?.id === d.id) this.fillText(tl, r.words, r.rotation || 0); }).catch(() => {});
    });
  },
  fillText(tl, words, rot = 0) {
    const ctx = this._measure || (this._measure = document.createElement('canvas').getContext('2d'));
    const frag = document.createDocumentFragment();
    const side = rot === 90 || rot === 270;  // página girada: el texto va en vertical
    words.forEach((w, k) => {
      const [x0, y0, x1, y1] = w.bbox, hh = y1 - y0, ww = x1 - x0;
      if (hh <= 0 || ww <= 0) return;
      const next = words[k + 1];
      const sep = !next ? '' : next.line === w.line ? ' ' : '\n';  // al copiar: espacios y saltos de línea
      const fs = (side ? ww : hh) * 0.9, len = side ? hh : ww;
      ctx.font = `${fs}px sans-serif`;
      const sx = len / (ctx.measureText(w.text).width || len);
      // origen y giro de la palabra según cómo esté girada la página (como el texto de la imagen)
      const [left, top] = { 0: [x0, y0], 90: [x1, y0], 180: [x1, y1], 270: [x0, y1] }[rot] || [x0, y0];
      const s = h('span', {}, w.text + sep);
      s.style.cssText = `left:${left}px;top:${top}px;font-size:${fs}px;transform:rotate(${rot}deg) scaleX(${sx})`;
      frag.append(s);
    });
    tl.append(frag);
  },
  drawHits() {
    const v = this.viewer;
    if (!v.pages) return;
    v.pages.forEach(p => p.ov.replaceChildren());
    (this.hits || []).forEach((hit, i) => {
      const ov = v.pageOv(hit.n);
      if (ov) v.box(hit.r, 'hit' + (i === this.hitIdx ? ' cur' : ''), ov);
    });
  },
};
