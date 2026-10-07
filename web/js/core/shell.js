'use strict';
// Estructura de la aplicación: barra superior (Inicio, Herramientas y documentos abiertos), vistas de
// Inicio y Herramientas, panel de herramientas ocultable (a la derecha) y tema claro/oscuro.

/* ---- iconos: trazo fino (24×24); la clase «f» pinta el relleno suave del color de la herramienta ---- */
const TOOL_ICONS = {
  edit: '<path class="f" d="M6 3.5h8.5L19 8v6.2"/><path d="M6 3.5v17h6.5"/><path d="M14.5 3.5V8H19"/><path d="M9 11.5h6M9 14.5h3"/><path class="f" d="M13.6 20.4l.6-2.6 5.2-5.2 2 2-5.2 5.2z"/>',
  library: '<path class="f" d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14.5 3.5V8H19"/><path d="M8.4 14.6c1.1-2 2.4-3 3.8-3s2.7 1 3.8 3c-1.1 2-2.4 3-3.8 3s-2.7-1-3.8-3z"/><circle cx="12.2" cy="14.6" r="1.2"/>',
  scanner: '<path d="M3.5 8.5V5.5a2 2 0 012-2h3M15.5 3.5h3a2 2 0 012 2v3M20.5 15.5v3a2 2 0 01-2 2h-3M8.5 20.5h-3a2 2 0 01-2-2v-3"/><rect class="f" x="7.5" y="7" width="9" height="10" rx="1"/><path d="M2.5 12h19"/>',
  pages: '<rect class="f" x="4" y="3.5" width="9.5" height="12.5" rx="1.3"/><path d="M8 20h7.5a4 4 0 004-4v-3.5"/><path d="M17 15.2l2.5-2.7 2.5 2.7"/>',
  merge: '<rect class="f" x="3.5" y="4" width="8" height="10" rx="1.3"/><rect x="12.5" y="4" width="8" height="10" rx="1.3"/><path d="M12 15.5v5M9.6 18.2l2.4 2.3 2.4-2.3"/>',
  convert: '<path class="f" d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14.5 3.5V8H19"/><path d="M9 12.2h6.2M13.2 10.2l2 2-2 2M15 17H8.8M10.8 15l-2 2 2 2"/>',
  sign: '<path class="f" d="M15 3.8l5.2 5.2-9.3 9.3-5.6 1 1-5.6z"/><path d="M12.6 6.2l5.2 5.2"/><path d="M3.5 21.2h8M14 21.2h6.5"/>',
  compare: '<rect class="f" x="3" y="4.5" width="8" height="15" rx="1.3"/><rect x="13" y="4.5" width="8" height="15" rx="1.3"/><path d="M5.7 9h2.6M5.7 12h2.6M15.7 9h2.6M15.7 12h2.6M5.7 15h1.6"/>',
  watermark: '<path class="f" d="M12 3.5c3.6 4 6.2 7 6.2 10.3a6.2 6.2 0 01-12.4 0c0-3.3 2.6-6.300 6.2-10.300z"/><path d="M9.1 14.6a3.1 3.1 0 002.9 2.700"/>',
  redact: '<path class="f" d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14.5 3.5V8H19"/><rect x="8.5" y="11" width="7.500" height="2.400" rx=".6" fill="currentColor" stroke="none"/><rect x="8.5" y="15.200" width="5" height="2.400" rx=".6" fill="currentColor" stroke="none"/>',
  protect: '<rect class="f" x="5" y="10.500" width="14" height="10" rx="2"/><path d="M8 10.500V8a4 4 0 018 0v2.500"/><circle cx="12" cy="15.300" r="1.400"/><path d="M12 16.700v1.800"/>',
  sanitize: '<path class="f" d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14.5 3.5V8H19"/><path d="M12.200 10.600l1.100 2.400 2.400 1.100-2.400 1.100-1.100 2.400-1.100-2.400-2.400-1.100 2.400-1.100z"/>',
};

const UI_ICONS = {
  home: '<path d="M4 11l8-6.500 8 6.500"/><path d="M6 9.800V20h4.200v-5.500h3.600V20H18V9.800"/>',
  tools: '<rect x="4" y="4" width="6.500" height="6.500" rx="1.500"/><rect x="13.500" y="4" width="6.500" height="6.500" rx="1.500"/><rect x="4" y="13.500" width="6.500" height="6.500" rx="1.500"/><rect x="13.500" y="13.500" width="6.500" height="6.500" rx="1.500"/>',
  search: '<circle cx="10.500" cy="10.500" r="6"/><path d="M15 15l5 5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  chevR: '<path d="M9 5l7 7-7 7"/>',
  chevL: '<path d="M15 5l-7 7 7 7"/>',
  more: '<circle cx="5.500" cy="12" r="1.300" fill="currentColor"/><circle cx="12" cy="12" r="1.300" fill="currentColor"/><circle cx="18.500" cy="12" r="1.300" fill="currentColor"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.600 5.600l1.400 1.400M17 17l1.400 1.400M18.400 5.600L17 7M7 17l-1.400 1.400"/>',
  moon: '<path d="M19.500 14.500A8 8 0 019.500 4.500a8 8 0 1010 10z"/>',
  auto: '<circle cx="12" cy="12" r="8"/><path d="M12 4v16" /><path d="M12 4a8 8 0 010 16z" fill="currentColor" stroke="none"/>',
  window: '<rect x="3.500" y="5" width="17" height="14" rx="2"/><path d="M3.500 9h17"/>',
  tile: '<rect x="3.500" y="4" width="7.500" height="7" rx="1.200"/><rect x="13" y="4" width="7.500" height="7" rx="1.200"/><rect x="3.500" y="13" width="7.500" height="7" rx="1.200"/><rect x="13" y="13" width="7.500" height="7" rx="1.200"/>',
  cascade: '<rect x="3.500" y="3.500" width="12" height="9" rx="1.500"/><rect x="8.500" y="9.500" width="12" height="9" rx="1.500"/>',
  refresh: '<path d="M19.500 12a7.500 7.500 0 11-2.200-5.300"/><path d="M19.500 4.500v4.500H15"/>',
  badge: '<path d="M6 3.500h8.500L19 8v12.500H6z"/><path d="M14.500 3.500V8H19"/><circle cx="12.500" cy="15" r="2.500"/>',
  upload: '<path d="M12 16V5M7.500 9.500L12 5l4.500 4.500"/><path d="M4.500 15v3.500a1.500 1.500 0 001.500 1.500h12a1.500 1.500 0 001.500-1.500V15"/>',
  file: '<path d="M6 3.500h8.500L19 8v12.500H6z"/><path d="M14.500 3.500V8H19"/><path d="M9 13h6M9 16.500h4"/>',
  lock: '<rect x="5" y="10.500" width="14" height="10" rx="2"/><path d="M8 10.500V8a4 4 0 018 0v2.500"/>',
  folder: '<path d="M3.500 7a2 2 0 012-2h4l2 2.500h7a2 2 0 012 2V17a2 2 0 01-2 2h-13a2 2 0 01-2-2z"/>',
  up: '<path d="M12 19V6M6.500 11.500L12 6l5.500 5.500"/>',
  star: '<path d="M12 4l2.400 5 5.400.7-4 3.800 1 5.400-4.800-2.600-4.800 2.600 1-5.400-4-3.800 5.400-.7z"/>',
  starFill: '<path d="M12 4l2.400 5 5.400.7-4 3.800 1 5.400-4.800-2.600-4.800 2.600 1-5.400-4-3.800 5.400-.7z" fill="currentColor"/>',
  print: '<path d="M7 8.500V4h10v4.500"/><rect x="4" y="8.500" width="16" height="8" rx="2"/><rect x="7.500" y="14" width="9" height="6" rx="1"/>',
  rotl: '<path d="M4.500 12a7.500 7.500 0 102.200-5.300"/><path d="M4.500 4.500v4.500H9"/>',
  rotr: '<path d="M19.500 12a7.500 7.500 0 11-2.200-5.300"/><path d="M19.500 4.500v4.500H15"/>',
};

const svg = (inner, size = 20, sw = 1.4) =>
  `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;
const uiIcon = (name, size = 18) => svg(UI_ICONS[name] || '', size, 1.5);
const toolIcon = (name, size = 24, sw = 1.2) => svg(TOOL_ICONS[name] || '', size, sw);

/* ---- herramientas, por categorías ---- */
const TOOL_META = {
  edit: { label: 'Editar PDF', c: '#e8567f', d: 'Edita textos, imágenes, formas y formularios, y busca dentro del documento.' },
  scanner: { label: 'Escáner', c: '#16b0a0', d: 'Convierte fotos de documentos (DNI, pasaporte, folios) en escaneos limpios con OCR.' },
  pages: { label: 'Páginas', c: '#5fb85a', d: 'Reordena, gira, extrae, numera y divide páginas.' },
  merge: { label: 'Unir PDFs', c: '#8b7cf0', d: 'Une PDFs e imágenes en un solo documento.' },
  convert: { label: 'Comprimir y convertir', c: '#1fb6c4', d: 'Comprime y convierte entre PDF, imágenes y Word.' },
  sign: { label: 'Firma digital', c: '#a259e6', d: 'Firma con certificado o DNIe, varios firmantes y comprobación de firmas.' },
  library: { label: 'Visor PDF', c: '#3b82f6', d: 'Abre muchos PDFs a la vez y busca en todos.' },
  compare: { label: 'Comparar versiones', c: '#d95bb0', d: 'Muestra lo quitado y lo añadido entre dos versiones.' },
  watermark: { label: 'Proteger documentación sensible', c: '#3f8ef0', d: 'Marca de agua, ocultar datos de DNI y rastreo de cada copia.' },
  redact: { label: 'Censurar', c: '#ee5a5a', d: 'Tapa datos sensibles de forma irreversible.' },
  protect: { label: 'Contraseña', c: '#6f7ff0', d: 'Cifra un PDF con contraseña y permisos.' },
  sanitize: { label: 'Limpiar metadatos', c: '#f0a030', d: 'Quita metadatos de PDF, imágenes y documentos Office.' },
};
const TOOL_GROUPS = [
  { title: 'Crear y editar', tools: ['edit', 'scanner', 'pages', 'merge', 'convert'] },
  { title: 'Firmar y revisar', tools: ['sign', 'library', 'compare'] },
  { title: 'Proteger y normalizar', tools: ['watermark', 'redact', 'protect', 'sanitize'] },
];
const HOME_FAVS = ['edit', 'sign', 'watermark', 'scanner', 'merge', 'redact'];

const plain = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const tcolor = name => `--c:${TOOL_META[name].c}`;

const Shell = {
  view: 'home',
  theme: 'auto',

  init() {
    this.buildPanel();
    this.buildTools();
    this.buildHome();
    this.initTopbar();
    this.initPanelToggle();
    this.initTheme();
    $$('[data-ic]').forEach(el => { el.innerHTML = uiIcon(el.dataset.ic, 16); });
    this.renderDocs();
  },

  /* ---- panel de herramientas (derecha) ---- */
  buildPanel() {
    const list = $('.nav-list');
    TOOL_GROUPS.forEach((g, i) => {
      if (i) list.append(h('div', { class: 'nav-sep' }));
      for (const t of g.tools) {
        list.append(h('button', { 'data-tool': t, title: TOOL_META[t].d, style: tcolor(t) },
          h('span', { class: 'ic', innerHTML: toolIcon(t, 22) }), h('span', { class: 'lb' }, TOOL_META[t].label)));
      }
    });
  },

  /* ---- vista «Herramientas» ---- */
  buildTools() {
    const root = $('#tool-tools');
    const search = h('input', { type: 'search', placeholder: 'Buscar herramientas…', 'aria-label': 'Buscar herramientas' });
    const empty = h('p', { class: 'muted tl-empty', hidden: true }, 'Ninguna herramienta coincide con la búsqueda.');
    const sections = TOOL_GROUPS.map(g => h('section', { class: 'tl-group' },
      h('h2', {}, g.title),
      h('div', { class: 'tl-grid' }, g.tools.map(t => this.tile(t)))));
    root.append(
      h('div', { class: 'tl-bar' }, h('div', { class: 'tl-search' }, h('span', { class: 'si', innerHTML: uiIcon('search', 18) }), search)),
      h('div', { class: 'tl-body' }, sections, empty));
    search.addEventListener('input', () => {
      const q = plain(search.value.trim());
      let any = false;
      sections.forEach(sec => {
        let n = 0;
        $$('.tl-tile', sec).forEach(el => {
          const m = TOOL_META[el.dataset.tool];
          const hit = !q || plain(m.label + ' ' + m.d).includes(q);
          el.hidden = !hit;
          if (hit) n++;
        });
        sec.hidden = !n;
        if (n) any = true;
      });
      empty.hidden = any;
    });
    search.addEventListener('keydown', e => {
      if (e.key !== 'Enter') return;
      const first = $('.tl-tile:not([hidden])', root);
      if (first) showTool(first.dataset.tool);
    });
  },

  tile(t) {
    const m = TOOL_META[t];
    return h('div', { class: 'tl-tile', 'data-tool': t, style: tcolor(t), title: m.d, tabindex: 0, role: 'button',
      onclick: () => showTool(t), onkeydown: e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); showTool(t); } } },
    h('div', { class: 'tl-ic', innerHTML: toolIcon(t, 52, 1.1) }),
    h('div', { class: 'tl-name' }, m.label),
    h('button', { class: 'tl-open', tabindex: -1, onclick: e => { e.stopPropagation(); showTool(t); } }, 'Abrir'));
  },

  /* ---- vista «Inicio» ---- */
  buildHome() {
    const root = $('#tool-home');
    this.recentBox = h('div', { class: 'hm-docs' });
    const drop = h('div', { class: 'hm-drop', onclick: () => this.openFiles() },
      h('div', { class: 'hm-drop-ic', innerHTML: uiIcon('upload', 30) }),
      h('div', { class: 'hm-drop-tx' }, h('h2', {}, 'Abre un documento'),
        h('p', {}, 'Arrastra aquí un PDF o una imagen, o elígelo en tu equipo. Se abre en el Visor PDF.')),
      h('div', { class: 'hm-drop-btns' },
        h('button', { class: 'primary', onclick: e => { e.stopPropagation(); this.openFiles(); } }, 'Abrir archivo…'),
        h('button', { onclick: e => { e.stopPropagation(); Files.toggle(true); } }, 'Explorar carpetas')));
    dropTarget(drop, files => this.openFiles(files));
    this.docsBox = h('div', { class: 'hm-docs' });
    root.append(h('div', { class: 'hm-body' },
      h('div', { class: 'hm-hero' }, h('h1', {}, 'Bienvenido a DocGuard'),
        h('p', {}, h('span', { innerHTML: uiIcon('lock', 15) }), ' Todo se procesa en tu equipo. Ningún archivo sale de él.')),
      drop,
      h('h3', { class: 'hm-h' }, 'Tus herramientas'),
      h('div', { class: 'hm-favs' }, HOME_FAVS.map(t => h('div', { class: 'hm-fav', style: tcolor(t), tabindex: 0, role: 'button',
        onclick: () => showTool(t), onkeydown: e => { if (e.key === 'Enter') showTool(t); } },
      h('div', { class: 'hm-fav-ic', innerHTML: toolIcon(t, 34, 1.15) }),
      h('div', {}, h('b', {}, TOOL_META[t].label), h('small', {}, TOOL_META[t].d))))),
      h('div', { class: 'hm-more' }, h('button', { onclick: () => showTool('tools') }, 'Ver todas las herramientas')),
      h('h3', { class: 'hm-h' }, 'Recientes'),
      this.recentBox,
      h('h3', { class: 'hm-h' }, 'Documentos abiertos'),
      this.docsBox));
  },

  /** Archivos abiertos hace poco desde el explorador o con doble clic (los que siguen existiendo). */
  async refreshRecents() {
    const r = await api('recent').catch(() => null);
    if (!r) return;
    this.recentBox.replaceChildren(...(r.files.length
      ? r.files.map(f => h('div', { class: 'hm-doc', title: f.path, onclick: () => Files.openFile(f) },
        h('span', { class: 'hm-doc-ic', style: `--c:${FX_COLORS[f.kind]}`, innerHTML: fxIcon(f.kind, 20) }),
        h('span', { class: 'nm' }, f.name),
        h('small', { class: 'muted hm-folder' }, f.folder),
        h('small', { class: 'muted' }, new Date(f.mtime * 1000).toLocaleDateString())))
      : [h('p', { class: 'muted' }, 'Los archivos que abras desde el explorador aparecerán aquí.')]));
  },

  /** Abre un documento ya cargado en la herramienta actual (si edita documentos) o, si no, en el Visor PDF. */
  async openInfo(info) {
    info = await unlockInfo(info);
    if (!info?.pages?.length || info.encrypted) return toast(`${info?.name || 'El archivo'}: no se puede mostrar (con contraseña o formato no admitido).`, 'err');
    const k = Tabs.tools.includes(this.view) ? this.view : 'library';
    showTool(k);
    if (k === 'library') Library.openDoc(info); else TOOLS[k].loadInfo(info);
  },

  async openFiles(files) {
    files = files || await pickFiles(ACCEPT_DOCS, true);
    if (!files?.length) return;
    showTool('library');
    Library.add(files);
  },

  /* ---- barra superior ---- */
  initTopbar() {
    $$('.tb-tab').forEach(b => { b.onclick = () => showTool(b.dataset.view); });
    $('.tb-tab[data-view=home]').prepend(h('span', { class: 'tb-ic', innerHTML: uiIcon('home', 16) }));
    $('.tb-tab[data-view=tools]').prepend(h('span', { class: 'tb-ic', innerHTML: uiIcon('tools', 16) }));
    const filesBtn = $('[data-act=files]');
    filesBtn.innerHTML = uiIcon('folder', 18);
    filesBtn.onclick = () => Files.toggle();
    const menuBtn = $('[data-act=menu]'), menu = $('.tb-menu');
    menuBtn.innerHTML = uiIcon('more', 18);
    const close = () => { menu.hidden = true; };
    menuBtn.onclick = e => { e.stopPropagation(); menu.hidden = !menu.hidden; };
    menu.addEventListener('click', close);
    document.addEventListener('click', e => { if (!e.target.closest('.tb-menu-wrap')) close(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  },

  /** Se llama desde showTool: marca la pestaña, la herramienta actual y si el panel se ve. */
  onView(name) {
    this.view = name;
    document.body.dataset.view = name;
    $$('.tb-tab').forEach(b => b.classList.toggle('on', b.dataset.view === name));
    if (name === 'home') this.refreshRecents();
    const chip = $('.tb-chip'), m = TOOL_META[name];
    chip.hidden = !m;
    if (m) {
      chip.style.cssText = tcolor(name);
      chip.replaceChildren(h('span', { innerHTML: toolIcon(name, 18, 1.3) }), m.label);
    }
    this.renderDocs();
  },

  /** Pestañas de los documentos abiertos (arriba) y lista en Inicio. */
  renderDocs() {
    const list = (typeof Tabs !== 'undefined' && Tabs.list) || [];
    const activeTool = Tabs.tools?.includes(this.view) ? TOOLS[this.view] : null;
    const activeId = activeTool?.info?.id;
    const bar = $('#topdocs');
    if (bar) {
      const items = list.map(t => h('div', { class: 'tb-doc' + (t.id === activeId ? ' on' : ''), title: t.name, onclick: () => this.openDoc(t) },
        h('span', { class: 'tb-doc-ic', innerHTML: uiIcon('file', 15) }),
        h('span', { class: 'nm' }, (t.edited ? '● ' : '') + t.name),
        h('button', { class: 'x', title: 'Cerrar', onclick: e => { e.stopPropagation(); Tabs.close(t); }, innerHTML: uiIcon('close', 12) })));
      if (list.length) items.push(h('button', { class: 'tb-doc-add', title: 'Abrir otro documento', onclick: () => this.openFiles(), innerHTML: uiIcon('plus', 16) }));
      bar.replaceChildren(...items);
    }
    if (this.docsBox) {
      this.docsBox.replaceChildren(...(list.length
        ? list.map(t => h('div', { class: 'hm-doc', onclick: () => this.openDoc(t) },
          h('span', { class: 'hm-doc-ic', innerHTML: uiIcon('file', 20) }),
          h('span', { class: 'nm' }, t.name),
          t.edited ? h('span', { class: 'badge' }, 'Con cambios') : null,
          h('button', { class: 'x', title: 'Cerrar', onclick: e => { e.stopPropagation(); Tabs.close(t); }, innerHTML: uiIcon('close', 14) })))
        : [h('p', { class: 'muted' }, 'Todavía no hay documentos abiertos.')]));
    }
  },

  openDoc(t) {
    const k = Tabs.tools.includes(this.view) ? this.view : 'edit';
    showTool(k);
    Tabs.open(k, t.id);
  },

  /* ---- panel ocultable: se recuerda en la configuración de DocGuard ---- */
  initPanelToggle() {
    const nav = $('.nav'), tg = $('.nav-toggle');
    const set = (collapsed, save = true) => {
      nav.classList.toggle('collapsed', collapsed);
      tg.innerHTML = uiIcon(collapsed ? 'chevL' : 'chevR', 14);
      tg.title = collapsed ? 'Mostrar el panel de herramientas' : 'Ocultar el panel de herramientas';
      if (save) api('ui', { set: { nav_collapsed: collapsed } }).catch(() => {});
      requestAnimationFrame(() => TOOLS[this.view]?.viewer?.fit?.());
    };
    tg.onclick = () => set(!nav.classList.contains('collapsed'));
    api('ui', {}).then(ui => set(!!ui.nav_collapsed, false)).catch(() => set(false, false));
  },

  /* ---- tema: automático (el del sistema), claro u oscuro ---- */
  initTheme() {
    const btn = $('[data-act=theme]');
    const apply = (mode, save) => {
      this.theme = mode;
      if (mode === 'auto') document.documentElement.removeAttribute('data-theme');
      else document.documentElement.dataset.theme = mode;
      btn.innerHTML = uiIcon({ auto: 'auto', light: 'sun', dark: 'moon' }[mode], 18);
      btn.title = { auto: 'Tema: automático (el del sistema)', light: 'Tema: claro', dark: 'Tema: oscuro' }[mode] + ' — pulsa para cambiar';
      try { localStorage.setItem('dg_theme', mode); } catch (e) { /* sin almacenamiento */ }
      if (save) api('ui', { set: { theme: mode } }).catch(() => {});
    };
    let first = 'auto';
    try { first = localStorage.getItem('dg_theme') || 'auto'; } catch (e) { /* sin almacenamiento */ }
    apply(first, false);
    btn.onclick = () => apply({ auto: 'light', light: 'dark', dark: 'auto' }[this.theme], true);
    api('ui', {}).then(ui => { if (ui.theme && ui.theme !== this.theme) apply(ui.theme, false); }).catch(() => {});
  },
};
