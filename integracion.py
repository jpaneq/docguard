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


# ---- servidor https://localhost:47821 para el complemento ----

_SERVER = {}


def start_addin_server(on_pdf):
    """Sirve las páginas del complemento y recibe los PDF que envía Word. on_pdf(ruta) los abre.
    Solo arranca si el certificado ya existe (es decir, si se instaló el complemento)."""
    pem, key, _ = _cert_paths()
    if _SERVER or not (os.path.exists(pem) and os.path.exists(key)):
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
            if name == "manifest.xml":
                return self._send(200, _manifest_xml().encode(), "application/xml")
            path = os.path.normpath(os.path.join(root, name))
            if not path.startswith(os.path.normpath(root)) or not os.path.isfile(path):
                return self._send(404, b"no encontrado")
            ctype = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                     ".png": "image/png", ".xml": "application/xml"}.get(os.path.splitext(path)[1], "application/octet-stream")
            with open(path, "rb") as f:
                self._send(200, f.read(), ctype)

        def do_POST(self):
            if urllib.parse.urlparse(self.path).path != "/recibir":
                return self._send(404)
            origin = self.headers.get("Origin")
            if origin and origin != ORIGIN:  # solo las páginas del propio complemento
                return self._send(403, b"origen no permitido")
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
            self._send(200, b"ok")

    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        return False  # otra ventana de DocGuard ya lo tiene abierto
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(pem, key)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    _SERVER["httpd"] = httpd
    return True


# --------------------------------------------------------------------------

def status():
    return {"platform": sys.platform, "pdf_service": mac_pdf_service_status(),
            "send_to": windows_send_to_status(), "word": word_addin_status(), "frozen": bool(_exe())}


def refresh_at_startup():
    """Al abrirse: rehace los accesos que el usuario tenga activados (por si DocGuard cambió de carpeta)."""
    try:
        if sys.platform == "darwin" and mac_pdf_service_status():
            mac_pdf_service(True)
        if sys.platform == "win32" and windows_send_to_status():
            windows_send_to(True)
    except Exception:
        pass

