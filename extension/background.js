// Abre en DocGuard los PDF que el navegador iba a mostrar. Si DocGuard no responde,
// se deja el PDF en el visor del navegador, como siempre.
const DOCGUARD = 'https://localhost:47821/recibir-navegador';
const hecho = new Map();  // tabId -> url ya enviada (evita repetir)

async function activado() {
  const { on = true } = await chrome.storage.local.get('on');
  return on;
}

async function ponerBadge() {
  const on = await activado();
  chrome.action.setBadgeText({ text: on ? '' : 'off' });
  chrome.action.setTitle({ title: on ? 'DocGuard: abrir PDF (activado). Clic para desactivar' : 'DocGuard: abrir PDF (desactivado). Clic para activar' });
}

chrome.action.onClicked.addListener(async () => {
  await chrome.storage.local.set({ on: !(await activado()) });
  ponerBadge();
});
chrome.runtime.onStartup.addListener(ponerBadge);
chrome.runtime.onInstalled.addListener(ponerBadge);

function nombreDe(url) {
  try {
    const n = decodeURIComponent(new URL(url).pathname.split('/').pop() || '');
    return n.replace(/\.pdf$/i, '') || 'Documento';
  } catch { return 'Documento'; }
}

async function enviar(tabId, url) {
  if (hecho.get(tabId) === url) return;
  hecho.set(tabId, url);
  try {
    const r = await fetch(url, { credentials: 'include' });
    if (!r.ok) throw new Error('descarga');
    const datos = await r.arrayBuffer();
    if (new TextDecoder().decode(datos.slice(0, 4)) !== '%PDF') throw new Error('no es PDF');
    const res = await fetch(DOCGUARD, { method: 'POST', body: datos, headers: { 'X-Nombre': encodeURIComponent(nombreDe(url)) } });
    if (!res.ok) throw new Error('DocGuard');
    chrome.tabs.remove(tabId);  // abierto en DocGuard: se cierra la pestaña del navegador
  } catch (e) {
    hecho.delete(tabId);  // sin DocGuard (o error): se queda el visor del navegador
  }
}

function esPdf(det) {
  const tipo = (det.responseHeaders || []).find(h => h.name.toLowerCase() === 'content-type')?.value || '';
  const disp = (det.responseHeaders || []).find(h => h.name.toLowerCase() === 'content-disposition')?.value || '';
  if (/attachment/i.test(disp)) return false;  // descargas explícitas: no se tocan
  return /application\/pdf/i.test(tipo) || (/octet-stream/i.test(tipo) && /\.pdf(\?|#|$)/i.test(det.url));
}

chrome.webRequest.onHeadersReceived.addListener(async det => {
  if (det.statusCode !== 200 || det.tabId < 0 || det.url.startsWith('https://localhost:47821')) return;
  if (!esPdf(det) || !(await activado())) return;
  enviar(det.tabId, det.url);
}, { urls: ['http://*/*', 'https://*/*'], types: ['main_frame'] }, ['responseHeaders']);

// PDF locales (file://): solo si en la ficha de la extensión se permite el acceso a archivos
chrome.tabs.onUpdated.addListener(async (tabId, cambio, tab) => {
  if (cambio.status === 'loading' && tab.url?.startsWith('file://') && /\.pdf$/i.test(tab.url) && await activado()) enviar(tabId, tab.url);
});
chrome.tabs.onRemoved.addListener(id => hecho.delete(id));
