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
