'use strict';
// Al abrirse, DocGuard mira si hay una versión nueva publicada y ofrece instalarla (nunca solo).

/** Notas de la versión (novedades/X.Y.md, publicadas en la release) como tarjetas: «# Titular», texto y «- 🔎 **Título** — detalle». */
function notesView(md) {
  const lines = (md || '').split('\n').map(l => l.trim()).filter(l => l && !/^\*\*Full Changelog/i.test(l));
  const head = lines.find(l => l.startsWith('# '));
  const sub = lines.filter(l => !l.startsWith('#') && !/^[-*] /.test(l)).join(' ');
  const body = lines.filter(l => /^[-*] /.test(l) || l.startsWith('## '));
  if (!head && !body.length) return h('pre', { class: 'update-notes' }, md);
  let k = 0;
  const list = body.map(l => {
    if (l.startsWith('## ')) return h('div', { class: 'wn-sec' }, l.slice(3));  // «## Nuevo», «## Arreglado»…
    const m = l.replace(/^[-*]\s+/, '').match(/^(\S+)\s+\*\*(.+?)\*\*\s*[—:-]?\s*(.*)$/);
    const it = m ? { ic: m[1], title: m[2], text: m[3].charAt(0).toUpperCase() + m[3].slice(1) } : { ic: '•', title: '', text: l.replace(/^[-*]\s+/, '') };
    return h('div', { class: 'wn-item', style: `--h:${(k++ * 47 + 215) % 360}` },
      h('span', { class: 'wn-ic' }, it.ic), h('div', {}, it.title ? h('b', {}, it.title) : null, h('p', {}, it.text)));
  });
  return h('div', { class: 'whatsnew' },
    h('div', { class: 'wn-hero' }, h('b', {}, head ? head.slice(2) : 'Novedades'), sub ? h('span', {}, sub) : null),
    h('div', { class: 'wn-list' }, list));
}

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
    if (!r.available) { if (manual) toast(r.error ? `No se ha podido consultar (¿sin internet?): ${String(r.error).slice(0, 160)}` : `Tienes la última versión (${r.current}).`, r.error ? 'err' : 'ok'); return; }
    toast(`Hay una versión nueva de DocGuard: ${r.version} (tienes la ${r.current}).`, 'ok', [{ label: 'Ver y actualizar…', fn: () => this.offer(r) }], 15000);
  },
  offer(r) {
    modal({
      wide: true,
      title: `DocGuard ${r.version} · novedades`,
      body: h('div', {}, h('p', {}, `Tienes la versión ${r.current}.`),
        r.notes ? notesView(r.notes) : null,
        h('p', { class: 'muted' }, 'Se descarga de GitHub, se comprueba su huella SHA-256 y, al reiniciar, sustituye al programa actual (la versión anterior se guarda). Guarda antes tus documentos abiertos.'),
        r.can_install ? null : h('p', { class: 'bad' }, 'Estás ejecutando DocGuard desde el código: actualízalo con git pull.')),
      actions: [{ label: 'Más tarde' }, ...(r.can_install ? [{ label: 'Descargar y reiniciar', primary: true, fn: () => this.install(r) }] : [])],
    });
  },
  async install(r) {
    const timer = setInterval(async () => {
      const p = await api('update/progress').catch(() => null);
      if (!p?.done) return;
      busyText(p.unpacking ? 'Descomprimiendo la versión ' + r.version + '…'
        : `Descargando la versión ${r.version}… ${Math.round(p.done / 1048576)}${p.total ? ' de ' + Math.round(p.total / 1048576) : ''} MB`);
    }, 700);
    const ok = await run('Descargando la versión ' + r.version + '…', () => api('update/download', r)).finally(() => clearInterval(timer));
    if (!ok) return;
    if (!(await confirmBox('Actualización lista', `DocGuard ${r.version} está descargado y comprobado. ¿Reiniciar ahora? (si no, se instalará al cerrar DocGuard)`, 'Reiniciar ahora'))) return;
    await window.pywebview.api.restart_to_update();
  },
};

// Iconos de estado de los PDF en el Finder / Explorador (firmado, contraseña, censurado, protegido).
const StatusIcons = {
  /** Windows: la primera vez tras actualizar, explica cómo activar los iconos en el Explorador. */
  async notice() {
    if (!window.pywebview) await new Promise(res => { window.addEventListener('pywebviewready', res, { once: true }); setTimeout(res, 3000); });
    const apiN = window.pywebview?.api;
    if (!apiN?.icons_setting || window.opener) return;
    const st = await apiN.icons_setting(null).catch(() => null);
    if (!st || st.platform !== 'win32' || st.notice_seen || st.machine || !st.enabled) return;
    await apiN.icons_notice_seen();
    const step = (n, text, img) => h('div', { class: 'help-step' }, h('p', {}, h('b', {}, n + '. '), text), h('img', { src: 'ayuda/' + img, alt: '' }));
    modal({
      title: 'Novedad: iconos de estado en el Explorador',
      wide: true,
      body: h('div', { class: 'help-steps' },
        h('p', {}, 'DocGuard puede mostrar en el Explorador de Windows si cada PDF está firmado, tiene contraseña, está censurado o protegido. Para activarlo:'),
        step(1, 'Arriba a la derecha, abre el menú «⋯» y pulsa «Iconos de estado…».', 'paso1.png'),
        step(2, 'Pulsa «Activar en el Explorador…» y acepta el permiso de Windows (se pide una sola vez).', 'paso2.png'),
        step(3, 'Listo: en las vistas de iconos medianos o más grandes verás así tus PDF.', 'paso3.png')),
      actions: [{ label: 'Más tarde' }, {
        label: 'Activar ahora', primary: true, fn: async () => {
          const ok = await apiN.icons_machine(true);
          toast(ok ? 'Iconos activados en el Explorador.' : 'No se han activado (se canceló el permiso de administrador). Puedes hacerlo luego en «Iconos de estado…».', ok ? 'ok' : 'err', [], 8000);
        },
      }],
    });
  },
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
          : h('div', {},
            h('p', { class: 'muted' }, 'Windows: el Explorador los muestra en todos los PDF, en las vistas de iconos medianos o más grandes. Puede que los PDF que ya habías visto tarden en actualizarse (el Explorador guarda las miniaturas).'),
            st.machine ? h('p', { class: 'ok' }, '✔ Activados en el Explorador.')
              : h('p', {}, 'Windows solo deja que el Explorador use estos iconos si se activan con permiso de administrador. Se pide una sola vez; las actualizaciones de DocGuard no lo vuelven a pedir.'))),
      actions: [
        ...(!mac && !st.machine ? [{ label: 'Activar en el Explorador…', fn: async () => {
          const ok = await apiN.icons_machine(true);
          toast(ok ? 'Iconos activados en el Explorador.' : 'No se han activado (se canceló el permiso de administrador).', ok ? 'ok' : 'err');
        } }] : []),
        ...(mac ? [{ label: 'Marcar los PDF de una carpeta…', fn: async () => { const n = await apiN.mark_folder(); if (n != null) toast(`${n} PDF marcados.`, 'ok'); return false; } }] : []),
        { label: 'Cerrar', primary: true, fn: async () => { if (cb.checked !== st.enabled) await apiN.icons_setting(cb.checked); } },
      ],
    });
  },
};

// Integración con otros programas: menú PDF de Imprimir (Mac), «Enviar a» (Windows) y botón en Word.
const Integration = {
  async open() {
    const apiN = window.pywebview?.api;
    if (!apiN?.integration) return toast('Solo disponible en el programa de escritorio.', '');
    const st = await apiN.integration();
    const mac = st.platform === 'darwin', win = st.platform === 'win32';
    const row = (kind, on, title, text) => {
      const cb = h('input', { type: 'checkbox', checked: !!on });
      cb.onchange = async () => {
        cb.disabled = true;
        const r = await run(cb.checked ? 'Activando…' : 'Quitando…', () => apiN.integration(kind, cb.checked));
        cb.disabled = false;
        if (!r?.ok) { cb.checked = !cb.checked; toast('No se ha podido cambiar (¿se canceló el permiso?).', 'err'); return; }
        toast(cb.checked ? 'Activado.' : 'Quitado.', 'ok');
      };
      return h('div', { class: 'integ-row' }, h('label', { class: 'inline' }, cb, h('b', {}, title)), h('p', { class: 'muted' }, text));
    };
    modal({
      title: 'Integración con Word y otros programas',
      body: h('div', {},
        mac ? row('pdf_service', st.pdf_service, 'Imprimir → PDF → «Abrir en DocGuard»',
          'En el diálogo de imprimir de Word (y de cualquier programa), el menú «PDF» de abajo a la izquierda tendrá «Abrir en DocGuard».') : null,
        win ? row('send_to', st.send_to, 'Botón derecho → «Enviar a» → DocGuard',
          'Con el botón derecho sobre un PDF o un documento de Word. Los documentos de Word se convierten a PDF (con Word o LibreOffice si están instalados).') : null,
        row('word', st.word, 'Botón «Exportar a DocGuard» en Word',
          'Aparece en la pestaña Inicio de Word (cierra y vuelve a abrir Word). Funciona aunque DocGuard esté cerrado: un proceso pequeño de DocGuard arranca al iniciar sesión y lo abre cuando hace falta. Al activarlo, ' +
          (mac ? 'el Mac pedirá tu contraseña' : 'Windows mostrará un aviso de seguridad') +
          ' para confiar en un certificado propio de DocGuard, que solo sirve en este equipo. Si no aparece, en Word: Insertar → Complementos → Mis complementos.'),
        row('browser', st.browser, 'Abrir en DocGuard los PDF de Chrome / Edge',
          'Los PDF que el navegador iba a mostrar se abren en DocGuard (si DocGuard no responde, se quedan en el navegador). Tras activarlo, instala la extensión una vez: en Chrome o Edge abre chrome://extensions (edge://extensions), activa «Modo de desarrollador», pulsa «Cargar descomprimida» y elige la carpeta: ' + st.browser_dir +
          '. Para PDF guardados en el equipo, en la ficha de la extensión activa «Permitir acceso a URL de archivos». En el icono de la extensión se puede desactivar. Comparte la escucha y el certificado del botón de Word.')),
      actions: [{ label: 'Cerrar', primary: true }],
    });
  },
};
