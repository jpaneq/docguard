'use strict';
// Pestañas de documentos (Editar, Censurar y Firma digital) y ventanas. La lista la guarda el
// servidor, así que todas las ventanas de DocGuard ven los mismos documentos abiertos.

const Tabs = {
  tools: ['edit', 'redact', 'sign'],
  list: [],
  init() {
    for (const k of this.tools) $('#tool-' + k).prepend(h('div', { class: 'doc-tabs', hidden: true }));
    window.addEventListener('focus', () => this.refresh());
    setInterval(() => { if (document.hasFocus()) this.refresh(); }, 3000);
    document.addEventListener('keydown', e => {
      if ((e.metaKey || e.ctrlKey) && !e.shiftKey && e.key.toLowerCase() === 'n') { e.preventDefault(); this.newWindow(); }
    });
    const native = !!window.pywebview || 'pywebview' in window;
    $$('[data-win]').forEach(b => { b.onclick = () => (b.dataset.win === 'new' ? this.newWindow() : this.arrange(b.dataset.win)); });
    if (!native) $$('[data-win=mosaico],[data-win=cascada]').forEach(b => { b.hidden = true; });
    this.refresh();
  },
  newWindow() {
    if (window.pywebview?.api?.new_window) window.pywebview.api.new_window();
    else window.open(location.href, '_blank');
  },
  arrange(mode) { window.pywebview?.api?.arrange?.(mode); },
  async add(info) {
    if (!info?.id || !info.pages?.length) return;
    await api('tabs/add', { id: info.id }).catch(() => {});
    this.refresh();
  },
  async refresh() {
    const r = await api('tabs/list').catch(() => null);
    if (!r) return;
    this.list = r.tabs;
    this.render();
  },
  render() {
    for (const k of this.tools) {
      const bar = $('#tool-' + k + ' .doc-tabs');
      if (!bar) continue;
      const active = TOOLS[k]?.info?.id;
      bar.hidden = !this.list.length;
      bar.replaceChildren(...this.list.map(t => h('div', {
        class: 'doc-tab' + (t.id === active ? ' on' : ''), title: t.name, onclick: () => this.open(k, t.id),
      }, h('span', { class: 'nm' }, (t.edited ? '● ' : '') + t.name),
      h('button', { class: 'x', title: 'Cerrar', onclick: e => { e.stopPropagation(); this.close(t); } }, '✕'))),
      h('button', { class: 'doc-tab-add', title: 'Abrir otro documento', onclick: () => $(`#tool-${k} [data-act=open]`)?.click() }, '+'));
    }
  },
  async open(k, id) {
    const info = await run('Abriendo…', () => api('info', { id }));
    if (info) TOOLS[k].loadInfo(info);
    this.render();
  },
  async close(t) {
    if (t.edited && !(await confirmBox('Cerrar documento', `«${t.name}» tiene cambios sin guardar. ¿Cerrarlo de todos modos?`, 'Cerrar'))) return;
    await api('tabs/close', { id: t.id }).catch(() => {});
    await this.refresh();
    for (const k of this.tools) {
      const tool = TOOLS[k];
      if (tool?.info?.id !== t.id) continue;
      const next = this.list[0];
      if (next) await this.open(k, next.id);
      else this.empty(tool);
    }
    if (CURRENT?.id === t.id) clearCurrent();
    this.render();
  },
  /** Deja la herramienta sin documento. */
  empty(tool) {
    tool.info = null;
    tool.st = null;
    const v = tool.viewer;
    if (v) {
      v.info = null;
      v.empty.style.display = '';
      if (v._wrap) v._wrap.style.display = 'none';
      if (v.stack) v.stack.innerHTML = '';
      if (v.bar) v.bar.style.display = 'none';
    }
    const dn = $('.doc-name', tool.root);
    if (dn) dn.textContent = '';
    tool.draw?.();
  },
};
