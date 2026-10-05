'use strict';
// Botón «Exportar a DocGuard» de Word: pide a Word el documento en PDF (por trozos) y lo envía a
// DocGuard, que lo abre en el Visor. Lo sirve el propio DocGuard en https://localhost:47821.

/** Muestra un aviso en una ventanita de Word (los botones de la cinta no tienen otra forma). */
function avisar(texto) {
  const url = location.origin + '/aviso.html?m=' + encodeURIComponent(texto);
  try { Office.context.ui.displayDialogAsync(url, { height: 25, width: 30, displayInIframe: true }); } catch (e) { console.log(texto); }
}

function leerPdf() {
  return new Promise((resolve, reject) => {
    Office.context.document.getFileAsync(Office.FileType.Pdf, { sliceSize: 4 * 1024 * 1024 }, res => {
      if (res.status !== Office.AsyncResultStatus.Succeeded) return reject(res.error);
      const file = res.value;
      const partes = [];
      let i = 0;
      const siguiente = () => file.getSliceAsync(i, r => {
        if (r.status !== Office.AsyncResultStatus.Succeeded) { file.closeAsync(); return reject(r.error); }
        partes.push(new Uint8Array(r.value.data));
        i += 1;
        if (i < file.sliceCount) siguiente();
        else { file.closeAsync(); resolve(new Blob(partes, { type: 'application/pdf' })); }
      });
      siguiente();
    });
  });
}

function nombreDocumento() {
  const url = Office.context.document.url || '';
  const nombre = decodeURIComponent(url.split(/[\\/]/).pop() || '');
  return nombre.replace(/\.(docx?|rtf|odt)$/i, '') || 'Documento de Word';
}

async function exportarADocGuard(event) {
  try {
    const pdf = await leerPdf();
    const r = await fetch('/recibir', { method: 'POST', body: pdf, headers: { 'X-Nombre': encodeURIComponent(nombreDocumento()) } });
    if (!r.ok) throw new Error(await r.text());
    avisar('Enviado a DocGuard: se ha abierto en su Visor PDF.');
  } catch (e) {
    avisar('No se pudo enviar a DocGuard: ' + (e && e.message ? e.message : e) + '. Comprueba que DocGuard está abierto.');
  }
  event.completed();
}

Office.onReady(() => {
  if (Office.actions && Office.actions.associate) Office.actions.associate('exportarADocGuard', exportarADocGuard);
});
window.exportarADocGuard = exportarADocGuard;
