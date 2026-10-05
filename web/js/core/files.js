'use strict';
// Explorador de archivos del lateral izquierdo: carpetas, unidades, carpetas fijadas y apertura de PDFs e imágenes.

const FX_ICONS = {
  dir: '<path class="f" d="M3.5 7a2 2 0 012-2h4l2 2.5h7a2 2 0 012 2V17a2 2 0 01-2 2h-13a2 2 0 01-2-2z"/>',
  pdf: '<path class="f" d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14.5 3.5V8H19"/><path d="M9 14h6M9 17h4"/>',
  img: '<rect class="f" x="3.5" y="5" width="17" height="14" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M4 17l5-5 4 4 3-3 4 4"/>',
  drive: '<rect class="f" x="3.5" y="8.5" width="17" height="8" rx="2"/><path d="M3.5 12.5h17"/><circle cx="7" cy="14.5" r=".7" fill="currentColor"/>',
};
const FX_COLORS = { dir: '#e9a820', pdf: '#e8567f', img: '#16b0a0', drive: '#7a8499' };
const fxIcon = (kind, size = 20) => svg(FX_ICONS[kind] || '', size, 1.3);

const Files = {
  data: null,
  sel: -1,

  init() {
    this.root = $('.fx');
    const btn = (ic, title, fn) => h('button', { class: 'fx-btn', title, onclick: fn, innerHTML: uiIcon(ic, 16) });
    this.upBtn = btn('up', 'Carpeta superior (Retroceso)', () => this.up());
    this.pinBtn = btn('star', 'Fijar esta carpeta', () => this.togglePin());
    this.search = h('input', { type: 'search', placeholder: 'Filtrar esta carpeta…', 'aria-label': 'Filtrar esta carpeta' });
    this.places = h('div', { class: 'fx-places' });
    this.crumbs = h('div', { class: 'fx-crumbs' });
    this.list = h('div', { class: 'fx-list', tabindex: 0 });
    this.foot = h('div', { class: 'fx-foot' });
    this.root.append(
      h('div', { class: 'fx-head' }, h('b', {}, 'Archivos'), h('span', { class: 'grow' }),
        this.upBtn, btn('refresh', 'Actualizar', () => this.go(this.data?.path)), this.pinBtn,
        btn('close', 'Cerrar el explorador (Ctrl+Mayús+E)', () => this.toggle(false))),
      this.places, this.crumbs,
      h('div', { class: 'fx-search' }, this.search),
      this.list, this.foot);
    makeResizable(this.root, 'right', 'fx', 210, 520);
    this.search.addEventListener('input', () => { this.sel = -1; this.renderList(); });
    this.search.addEventListener('keydown', e => { if (e.key === 'ArrowDown') { e.preventDefault(); this.list.focus(); this.move(1); } });
    this.list.addEventListener('keydown', e => this.key(e));
    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'e') { e.preventDefault(); this.toggle(); }
    });
    api('ui', {}).then(ui => { if (ui.fx_open) this.toggle(true, false); }).catch(() => {});
  },

  toggle(on = this.root.hidden, save = true) {
    this.root.hidden = !on;
    $('[data-act=files]')?.classList.toggle('on', on);
    if (on && !this.data) this.go();
    if (save) api('ui', { set: { fx_open: on } }).catch(() => {});
    requestAnimationFrame(() => TOOLS[Shell.view]?.viewer?.fit?.());
  },

  async go(path) {
    const r = await api('fs/list', path === undefined || path === null ? {} : { path }).catch(e => { toast(e.message, 'err'); return null; });
    if (!r) return;
    this.data = r;
    this.search.value = '';
    this.sel = -1;
    this.render();
  },

  up() { if (this.data && this.data.parent !== null) this.go(this.data.parent); },

  async togglePin() {
    const d = this.data;
    if (!d?.path) return;
    const r = await api('fs/pin', { path: d.path, pin: !d.pinned }).catch(e => { toast(e.message, 'err'); return null; });
    if (!r) return;
    d.pins = r.pins;
    d.pinned = r.pinned;
    this.render();
  },

  same: (a, b) => (a || '').toLowerCase() === (b || '').toLowerCase(),

  render() {
    const d = this.data;
    const chip = (p, ic, label, cls = '') => h('button', { class: 'fx-chip ' + cls + (this.same(p.path, d.path) ? ' on' : ''), title: p.path, onclick: () => this.go(p.path) },
      ic ? h('span', { class: 'fx-chip-ic', innerHTML: ic }) : null, label);
    this.places.replaceChildren(
      ...d.places.map(p => chip(p, '', p.name)),
      ...d.pins.map(p => chip(p, uiIcon('starFill', 12), p.name, 'pin')),
      ...d.drives.map(p => chip(p, '', p.name, 'drv')));
    this.crumbs.replaceChildren(...d.crumbs.flatMap((c, i) => [
      i ? h('span', { class: 'fx-sep' }, '›') : null,
      h('button', { class: 'fx-crumb' + (i === d.crumbs.length - 1 ? ' last' : ''), title: c.path || 'Este equipo', onclick: () => this.go(c.path) }, c.name),
    ]).filter(Boolean));
    this.crumbs.scrollLeft = this.crumbs.scrollWidth;
    this.upBtn.disabled = d.parent === null;
    this.pinBtn.disabled = !d.path;
    this.pinBtn.innerHTML = uiIcon(d.pinned ? 'starFill' : 'star', 16);
    this.pinBtn.title = d.pinned ? 'Quitar de las carpetas fijadas' : 'Fijar esta carpeta';
    this.renderList();
  },

  shown() {
    const q = plain(this.search.value.trim());
    return this.data.entries.filter(e => !q || plain(e.name).includes(q));
  },

  renderList() {
    const items = this.shown();
    this.items = items;
    this.list.replaceChildren(...items.map((e, i) => {
      const meta = e.kind === 'dir' ? '' : kb(e.size);
      const when = e.mtime ? new Date(e.mtime * 1000).toLocaleDateString() : '';
      return h('div', { class: 'fx-row' + (i === this.sel ? ' sel' : ''), style: `--c:${FX_COLORS[e.name.length === 2 && e.name.endsWith(':') ? 'drive' : e.kind]}`,
        title: e.kind === 'dir' ? e.path : `${e.name}\n${meta} · ${when}`, onclick: () => { this.sel = i; this.activate(e); } },
      h('span', { class: 'fx-ic', innerHTML: fxIcon(e.name.length === 2 && e.name.endsWith(':') ? 'drive' : e.kind) }),
      h('span', { class: 'nm' }, e.name), meta ? h('small', {}, meta) : null);
    }));
    if (!items.length) this.list.append(h('p', { class: 'fx-empty muted' }, this.search.value ? 'Nada coincide con el filtro.' : 'Carpeta sin PDFs ni imágenes.'));
    const dirs = items.filter(e => e.kind === 'dir').length, files = items.length - dirs;
    this.foot.textContent = `${dirs} carpeta${dirs === 1 ? '' : 's'} · ${files} archivo${files === 1 ? '' : 's'}` + (this.data.truncated ? ' (lista recortada)' : '');
  },

  activate(e) {
    if (e.kind === 'dir') this.go(e.path);
    else this.openFile(e);
  },

  async openFile(e) {
    const info = await run('Abriendo…', () => api('fs/open', { path: e.path }));
    if (info) Shell.openInfo(info);
  },

  move(step) {
    if (!this.items?.length) return;
    this.sel = clamp((this.sel < 0 ? (step > 0 ? -1 : 0) : this.sel) + step, 0, this.items.length - 1);
    $$('.fx-row', this.list).forEach((r, i) => r.classList.toggle('sel', i === this.sel));
    $$('.fx-row', this.list)[this.sel]?.scrollIntoView({ block: 'nearest' });
  },

  key(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); this.move(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); this.move(-1); }
    else if (e.key === 'Enter' && this.items?.[this.sel]) { e.preventDefault(); this.activate(this.items[this.sel]); }
    else if (e.key === 'Backspace') { e.preventDefault(); this.up(); }
  },
};
