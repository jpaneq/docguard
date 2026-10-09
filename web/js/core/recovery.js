'use strict';
// Autoguardado: copias de recuperación (NO son un guardado; el archivo del usuario no se toca).

const Recovery = {
  /** Al arrancar: si una sesión anterior se cerró con cambios sin guardar, ofrece recuperarlos. */
  async check() {
    const r = await api('recovery/list', {}).catch(() => null);
    if (r?.items?.length) this.show(r.items);
  },
  ago(t) {
    const m = Math.round((Date.now() / 1000 - t) / 60);
    if (m < 1) return 'hace un momento';
    if (m < 60) return `hace ${m} min`;
    const hh = Math.round(m / 60);
    return hh < 24 ? `hace ${hh} h` : new Date(t * 1000).toLocaleDateString();
  },
  show(items) {
    const list = h('div', { class: 'rc-list' });
    let close;
    const refresh = () => { if (!list.children.length) close?.(); };
    for (const m of items) {
      const card = h('div', { class: 'rc-item' },
        h('span', { class: 'rc-ic' }, '🛟'),
        h('div', { class: 'rc-t' }, h('b', {}, m.name), h('small', { class: 'muted' }, `${m.pages} pág. · guardada ${this.ago(m.saved)} · ${(m.size / 1048576).toFixed(1)} MB`)),
        h('button', { class: 'primary', onclick: async () => {
          const info = await run('Recuperando…', () => api('recovery/open', { id: m.id }));
          if (!info) return;
          card.remove(); refresh();
          Shell.openInfo(info);
          toast('Recuperado. Pulsa «Guardar PDF…» para conservarlo: el autoguardado no es un guardado.', 'ok', [], 7000);
        } }, 'Recuperar'),
        h('button', { onclick: async () => { await api('recovery/discard', { id: m.id }); card.remove(); refresh(); } }, 'Descartar'));
      list.append(card);
    }
    close = modal({
      wide: true,
      title: 'Documentos sin guardar',
      body: h('div', {},
        h('p', {}, 'DocGuard se cerró con cambios sin guardar. Se conservó una copia de recuperación de estos documentos:'),
        list,
        h('p', { class: 'muted' }, 'La copia de recuperación no es un guardado definitivo: tu archivo original no se ha modificado. Al recuperarla se abre como documento editado, y hay que guardarla con «Guardar PDF…».')),
      actions: [{ label: 'Decidir más tarde' }, { label: 'Descartar todas', fn: async () => { await api('recovery/discard', { all: true }); } }],
    });
  },
  async settings() {
    const s = await api('autosave/settings', {});
    const on = h('input', { type: 'checkbox', checked: s.enabled });
    const sec = h('select', {}, [[15, '15 segundos'], [30, '30 segundos'], [60, '1 minuto'], [120, '2 minutos'], [300, '5 minutos']]
      .map(([v, t]) => h('option', { value: v, selected: v === s.seconds }, t)));
    const save = async () => { await api('autosave/settings', { enabled: on.checked, seconds: +sec.value }); };
    modal({
      title: 'Autoguardado y recuperación',
      body: h('div', {},
        h('label', { class: 'inline' }, on, h('b', {}, 'Guardar copias de recuperación mientras edito')),
        h('label', {}, 'Con cambios sin guardar, como mucho cada', sec),
        h('p', { class: 'muted' }, 'Si DocGuard se cierra de golpe, al abrirlo podrás recuperar lo que habías hecho. No es un guardado definitivo: no toca tu archivo original ni crea PDFs en tu carpeta; las copias viven en la carpeta de configuración de DocGuard y se borran al guardar el PDF, al cerrar el documento, al descartarlas o a los 14 días.'),
        h('button', { onclick: async () => {
          const r = await api('recovery/list', { force: true });
          if (!r.items.length) return toast('No hay copias de recuperación pendientes.', '');
          this.show(r.items);
        } }, 'Ver copias de recuperación…')),
      actions: [{ label: 'Cancelar' }, { label: 'Guardar ajustes', primary: true, fn: save }],
    });
  },
};
