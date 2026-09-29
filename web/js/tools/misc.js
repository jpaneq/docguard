'use strict';
// Contraseña, Comprimir y convertir, Limpiar metadatos y Unir PDFs.

/* ======================================================================
   CONTRASEÑA, CONVERTIR, LIMPIAR, UNIR
   ====================================================================== */

const Protect = {
  init() {
    this.root = $('#tool-protect');
    this.files = new FileList($('[data-role=files]', this.root), {
      multiple: false, accept: ACCEPT_DOCS, onselect: info => { if (info) setCurrent(info); },
    });
    const k = n => $(`[data-k=${n}]`, this.root);
    $('[data-act=protect]', this.root).onclick = async () => {
      const f = this.files.current;
      if (!f) return toast('Elige primero un archivo.', 'err');
      if (!k('pw1').value) return toast('Escribe una contraseña.', 'err');
      if (k('pw1').value !== k('pw2').value) return toast('Las contraseñas no coinciden.', 'err');
      saveResult(await run('Cifrando…', () => api('encrypt', {
        id: f.id, user_pw: k('pw1').value, owner_pw: k('owner').value, print: k('print').checked, copy: k('copy').checked, edit: k('edit').checked,
      })));
    };
    $('[data-act=unprotect]', this.root).onclick = async () => {
      const f = this.files.current;
      if (!f) return toast('Elige primero un archivo.', 'err');
      saveResult(await run('Quitando la contraseña…', () => api('decrypt', { id: f.id, password: k('pwrm').value })));
    };
  },
  loadInfo(info) { this.files.setItems([info]); },
};

function batchTool(id, accept, handlers) {
  const root = $('#' + id);
  const files = new FileList($('[data-role=files]', root), { accept });
  for (const [act, fn] of Object.entries(handlers)) {
    $(`[data-act=${act}]`, root).onclick = async () => {
      if (!files.items.length) return toast('Añade algún archivo a la lista.', 'err');
      saveResult(await run('Procesando…', () => fn(files, root)));
    };
  }
  return { files, loadInfo: info => files.setItems([info]) };
}
