'use strict';
// Herramienta Escáner: convierte fotos de documentos en escaneos limpios y los digitaliza.

const Scanner = {
  init() {
    this.root = $('#tool-scanner');
    this.items = [];      // [{info, n, quad, rot, conf}]
    this.cur = -1;
    this.stage = $('.scan-stage', this.root);
    this.img = $('.scan-stage img', this.root);
    this.svg = $('.scan-svg', this.root);
    this.res = $('.scan-result-img img', this.root);
    const act = (a, f) => { $(`[data-act=${a}]`, this.root).onclick = f; };
    act('add', async () => this.add(await pickFiles(ACCEPT_DOCS, true)));
    act('mobile', () => this.mobile());
    act('export', () => this.export());
    act('redetect', () => this.redetect());
    act('full', () => { const it = this.item; if (it) { it.quad = [[0, 0], [1, 0], [1, 1], [0, 1]]; this.drawQuad(); this.schedule(); } });
    act('rotate', () => { const it = this.item; if (it) { it.rot = (it.rot + 90) % 360; this.renderList(); this.schedule(); } });
    for (const k of ['kind', 'mode']) this.k(k).onchange = () => this.schedule();
    this.k('fmt').onchange = () => { const pdf = this.k('fmt').value === 'pdf'; for (const k of ['layout', 'ocr', 'pdfa']) this.k(k).disabled = !pdf; };
    dropTarget(this.root, f => this.add(f));
    this.img.addEventListener('load', () => this.drawQuad());
    new ResizeObserver(() => { this.drawQuad(); this.schedule(); }).observe(this.stage);
    // lupa: al mover una esquina se ve ampliado el punto exacto
    this.lens = h('canvas', { class: 'scan-lens', width: 180, height: 180 });
    this.stage.append(this.lens);
    this.corner = null;  // esquina elegida (se afina con las flechas del teclado)
    document.addEventListener('keydown', e => this.nudge(e));
    this.render();
  },
  k(n) { return $(`[data-k=${n}]`, this.root); },
  get item() { return this.items[this.cur]; },
  loadInfo(info) { this.items = []; this.addInfo(info); },

  async add(files) {
    if (!files.length) return;
    busy(true, 'Abriendo…');
    try {
      for (const f of files) {
        try { await this.addInfo(await uploadFile(f), false); } catch (e) { toast(e.message, 'err'); }
      }
    } finally { busy(false); }
    this.render();
  },
  /** Añade un documento (cada página de un PDF es una imagen a escanear) y detecta sus bordes. */
  async addInfo(info, render = true) {
    if (!info.pages?.length || info.encrypted) return toast(`${info.name}: no se puede escanear.`, 'err');
    const pages = info.pages.slice(0, 30);
    busy(true, 'Detectando los bordes…');
    try {
      for (let n = 0; n < pages.length; n++) {
        busyText(`Detectando los bordes… ${info.name}${pages.length > 1 ? ` (página ${n + 1})` : ''}`);
        const r = await api('scan/detect', { id: info.id, n });
        this.items.push({ info, n, quad: r.quad, conf: r.conf, rot: 0 });
      }
    } catch (e) { toast(e.message, 'err'); } finally { busy(false); }
    if (this.cur < 0 && this.items.length) this.cur = 0;
    if (render) this.render();
    const low = this.items.filter(i => i.conf < 0.3).length;
    if (low) toast(`${low} imagen(es) sin bordes claros: ajusta las esquinas a mano (o usa «Toda la imagen»).`, '', [], 6000);
  },
  /** Escanear con el móvil: un QR abre en el móvil una página para hacer la foto, que llega aquí por la wifi. */
  async mobile() {
    const r = await run('Preparando…', () => api('mobile/start'));
    if (!r) return;
    const count = h('b', {}, '0');
    const left = h('span', {}, 'caduca en 10 min');
    let stop = false;
    modal({
      title: 'Escanear con el móvil',
      body: h('div', { class: 'mobile' },
        h('img', { src: 'data:image/png;base64,' + r.qr, class: 'mobile-qr', alt: 'Código QR' }),
        h('ol', { class: 'help' },
          h('li', {}, 'Conecta el móvil a la misma wifi que este ordenador.'),
          h('li', {}, 'Escanea este código con la cámara del móvil y abre el enlace.'),
          h('li', {}, 'Pulsa «Hacer foto» y fotografía el documento: aparecerá aquí solo, listo para enderezarlo.')),
        h('p', {}, 'Fotos recibidas: ', count, ' · ', left),
        h('details', {}, h('summary', {}, '¿No se abre en el móvil?'),
          h('ul', { class: 'help' },
            h('li', {}, 'El móvil tiene que estar en la misma wifi que el ordenador (no en la de invitados, que suele aislar los aparatos) y sin VPN.'),
            h('li', {}, 'iPhone: abre la Cámara, apunta al código y toca el enlace amarillo que aparece. Android: usa la cámara o Google Lens.'),
            h('li', {}, 'Si el ordenador preguntó si DocGuard puede aceptar conexiones entrantes y dijiste que no: Ajustes del Sistema → Red → Cortafuegos → Opciones → DocGuard → Permitir.'),
            h('li', {}, 'Mantén esta ventana abierta mientras haces las fotos: al cerrarla (o a los 10 minutos) el enlace deja de funcionar.'),
            h('li', {}, 'También puedes escribir la dirección de abajo en el navegador del móvil.'))),
        h('p', { class: 'muted' }, 'La foto no pasa por internet, pero viaja sin cifrar por la wifi: úsalo solo en tu wifi de casa.'),
        h('p', { class: 'muted mono' }, r.url)),
      actions: [{ label: 'Terminar', primary: true }],
      onclose: () => { stop = true; api('mobile/stop').catch(() => {}); },
    });
    const tick = async () => {
      if (stop) return;
      const s = await api('mobile/status').catch(() => null);
      if (s) {
        for (const info of s.items) await this.addInfo(info);
        count.textContent = s.count;
        left.textContent = s.alive ? `caduca en ${Math.max(1, Math.ceil(s.left / 60))} min` : 'enlace caducado';
        if (!s.alive) return;
      }
      setTimeout(tick, 1500);
    };
    tick();
  },
  async redetect() {
    const it = this.item;
    if (!it) return;
    const r = await run('Detectando…', () => api('scan/detect', { id: it.info.id, n: it.n }));
    if (r) { it.quad = r.quad; it.conf = r.conf; this.drawQuad(); this.schedule(); }
  },

  render() {
    const has = this.items.length > 0;
    $('.scan-empty', this.root).hidden = has;
    $('.work', this.root).style.visibility = has ? '' : 'hidden';
    $('[data-role=count]', this.root).textContent = has ? `${this.items.length} imagen(es)` : '';
    this.renderList();
    if (!has) return;
    const it = this.item;
    const z = Math.min(2, (this.stage.clientWidth - 36) / it.info.pages[it.n][0]) * (window.devicePixelRatio || 1);
    this.img.src = pageUrl(it.info.id, it.n, Math.max(0.2, z).toFixed(3));
    this.schedule();
  },
  renderList() {
    const list = $('.scan-list', this.root);
    list.innerHTML = '';
    this.items.forEach((it, i) => {
      const el = h('div', { class: 'scan-item' + (i === this.cur ? ' on' : ''), draggable: true, onclick: () => { this.cur = i; this.render(); } },
        h('img', { src: pageUrl(it.info.id, it.n, 0.2), style: it.rot ? `transform:rotate(${it.rot}deg)` : '' }),
        it.conf < 0.3 ? h('span', { class: 'low', title: 'Bordes poco claros: revísalos' }, 'revisar') : null,
        h('div', { class: 'n' }, `${i + 1}${it.info.pages.length > 1 ? ` · p${it.n + 1}` : ''}`,
          h('button', { title: 'Quitar', onclick: e => { e.stopPropagation(); this.items.splice(i, 1); this.cur = Math.min(this.cur, this.items.length - 1); this.render(); } }, '✕')));
      el.addEventListener('dragstart', e => e.dataTransfer.setData('text/x-scan', i));
      el.addEventListener('dragover', e => { if (e.dataTransfer.types.includes('text/x-scan')) e.preventDefault(); });
      el.addEventListener('drop', e => {
        const from = e.dataTransfer.getData('text/x-scan');
        if (from === '') return;
        e.preventDefault(); e.stopPropagation();
        const [m] = this.items.splice(+from, 1);
        this.items.splice(i, 0, m);
        this.cur = i;
        this.renderList();
      });
      list.append(el);
    });
  },

  /* ---- esquinas arrastrables ---- */
  drawQuad() {
    const it = this.item;
    const svg = this.svg;
    svg.innerHTML = '';
    if (!it || !this.img.naturalWidth) return;
    const r = this.img.getBoundingClientRect(), s = this.stage.getBoundingClientRect();
    Object.assign(svg.style, { left: r.left - s.left + 'px', top: r.top - s.top + 'px', width: r.width + 'px', height: r.height + 'px' });
    svg.setAttribute('viewBox', `0 0 ${r.width} ${r.height}`);
    const pts = it.quad.map(([x, y]) => [x * r.width, y * r.height]);
    const NS = 'http://www.w3.org/2000/svg';
    const poly = document.createElementNS(NS, 'polygon');
    poly.setAttribute('points', pts.map(p => p.join(',')).join(' '));
    svg.append(poly);
    pts.forEach((p, i) => {
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', p[0]); c.setAttribute('cy', p[1]); c.setAttribute('r', 9);
      if (i === this.corner) c.classList.add('on');
      c.addEventListener('mousedown', e => {
        e.preventDefault();
        this.corner = i;
        this.showLens(i, e.clientX, e.clientY);
        const mv = ev => {
          const rr = this.img.getBoundingClientRect();
          it.quad[i] = [clamp((ev.clientX - rr.left) / rr.width, 0, 1), clamp((ev.clientY - rr.top) / rr.height, 0, 1)];
          this.drawQuad();
          this.showLens(i, ev.clientX, ev.clientY);
        };
        window.addEventListener('mousemove', mv);
        window.addEventListener('mouseup', () => {
          window.removeEventListener('mousemove', mv);
          this.hideLens();
          it.conf = 1; this.drawQuad(); this.renderList(); this.schedule();
        }, { once: true });
      });
      svg.append(c);
    });
  },

  /* ---- lupa ---- */
  /** Imagen con más resolución para la lupa (se carga al empezar a mover una esquina). */
  lensSource() {
    const it = this.item;
    const key = `${it.info.id}:${it.n}`;
    if (this._lensKey !== key) {
      this._lensKey = key;
      this._lensImg = new Image();
      const [w, hgt] = it.info.pages[it.n];
      this._lensImg.src = pageUrl(it.info.id, it.n, Math.min(3, 2800 / Math.max(w, hgt)).toFixed(3));
      this._lensImg.onload = () => { if (this.lens.style.display === 'block' && this._lensAt) this.showLens(...this._lensAt); };
    }
    return this._lensImg.complete && this._lensImg.naturalWidth ? this._lensImg : this.img;
  },
  /** Muestra ampliado (×4) el punto de la esquina i, con la cruz y los bordes del recuadro. */
  showLens(i, cx, cy) {
    const it = this.item;
    if (!it || !this.img.naturalWidth) return;
    this._lensAt = [i, cx, cy];
    const src = this.lensSource();
    const r = this.img.getBoundingClientRect(), s = this.stage.getBoundingClientRect();
    const L = this.lens, S = L.width, zoom = 4;
    const [nx, ny] = it.quad[i];
    const W = src.naturalWidth, H = src.naturalHeight;
    const sw = S / zoom * (W / r.width), sh = S / zoom * (H / r.height);  // zona de la imagen que se ve
    const x0 = nx * W - sw / 2, y0 = ny * H - sh / 2;
    const ctx = L.getContext('2d');
    ctx.fillStyle = '#2b2f38';
    ctx.fillRect(0, 0, S, S);
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(src, x0, y0, sw, sh, 0, 0, S, S);
    const at = ([qx, qy]) => [(qx * W - x0) / sw * S, (qy * H - y0) / sh * S];
    ctx.strokeStyle = 'rgba(37, 99, 217, .95)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(...at(it.quad[(i + 3) % 4]));
    ctx.lineTo(S / 2, S / 2);
    ctx.lineTo(...at(it.quad[(i + 1) % 4]));
    ctx.stroke();
    ctx.strokeStyle = '#ff2d55';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (const [a, b, c, d] of [[S / 2, 0, S / 2, S / 2 - 7], [S / 2, S / 2 + 7, S / 2, S], [0, S / 2, S / 2 - 7, S / 2], [S / 2 + 7, S / 2, S, S / 2]]) {
      ctx.moveTo(a, b); ctx.lineTo(c, d);
    }
    ctx.stroke();
    // arriba a la izquierda del puntero; si no cabe, al otro lado
    let left = cx - s.left - S - 28, top = cy - s.top - S - 28;
    if (left < 4) left = cx - s.left + 28;
    if (top < 4) top = cy - s.top + 28;
    Object.assign(L.style, { left: Math.min(left, s.width - S - 4) + 'px', top: Math.min(top, s.height - S - 4) + 'px', display: 'block' });
  },
  hideLens() { this.lens.style.display = 'none'; this._lensAt = null; },
  /** Flechas del teclado: afinan la última esquina movida (1 píxel; con Mayús, 10). */
  nudge(e) {
    const it = this.item;
    if (!this.root.classList.contains('active') || !it || this.corner == null || /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName)) return;
    if (e.key === 'Escape') { this.corner = null; this.hideLens(); this.drawQuad(); return; }
    const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
    if (!d) return;
    e.preventDefault();
    const r = this.img.getBoundingClientRect();
    const step = e.shiftKey ? 10 : 1;
    const q = it.quad[this.corner];
    it.quad[this.corner] = [clamp(q[0] + d[0] * step / r.width, 0, 1), clamp(q[1] + d[1] * step / r.height, 0, 1)];
    it.conf = 1;
    this.drawQuad();
    const [nx, ny] = it.quad[this.corner];
    this.showLens(this.corner, r.left + nx * r.width, r.top + ny * r.height);
    clearTimeout(this._lensT);
    this._lensT = setTimeout(() => this.hideLens(), 1400);
    this.schedule();
  },

  /* ---- resultado ---- */
  schedule() { clearTimeout(this._t); this._t = setTimeout(() => this.preview(), 250); },
  async preview() {
    const it = this.item;
    if (!it) return;
    const box = $('.scan-result-img', this.root);
    const maxw = Math.round(Math.min(1400, Math.max(300, box.clientWidth * (window.devicePixelRatio || 1))));
    const seq = (this._seq = (this._seq || 0) + 1);
    try {
      const blob = await api('scan/preview', { id: it.info.id, n: it.n, quad: it.quad, rot: it.rot,
        kind: this.k('kind').value, mode: this.k('mode').value, maxw });
      if (seq !== this._seq) return;
      if (this._url) URL.revokeObjectURL(this._url);
      this._url = URL.createObjectURL(blob);
      this.res.src = this._url;
    } catch (e) { toast(e.message, 'err'); }
  },
  async export() {
    if (!this.items.length) return toast('Añade primero alguna foto.', 'err');
    const res = await run('Digitalizando…', () => api('scan/export', {
      pages: this.items.map(it => ({ id: it.info.id, n: it.n, quad: it.quad, rot: it.rot })),
      kind: this.k('kind').value, mode: this.k('mode').value, fmt: this.k('fmt').value,
      layout: this.k('layout').value, ocr: this.k('ocr').checked, pdfa: this.k('pdfa').checked,
    }));
    saveResult(res);
  },
};
