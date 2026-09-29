"""DocGuard V1: abre la interfaz web en una ventana nativa (o en el navegador).

  DocGuard              ventana nativa (pywebview)
  DocGuard --browser    usa el navegador predeterminado
  DocGuard --selftest   comprueba el funcionamiento sin abrir ventana
"""

import os
import subprocess
import sys
import time
import webbrowser

import server


class Api:
    """Funciones que la interfaz puede llamar dentro de la ventana nativa."""

    def save_result(self, rid):
        import webview
        files = server.RESULTS.get(rid)
        if not files:
            return None
        win = webview.windows[0]
        dialogs = getattr(webview, "FileDialog", None)
        save_t = dialogs.SAVE if dialogs else webview.SAVE_DIALOG
        folder_t = dialogs.FOLDER if dialogs else webview.FOLDER_DIALOG
        if len(files) == 1:
            r = win.create_file_dialog(save_t, save_filename=files[0][0])
            folder = False
        else:
            r = win.create_file_dialog(folder_t)
            folder = True
        if not r:
            return None
        target = r if isinstance(r, str) else r[0]
        return server.save_result_to(rid, target, folder)

    def reveal(self, path):
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])


def _selftest_signing(pdf):
    """Firma con un certificado de prueba generado al vuelo y comprueba la firma."""
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    import signing
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Autotest DocGuard")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    p12 = pkcs12.serialize_key_and_certificates(b"t", key, cert, None, serialization.BestAvailableEncryption(b"x"))
    out = signing.sign_pdf(pdf, p12, "x", page=0, view_rect=[300, 600, 540, 670], reason="autotest")
    r = signing.verify_pdf(out)
    return bool(r) and r[0]["intact"] and r[0]["valid"]


def selftest():
    import base64
    import json
    import urllib.request

    import pymupdf as fitz

    import core
    url, httpd = server.start()
    base = url.split("/?")[0]

    def call(op, payload=None, raw=None, name=None):
        data = raw if raw is not None else json.dumps(payload or {}).encode()
        req = urllib.request.Request(f"{base}/api/{op}", data=data, method="POST",
                                     headers={"X-Token": server.TOKEN, **({"X-Filename": name} if name else {})})
        with urllib.request.urlopen(req) as r:
            body = r.read()
            return json.loads(body) if r.headers.get_content_type() == "application/json" else body

    doc = fitz.open()
    doc.new_page().insert_text((50, 80), "DNI 12345678Z", fontsize=14)
    info = call("open", raw=doc.tobytes(), name="prueba.pdf")
    checks = {
        "abrir": info["pages"] == [[595.0, 842.0]],
        "marca de agua": call("wm/preview", {"id": info["id"], "n": 0, "params": {"text": "x"}})[:2] == b"\xff\xd8",
        "detección": "DNI / NIE" in call("detect", {"id": info["id"]})["found"],
        "edición": call("edit/state", {"id": info["id"], "n": 0})["spans"][0]["text"] == "DNI 12345678Z",
    }
    pix = doc[0].get_pixmap(dpi=200)
    scan = call("open", raw=pix.tobytes("png"), name="scan.png")
    call("ocr", {"id": scan["id"], "n": 0})
    checks["OCR"] = "DNI / NIE" in call("detect", {"id": scan["id"]})["found"]
    checks["firma digital"] = _selftest_signing(doc.tobytes())
    try:
        import pkcs11  # noqa: F401
        import signing
        signing.pkcs11_modules()
        checks["DNIe / PKCS#11"] = True
    except Exception:
        checks["DNIe / PKCS#11"] = False
    httpd.shutdown()
    for k, v in checks.items():
        print(f"{'OK ' if v else 'FALLO'} {k}")
    return all(checks.values())


def main():
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)
    url, httpd = server.start()
    if "--browser" not in sys.argv:
        try:
            import webview
            webview.create_window("DocGuard", url, js_api=Api(), width=1320, height=880, min_size=(900, 600))
            webview.start()
            return
        except Exception as ex:  # sin ventana nativa: se usa el navegador
            print("Ventana nativa no disponible, se abre el navegador:", ex)
    webbrowser.open(url)
    print("DocGuard funcionando en", url, "(Ctrl+C para salir)")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
