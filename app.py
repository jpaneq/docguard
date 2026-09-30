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

    def email(self, path):
        """Abre un correo nuevo con el archivo adjunto (Mail en macOS, Outlook en Windows)."""
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Mail", path])
                return "mail"
            if sys.platform == "win32":
                import shutil
                outlook = shutil.which("outlook") or next((p for p in (
                    r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
                    r"C:\Program Files (x86)\Microsoft Office\root\Office16\OUTLOOK.EXE") if os.path.exists(p)), None)
                if outlook:
                    subprocess.Popen([outlook, "/a", path])
                    return "outlook"
        except Exception:
            pass
        self.reveal(path)
        return "reveal"

    def pick_folder(self):
        """Elige una carpeta (p. ej. para la copia automática del historial)."""
        import webview
        dialogs = getattr(webview, "FileDialog", None)
        r = webview.windows[0].create_file_dialog(dialogs.FOLDER if dialogs else webview.FOLDER_DIALOG)
        return (r if isinstance(r, str) else r[0]) if r else None

    def open_result(self, rid):
        """Abre un resultado (p. ej. el PDF de prueba de firma) con el programa predeterminado."""
        import tempfile
        files = server.RESULTS.get(rid)
        if not files:
            return None
        folder = tempfile.mkdtemp(prefix="docguard_")
        path = server.save_result_to(rid, folder, True)[0]
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
        return path

    def compose(self, url):
        """Abre un correo nuevo (mailto:) en el programa de correo predeterminado; no lo envía."""
        if not str(url).startswith("mailto:"):
            return False
        return webbrowser.open(url)

    def reveal(self, path):
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])


def _test_p12(cn="Autotest DocGuard"):
    """Certificado de prueba generado al vuelo (contraseña «x»)."""
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .sign(key, hashes.SHA256()))
    return pkcs12.serialize_key_and_certificates(b"t", key, cert, None, serialization.BestAvailableEncryption(b"x"))


def _selftest_signing(pdf):
    """Firma con un certificado de prueba generado al vuelo y comprueba la firma."""
    import signing
    out = signing.sign_pdf(pdf, _test_p12(), "x", page=0, view_rect=[300, 600, 540, 670], reason="autotest")
    r = signing.verify_pdf(out)
    return bool(r) and r[0]["intact"] and r[0]["valid"]


def _selftest_signed_copy(call, png):
    """Modo rápido con firma en la franja, contraseña y acuse de recibo; después «Comprobar una
    copia» debe reconocerla (huella exacta, rastreo y huella de las zonas ocultas) y validar las
    firmas, también cuando el destinatario ya ha firmado el acuse."""
    import base64
    import io

    import pymupdf as fitz
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers

    import signing
    p12 = _test_p12()
    info = call("open", raw=png, name="dni.png")
    params = {"text": "Solo para {destinatario}", "level": "reforzada", "strike": True, "mark": True, "autohide": True,
              "robust": True, "fingerprint": True, "labels": True, "notice": True, "maxside": "1600", "password": "clave",
              "qr": {"enabled": True, "recipient": "Autotest", "purpose": "prueba", "mode": "vcard", "pos": "auto", "size": 22},
              "hide": {info["id"]: {"0": [{"r": [0.08, 0.3, 0.45, 0.42], "k": "soporte"}, {"r": [0.55, 0.6, 0.9, 0.75], "k": "can"}]}}}
    res = call("wm/export", {"ids": [info["id"]], "params": params, "fmt": "pdf", "sign": {
        "source": "file", "p12": base64.b64encode(p12).decode(), "password": "x", "tsa": "", "ltv": False,
        "ack": True, "place": "band"}})
    ref, data = res["refs"][0], server.RESULTS[res["rid"]][0][1]
    doc = fitz.open("pdf", data)
    ok = bool(doc.needs_pass and doc.authenticate("clave")) and len(list(doc[0].widgets())) == 2
    ok = ok and doc[0].rect.height > max(i["bbox"][3] for i in doc[0].get_image_info()) + 5  # franja fuera de la imagen
    copy = call("open", raw=data, name="copia.pdf")
    r1 = call("wm/check", {"id": copy["id"]})
    ok = ok and r1.get("needs_password") and r1["file"] and r1["file"][0]["ref"] == ref and r1["file"][0]["exact"]
    r2 = call("wm/check", {"id": copy["id"], "password": "clave"})
    names = {m["name"] for f in r2["found"] if f["ref"] == ref for m in f["methods"]}
    ok = ok and {"Huella exacta del archivo", "Huella de las zonas ocultas"} <= names
    ok = ok and any(n.startswith("Rastreo reforzado") for n in names)
    ok = ok and len(r2["signatures"]) == 1 and r2["signatures"][0]["intact"] and r2["signatures"][0]["valid"]
    informe = server.RESULTS[call("wm/report", {"id": copy["id"]})["rid"]][0][1]  # informe en PDF (sin sello: sin red)
    ok = ok and ref in "".join(p.get_text() for p in fitz.open("pdf", informe))
    w = IncrementalPdfFileWriter(io.BytesIO(data))
    w.encrypt("clave")
    acuse = signers.PdfSigner(signers.PdfSignatureMetadata(field_name=signing.ACK_FIELD),
                              signer=signing._load_signer(_test_p12("Destinatario"), "x")).sign_pdf(w).getvalue()
    r3 = call("wm/check", {"id": call("open", raw=acuse, name="acuse.pdf")["id"], "password": "clave"})
    ok = ok and r3["file"] and r3["file"][0]["ref"] == ref and not r3["file"][0]["exact"]
    return bool(ok and len(r3["signatures"]) == 2 and all(x["intact"] and x["valid"] for x in r3["signatures"]))


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
    import base64 as _b64
    prueba = call("sign/test", {"source": "file", "p12": _b64.b64encode(_test_p12("Prueba de firma")).decode(), "password": "x"})
    checks["probar mi firma"] = bool(prueba["signature"]["intact"] and prueba["signature"]["valid"]
                                     and prueba["profile"]["subject"] == "Prueba de firma")
    import signing as _signing
    lote_ids = [call("open", raw=doc.tobytes(), name=f"lote{i}.pdf")["id"] for i in range(2)]
    lote = call("sign/batch", {"ids": lote_ids, "place": "margin_last", "source": "file", "password": "x",
                               "p12": _b64.b64encode(_test_p12("Lote")).decode()})
    firmados = server.RESULTS[lote["rid"]]
    checks["firma por lotes"] = len(firmados) == 2 and all(
        len(v := _signing.verify_pdf(b)) == 1 and v[0]["intact"] and v[0]["valid"] for _, b in firmados)
    import protect
    from PIL import Image
    card = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    out = protect.watermark(card, "Solo para prueba", level="maxima",
                            qr={"data": protect.qr_text("A", "B", "0000ABCD")}, mark="0000ABCD")
    checks["protección reforzada + QR + marca invisible"] = protect.detect_mark(out)[0] == "0000ABCD"
    import datetime as _dt
    ayer = (_dt.date.today() - _dt.timedelta(days=1)).strftime("%d/%m/%Y")
    from PIL import ImageDraw as _D
    retrato = Image.new("RGB", (1000, 630), (222, 230, 226))
    _d = _D.Draw(retrato)
    _d.rectangle((60, 120, 300, 440), fill=(170, 180, 200))
    _d.ellipse((120, 170, 240, 330), fill=(224, 172, 140))
    _d.rectangle((150, 320, 210, 380), fill=(224, 172, 140))
    import numpy as _np
    ruido = _np.random.default_rng(5).integers(-25, 25, (630, 1000, 3))  # textura: miles de colores distintos
    retrato = Image.fromarray(_np.clip(_np.asarray(retrato, dtype=int) + ruido, 0, 255).astype(_np.uint8))
    _oculta, _r = protect.obscure_photo(retrato, "pixel")
    _caja = _oculta.crop((int(_r[0] * 1000), int(_r[1] * 630), int(_r[2] * 1000), int(_r[3] * 630))) if _r else None
    checks["foto irreconocible"] = bool(_r and _r[0] < 0.12 and _r[2] > 0.24 and _r[1] < 0.27 and _r[3] > 0.6
                                        and len(_caja.getcolors(100000) or []) <= 7 * 12)  # solo bloques gruesos
    checks["caducidad de la copia"] = ("Válida hasta: 30/10/2099" in protect.qr_payload("vcard", "A", "B", "R", until="30/10/2099")
                                       and protect.until_date("2099-10-30") == "30/10/2099"
                                       and protect.expired(ayer) and not protect.expired("30/10/2099"))
    # reverso de DNI sintético (domicilio y MRZ)
    import idfields
    from PIL import ImageDraw
    back = Image.new("RGB", (1600, 1010), (225, 232, 228))
    dr = ImageDraw.Draw(back)
    import core as _core
    dr.text((80, 60), "DOMICILIO", font=_core.get_font(28), fill=(80, 80, 90))
    dr.text((80, 100), "C. EJEMPLO 12", font=_core.get_font(44), fill=(20, 20, 30))
    for i, l in enumerate(["IDESPCAA123456499999999R<<<<<<", "9003141F3107229ESP<<<<<<<<<<<6"]):
        dr.text((80, 700 + i * 90), l, font=_core.get_font(56), fill=(20, 20, 30))
    # rastreo reforzado y huella, con un historial temporal (no toca el del usuario)
    import tempfile as _tmp
    previo = os.environ.get("DOCGUARD_CONFIG")
    os.environ["DOCGUARD_CONFIG"] = _tmp.mkdtemp(prefix="dg_selftest_")
    try:
        ref = protect.register("autotest", "", "", "")
        zona = [{"r": [0.08, 0.3, 0.45, 0.42], "k": "soporte"}, {"r": [0.55, 0.6, 0.9, 0.75], "k": "can"}]
        prot = protect.watermark(card, "Solo para prueba", level="reforzada", hide=zona, ref=ref, mark=ref, lines=[],
                                 robust=True, fingerprint=True, hide_label="SOLO PARA PRUEBA")
        protect.register_fingerprint(ref, protect.LAST_HIDE)
        ids = protect.identify_robust(prot)
        fps = protect.match_fingerprint(prot)
        checks["rastreo reforzado + huella"] = bool(ids and ids[0][0] == ref and fps and fps[0]["ref"] == ref)
        buf = __import__("io").BytesIO()
        back.save(buf, "PNG")
        checks["copia firmada (franja, contraseña, acuse y comprobación)"] = _selftest_signed_copy(call, buf.getvalue())
        # historial: copia automática en una carpeta (temporal), exportar e importar uniendo huellas
        import json as _json
        import records
        carpeta = _tmp.mkdtemp(prefix="dg_copia_")
        call("registry/backup", {"folder": carpeta})
        ref_h = protect.register("Historial", "prueba", "", "")
        protect.update_registry(ref_h, sha256=["a" * 64])
        copia = _json.load(open(os.path.join(carpeta, "DocGuard_historial.json"), encoding="utf-8"))
        exportado = _json.loads(server.RESULTS[call("registry/export")["rid"]][0][1])
        exportado["entregas"][ref_h]["sha256"] = ["b" * 64]
        imp = call("registry/import", {"id": call("open", raw=_json.dumps(exportado).encode(), name="h.json")["id"]})
        checks["historial: copia, exportar e importar"] = (ref_h in copia["entregas"] and imp["merged"] >= 1
                                                           and set(protect.lookup(ref_h)["sha256"]) == {"a" * 64, "b" * 64})
        records.set_backup_folder("")
        # seguimiento: se envía con un recuadro pendiente y vuelve firmado por otra persona
        contrato = _signing.add_signature_fields(doc.tobytes(), [{"name": "Yo", "page": 0, "rect": [60, 700, 260, 760]},
                                                                 {"name": "Otro", "page": 0, "rect": [330, 700, 530, 760]}])
        c_id = call("open", raw=contrato, name="contrato.pdf")["id"]
        enviado = server.RESULTS[call("sign", {"id": c_id, "source": "file", "password": "x", "field": "Yo", "track": True,
                                               "p12": _b64.b64encode(_test_p12("Yo")).decode()})["rid"]][0][1]
        vuelta = _signing.sign_pdf(enviado, _test_p12("Otro"), "x", field_name="Otro")
        seg = call("track/check", {"id": call("open", raw=vuelta, name="contrato_firmado.pdf")["id"]})
        checks["seguimiento de envíos a firmar"] = bool(seg["match"] and not seg["pending"] and len(seg["after"]) == 1
                                                        and seg["record"]["estado"] == "completo")
    finally:
        if previo is None:
            os.environ.pop("DOCGUARD_CONFIG", None)
        else:
            os.environ["DOCGUARD_CONFIG"] = previo
    kinds = {it["kind"] for it in idfields.detect(back)["items"]}
    # escáner: una tarjeta clara fotografiada sobre fondo oscuro
    import scan
    from PIL import ImageDraw as _ID
    foto = Image.new("RGB", (1200, 900), (60, 45, 35))
    _ID.Draw(foto).polygon([(250, 200), (950, 160), (1000, 640), (220, 700)], fill=(225, 232, 238))
    q, _c = scan.detect_quad(foto)
    esperado = [(250, 200), (950, 160), (1000, 640), (220, 700)]
    checks["escáner (bordes y perspectiva)"] = all(abs(x * 1200 - ex) < 15 and abs(y * 900 - ey) < 15
                                                    for (x, y), (ex, ey) in zip(q, esperado))
    import tempfile as _tf
    import convert
    with _tf.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "a.pdf")
        doc.save(src)
        convert.pdf_to_docx(src, os.path.join(tmp, "a.docx"))
        convert.document_to_pdf(os.path.join(tmp, "a.docx"), os.path.join(tmp, "b.pdf"))
        checks["conversión PDF ↔ Word"] = "12345678Z" in fitz.open(os.path.join(tmp, "b.pdf"))[0].get_text()
    checks["detección DNI/pasaporte"] = {"mrz", "domicilio"} <= kinds
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
