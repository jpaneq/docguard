'use strict';
// Herramienta Marca de agua (protección, QR, ocultar datos de DNI/pasaporte).

/* ======================================================================
   MARCA DE AGUA
   ====================================================================== */

const SIG_DEFAULT = [0.6, 0.86, 0.97, 0.97];  // firma dentro del documento: abajo a la derecha

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
    for (const k of ['robust', 'fingerprint', 'labels', 'stamp', 'notice', 'maxside', 'photo']) this.k(k).addEventListener('change', () => { this.photoWarned = false; this.schedule(); });
    $('[data-act=quick]', this.root).onclick = () => this.quick();
    $('[data-act=toscan]', this.root).onclick = () => {
      const cur = this.files.current;
      if (!cur) return toast('Abre primero la foto del documento.', 'err');
      showTool('scanner');
      Scanner.items = [];
      Scanner.addInfo(cur);
    };
    for (const [q, t] of [['q_recipient', 'qr_recipient'], ['q_purpose', 'qr_purpose'], ['q_until', 'qr_until'], ['q_password', 'password']]) {
      this.k(q).addEventListener('input', () => { this.k(t).value = this.k(q).value; this.schedule(); });
    }
    $('[data-act=registry]', this.root).onclick = () => this.registry();
    $('[data-act=midni]', this.root).onclick = () => Share.open('midni', this.shareCtx());
    this.initSign();
    new ResizeObserver(() => this.schedule()).observe($('.preview-img', this.root));
    makeResizable($('.side-panel', this.root), 'right', 'wm-side', 260, 620);
    // rueda del ratón sobre la vista previa: pasa a la página siguiente o anterior
    let wheelLock = 0;
    $('.preview-img', this.root).addEventListener('wheel', e => {
      const box = e.currentTarget;
      if (this.pages() < 2 || Date.now() < wheelLock) return;
      const atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 2;
      const atTop = box.scrollTop <= 0;
      if (e.deltaY > 20 && atBottom && this.n < this.pages() - 1) { this.n++; wheelLock = Date.now() + 450; this.preview(); }
      else if (e.deltaY < -20 && atTop && this.n > 0) { this.n--; wheelLock = Date.now() + 450; this.preview(); }
    }, { passive: true });
    this.outputs();
    this.loadPresets();
  },
  loadInfo(info) { this.files.setItems([info]); },
  /** Firma digital de la copia: opciones del modo rápido (se recuerdan en este equipo). */
  initSign() {
    const load = (k, def) => { try { const v = localStorage.getItem('dg_' + k); return v === null ? def : v; } catch (e) { return def; } };
    const save = (k, v) => { try { localStorage.setItem('dg_' + k, v); } catch (e) { /* sin almacenamiento */ } };
    this.k('q_sign').checked = load('q_sign', '0') === '1';
    this.k('q_ltv').checked = load('q_ltv', '1') === '1';
    this.k('q_ack').checked = load('q_ack', '0') === '1';
    for (const k of ['q_tsa', 'q_place']) {
      const v = load(k, null);
      if (v !== null && [...this.k(k).options].some(o => o.value === v)) this.k(k).value = v;
    }
    const sync = () => {
      const src = Sign.source || 'file';
      const band = this.k('q_place').value === 'band';
      $('[data-role=qsign]', this.root).hidden = !this.k('q_sign').checked;
      $('[data-role=qinside]', this.root).hidden = this.k('q_place').value !== 'inside';
      this.k('q_ack').disabled = !band;
      $('[data-role=signhint]', this.root).hidden = !this.k('q_sign').checked;
      $$('[data-qsrc]', this.root).forEach(b => b.classList.toggle('on', b.dataset.qsrc === src));
      $$('[data-qpane]', this.root).forEach(p => { p.hidden = p.dataset.qpane !== src; });
      $('.q-cert', this.root).textContent = Sign.certSubject || Sign.certName || 'Ninguno';
    };
    for (const k of ['q_sign', 'q_ltv', 'q_ack']) this.k(k).addEventListener('change', () => { save(k, this.k(k).checked ? '1' : '0'); sync(); });
    for (const k of ['q_tsa', 'q_place']) this.k(k).addEventListener('change', () => { save(k, this.k(k).value); sync(); this.renderHide(); this.schedule(); });
    $('[data-act=qplace]', this.root).onclick = () => {
      if (!this.files.current) return toast('Abre primero el documento.', 'err');
      this.placing = true;
      this.hov.classList.add('placing');
      toast('Arrastra sobre el documento el recuadro donde irá la firma.', '', [], 5000);
    };
    $$('[data-qsrc]', this.root).forEach(b => b.onclick = () => Sign.setSource(b.dataset.qsrc));
    $('[data-act=qcert]', this.root).onclick = () => Sign.pickCert();
    $('[data-act=qcard]', this.root).onclick = () => Sign.useCard();
    document.addEventListener('signer-changed', () => { sync(); if (this.k('q_sign').checked) this.schedule(); });
    sync();
  },
  shareCtx(res) {
    return res ? { who: res.who, purpose: res.purpose, ref: res.refs?.[0], signed: res.signed, ack: res.ack, password: res.password, until: res.until }
      : { who: (this.k('q_recipient').value || this.k('qr_recipient').value).trim(), purpose: (this.k('q_purpose').value || this.k('qr_purpose').value).trim(),
        signed: this.k('q_sign').checked, password: !!this.k('password').value,
        until: (v => v ? v.split('-').reverse().join('/') : '')(this.k('q_until').value || this.k('qr_until').value),
        ack: this.k('q_sign').checked && this.k('q_place').value === 'band' && this.k('q_ack').checked };
  },
  k(name) { return $(`[data-k=${name}]`, this.root); },
  pages() { return Math.max(1, this.files.current?.pages.length || 1); },
  outputs() { $$('input[type=range]', this.root).forEach(r => { r.parentElement.querySelector('output').textContent = r.value; }); },
  params() {
    const p = {};
    for (const k of ['text', 'angle', 'size', 'gap_x', 'gap_y', 'opacity', 'color', 'level']) p[k] = this.k(k).value;
    for (const k of ['hardened', 'strike', 'mark']) p[k] = this.k(k).checked;
    p.autohide = this.k('autohide').checked;
    p.password = this.k('password').value;
    for (const k of ['robust', 'fingerprint', 'labels', 'stamp', 'notice']) p[k] = this.k(k).checked;
    p.maxside = this.k('maxside').value;
    p.photo = this.k('photo').value;
    const cur = this.files.current;
    p.hide_page = cur ? this.activeRects(cur.id, this.n).map(x => ({ r: x.r, k: x.kind })) : [];
    p.hide = {};
    for (const [id, pages] of Object.entries(this.hideData)) {
      p.hide[id] = {};
      for (const n of Object.keys(pages)) p.hide[id][n] = this.activeRects(id, +n).map(x => ({ r: x.r, k: x.kind }));
    }
    p.qr = { enabled: this.k('qr').checked, recipient: this.k('qr_recipient').value, purpose: this.k('qr_purpose').value, until: this.k('qr_until').value,
      size: +this.k('qr_size').value, pos: this.k('qr_pos').value, mode: this.k('qr_mode').value, base_url: this.k('qr_base').value };
    // vista previa de la franja de firma que irá debajo del documento
    if (this.k('q_sign').checked && this.k('q_place').value === 'band') p.sign_band = { name: Sign.signerHint(), ack: this.k('q_ack').checked };
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
      this.band = parseFloat(blob.headers?.get('X-Band') || '0') || 0;  // parte de abajo: franja de firma
      if (blob.headers?.get('X-Photo') === '0' && !this.photoWarned) {
        this.photoWarned = true;
        toast('No se ha encontrado la foto del titular: tápala arrastrando un recuadro sobre ella en la vista previa.', 'err', [], 8000);
      }
      this.url = URL.createObjectURL(blob);
      this.img.src = this.url;
    } catch (e) { toast(e.message, 'err'); }
  },
  async export() {
    if (!this.files.items.length) return toast('Abre primero algún documento.', 'err');
    const fmt = $('input[name=wmfmt]:checked', this.root).value;
    const w = this.k('width').value.trim(), hh = this.k('height').value.trim();
    if ((w && !(+w > 0)) || (hh && !(+hh > 0))) return toast('El tamaño debe ser un número de píxeles.', 'err');
    let sign = null;
    if (this.k('q_sign').checked) {
      if (fmt !== 'pdf') return toast('La firma digital solo se puede añadir al guardar como PDF.', 'err');
      // el PIN o la contraseña se piden antes de procesar nada (cancelar no deja nada a medias)
      const cred = await Sign.credential();
      if (!cred) return;
      const place = this.k('q_place').value;
      sign = { ...cred, tsa: this.k('q_tsa').value, ltv: this.k('q_ltv').checked, place,
        ack: place === 'band' && this.k('q_ack').checked, page: this.sigPos?.n ?? 0, rect: this.sigPos?.r || SIG_DEFAULT };
    }
    const res = await run(sign ? 'Protegiendo y firmando…' : 'Aplicando la marca de agua…', () => api('wm/export', {
      ids: this.files.ids, params: this.params(), fmt, width: w || null, height: hh || null, sign, pdfa: this.k('pdfa').checked,
    }));
    if (!res) return;
    const ctx = this.shareCtx(res);
    const actions = [{ label: 'Texto para el correo…', fn: () => Share.open('copia', ctx) }];
    if (window.pywebview?.api?.email) actions.unshift({ label: 'Enviar por correo…', fn: paths => this.mail(paths, ctx) });
    saveResult(res, [], res.refs?.length ? actions : []);
  },
  /** Correo nuevo con la copia adjunta; el texto de condiciones queda copiado para pegarlo. */
  async mail(paths, ctx) {
    if (!paths?.length) return;
    const t = Share.texts(ctx).copia;
    const copied = await copyText(`${t.body}`);
    const how = await window.pywebview.api.email(paths[0]);
    toast((how === 'reveal' ? 'No se ha encontrado Mail/Outlook: adjunta el archivo que se muestra en la carpeta.' : 'Correo nuevo con la copia adjunta.')
      + (copied ? ' El texto con las condiciones está copiado: pégalo en el mensaje (⌘V / Ctrl+V).' : ''), 'ok', [], 10000);
  },
  /** Modo rápido: configuración recomendada para DNI/pasaporte y guardar en un paso. */
  async quick() {
    if (!this.files.items.length) return toast('Abre o arrastra primero el DNI o pasaporte.', 'err');
    const who = this.k('q_recipient').value.trim();
    if (!who) { this.k('q_recipient').focus(); return toast('Indica para quién es la copia.', 'err'); }
    this.k('text').value = 'Solo para {destinatario} – {fecha}' + (this.k('q_until').value ? ' – hasta {caducidad}' : '');
    this.k('qr_until').value = this.k('q_until').value;
    this.k('level').value = 'reforzada';
    for (const k of ['strike', 'mark', 'autohide', 'qr', 'robust', 'fingerprint', 'labels', 'stamp', 'notice']) this.k(k).checked = true;
    this.k('qr_pos').value = 'auto';
    if (!this.k('maxside').value) this.k('maxside').value = '1600';
    $('[data-role=qr]', this.root).hidden = false;
    this.k('qr_recipient').value = who;
    this.k('qr_purpose').value = this.k('q_purpose').value.trim();
    this.k('password').value = this.k('q_password').value;
    $('input[name=wmfmt][value=pdf]', this.root).checked = true;
    this.outputs();
    await this.preview();
    // se asegura de que todas las páginas tengan revisados sus datos ocultos
    await this.export();
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
    if (this.k('autohide').checked) pg.items.forEach((it, ii) => { if (it.on) it.rects.forEach((r, ri) => out.push({ r, key: [ii, ri], kind: it.kind })); });
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
      d.addEventListener('mousedown', e => { if (this.placing) return; e.stopPropagation(); this.hsel = a.key; this.renderHide(); });
      if (isSel) d.append(h('div', { class: 'x', title: 'Quitar esta zona', onmousedown: e => { e.stopPropagation(); this.removeHide(a.key); } }, '✕'));
      this.hov.append(d);
    }
    // posición de la firma dentro del documento
    if (this.k('q_sign').checked && this.k('q_place').value === 'inside' && this.n === (this.sigPos?.n ?? 0)) {
      const [x0, y0, x1, y1] = this.sigPos?.r || SIG_DEFAULT;
      this.hov.append(h('div', { class: 'sigpos' + (this.sigPos ? '' : ' default'), title: 'Aquí irá la firma (usa «Colocar la firma» para moverla)',
        style: `left:${x0 * 100}%;top:${y0 * 100}%;width:${(x1 - x0) * 100}%;height:${(y1 - y0) * 100}%` }, '✍ Firma digital'));
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
    Object.assign(this.hov.style, { left: r.left - b.left + box.scrollLeft + 'px', top: r.top - b.top + box.scrollTop + 'px', width: r.width + 'px',
      height: r.height * (1 - (this.band || 0)) + 'px' });
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
      if (this.placing) {  // se está colocando la firma, no una zona oculta
        this.placing = false;
        this.hov.classList.remove('placing');
        if ((r[2] - r[0]) * R.width >= 6 && (r[3] - r[1]) * R.height >= 6) this.sigPos = { n: this.n, r };
        this.renderHide();
        return;
      }
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
    const info = await run('Abriendo…', () => uploadFile(f));
    if (!info) return;
    const done = () => api('close', { id: info.id }).catch(() => {});
    let r = await run('Analizando la copia…', () => api('wm/check', { id: info.id }));
    if (r?.needs_password) {
      const pw = await ask('Copia protegida con contraseña', 'Contraseña para abrirla (para comprobar sus marcas y firmas)', '', { password: true });
      if (pw) r = (await run('Analizando la copia…', () => api('wm/check', { id: info.id, password: pw }))) || r;
    }
    if (!r) return done();
    this.showCheck(r, info.id, done);  // el documento se cierra al cerrar la ventana (lo usa el informe)
  },
  showCheck(r, id, onclose) {
    const body = h('div', {});
    if (r.needs_password) body.append(h('p', { class: 'muted' }, 'Sin la contraseña solo se ha podido comprobar la huella exacta del archivo.'));
    if (r.found.length) {
      for (const x of r.found) {
        body.append(h('div', { class: 'sig-result' },
          h('div', {}, h('b', { class: 'ok' }, `✔ Copia identificada: ${x.ref}`), x.page > 1 ? ` (página ${x.page})` : ''),
          h('ul', { class: 'help' }, x.methods.map(m => h('li', {}, m.name, m.detail ? h('small', {}, ` · ${m.detail}`) : null))),
          x.record ? h('div', { class: 'kv' },
            h('b', {}, 'Entregado a'), h('span', {}, x.record.destinatario || '—'),
            h('b', {}, 'Finalidad'), h('span', {}, x.record.finalidad || '—'),
            h('b', {}, 'Fecha'), h('span', {}, x.record.fecha),
            x.record.caduca ? h('b', {}, 'Válida hasta') : null,
            x.record.caduca ? h('span', {}, x.record.caduca, x.caducada ? h('b', { class: 'bad' }, ' · CADUCADA') : null) : null,
            h('b', {}, 'Texto'), h('span', {}, x.record.texto || '—'),
            h('b', {}, 'Archivo'), h('span', {}, x.record.archivo || '—'))
            : h('p', { class: 'muted' }, 'Esta referencia no está en el historial de este equipo (quizá se marcó en otro).')));
      }
      if (r.found.some(x => !x.methods.some(m => m.name === 'Marca invisible')))
        body.append(h('p', { class: 'muted' }, 'La marca invisible clásica no está: la copia se ha alterado (quizá con IA), pero se ha podido identificar igualmente.'));
    } else {
      body.append(h('p', {}, 'No se ha podido identificar. Puede que la copia no sea de DocGuard, que sea de otro equipo, o que se haya recortado, girado o regenerado por completo.'));
    }
    if (r.signatures?.length) {
      const who = s => s.signer.replace(/^Common Name:\s*/, '');
      body.append(h('div', { class: 'sig-result' }, h('b', {}, 'Firmas digitales'),
        h('ul', { class: 'help' }, r.signatures.map(s => h('li', {},
          h('b', { class: s.intact && s.valid ? 'ok' : 'bad' }, s.intact && s.valid ? '✔ ' : '✘ '),
          `${s.field}: ${who(s)}${s.time ? ' · ' + s.time : ''}`,
          h('small', {}, s.intact && s.valid ? ' · íntegra: lo firmado no ha cambiado' : ' · NO válida o documento alterado',
            s.modified_after ? ' · después se añadieron otras firmas o datos de validación' : '',
            s.timestamp ? ` · sello de tiempo ${s.timestamp.time}${s.timestamp.by ? ' (' + s.timestamp.by + ')' : ''}` : '',
            s.ltv ? ' · con validación a largo plazo' : ''))))));
    } else if (r.sig_error) body.append(h('p', { class: 'muted' }, `No se han podido leer las firmas: ${r.sig_error}`));
    if (r.hints?.length) body.append(h('div', { class: 'sig-result' }, h('b', { class: 'bad' }, '⚠ Indicios de edición con IA'),
      h('ul', { class: 'help' }, r.hints.map(t => h('li', {}, t)))));
    const report = id && !r.needs_password ? [{ label: 'Guardar informe (PDF)…', fn: async () => {
      const res = await run('Generando el informe…', () => api('wm/report', { id, tsa: 'http://tss.accv.es:8318/tsa' }));
      if (res) saveResult(res);
      return false;
    } }] : [];
    modal({ title: 'Comprobar una copia', body, actions: [...report, { label: 'Cerrar', primary: true }], onclose });
  },
  async registry() {
    const r = await run('Cargando…', () => api('wm/registry'));
    if (!r) return;
    let close;
    const again = () => { close?.(); this.registry(); };
    const b = r.backup;
    const status = h('div', { class: 'reg-backup' },
      b.folder ? h('span', {}, '💾 Copia automática en ', h('b', {}, b.folder), b.last ? ` · última: ${b.last}` : '')
        : h('span', { class: 'muted' }, 'Sin copia automática: si pierdes este equipo, pierdes el historial.'),
      b.error ? h('div', { class: 'bad' }, `⚠ La última copia falló: ${b.error}`) : null,
      b.damaged ? h('div', { class: 'bad' }, `⚠ ${b.damaged}. Puedes recuperarlo con «Importar…» (o desde tu copia automática).`) : null,
      h('div', { class: 'row' },
        h('button', { onclick: () => this.backupFolder(b.folder).then(ok => ok && again()) }, b.folder ? 'Cambiar carpeta…' : 'Copia automática…'),
        b.folder ? h('button', { onclick: async () => { await run('Guardando…', () => api('registry/backup', { folder: '' })); again(); } }, 'Desactivar') : null,
        h('button', { onclick: async () => saveResult(await run('Exportando…', () => api('registry/export'))) }, 'Exportar…'),
        h('button', { onclick: () => this.importRegistry().then(ok => ok && again()) }, 'Importar…')));
    const del = async x => {
      if (!(await confirmBox('Borrar del historial', `¿Borrar la entrega ${x.ref} (${x.destinatario || 'sin destinatario'})? Sin ella no se podrá identificar esa copia.`, 'Borrar'))) return;
      await run('Borrando…', () => api('registry/delete', { ref: x.ref }));
      again();
    };
    const table = r.items.length ? h('table', { class: 'reg' },
      h('tr', {}, h('th', {}, 'Fecha'), h('th', {}, 'Ref.'), h('th', {}, 'Entregado a'), h('th', {}, 'Finalidad'), h('th', {}, 'Archivo'), h('th', {}, 'Firmada'), h('th', {}, '')),
      r.items.map(x => h('tr', {}, h('td', {}, x.fecha), h('td', {}, x.ref), h('td', {}, x.destinatario || '—'),
        h('td', {}, x.finalidad || '—'), h('td', {}, x.archivo),
        h('td', { title: x.firma ? [x.firma.sello && 'con sello de tiempo', x.firma.ltv && 'validación a largo plazo', x.firma.acuse && 'con acuse de recibo'].filter(Boolean).join(', ') : '' },
          x.firma ? '✔ ' + x.firma.por : '—'),
        h('td', {}, h('button', { class: 'mini', title: 'Borrar del historial', onclick: () => del(x) }, '✕')))))
      : h('p', {}, 'Todavía no has entregado documentos con marca de rastreo o QR.');
    close = modal({ title: 'Historial de entregas', body: h('div', {}, status, table), actions: [{ label: 'Cerrar', primary: true }], wide: true });
  },
  /** Carpeta donde se copia el historial cada vez que cambia (iCloud Drive, Google Drive, un USB…). */
  async backupFolder(current) {
    const folder = window.pywebview?.api?.pick_folder ? await window.pywebview.api.pick_folder()
      : await ask('Copia automática del historial', 'Ruta de la carpeta (por ejemplo, una de iCloud Drive o Google Drive)', current || '');
    if (!folder) return false;
    const r = await run('Copiando el historial…', () => api('registry/backup', { folder }));
    if (r) toast(`Historial copiado en ${r.folder}. Se copiará solo cada vez que cambie.`, 'ok', [], 7000);
    return !!r;
  },
  async importRegistry() {
    const [f] = await pickFiles('application/json,.json');
    if (!f) return false;
    const r = await run('Importando…', async () => {
      const info = await uploadFile(f);
      try { return await api('registry/import', { id: info.id }); } finally { api('close', { id: info.id }).catch(() => {}); }
    });
    if (r) toast(`Historial importado: ${r.added} entrada(s) nueva(s) y ${r.merged} unida(s) con las que ya tenías.`, 'ok', [], 7000);
    return !!r;
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
    for (const k of ['strike', 'mark', 'robust', 'fingerprint', 'labels', 'stamp', 'notice']) if (p[k] != null) this.k(k).checked = p[k];
    if (p.maxside != null) this.k('maxside').value = p.maxside;
    if (p.photo != null) this.k('photo').value = p.photo;
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
