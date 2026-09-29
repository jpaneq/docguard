'use strict';
// Herramienta Marca de agua (protección, QR, ocultar datos de DNI/pasaporte).

/* ======================================================================
   MARCA DE AGUA
   ====================================================================== */

const Wm = {
  init() {
    this.root = $('#tool-watermark');
    this.img = $('.preview-img img', this.root);
    this.n = 0;
    this.files = new FileList($('[data-role=files]', this.root), {
      accept: ACCEPT_DOCS, onselect: info => { this.n = 0; if (info) setCurrent(info); this.preview(); },
      onchange: () => this.preview(),
    });
    dropTarget($('.preview', this.root), f => this.files.add(f));
    $$('input,select', this.root).forEach(el => el.addEventListener('input', () => { this.outputs(); this.schedule(); }));
    $('[data-act=prev]', this.root).onclick = () => { this.n = Math.max(0, this.n - 1); this.preview(); };
    $('[data-act=next]', this.root).onclick = () => { this.n = Math.min(this.pages() - 1, this.n + 1); this.preview(); };
    $('[data-act=export]', this.root).onclick = () => this.export();
    $('[data-k=preset]', this.root).onchange = e => this.applyPreset(e.target.value);
    $('[data-act=preset-save]', this.root).onclick = () => this.savePreset();
    $('[data-act=preset-del]', this.root).onclick = () => this.deletePreset();
    this.k('qr').addEventListener('change', () => { $('[data-role=qr]', this.root).hidden = !this.k('qr').checked; });
    this.hideData = {};
    this.hov = $('.hide-ov', this.root);
    this.img.addEventListener('load', () => this.placeOverlay());
    new ResizeObserver(() => this.placeOverlay()).observe($('.preview-img', this.root));
    this.hov.addEventListener('mousedown', e => this.hideDown(e));
    this.k('autohide').addEventListener('change', () => { this.ensureHide(); this.renderHide(); this.schedule(); });
    document.addEventListener('keydown', e => {
      if (!this.root.classList.contains('active') || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
      if ((e.key === 'Delete' || e.key === 'Backspace') && this.hsel) { e.preventDefault(); this.removeHide(this.hsel); }
    });
    const qrMode = () => {
      $('[data-role=qrweb]', this.root).hidden = this.k('qr_mode').value !== 'web';
      try { localStorage.setItem('dg_qr_base', this.k('qr_base').value); localStorage.setItem('dg_qr_mode', this.k('qr_mode').value); } catch (e) { /* sin almacenamiento */ }
    };
    try {
      this.k('qr_base').value = localStorage.getItem('dg_qr_base') || '';
      this.k('qr_mode').value = localStorage.getItem('dg_qr_mode') || 'vcard';
    } catch (e) { /* sin almacenamiento */ }
    this.k('qr_mode').addEventListener('change', qrMode);
    this.k('qr_base').addEventListener('change', qrMode);
    qrMode();
    this.k('level').addEventListener('change', () => { this.k('strike').disabled = this.k('level').value === 'basica'; });
    $('[data-act=check]', this.root).onclick = () => this.check();
    $('[data-act=registry]', this.root).onclick = () => this.registry();
    new ResizeObserver(() => this.schedule()).observe($('.preview-img', this.root));
    this.outputs();
    this.loadPresets();
  },
  loadInfo(info) { this.files.setItems([info]); },
  k(name) { return $(`[data-k=${name}]`, this.root); },
  pages() { return Math.max(1, this.files.current?.pages.length || 1); },
  outputs() { $$('input[type=range]', this.root).forEach(r => { r.parentElement.querySelector('output').textContent = r.value; }); },
  params() {
    const p = {};
    for (const k of ['text', 'angle', 'size', 'gap_x', 'gap_y', 'opacity', 'color', 'level']) p[k] = this.k(k).value;
    for (const k of ['hardened', 'strike', 'mark']) p[k] = this.k(k).checked;
    p.autohide = this.k('autohide').checked;
    const cur = this.files.current;
    p.hide_page = cur ? this.activeRects(cur.id, this.n).map(x => x.r) : [];
    p.hide = {};
    for (const [id, pages] of Object.entries(this.hideData)) {
      p.hide[id] = {};
      for (const n of Object.keys(pages)) p.hide[id][n] = this.activeRects(id, +n).map(x => x.r);
    }
    p.qr = { enabled: this.k('qr').checked, recipient: this.k('qr_recipient').value, purpose: this.k('qr_purpose').value,
      size: +this.k('qr_size').value, pos: this.k('qr_pos').value, mode: this.k('qr_mode').value, base_url: this.k('qr_base').value };
    return p;
  },
  schedule() { clearTimeout(this.t); this.t = setTimeout(() => this.preview(), 150); },
  async preview() {
    const cur = this.files.current;
    const box = $('.preview-img', this.root);
    box.classList.toggle('has', !!cur);
    $('.pager', this.root).style.visibility = cur && this.pages() > 1 ? '' : 'hidden';
    $('.pager span', this.root).textContent = `${this.n + 1} / ${this.pages()}`;
    if (!cur) { this.renderHide(); return; }
    if (this.ensureHide()) return;  // se volverá a llamar al terminar la detección
    this.renderHide();
    const maxw = Math.round(Math.min(1400, (box.clientWidth - 32) * (window.devicePixelRatio || 1)));
    const seq = (this.seq = (this.seq || 0) + 1);
    try {
      const blob = await api('wm/preview', { id: cur.id, n: this.n, params: this.params(), maxw: Math.max(300, maxw) });
      if (seq !== this.seq) return;
      if (this.url) URL.revokeObjectURL(this.url);
      this.url = URL.createObjectURL(blob);
      this.img.src = this.url;
    } catch (e) { toast(e.message, 'err'); }
  },
  async export() {
    if (!this.files.items.length) return toast('Abre primero algún documento.', 'err');
    const fmt = $('input[name=wmfmt]:checked', this.root).value;
    const w = this.k('width').value.trim(), hh = this.k('height').value.trim();
    if ((w && !(+w > 0)) || (hh && !(+hh > 0))) return toast('El tamaño debe ser un número de píxeles.', 'err');
    const res = await run('Aplicando la marca de agua…', () => api('wm/export', {
      ids: this.files.ids, params: this.params(), fmt, width: w || null, height: hh || null,
    }));
    saveResult(res);
  },
  /* ---- ocultar datos del documento de identidad ---- */
  hidePage(id, n) { return this.hideData[id]?.[n]; },
  ensureHide() {
    const cur = this.files.current;
    if (!cur || !this.k('autohide').checked) return false;
    const pg = this.hidePage(cur.id, this.n);
    if (pg) return false;
    (this.hideData[cur.id] = this.hideData[cur.id] || {})[this.n] = { loading: true, items: [], manual: [] };
    const n = this.n;
    busy(true, 'Buscando datos que ocultar…');
    api('idfields', { id: cur.id, n }).then(r => {
      this.hideData[cur.id][n] = { doc: r.doc, items: r.items.map(it => ({ ...it, on: true })), manual: [] };
      if (r.items.length) toast(`${r.doc === 'pasaporte' ? 'Pasaporte' : r.doc === 'dni' ? 'DNI' : 'Documento'}: ${r.items.length} dato(s) que conviene ocultar. Revísalos en la vista previa.`, 'ok', [], 5000);
    }).catch(e => { toast(e.message, 'err'); this.hideData[cur.id][n] = { items: [], manual: [] }; })
      .finally(() => { busy(false); this.preview(); });
    return true;
  },
  activeRects(id, n) {
    const pg = this.hidePage(id, n);
    if (!pg || pg.loading) return [];
    const out = [];
    if (this.k('autohide').checked) pg.items.forEach((it, ii) => { if (it.on) it.rects.forEach((r, ri) => out.push({ r, key: [ii, ri] })); });
    pg.manual.forEach((r, mi) => out.push({ r, key: ['m', mi] }));
    return out;
  },
  renderHide() {
    const list = $('[data-role=hidelist]', this.root);
    list.innerHTML = '';
    this.hov.innerHTML = '';
    const cur = this.files.current;
    const pg = cur && this.hidePage(cur.id, this.n);
    if (pg && !pg.loading && this.k('autohide').checked) {
      if (!pg.items.length) list.append(h('small', {}, 'No se han detectado datos de DNI/pasaporte en esta página.'));
      pg.items.forEach(it => {
        const cb = h('input', { type: 'checkbox', checked: it.on, onchange: () => { it.on = cb.checked; this.renderHide(); this.schedule(); } });
        list.append(h('div', {}, h('label', { class: 'inline' }, cb, it.label), it.text ? h('div', { class: 'ex' }, it.text.slice(0, 60)) : null));
      });
    }
    if (!cur) return;
    for (const a of this.activeRects(cur.id, this.n)) {
      const [x0, y0, x1, y1] = a.r;
      const isSel = this.hsel && this.hsel.join() === a.key.join();
      const d = h('div', { class: 'hbox' + (isSel ? ' sel' : ''), style: `left:${x0 * 100}%;top:${y0 * 100}%;width:${(x1 - x0) * 100}%;height:${(y1 - y0) * 100}%` });
      d.addEventListener('mousedown', e => { e.stopPropagation(); this.hsel = a.key; this.renderHide(); });
      if (isSel) d.append(h('div', { class: 'x', title: 'Quitar esta zona', onmousedown: e => { e.stopPropagation(); this.removeHide(a.key); } }, '✕'));
      this.hov.append(d);
    }
  },
  removeHide(key) {
    const cur = this.files.current;
    const pg = this.hidePage(cur.id, this.n);
    if (key[0] === 'm') pg.manual.splice(key[1], 1);
    else {
      const it = pg.items[key[0]];
      it.rects.splice(key[1], 1);
      if (!it.rects.length) it.on = false;
    }
    this.hsel = null;
    this.renderHide();
    this.schedule();
  },
  placeOverlay() {
    const box = $('.preview-img', this.root);
    const b = box.getBoundingClientRect(), r = this.img.getBoundingClientRect();
    Object.assign(this.hov.style, { left: r.left - b.left + box.scrollLeft + 'px', top: r.top - b.top + box.scrollTop + 'px', width: r.width + 'px', height: r.height + 'px' });
  },
  hideDown(e) {
    const cur = this.files.current;
    if (!cur || e.button !== 0) return;
    this.hsel = null;
    const R = this.hov.getBoundingClientRect();
    const pt = ev => [clamp((ev.clientX - R.left) / R.width, 0, 1), clamp((ev.clientY - R.top) / R.height, 0, 1)];
    const p0 = pt(e);
    const box = h('div', { class: 'drag-box' });
    this.hov.append(box);
    const mv = ev => { const r = norm(p0, pt(ev)); Object.assign(box.style, { left: r[0] * 100 + '%', top: r[1] * 100 + '%', width: (r[2] - r[0]) * 100 + '%', height: (r[3] - r[1]) * 100 + '%' }); };
    window.addEventListener('mousemove', mv);
    window.addEventListener('mouseup', ev => {
      window.removeEventListener('mousemove', mv);
      box.remove();
      const r = norm(p0, pt(ev));
      if ((r[2] - r[0]) * R.width < 6 || (r[3] - r[1]) * R.height < 6) { this.renderHide(); return; }
      const d = this.hideData[cur.id] = this.hideData[cur.id] || {};
      d[this.n] = d[this.n] || { items: [], manual: [] };
      d[this.n].manual.push(r);
      this.renderHide();
      this.schedule();
    }, { once: true });
  },

  async check() {
    const [f] = await pickFiles(ACCEPT_DOCS);
    if (!f) return;
    const r = await run('Buscando la marca invisible…', async () => {
      const info = await uploadFile(f);
      try { return await api('wm/check', { id: info.id }); } finally { api('close', { id: info.id }).catch(() => {}); }
    });
    if (!r) return;
    const body = r.found.length ? h('div', {}, r.found.map(x => h('div', { class: 'sig-result' },
      h('div', {}, h('b', { class: 'ok' }, `✔ Marca encontrada: ${x.ref}`), x.page > 1 ? ` (página ${x.page})` : ''),
      x.record ? h('div', { class: 'kv' },
        h('b', {}, 'Entregado a'), h('span', {}, x.record.destinatario || '—'),
        h('b', {}, 'Finalidad'), h('span', {}, x.record.finalidad || '—'),
        h('b', {}, 'Fecha'), h('span', {}, x.record.fecha),
        h('b', {}, 'Texto'), h('span', {}, x.record.texto || '—'),
        h('b', {}, 'Archivo'), h('span', {}, x.record.archivo || '—'))
        : h('p', { class: 'muted' }, 'Esta referencia no está en el historial de este equipo (quizá se marcó en otro).'))))
      : h('p', {}, 'No se ha encontrado ninguna marca invisible de DocGuard. Puede que no la tenga, o que la imagen se haya recortado, girado o regenerado por completo.');
    modal({ title: 'Comprobar marca invisible', body, actions: [{ label: 'Cerrar', primary: true }] });
  },
  async registry() {
    const r = await run('Cargando…', () => api('wm/registry'));
    if (!r) return;
    const body = r.items.length ? h('table', { class: 'reg' },
      h('tr', {}, h('th', {}, 'Fecha'), h('th', {}, 'Ref.'), h('th', {}, 'Entregado a'), h('th', {}, 'Finalidad'), h('th', {}, 'Archivo')),
      r.items.map(x => h('tr', {}, h('td', {}, x.fecha), h('td', {}, x.ref), h('td', {}, x.destinatario || '—'),
        h('td', {}, x.finalidad || '—'), h('td', {}, x.archivo))))
      : h('p', {}, 'Todavía no has entregado documentos con marca de rastreo o QR.');
    modal({ title: 'Historial de entregas', body, actions: [{ label: 'Cerrar', primary: true }], wide: true });
  },
  settings() {
    return { ...this.params(), fmt: $('input[name=wmfmt]:checked', this.root).value, width: this.k('width').value, height: this.k('height').value };
  },
  async loadPresets() {
    try { this.presets = (await api('presets')).presets; } catch (e) { this.presets = {}; }
    const sel = this.k('preset');
    const cur = sel.value;
    sel.innerHTML = '';
    sel.append(h('option', { value: '' }, '—'), ...Object.keys(this.presets).sort().map(n => h('option', { value: n }, n)));
    sel.value = cur in this.presets ? cur : '';
  },
  applyPreset(name) {
    const p = this.presets[name];
    if (!p) return;
    for (const k of ['text', 'angle', 'size', 'gap_x', 'gap_y', 'opacity', 'width', 'height']) if (p[k] != null) this.k(k).value = p[k];
    if (p.color) this.k('color').value = Array.isArray(p.color) ? '#' + p.color.map(c => (+c).toString(16).padStart(2, '0')).join('') : p.color;
    this.k('hardened').checked = p.hardened !== false;
    if (p.level) this.k('level').value = p.level;
    for (const k of ['strike', 'mark']) if (p[k] != null) this.k(k).checked = p[k];
    if (p.qr) {
      this.k('qr').checked = !!p.qr.enabled;
      $('[data-role=qr]', this.root).hidden = !p.qr.enabled;
      this.k('qr_recipient').value = p.qr.recipient || '';
      this.k('qr_purpose').value = p.qr.purpose || '';
      if (p.qr.size) this.k('qr_size').value = p.qr.size;
      if (p.qr.pos) this.k('qr_pos').value = p.qr.pos;
      if (p.qr.mode) { this.k('qr_mode').value = p.qr.mode; this.k('qr_mode').dispatchEvent(new Event('change')); }
      if (p.qr.base_url) this.k('qr_base').value = p.qr.base_url;
    }
    const f = $(`input[name=wmfmt][value=${(p.fmt || 'pdf').toLowerCase()}]`, this.root);
    if (f) f.checked = true;
    this.outputs();
    this.preview();
  },
  async savePreset() {
    const name = await ask('Guardar plantilla', 'Nombre de la plantilla', this.k('preset').value);
    if (!name) return;
    this.presets[name] = this.settings();
    await run('Guardando…', () => api('presets/save', { presets: this.presets }));
    await this.loadPresets();
    this.k('preset').value = name;
  },
  async deletePreset() {
    const name = this.k('preset').value;
    if (!name || !(await confirmBox('Borrar plantilla', `¿Borrar la plantilla «${name}»?`, 'Borrar'))) return;
    delete this.presets[name];
    await api('presets/save', { presets: this.presets });
    this.loadPresets();
  },
};
