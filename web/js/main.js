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

function showTool(name) {
  syncTool(name);
  $$('.nav button').forEach(b => b.classList.toggle('active', b.dataset.tool === name));
  $$('.tool').forEach(s => s.classList.toggle('active', s.id === 'tool-' + name));
  requestAnimationFrame(() => TOOLS[name]?.viewer?.fit());
  if (name === 'watermark') Wm.schedule();
}

function init() {
  Edit.init(); Wm.init(); Redact.init(); Sign.init(); Pages.init(); Protect.init();
  Object.assign(TOOLS, { edit: Edit, watermark: Wm, redact: Redact, sign: Sign, pages: Pages, protect: Protect });
  $('.cd-close').onclick = clearCurrent;
  TOOLS.convert = batchTool('tool-convert', '', {
    todocx: f => api('todocx', { ids: f.ids }),
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
  $$('.nav button').forEach(b => b.onclick = () => showTool(b.dataset.tool));
  Sigs.load();
  Tabs.init();
}

init();
