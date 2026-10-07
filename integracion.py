"""Integración de DocGuard con otros programas:

  - Mac: «Abrir en DocGuard» en el menú «PDF» del diálogo de imprimir (Word y cualquier programa).
  - Windows: «Enviar a → DocGuard» al pulsar con el botón derecho sobre un archivo.
  - Word (Mac y Windows): botón «Exportar a DocGuard» en la cinta (complemento de Office). Word
    convierte el documento a PDF y lo envía a DocGuard por https://localhost:47821, con un
    certificado propio que hay que aceptar una vez.

Todo es solo para el usuario actual y se puede quitar."""

import datetime
import os
import ssl
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import core

PORT = 47821
ORIGIN = f"https://localhost:{PORT}"
ADDIN_ID = "6f1d2c47-8a3b-4e5d-9c21-0d6b7e4a9f13"
PDF_SERVICE = "Abrir en DocGuard"


def _exe():
    """Ruta del programa (la .app en Mac, DocGuard.exe en Windows) o None desde el código."""
    if not getattr(sys, "frozen", False):
        return None
    exe = os.path.abspath(sys.executable)
    if sys.platform == "darwin":
        return exe.split(".app/")[0] + ".app" if ".app/" in exe else None
    return exe


# --------------------------------------------------------------------------
# Mac: menú «PDF» del diálogo de imprimir
# --------------------------------------------------------------------------

def _pdf_services_dir():
    return os.path.expanduser("~/Library/PDF Services")


def mac_pdf_service(enable=True):
    """Crea (o quita) «Abrir en DocGuard» en el menú PDF de Imprimir. El script copia el PDF
    (el sistema borra el suyo al terminar) y lo abre con DocGuard."""
    if sys.platform != "darwin":
        return False
    path = os.path.join(_pdf_services_dir(), PDF_SERVICE)
    if not enable:
        if os.path.exists(path):
            os.remove(path)
        return True
    app = _exe() or "/Applications/DocGuard.app"
    os.makedirs(_pdf_services_dir(), exist_ok=True)
    script = f'''#!/bin/sh
# Creado por DocGuard: «{PDF_SERVICE}» en el menú PDF de Imprimir. Argumentos: título, opciones, PDF.
dir="$TMPDIR/DocGuard-impresos"
mkdir -p "$dir"
name=$(printf '%s' "$1" | tr -d '/:\\\\' | cut -c1-80)
[ -z "$name" ] && name="Documento"
dest="$dir/$name.pdf"
cp "$3" "$dest"
open -a "{app}" "$dest"
'''
    with open(path, "w") as f:
        f.write(script)
    os.chmod(path, 0o755)
    return True


def mac_pdf_service_status():
    return os.path.isfile(os.path.join(_pdf_services_dir(), PDF_SERVICE)) if sys.platform == "darwin" else None


# --------------------------------------------------------------------------
# Windows: «Enviar a»
# --------------------------------------------------------------------------

def _sendto_link():
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "SendTo", "DocGuard.lnk")


def windows_send_to(enable=True):
    """Crea (o quita) el acceso «DocGuard» en «Enviar a». Se rehace al abrir DocGuard, así que
    siempre apunta al DocGuard.exe actual."""
    if sys.platform != "win32":
        return False
    link = _sendto_link()
    if not enable:
        if os.path.exists(link):
            os.remove(link)
        return True
    exe = _exe()
    if not exe:
        return False
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LINK);"
          "$s.TargetPath=$env:EXE;$s.IconLocation=$env:EXE+',0';"
          "$s.Description='Abrir en DocGuard (los documentos de Word se convierten a PDF)';$s.Save()")
    env = dict(os.environ, LINK=link, EXE=exe)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, capture_output=True,
                   creationflags=0x08000000)
    return os.path.exists(link)


def windows_send_to_status():
    return os.path.exists(_sendto_link()) if sys.platform == "win32" else None


# --------------------------------------------------------------------------
# Word: complemento de Office con el botón «Exportar a DocGuard»
# --------------------------------------------------------------------------

def _office_dir():
    d = os.path.join(core.config_dir(), "office")
    os.makedirs(d, exist_ok=True)
    return d


def _cert_paths():
    d = _office_dir()
    return os.path.join(d, "localhost.pem"), os.path.join(d, "localhost.key"), os.path.join(d, "localhost.cer")


def _ensure_cert():
    """Certificado propio para https://localhost (10 años). Solo sirve en este equipo."""
    pem, key, cer = _cert_paths()
    if os.path.exists(pem) and os.path.exists(key):
        return pem, key, cer
    import ipaddress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "DocGuard localhost"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "DocGuard (solo este equipo)")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(k.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1)).not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"),
                                                        x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=True, key_cert_sign=True,
                                         content_commitment=False, data_encipherment=False, key_agreement=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(k, hashes.SHA256()))
    with open(key, "wb") as f:
        f.write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                serialization.NoEncryption()))
    with open(pem, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(cer, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.DER))
    return pem, key, cer


def _trust_cert(cer, pem):
    """Pide al sistema que confíe en el certificado (Mac: contraseña; Windows: un aviso de seguridad)."""
    if sys.platform == "darwin":
        r = subprocess.run(["security", "add-trusted-cert", "-r", "trustRoot", "-p", "ssl",
                            "-k", os.path.expanduser("~/Library/Keychains/login.keychain-db"), pem],
                           capture_output=True)
        return r.returncode == 0
    if sys.platform == "win32":
        r = subprocess.run(["certutil", "-user", "-addstore", "Root", cer], capture_output=True,
                           creationflags=0x08000000)
        return r.returncode == 0
    return False


def _untrust_cert(pem, cer):
    if sys.platform == "darwin":
        subprocess.run(["security", "remove-trusted-cert", pem], capture_output=True)
        subprocess.run(["security", "delete-certificate", "-c", "DocGuard localhost"], capture_output=True)
    elif sys.platform == "win32":
        subprocess.run(["certutil", "-user", "-delstore", "Root", "DocGuard localhost"], capture_output=True,
                       creationflags=0x08000000)


def _manifest_xml():
    with open(core.resource_path(os.path.join("web", "addin", "manifest.xml")), encoding="utf-8") as f:
        return f.read().replace("{ORIGIN}", ORIGIN).replace("{ID}", ADDIN_ID).replace("{VERSION}", core.VERSION + ".0.0")


def _mac_wef_dir():
    return os.path.expanduser("~/Library/Containers/com.microsoft.Word/Data/Documents/wef")


def _win_manifest_path():
    return os.path.join(_office_dir(), "DocGuard-Word.xml")


def word_addin(enable=True):
    """Instala (o quita) el botón «Exportar a DocGuard» en Word para este usuario."""
    pem, key, cer = _ensure_cert() if enable else _cert_paths()
    if not enable:
        if not browser_ext_status():
            _stop_listener()
            _autostart(False)
        if sys.platform == "darwin":
            p = os.path.join(_mac_wef_dir(), "DocGuard-Word.xml")
            if os.path.exists(p):
                os.remove(p)
        elif sys.platform == "win32":
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Office\16.0\WEF\Developer", 0,
                                    winreg.KEY_SET_VALUE) as k:
                    winreg.DeleteValue(k, ADDIN_ID)
            except OSError:
                pass
        if not browser_ext_status():
            _untrust_cert(pem, cer)
        return True
    if not _trust_cert(cer, pem):
        return False
    xml = _manifest_xml()
    if sys.platform == "darwin":
        os.makedirs(_mac_wef_dir(), exist_ok=True)
        with open(os.path.join(_mac_wef_dir(), "DocGuard-Word.xml"), "w", encoding="utf-8") as f:
            f.write(xml)
    elif sys.platform == "win32":
        import winreg
        with open(_win_manifest_path(), "w", encoding="utf-8") as f:
            f.write(xml)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Office\16.0\WEF\Developer") as k:
            winreg.SetValueEx(k, ADDIN_ID, 0, winreg.REG_SZ, _win_manifest_path())
    else:
        return False
    return True


def word_addin_status():
    if sys.platform == "darwin":
        return os.path.exists(os.path.join(_mac_wef_dir(), "DocGuard-Word.xml"))
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Office\16.0\WEF\Developer") as k:
                winreg.QueryValueEx(k, ADDIN_ID)
            return True
        except OSError:
            return False
    return None


# Navegador (Chrome/Edge): extensión que abre en DocGuard los PDF que el navegador iba a mostrar.
# Usa la misma escucha y el mismo certificado que el botón de Word.

def browser_ext_dir():
    return os.path.join(core.config_dir(), "extension-navegador")


def _browser_flag():
    return os.path.join(_office_dir(), "navegador.activo")


def browser_ext_status():
    return os.path.exists(_browser_flag())


def browser_ext(enable=True):
    """Activa (o quita) la recepción de PDF desde la extensión del navegador y deja la carpeta lista para cargarla."""
    import shutil
    pem, key, cer = _ensure_cert() if enable else _cert_paths()
    if not enable:
        try:
            os.remove(_browser_flag())
        except OSError:
            pass
        if not word_addin_status():
            _stop_listener()
            _autostart(False)
            _untrust_cert(pem, cer)
        return True
    if not _trust_cert(cer, pem):
        return False
    src = core.resource_path("extension")
    if os.path.isdir(src):
        shutil.rmtree(browser_ext_dir(), ignore_errors=True)
        shutil.copytree(src, browser_ext_dir())
    open(_browser_flag(), "w").close()
    return True


# ---- escucha del botón de Word ----
# Un proceso pequeño de DocGuard («DocGuard --escucha») arranca al iniciar sesión y atiende
# https://localhost:47821: sirve las páginas del complemento y recibe los PDF. Si DocGuard está
# abierto, se lo pasa a su ventana; si no, lo abre con el PDF.

_SERVER = {}
LISTENER_LABEL = "com.docguard.escucha"
RUN_VALUE = "DocGuard (botón de Word)"


def _open_file():
    return os.path.join(_office_dir(), "abierto.json")


def announce_open(url_with_token):
    """La ventana de DocGuard anuncia dónde recibir archivos mientras está abierta."""
    import json
    base, _, tok = url_with_token.partition("?t=")
    with open(_open_file(), "w") as f:
        json.dump({"url": base, "token": tok, "pid": os.getpid()}, f)


def announce_closed():
    try:
        os.remove(_open_file())
    except OSError:
        pass


def _deliver(path):
    """Abre el PDF en la ventana de DocGuard si está abierta; si no, abre DocGuard con él."""
    import json
    import urllib.request
    try:
        with open(_open_file()) as f:
            info = json.load(f)
        req = urllib.request.Request(info["url"] + "api/external/open", data=json.dumps({"path": path}).encode(),
                                     headers={"X-Token": info["token"], "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()
        return
    except Exception:
        pass
    app = _exe()
    if sys.platform == "darwin" and app:
        subprocess.Popen(["open", "-a", app, path])
    elif app:
        subprocess.Popen([app, path], creationflags=0x00000008)  # separado de la escucha
    else:  # desde el código
        subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py"), path])


def _listener_cmd():
    if getattr(sys, "frozen", False):
        return [os.path.abspath(sys.executable), "--escucha"]
    return [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py"), "--escucha"]


def _listener_version():
    """Versión de la escucha que esté en marcha, o None."""
    import urllib.request
    pem = _cert_paths()[0]
    try:
        ctx = ssl.create_default_context(cafile=pem)
        with urllib.request.urlopen(ORIGIN + "/version", context=ctx, timeout=2) as r:
            return r.read().decode().strip()
    except Exception:
        return None


def _stop_listener():
    import urllib.request
    try:
        ctx = ssl.create_default_context(cafile=_cert_paths()[0])
        urllib.request.urlopen(urllib.request.Request(ORIGIN + "/salir", data=b"", headers={"Origin": ORIGIN}),
                               context=ctx, timeout=2).read()
    except Exception:
        pass


def _autostart(enable):
    """Arranque de la escucha al iniciar sesión (solo este usuario, sin permisos)."""
    cmd = _listener_cmd()
    if sys.platform == "darwin":
        import plistlib
        plist = os.path.expanduser(f"~/Library/LaunchAgents/{LISTENER_LABEL}.plist")
        uid = str(os.getuid())
        subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LISTENER_LABEL}"], capture_output=True)
        if not enable:
            if os.path.exists(plist):
                os.remove(plist)
            return
        os.makedirs(os.path.dirname(plist), exist_ok=True)
        with open(plist, "wb") as f:
            plistlib.dump({"Label": LISTENER_LABEL, "ProgramArguments": cmd, "RunAtLoad": True,
                           "ProcessType": "Background", "LimitLoadToSessionType": "Aqua"}, f)
        subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", plist], capture_output=True)
    elif sys.platform == "win32":
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
            if enable:
                winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, " ".join(f'"{c}"' if " " in c else c for c in cmd))
            else:
                try:
                    winreg.DeleteValue(k, RUN_VALUE)
                except OSError:
                    pass


def ensure_listener():
    """Deja la escucha en marcha con la versión actual de DocGuard (y su arranque al iniciar sesión)."""
    if not (word_addin_status() or browser_ext_status()):
        return False
    v = _listener_version()
    if v == core.VERSION:
        return True
    if v:
        _stop_listener()
        import time
        time.sleep(1)
    _autostart(True)
    if sys.platform == "win32" or _listener_version() is None:
        if sys.platform == "win32":
            subprocess.Popen(_listener_cmd(), creationflags=0x00000008 | 0x08000000)
        elif _listener_version() is None:
            subprocess.Popen(_listener_cmd(), start_new_session=True)
    return True


def run_listener():
    """Proceso «DocGuard --escucha»: atiende el botón de Word hasta que se le pide salir."""
    if not start_addin_server(_deliver):
        return
    _SERVER["stop"] = threading.Event()
    _SERVER["stop"].wait()


def start_addin_server(on_pdf):
    """Sirve las páginas del complemento y recibe los PDF que envía Word. on_pdf(ruta) los abre."""
    pem, key, _ = _cert_paths()
    if "httpd" in _SERVER or not (os.path.exists(pem) and os.path.exists(key)):
        return False
    root = core.resource_path(os.path.join("web", "addin"))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            name = urllib.parse.urlparse(self.path).path.lstrip("/") or "funciones.html"
            if name == "version":
                return self._send(200, core.VERSION.encode())
            if name == "manifest.xml":
                return self._send(200, _manifest_xml().encode(), "application/xml")
            path = os.path.normpath(os.path.join(root, name))
            if not path.startswith(os.path.normpath(root)) or not os.path.isfile(path):
                return self._send(404, b"no encontrado")
            ctype = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                     ".png": "image/png", ".xml": "application/xml"}.get(os.path.splitext(path)[1], "application/octet-stream")
            with open(path, "rb") as f:
                self._send(200, f.read(), ctype)

        def do_OPTIONS(self):  # permiso previo (CORS) de la extensión del navegador
            origin = self.headers.get("Origin") or ""
            self.send_response(204 if origin.startswith("chrome-extension://") else 403)
            if origin.startswith("chrome-extension://"):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Headers", "X-Nombre, Content-Type")
                self.send_header("Access-Control-Allow-Methods", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self):
            route = urllib.parse.urlparse(self.path).path
            origin = self.headers.get("Origin")
            if route == "/recibir-navegador":  # extensión de Chrome/Edge: solo si el usuario la activó
                if not (origin or "").startswith("chrome-extension://") or not browser_ext_status():
                    return self._send(403, b"origen no permitido")
                route = "/recibir"
            elif origin and origin != ORIGIN:  # solo las páginas del propio complemento
                return self._send(403, b"origen no permitido")
            if route == "/salir":
                self._send(200, b"adios")
                if "stop" in _SERVER:
                    threading.Thread(target=lambda: (_SERVER["httpd"].shutdown(), _SERVER["stop"].set()), daemon=True).start()
                return
            if route != "/recibir":
                return self._send(404)
            n = int(self.headers.get("Content-Length", 0))
            if not 0 < n <= 300 << 20:
                return self._send(400, b"tamano no valido")
            data = self.rfile.read(n)
            if not data.startswith(b"%PDF"):
                return self._send(400, b"no es un PDF")
            name = urllib.parse.unquote(self.headers.get("X-Nombre") or "Documento de Word")
            name = "".join(c for c in os.path.splitext(os.path.basename(name))[0] if c not in '\\/:*?"<>|')[:80] or "Documento"
            folder = os.path.join(tempfile.gettempdir(), "DocGuard-Word")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, name + ".pdf")
            with open(path, "wb") as f:
                f.write(data)
            threading.Thread(target=on_pdf, args=(path,), daemon=True).start()
            if (origin or "").startswith("chrome-extension://"):
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")
                return
            self._send(200, b"ok")

    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        return False  # ya hay una escucha en marcha
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(pem, key)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    _SERVER["httpd"] = httpd
    return True


# --------------------------------------------------------------------------

def status():
    return {"platform": sys.platform, "pdf_service": mac_pdf_service_status(),
            "send_to": windows_send_to_status(), "word": word_addin_status(), "browser": browser_ext_status(),
            "browser_dir": browser_ext_dir(), "frozen": bool(_exe())}


def refresh_at_startup():
    """Al abrirse: rehace los accesos que el usuario tenga activados (por si DocGuard cambió de carpeta)."""
    try:
        if sys.platform == "darwin" and mac_pdf_service_status():
            mac_pdf_service(True)
        if sys.platform == "win32" and windows_send_to_status():
            windows_send_to(True)
        ensure_listener()
    except Exception:
        pass

