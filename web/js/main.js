'use strict';
// Arranque: registra las herramientas y la navegación.

/* ======================================================================
   Navegación
   ====================================================================== */

const TOOLS = {};

/** Al entrar en una herramienta, abre en ella el documento actual (con sus cambios). */
function syncTool(name) {
  const t = TOOLS[name];
  if (!CURRENT || !t) return;
  const same = t.info?.id === CURRENT.id;
  if (name === 'edit') { if (same) t.refresh(true); else t.loadInfo(CURRENT); }
  else if (name === 'redact') { if (same) { t.words = {}; t.viewer.refresh(); t.ensureWords(t.viewer.n); } else t.loadInfo(CURRENT); }
  else if (name === 'sign') { if (same) t.viewer.refresh(); else t.loadInfo(CURRENT); }
  else if (name === 'pages') { if (same) { t.v++; t.render(); } else t.loadInfo(CURRENT); }
  else if (name === 'watermark' || name === 'protect') {
    const fl = t.files;
    const i = fl.items.findIndex(x => x.id === CURRENT.id);
    if (i >= 0) { fl.cur = i; fl.render(); }
    else if (fl.items.length <= 1) { fl.items = [CURRENT]; fl.cur = 0; fl.render(); }
    else { fl.items.unshift(CURRENT); fl.cur = 0; fl.render(); }
    if (name === 'watermark') { t.n = 0; t.preview(); }
  } else if (name === 'scanner') { if (!t.items.length && CURRENT.pages?.length) t.addInfo(CURRENT); }
  else if (name === 'library') { if (CURRENT.pages?.length) t.loadInfo(CURRENT); }
  else if (name === 'compare') { if (!t.a && !t.b) t.set('a', CURRENT); }
  else if (t.files && !t.files.items.length) { t.files.items = [CURRENT]; t.files.render(); }
}

/** «Poner / Quitar marca de agua»: acciones del panel derecho que trabajan sobre el documento actual en Editar. */
function runToolAction(name) {
  const d = (Shell.view === 'library' && Library.reading) || Edit.info || CURRENT;
  if (!d) return toast(`Abre primero un documento para usar «${TOOL_META[name].label}».`, 'err');
  showTool('edit');
  if (!Edit.info || Edit.info.id !== d.id) Edit.loadInfo(d);
  setTimeout(() => (name === 'wm_add' ? Edit.watermarkPanel() : Edit.removeWatermarks()), 200);
}

function showTool(name) {
  if (TOOL_META[name]?.action) return runToolAction(name);
  syncTool(name);
  $$('.nav button').forEach(b => b.classList.toggle('active', b.dataset.tool === name));
  $$('.tool').forEach(s => s.classList.toggle('active', s.id === 'tool-' + name));
  requestAnimationFrame(() => TOOLS[name]?.viewer?.fit());
  if (name === 'watermark') Wm.schedule();
  Shell.onView(name);
}

function init() {
  Shell.init();
  Files.init();
  Edit.init(); Wm.init(); Redact.init(); Sign.init(); Pages.init(); Protect.init();
  Object.assign(TOOLS, { edit: Edit, watermark: Wm, redact: Redact, sign: Sign, pages: Pages, protect: Protect });
  $('.cd-close').onclick = clearCurrent;
  TOOLS.convert = batchTool('tool-convert', '', {
    todocx: (f, r) => api('todocx', { ids: f.ids, mode: $('[data-k=wmode]', r).value }),
    doctopdf: f => api('doctopdf', { ids: f.ids }),
    compress: (f, r) => api('compress', { ids: f.ids, level: $('[data-k=level]', r).value }),
    toimages: (f, r) => api('toimages', { ids: f.ids, fmt: $('[data-k=fmt]', r).value, dpi: +$('[data-k=dpi]', r).value }),
    topdf: f => api('topdf', { ids: f.ids }),
  });
  TOOLS.sanitize = batchTool('tool-sanitize', '', { clean: f => api('sanitize', { ids: f.ids }) });
  Merge.init();
  TOOLS.merge = Merge;
  Compare.init();
  TOOLS.compare = Compare;
  Library.init();
  TOOLS.library = Library;
  Scanner.init();
  TOOLS.scanner = Scanner;
  $$('.nav button[data-tool]').forEach(b => b.onclick = () => showTool(b.dataset.tool));
  // Se abre en Inicio; si DocGuard se abrió con un documento (…&open=id), directamente en el Visor con él
  const openId = new URLSearchParams(location.search).get('open');
  if (openId) {
    showTool('library');
    api('info', { id: openId }).then(info => Library.openDoc(info)).catch(e => toast('No se pudo abrir el documento: ' + e.message, 'err'));
  } else showTool('home');
  Sigs.load();
  Tabs.init();
  Update.init();
  setTimeout(() => Recovery.check(), 1500);
  StatusIcons.notice();
}

init();
