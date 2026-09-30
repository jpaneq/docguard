"""Escanear con el móvil: un servidor temporal, aparte del de la aplicación, que solo escucha
en la dirección de la red local (la wifi de casa) y solo sabe recibir fotos.

- Enlace con una clave aleatoria larga (no se puede adivinar) que caduca a los 10 minutos o
  al cerrar la ventana; cualquier otra dirección responde «no encontrado».
- Solo admite fotos JPG o PNG, de hasta 25 MB y un máximo de 40 por sesión.
- Nunca expone la API de DocGuard ni su clave: las fotos se quedan en una bandeja que la
  aplicación recoge.
- Va por HTTP en la red local: la foto no pasa por internet, pero viaja sin cifrar por la
  wifi. Por eso se avisa de usarlo solo en una red de confianza."""

import ipaddress
import re
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LIFETIME = 600
MAX_BYTES = 25 * 1024 * 1024
MAX_PHOTOS = 40

PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>DocGuard · Escanear</title>
<style>
  body { margin: 0; font: 17px/1.45 -apple-system, system-ui, sans-serif; background: #f4f5f8; color: #1b2130; padding: 22px; }
  h1 { font-size: 22px; margin: 0 0 6px; }
  .btn { display: block; text-align: center; background: #2563d9; color: #fff; border-radius: 14px; padding: 18px; font-size: 20px; font-weight: 600; margin: 18px 0; }
  #st { font-weight: 600; min-height: 1.4em; }
  #th img { width: 31%; margin: 1%; border-radius: 6px; }
  .note { color: #6b7385; font-size: 14px; }
</style></head><body>
<h1>DocGuard · Escanear</h1>
<p>Haz una foto del documento: llegará a tu ordenador por tu wifi, sin pasar por internet.</p>
<label class="btn">📷 Hacer foto<input id="f" type="file" accept="image/jpeg,image/png,image/*" capture="environment" multiple hidden></label>
<p id="st"></p><div id="th"></div>
<p class="note">Úsalo solo en tu wifi de casa: la foto viaja por la red local sin cifrar. Este enlace caduca a los 10 minutos.</p>
<script>
  const st = document.getElementById('st'), th = document.getElementById('th');
  let n = 0;
  document.getElementById('f').onchange = async e => {
    for (const file of e.target.files) {
      st.textContent = 'Enviando…';
      try {
        const r = await fetch(location.pathname + '/subir', { method: 'POST', body: file,
          headers: { 'X-Nombre': encodeURIComponent(file.name || 'foto.jpg') } });
        if (!r.ok) { st.textContent = '✘ ' + await r.text(); continue; }
        n++;
        const img = new Image();
        img.src = URL.createObjectURL(file);
        th.prepend(img);
        st.textContent = '✔ ' + n + ' foto(s) enviada(s). Puedes hacer otra.';
      } catch (err) { st.textContent = '✘ No se ha podido enviar. ¿Sigue abierta la ventana en el ordenador?'; }
    }
    e.target.value = '';
  };
</script></body></html>"""


def lan_ip():
    """Dirección de este equipo en la red local (sin enviar nada)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except OSError:
        ip = None
    finally:
        s.close()
    if not ip or ip.startswith("127."):
        raise ValueError("Este equipo no está conectado a una red local (wifi).")
    if not ipaddress.ip_address(ip).is_private:
        raise ValueError("Este equipo no está en una red privada: por seguridad no se activa.")
    return ip


def _name(raw, data):
    ext = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
    base = re.sub(r"[^\w\- ]", "", re.sub(r"\.[A-Za-z0-9]+$", "", raw or ""))[:40].strip() or "foto_movil"
    return base + ext


class Session:
    def __init__(self):
        self.token = secrets.token_urlsafe(24)
        self.inbox, self.count = [], 0
        self.lock = threading.Lock()
        self.expires = time.time() + LIFETIME
        self.stopped = False
        ip = lan_ip()
        self.httpd = ThreadingHTTPServer((ip, 0), _handler(self))
        self.httpd.daemon_threads = True
        self.url = f"http://{ip}:{self.httpd.server_address[1]}/m/{self.token}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.timer = threading.Timer(LIFETIME, self.stop)
        self.timer.daemon = True
        self.timer.start()

    @property
    def alive(self):
        return not self.stopped and time.time() < self.expires

    def stop(self):
        if self.stopped:
            return
        self.stopped = True
        self.timer.cancel()
        threading.Thread(target=lambda: (self.httpd.shutdown(), self.httpd.server_close()), daemon=True).start()

    def take(self):
        with self.lock:
            items, self.inbox = self.inbox, []
        return items


def _handler(sess):
    page_path, upload_path = f"/m/{sess.token}", f"/m/{sess.token}/subir"

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; img-src blob:; style-src 'unsafe-inline'; "
                                                        "script-src 'unsafe-inline'; connect-src 'self'")
            if code != 200:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not sess.alive or self.path.split("?")[0] != page_path:
                return self.send(404, "no encontrado")
            self.send(200, PAGE, "text/html; charset=utf-8")

        def do_POST(self):
            if not sess.alive or self.path != upload_path:
                return self.send(404, "no encontrado")
            try:
                size = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                size = 0
            if size <= 0 or size > MAX_BYTES:
                return self.send(413, "La foto es demasiado grande (máximo 25 MB).")
            with sess.lock:
                if sess.count >= MAX_PHOTOS:
                    return self.send(429, "Demasiadas fotos en esta sesión.")
            data = self.rfile.read(size)
            if not (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"):
                return self.send(415, "Solo se admiten fotos JPG o PNG.")
            from urllib.parse import unquote
            with sess.lock:
                sess.count += 1
                sess.inbox.append((_name(unquote(self.headers.get("X-Nombre", "")), data), data))
            self.send(200, "ok")

        def do_PUT(self):
            self.send(404, "no encontrado")

        do_DELETE = do_PUT

    return Handler
