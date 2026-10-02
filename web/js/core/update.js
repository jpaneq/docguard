'use strict';
// Al abrirse, DocGuard mira si hay una versión nueva publicada y ofrece instalarla (nunca solo).

const Update = {
  async init() {
    const v = await api('version').catch(() => null);
    if (v) $$('[data-role=version]').forEach(el => { el.textContent = 'Versión ' + v.version; });
    if (!window.pywebview) {  // en Windows pywebview se conecta un instante después de cargar
      await new Promise(res => { window.addEventListener('pywebviewready', res, { once: true }); setTimeout(res, 3000); });
      if (!window.pywebview) return;  // en el navegador no se actualiza
    }
    try {  // una vez cada pocas horas aunque haya varias ventanas
      if (Date.now() - (+localStorage.getItem('dg_update_seen') || 0) < 6 * 3600e3) return;
    } catch (e) { /* sin almacenamiento */ }
    setTimeout(() => this.check(false), 4000);
  },
  async check(manual = true) {
    const r = await (manual ? run('Buscando actualizaciones…', () => api('update/check')) : api('update/check').catch(() => null));
    if (!r) return;
    try { localStorage.setItem('dg_update_seen', Date.now()); } catch (e) { /* sin almacenamiento */ }
    if (!r.available) { if (manual) toast(r.error ? 'No se ha podido consultar (¿sin internet?).' : `Tienes la última versión (${r.current}).`, r.error ? 'err' : 'ok'); return; }
    toast(`Hay una versión nueva de DocGuard: ${r.version} (tienes la ${r.current}).`, 'ok', [{ label: 'Ver y actualizar…', fn: () => this.offer(r) }], 15000);
  },
  offer(r) {
    modal({
      title: `DocGuard ${r.version}`,
      body: h('div', {}, h('p', {}, `Tienes la versión ${r.current}.`),
        r.notes ? h('pre', { class: 'update-notes' }, r.notes) : null,
        h('p', { class: 'muted' }, 'Se descarga de GitHub, se comprueba su huella SHA-256 y, al reiniciar, sustituye al programa actual (la versión anterior se guarda). Guarda antes tus documentos abiertos.'),
        r.can_install ? null : h('p', { class: 'bad' }, 'Estás ejecutando DocGuard desde el código: actualízalo con git pull.')),
      actions: [{ label: 'Más tarde' }, ...(r.can_install ? [{ label: 'Descargar y reiniciar', primary: true, fn: () => this.install(r) }] : [])],
    });
  },
  async install(r) {
    const ok = await run('Descargando la versión ' + r.version + '…', () => api('update/download', r));
    if (!ok) return;
    if (!(await confirmBox('Actualización lista', `DocGuard ${r.version} está descargado y comprobado. ¿Reiniciar ahora? (si no, se instalará al cerrar DocGuard)`, 'Reiniciar ahora'))) return;
    await window.pywebview.api.restart_to_update();
  },
};

// Iconos de estado de los PDF en el Finder / Explorador (firmado, contraseña, censurado, protegido).
const StatusIcons = {
  async open() {
    const apiN = window.pywebview?.api;
    if (!apiN?.icons_setting) return toast('Solo disponible en el programa de escritorio.', '');
    const st = await apiN.icons_setting(null);
    const mac = st.platform === 'darwin';
    const cb = h('input', { type: 'checkbox', checked: st.enabled });
    modal({
      title: 'Iconos de estado de los PDF',
      body: h('div', {},
        h('p', {}, 'Los PDF se ven en rojo, con una insignia si están firmados ✍, con contraseña 🔒, censurados ▬ o protegidos 🛡.'),
        h('label', { class: 'inline' }, cb, 'Mostrar los iconos de estado'),
        mac ? h('p', { class: 'muted' }, 'Mac: se aplican a los PDF que guarda DocGuard (también con etiquetas de color del Finder). Para los que ya tienes, usa el botón de abajo. El icono solo existe en tu Mac: al enviar el PDF se ve normal. El Finder deja de mostrar la miniatura de la primera página en esos archivos.')
          : h('p', { class: 'muted' }, 'Windows: el Explorador los muestra en todos los PDF, en las vistas de iconos medianos o más grandes. Solo para tu usuario y sin permisos de administrador. Puede que los PDF que ya habías visto tarden en actualizarse (el Explorador guarda las miniaturas).')),
      actions: [
        ...(mac ? [{ label: 'Marcar los PDF de una carpeta…', fn: async () => { const n = await apiN.mark_folder(); if (n != null) toast(`${n} PDF marcados.`, 'ok'); return false; } }] : []),
        { label: 'Cerrar', primary: true, fn: async () => { if (cb.checked !== st.enabled) await apiN.icons_setting(cb.checked); } },
      ],
    });
  },
};
