'use strict';
// Lista de archivos con arrastrar y soltar y reordenación.

/* ======================================================================
   Listas de archivos
   ====================================================================== */

class FileList {
  constructor(el, { multiple = true, accept = '', onchange = null, onselect = null, hint = null } = {}) {
    Object.assign(this, { el, multiple, accept, onchange, onselect });
    this.items = []; this.cur = 0;
    this.hint = hint || (multiple ? 'Arrastra aquí los archivos o' : 'Arrastra aquí el archivo o');
    dropTarget(el, files => this.add(files));
    this.render();
  }
  async add(files) {
    if (!files.length) return;
    if (!this.multiple) files = files.slice(0, 1);
    const infos = [];
    busy(true, 'Abriendo…');
    try {
      for (const f of files) {
        try { infos.push(await uploadFile(f)); } catch (e) { toast(e.message, 'err'); }
      }
    } finally { busy(false); }
    this.items = this.multiple ? this.items.concat(infos) : infos;
    if (!this.multiple || this.items.length === infos.length) this.cur = 0;
    this.render();
    this.onchange?.(this.items);
    if (infos.length) this.onselect?.(this.items[this.cur]);
  }
  setItems(items) { this.items = items; this.cur = 0; this.render(); this.onchange?.(items); this.onselect?.(items[0]); }
  get current() { return this.items[this.cur]; }
  get ids() { return this.items.map(i => i.id); }
  render() {
    this.el.innerHTML = '';
    this.items.forEach((it, i) => {
      const row = h('div', { class: 'file' + (this.onselect && i === this.cur ? ' cur' : ''), draggable: true, title: it.name },
        h('span', { class: 'n' }, it.name), h('small', {}, kb(it.size)),
        this.multiple && h('button', { title: 'Subir', onclick: e => { e.stopPropagation(); this.move(i, i - 1); } }, '↑'),
        this.multiple && h('button', { title: 'Bajar', onclick: e => { e.stopPropagation(); this.move(i, i + 1); } }, '↓'),
        h('button', { title: 'Quitar', onclick: e => { e.stopPropagation(); this.remove(i); } }, '✕'));
      row.addEventListener('click', () => { if (this.onselect) { this.cur = i; this.render(); this.onselect(it); } });
      row.addEventListener('dragstart', e => e.dataTransfer.setData('text/x-idx', i));
      row.addEventListener('dragover', e => { if (e.dataTransfer.types.includes('text/x-idx')) e.preventDefault(); });
      row.addEventListener('drop', e => {
        const from = e.dataTransfer.getData('text/x-idx');
        if (from !== '') { e.preventDefault(); e.stopPropagation(); this.move(+from, i); }
      });
      this.el.append(row);
    });
    this.el.append(h('div', { class: 'hint' }, this.hint + ' ',
      h('button', { onclick: async () => this.add(await pickFiles(this.accept, this.multiple)) }, this.multiple ? 'Añadir archivos…' : 'Elegir archivo…')));
  }
  move(i, j) {
    if (j < 0 || j >= this.items.length || i === j) return;
    const [it] = this.items.splice(i, 1);
    this.items.splice(j, 0, it);
    this.cur = j;
    this.render();
    this.onchange?.(this.items);
  }
  remove(i) {
    const [it] = this.items.splice(i, 1);
    api('close', { id: it.id }).catch(() => {});
    this.cur = clamp(this.cur, 0, Math.max(0, this.items.length - 1));
    this.render();
    this.onchange?.(this.items);
    if (this.items.length) this.onselect?.(this.current); else this.onselect?.(null);
  }
}
