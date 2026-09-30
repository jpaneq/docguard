'use strict';
// Herramienta Firma digital (archivo .p12/.pfx y DNIe).

/* ======================================================================
   FIRMA DIGITAL
   ====================================================================== */

const Sign = {
  init() {
    this.root = $('#tool-sign');
    this.viewer = new ContViewer($('.viewer-host', this.root), { keepOverlays: true, firstClickActivates: false });
    this.viewer.onrender = () => this.draw();
    this.viewer.on('mousedown', e => this.down(e));
    makeResizable($('.props', this.root), 'left', 'sign', 260, 620);
    this.rect = null; this.p12 = null;
    dropTarget(this.viewer.el, f => this.openFile(f[0]));
    const act = (a, f) => { $(`[data-act=${a}]`, this.root).onclick = f; };
    const k = n => $(`[data-k=${n}]`, this.root);
    this.k = k;
    act('open', async () => { const [f] = await pickFiles(ACCEPT_PDF); if (f) this.openFile(f); });
    act('cert', () => this.pickCert());
    act('certinfo', () => this.certInfo());
    act('newsig', async () => { const id = await Sigs.create(); if (id) this.fillSigs(id); });
    act('sign', () => this.sign('save'));
    act('signnext', () => this.sign('next'));
    act('signmail', () => this.sign('mail'));
    act('verify', () => this.verify());
    act('prepfields', () => this.togglePrep());
    this.fields = []; this.field = null; this.prep = null;
    // sello de tiempo y validación: se recuerda lo último que se eligió
    try {
      const t = localStorage.getItem('dg_sign_tsa');
      if (t !== null && [...k('tsa').options].some(o => o.value === t)) k('tsa').value = t;
      k('tsa_custom').value = localStorage.getItem('dg_sign_tsa_custom') || '';
      k('ltv').checked = localStorage.getItem('dg_sign_ltv') === '1';
    } catch (e) { /* sin almacenamiento */ }
    k('tsa_custom').hidden = k('tsa').value !== 'custom';
    const keep = () => { try { localStorage.setItem('dg_sign_tsa', k('tsa').value); localStorage.setItem('dg_sign_tsa_custom', k('tsa_custom').value); localStorage.setItem('dg_sign_ltv', k('ltv').checked ? '1' : '0'); } catch (e) { /* sin almacenamiento */ } };
    k('tsa').onchange = () => { k('tsa_custom').hidden = k('tsa').value !== 'custom'; keep(); };
    k('tsa_custom').onchange = keep;
    k('ltv').onchange = keep;
    this.source = 'file';
    $$('[data-src]', this.root).forEach(b => b.onclick = () => this.setSource(b.dataset.src));
    k('margin').onchange = () => { this.draw(); document.dispatchEvent(new Event('signer-changed')); };
    k('module').onchange = () => { k('module_custom').hidden = k('module').value !== 'custom'; };
    act('p11list', () => this.listCards());
    act('p11login', () => this.login());
    this.card = { state: 'off' };
    k('p11cert').onchange = () => { if (this.card.state === 'ok') this.setCard('found', this.card.text); };
    setInterval(() => this.poll(), 4000);
    k('visible').onchange = () => this.draw();
    document.addEventListener('sigs-changed', () => this.fillSigs());
  },
  /** Origen del certificado: 'file' (.p12/.pfx) o 'card' (DNIe/tarjeta). Lo comparte el modo rápido. */
  setSource(src) {
    this.source = src;
    $$('[data-src]', this.root).forEach(x => x.classList.toggle('on', x.dataset.src === src));
    $$('[data-pane]', this.root).forEach(p => { p.hidden = p.dataset.pane !== src; });
    if (src === 'card' && !this.modulesLoaded) this._modules = this.loadModules();
    document.dispatchEvent(new Event('signer-changed'));
  },
  async pickCert() {
    const [f] = await pickFiles('');
    if (!f) return false;
    this.p12 = await fileToB64(f);
    this.certName = f.name;
    this.certSubject = '';
    $('.cert-name', this.root).textContent = f.name;
    $('.cert-info', this.root).innerHTML = '';
    document.dispatchEvent(new Event('signer-changed'));
    return true;
  },
  /** Detecta el DNIe (o tarjeta) desde otra herramienta. */
  async useCard() {
    this.setSource('card');
    await this._modules;
    if (this.module()) await this.listCards();
  },
  /** Nombre del titular si ya se conoce (para la vista previa). */
  signerHint() {
    if (this.source === 'card') return this.card.state === 'ok' ? this.card.text : '';
    return this.certSubject || '';
  },
  /** Credenciales para firmar. Pide siempre el PIN o la contraseña (no se guardan). */
  async credential() {
    if (this.source === 'card') {
      if (!this.k('p11cert').value) await this.useCard();
      const c = this.k('p11cert').value;
      if (!c) { toast('No se detecta el DNIe. Insértalo en el lector (ver «Firma digital» para instalar el módulo).', 'err', [], 8000); return null; }
      const pin = await ask('PIN del DNIe', 'PIN de la tarjeta (se bloquea tras 3 intentos fallidos; no se guarda)', '', { password: true });
      if (!pin) return null;
      const { token, serial, id } = JSON.parse(c);
      return { source: 'card', module: this.module(), token, serial, cert_id: id, pin };
    }
    if (!this.p12 && !(await this.pickCert())) return null;
    const pw = await ask('Contraseña del certificado', `Contraseña de ${this.certName || 'tu certificado'} (no se guarda)`, '', { password: true });
    if (pw === null) return null;
    return { source: 'file', p12: this.p12, password: pw };
  },
  async loadModules() {
    this.modulesLoaded = true;
    const r = await run('Buscando módulos…', () => api('p11/modules'));
    const s = this.k('module');
    s.innerHTML = '';
    for (const m of r?.modules || []) s.append(h('option', { value: m }, m.split(/[\\/]/).pop() + ' — ' + m));
    s.append(h('option', { value: 'custom' }, 'Otro (indicar ruta)…'));
    if (!r?.modules.length) {
      s.value = 'custom';
      this.k('module_custom').hidden = false;
      toast('No se ha encontrado el módulo del DNIe ni OpenSC. Instálalo (ver ayuda) o indica su ruta.', 'err', [], 9000);
    }
  },
  module() { return this.k('module').value === 'custom' ? this.k('module_custom').value.trim() : this.k('module').value; },
  /** Indicador del DNIe: off (gris), found (ámbar, falta PIN), ok (verde, conectado). */
  setCard(state, text) {
    this.card = { state, text };
    const labels = { off: 'Sin tarjeta', found: 'Tarjeta detectada — introduce el PIN', ok: 'DNIe conectado' };
    for (const el of $$('.card-status')) {
      el.className = el.className.replace(/\b(off|found|ok)\b/g, '').trim() + ' ' + state;
      const t = el.querySelector('.txt');
      if (el.classList.contains('nav-card')) {
        el.hidden = state === 'off';
        t.textContent = state === 'ok' ? `DNIe conectado · ${text}` : 'Tarjeta detectada';
      } else t.textContent = state === 'ok' ? `✔ DNIe conectado correctamente · ${text}` : (text && state === 'found' ? `${labels.found} (${text})` : labels[state]);
    }
  },
  async poll() {
    if (this.source !== 'card' && this.card.state === 'off') return;
    const module = this.module();
    if (!module || this.polling) return;
    this.polling = true;
    try {
      const r = await api('p11/list', { module });
      const present = r.tokens.some(t => t.certs.length);
      const serials = r.tokens.filter(t => t.certs.length).map(t => t.serial).join();
      const changed = present && this.cardSerials !== undefined && serials !== this.cardSerials;
      this.cardSerials = serials;
      if (!present && this.card.state !== 'off') {
        this.setCard('off');
        this.k('pin').value = '';
        toast('Se ha retirado la tarjeta.', '');
      } else if (present && (this.card.state === 'off' || changed)) {
        // otra tarjeta (p. ej. el DNIe del siguiente firmante): sus certificados y PIN nuevo
        this.fillCerts(r.tokens);
        this.k('pin').value = '';
        this.setCard('found', r.tokens[0].token);
        const who = r.tokens.find(t => t.certs.length)?.certs[0]?.subject;
        if (changed && who) toast(`Tarjeta detectada: ${who}. Escribe su PIN.`, '');
      }
    } catch (e) { /* lector no disponible: se ignora en el sondeo */ } finally { this.polling = false; }
  },
  fillCerts(tokens) {
    const s = this.k('p11cert');
    const cur = s.value;
    s.innerHTML = '';
    for (const t of tokens) for (const c of t.certs) {
      s.append(h('option', { value: JSON.stringify({ token: t.token, serial: t.serial, id: c.id }) },
        `${c.signing ? '✍ ' : ''}${c.subject} · ${c.label} (${t.token}, caduca ${c.valid_to})`));
    }
    if ([...s.options].some(o => o.value === cur)) s.value = cur;
    return s.options.length;
  },
  async login() {
    const c = this.k('p11cert').value;
    if (!c) return toast('Detecta primero la tarjeta.', 'err');
    if (!this.k('pin').value) return toast('Escribe el PIN.', 'err');
    const { token, serial, id } = JSON.parse(c);
    const r = await run('Verificando el PIN…', () => api('p11/login', { module: this.module(), token, serial, cert_id: id, pin: this.k('pin').value }));
    if (!r) { this.k('pin').value = ''; return; }
    this.setCard('ok', r.subject);
    toast(`DNIe conectado: ${r.subject}`, 'ok');
  },
  async listCards() {
    const module = this.module();
    if (!module) return toast('Indica el módulo PKCS#11.', 'err');
    const r = await run('Leyendo la tarjeta…', () => api('p11/list', { module }));
    if (!r) return;
    if (!this.fillCerts(r.tokens)) {
      this.k('p11cert').append(h('option', { value: '' }, 'No hay tarjeta o certificados'));
      this.setCard('off');
      toast('No se ha encontrado ninguna tarjeta con certificados. ¿Está bien insertada en el lector?', 'err');
    } else {
      if (this.card.state !== 'ok') this.setCard('found', r.tokens[0].token);
      toast(`Tarjeta detectada: ${r.tokens.map(t => t.token).join(', ')}`, 'ok');
    }
  },
  fillSigs(select) {
    const s = this.k('sig');
    const cur = select ?? s.value;
    s.innerHTML = '';
    s.append(h('option', { value: '' }, 'Sin imagen'), ...Sigs.items.map((it, i) => h('option', { value: it.id }, `Firma ${i + 1}`)));
    s.value = Sigs.items.some(i => i.id === cur) ? cur : '';
  },
  async openFile(f) { const info = await run('Abriendo…', () => uploadFile(f)); if (info) this.loadInfo(info); },
  loadInfo(info) {
    if (!info.pages.length) return toast('Solo se pueden firmar PDFs o imágenes (se convierten a PDF).', 'err');
    if (info.encrypted) return toast('Quita primero la contraseña del PDF.', 'err');
    this.info = info; this.rect = null;
    setCurrent(info);
    $('.doc-name', this.root).textContent = info.name;
    this.viewer.load(info);
    this.listSignatures(info.id);
    this.loadFields();
  },
  draw() {
    const v = this.viewer;
    if (!this.info) return;
    (v.pages || []).forEach((p, i) => { p.ov.replaceChildren(); p.ov.classList.add('draw'); });
    // recuadros preparados (y los que se están preparando)
    for (const f of [...this.fields, ...(this.prep || []).map(p => ({ ...p, pending: true }))]) {
      const ov = v.pageOv(f.page);
      if (!ov) continue;
      const d = v.box(f.rect, 'sigfield' + (f.signed ? ' signed' : '') + (this.field === f.name ? ' cur' : ''), ov);
      d.append(h('span', { class: 'lbl' }, (f.signed ? '✔ ' : '') + f.name + (f.pending ? ' (sin crear)' : '')));
      if (!f.pending && !f.signed) d.addEventListener('mousedown', e => { e.stopPropagation(); this.pickField(f.name); });
    }
    if (this.rect && this.k('visible').checked && !this.k('margin').checked) {
      const ov = v.pageOv(this.rect.n);
      if (ov) v.box(this.rect.r, 'sigbox', ov);
    }
  },
  async down(e) {
    if (e.button !== 0 || !this.info) return;
    if (this.prep) {
      const d = await this.viewer.drag(e);
      if (!d.moved) return;
      const name = await ask('Recuadro de firma', 'Nombre del firmante (o su papel)', `Firmante ${this.fields.length + this.prep.length + 1}`);
      if (name) { this.prep.push({ name, page: this.viewer.n, rect: d.rect }); this.renderFields(); this.draw(); }
      return;
    }
    if (!this.k('visible').checked || this.k('margin').checked) return;
    const d = await this.viewer.drag(e);
    if (d.moved) { this.rect = { n: this.viewer.n, r: d.rect }; this.field = null; this.renderFields(); this.draw(); }
  },

  /* ---- recuadros de firma para varios firmantes ---- */
  async loadFields() {
    if (!this.info) return;
    const r = await api('sign/fields', { id: this.info.id }).catch(() => ({ fields: [] }));
    this.fields = r.fields;
    // con firmas ya hechas no se puede añadir el margen (las invalidaría)
    const signedAny = this.fields.some(f => f.signed);
    this.k('margin').disabled = signedAny;
    if (signedAny) this.k('margin').checked = false;
    const pending = this.fields.filter(f => !f.signed);
    if (!this.fields.some(f => f.name === this.field && !f.signed)) this.field = pending[0]?.name || null;
    if (this.field) this.rect = null;
    this.renderFields();
    this.draw();
  },
  pickField(name) { this.field = name; this.rect = null; this.renderFields(); this.draw(); },
  renderFields() {
    const box = $('.field-list', this.root);
    box.innerHTML = '';
    if (this.prep) {
      box.append(h('p', {}, 'Arrastra en la página el recuadro de cada firmante.'),
        ...this.prep.map((p, i) => h('div', { class: 'field-row' }, `✎ ${p.name} · pág. ${p.page + 1}`,
          h('button', { onclick: () => { this.prep.splice(i, 1); this.renderFields(); this.draw(); } }, '✕'))),
        h('div', { class: 'row' },
          h('button', { class: 'primary', disabled: !this.prep.length, onclick: () => this.createFields() }, `Crear ${this.prep.length} recuadro(s)`),
          h('button', { onclick: () => this.togglePrep() }, 'Cancelar')));
      return;
    }
    if (!this.fields.length) { box.append(h('span', { class: 'muted' }, 'Sin recuadros preparados: la firma irá donde dibujes.')); return; }
    for (const f of this.fields) {
      box.append(h('div', { class: 'field-row' + (this.field === f.name ? ' cur' : '') },
        f.signed ? h('b', { class: 'ok' }, '✔') : h('input', { type: 'radio', name: 'sigfield', checked: this.field === f.name, onchange: () => this.pickField(f.name) }),
        h('span', {}, `${f.name} · pág. ${f.page + 1}`), f.signed ? h('small', {}, 'firmado') : null));
    }
    const left = this.fields.filter(f => !f.signed).length;
    box.append(h('small', {}, left ? `Faltan ${left} firma(s). Firma ahora: ${this.field || '—'}.` : 'Todas las firmas están completas.'));
  },
  togglePrep() {
    if (!this.info) return toast('Abre primero un PDF.', 'err');
    this.prep = this.prep ? null : [];
    $('[data-act=prepfields]', this.root).textContent = this.prep ? 'Terminar de preparar' : 'Preparar recuadros para varios firmantes…';
    this.renderFields();
    this.draw();
  },
  async createFields() {
    const specs = this.prep.map(p => ({ name: p.name, page: p.page, rect: p.rect }));
    const r = await run('Creando recuadros…', () => api('sign/fields/add', { id: this.info.id, fields: specs }));
    if (!r) return;
    this.prep = null;
    $('[data-act=prepfields]', this.root).textContent = 'Preparar recuadros para varios firmantes…';
    this.loadInfo(r.info);
    toast('Recuadros creados. Cada firmante elige su recuadro y firma; puedes guardar esta versión y enviarla.', 'ok', [{ label: 'Guardar…', fn: () => saveResult({ rid: r.rid, files: [{ name: r.info.name, size: r.info.size }] }) }], 9000);
  },
  async certInfo() {
    if (!this.p12) return toast('Elige primero el archivo del certificado.', 'err');
    const r = await run('Comprobando…', () => api('certinfo', { p12: this.p12, password: this.k('password').value }));
    if (!r) return;
    this.certSubject = r.subject.replace(/^Common Name:\s*/, '').split(', Serial')[0];
    document.dispatchEvent(new Event('signer-changed'));
    $('.cert-info', this.root).replaceChildren(h('div', { class: 'kv' },
      h('b', {}, 'Titular'), h('span', {}, r.subject), h('b', {}, 'Emisor'), h('span', {}, r.issuer),
      h('b', {}, 'Válido'), h('span', {}, `${r.valid_from} – ${r.valid_to}`)));
  },
  async sign(mode = 'save') {
    if (!this.info) return toast('Abre primero un PDF.', 'err');
    let cred;
    if (this.source === 'card') {
      const c = this.k('p11cert').value;
      if (!c) return toast('Detecta la tarjeta y elige un certificado.', 'err');
      if (!this.k('pin').value) return toast('Escribe el PIN de la tarjeta.', 'err');
      const { token, serial, id } = JSON.parse(c);
      cred = { source: 'card', module: this.module(), token, serial, cert_id: id, pin: this.k('pin').value };
    } else {
      if (!this.p12) return toast('Elige el certificado (.p12 / .pfx).', 'err');
      cred = { source: 'file', p12: this.p12, password: this.k('password').value };
    }
    const margin = this.k('margin').checked;  // tiene prioridad sobre un recuadro preparado (queda libre para su firmante)
    const visible = this.k('visible').checked && !margin;
    if (visible && !this.rect && !this.field) return toast('Arrastra en la página el recuadro donde irá la firma, elige un recuadro preparado, marca «En un margen añadido abajo» o desmarca «Firma visible».', 'err');
    const tsa = this.k('tsa').value === 'custom' ? this.k('tsa_custom').value.trim() : this.k('tsa').value;
    const res = await run('Firmando…', () => api('sign', {
      id: this.info.id, ...cred, margin,
      n: margin ? this.viewer.n : (visible && this.rect ? this.rect.n : null), rect: visible && this.rect && !this.field ? this.rect.r : null,
      field: margin ? null : this.field || null, sig: visible ? this.k('sig').value : '',
      reason: this.k('reason').value, location: this.k('location').value, contact: this.k('contact').value, tsa,
      ltv: this.k('ltv').checked,
    }));
    if (this.source === 'card' && !res && this.card.state === 'ok') this.setCard('found', this.card.text);
    if (!res) return;
    if (res.notes?.length && mode !== 'save') toast(res.notes.join(' · '), '', [], 8000);
    if (mode === 'next') return this.nextSigner(res);
    if (mode === 'mail') return this.mailResult(res);
    saveResult(res);
    this.nextSignerDoc(res, false);
  },
  /** Deja abierto el documento ya firmado para que firme otra persona (sin invalidar la firma anterior). */
  async nextSigner(res) {
    await this.nextSignerDoc(res, true);
    // se borran las credenciales del firmante anterior
    this.p12 = null;
    this.certName = this.certSubject = '';
    $('.cert-name', this.root).textContent = 'Ninguno';
    $('.cert-info', this.root).innerHTML = '';
    this.k('password').value = '';
    this.k('pin').value = '';
    if (this.card.state === 'ok') this.setCard('found', this.card.text);
    modal({
      title: 'Firma añadida',
      body: h('div', {}, h('p', {}, 'El documento ya tiene tu firma. Ahora puede firmar la siguiente persona en este mismo equipo:'),
        h('ol', { class: 'help' },
          h('li', {}, 'Elige su certificado (.p12 / .pfx) o que inserte su DNIe y escriba su PIN.'),
          h('li', {}, 'Dibuja el recuadro de su firma (en otro sitio o página).'),
          h('li', {}, 'Pulsa «Firmar y guardar» o vuelve a pasar al siguiente.'))),
      actions: [{ label: 'Guardar ahora esta versión…', fn: () => saveResult(res) }, { label: 'Entendido', primary: true }],
    });
  },
  async nextSignerDoc(res, open) {
    const info = await api('open_result', { rid: res.rid }).catch(() => null);
    if (!info) return;
    if (open) { this.loadInfo(info); this.rect = null; this.draw(); }
    else if (this.fields.length) { this.loadInfo(info); }
    this.listSignatures(info.id);
    this.loadFields();
  },
  async mailResult(res) {
    if (window.pywebview?.api?.save_result) {
      const paths = await window.pywebview.api.save_result(res.rid);
      if (!paths) return toast('No se ha guardado.', '');
      const how = await window.pywebview.api.email(paths[0]);
      toast(how === 'reveal' ? 'Guardado. No se ha encontrado Mail/Outlook: adjunta el archivo que se muestra en la carpeta.' : 'Guardado y adjuntado a un correo nuevo.', 'ok', [], 7000);
    } else {
      await saveResult(res);
      toast('Descargado. Adjúntalo a un correo para enviarlo al siguiente firmante.', '', [], 6000);
    }
    this.nextSignerDoc(res, false);
  },
  async listSignatures(id = this.info?.id) {
    const box = $('.sig-list', this.root);
    if (!id) { box.textContent = '—'; return; }
    try {
      const r = await api('verify', { id });
      box.replaceChildren(...(r.signatures.length ? r.signatures.map((s, i) => h('div', { class: 'sig-result' },
        h('b', { class: s.intact && s.valid ? 'ok' : 'bad' }, `${s.intact && s.valid ? '✔' : '✘'} ${i + 1}. `), s.signer.replace('Common Name: ', ''),
        h('div', { class: 'muted' }, s.time))) : [h('span', {}, 'Todavía no hay firmas digitales.')]));
    } catch (e) { box.textContent = '—'; }
  },
  async verify() {
    if (!this.info) return toast('Abre primero un PDF.', 'err');
    const r = await run('Verificando…', () => api('verify', { id: this.info.id }));
    if (!r) return;
    const body = h('div', {}, r.signatures.length ? r.signatures.map(s => h('div', { class: 'sig-result' },
      h('div', {}, h('b', {}, s.field), ' — ', s.signer),
      h('div', { class: 'muted' }, `Emisor: ${s.issuer}${s.time ? ' · ' + s.time : ''}${s.reason ? ' · Motivo: ' + s.reason : ''}`),
      h('div', {}, s.intact && s.valid ? h('b', { class: 'ok' }, '✔ Firma íntegra: el documento no ha cambiado desde la firma')
        : h('b', { class: 'bad' }, '✘ Firma NO válida o documento alterado')),
      h('div', { class: 'muted' }, s.trusted ? 'Certificado de confianza.' : 'Certificado no verificado contra una autoridad de confianza de este equipo (normal con certificados propios o si falta la cadena).'),
      s.modified_after ? h('div', { class: 'muted' }, 'Hay cambios posteriores a esta firma (otras firmas o anotaciones).') : null,
    )) : h('p', {}, 'Este PDF no tiene firmas digitales.'));
    modal({ title: 'Firmas del documento', body, actions: [{ label: 'Cerrar', primary: true }] });
  },
};
