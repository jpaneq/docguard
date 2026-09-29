'use strict';
// Firmas manuscritas guardadas (compartidas por Editar y Firma digital).

/* ======================================================================
   Firmas manuscritas (compartido entre Editar y Firma digital)
   ====================================================================== */

const Sigs = {
  items: [],
  async load() {
    try { this.items = (await api('sigimgs')).items; } catch (e) { this.items = []; }
    document.dispatchEvent(new Event('sigs-changed'));
    return this.items;
  },
  src(it) { return 'data:image/png;base64,' + it.png; },
  ratio(id) {
    return new Promise(res => {
      const it = this.items.find(s => s.id === id);
      if (!it) return res(3);
      const im = new Image();
      im.onload = () => res(im.width / im.height);
      im.src = this.src(it);
    });
  },
  /** Ventana para dibujar o subir una firma. Devuelve el id guardado. */
  create() {
    return new Promise(res => {
      const cv = h('canvas', { class: 'sig-canvas', width: 520, height: 200 });
      const ctx = cv.getContext('2d');
      ctx.lineWidth = 3; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = '#1a3fa8';
      let drawing = false, drawn = false, upload = null;
      const pos = e => { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * cv.width / r.width, (e.clientY - r.top) * cv.height / r.height]; };
      cv.addEventListener('pointerdown', e => { drawing = true; drawn = true; upload = null; ctx.beginPath(); ctx.moveTo(...pos(e)); cv.setPointerCapture(e.pointerId); });
      cv.addEventListener('pointermove', e => { if (drawing) { ctx.lineTo(...pos(e)); ctx.stroke(); } });
      cv.addEventListener('pointerup', () => { drawing = false; });
      const color = h('select', { onchange: () => { ctx.strokeStyle = color.value; } },
        h('option', { value: '#1a3fa8' }, 'Azul'), h('option', { value: '#111111' }, 'Negro'));
      const white = h('input', { type: 'checkbox', checked: true });
      const body = h('div', {},
        h('p', { class: 'muted' }, 'Dibuja tu firma con el ratón o el trackpad, o sube una imagen (foto o escaneo).'),
        cv,
        h('div', { class: 'row' }, 'Color', color,
          h('button', { onclick: () => { ctx.clearRect(0, 0, cv.width, cv.height); drawn = false; upload = null; } }, 'Borrar'),
          h('button', {
            onclick: async () => {
              const [f] = await pickFiles('image/*');
              if (!f) return;
              upload = await fileToB64(f);
              const im = new Image();
              im.onload = () => {
                ctx.clearRect(0, 0, cv.width, cv.height);
                const s = Math.min(cv.width / im.width, cv.height / im.height);
                ctx.drawImage(im, (cv.width - im.width * s) / 2, (cv.height - im.height * s) / 2, im.width * s, im.height * s);
              };
              im.src = 'data:image/*;base64,' + upload;
            },
          }, 'Subir imagen…')),
        h('label', { class: 'inline' }, white, 'Quitar el fondo blanco (para imágenes escaneadas)'));
      modal({
        title: 'Nueva firma manuscrita', body,
        actions: [{ label: 'Cancelar', fn: () => res(null) }, {
          label: 'Guardar firma', primary: true, fn: async () => {
            if (!drawn && !upload) { toast('Dibuja o sube una firma.', 'err'); return false; }
            const png = upload || cv.toDataURL('image/png').split(',')[1];
            const r = await run('Guardando…', () => api('sigimg/save', { png, remove_white: !!upload && white.checked }));
            if (!r) return false;
            await this.load();
            res(r.id);
          },
        }],
      });
    });
  },
  /** Galería con selección. onpick(id) */
  gallery(selected, onpick) {
    const g = h('div', { class: 'sig-gallery' });
    for (const it of this.items) {
      g.append(h('div', { class: 'sig-item' + (it.id === selected ? ' sel' : ''), onclick: () => onpick(it.id), title: 'Usar esta firma' },
        h('img', { src: this.src(it) }),
        h('button', {
          title: 'Borrar', onclick: async e => {
            e.stopPropagation();
            if (await confirmBox('Borrar firma', '¿Borrar esta firma guardada?', 'Borrar')) {
              await api('sigimg/delete', { id: it.id });
              await this.load();
              if (it.id === selected) onpick(null);
            }
          },
        }, '✕')));
    }
    if (!this.items.length) g.append(h('small', {}, 'Aún no tienes firmas guardadas.'));
    return g;
  },
};
