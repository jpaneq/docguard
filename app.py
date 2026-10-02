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


APP_URL = None  # dirección de la interfaz (con su clave): la comparten todas las ventanas


def make_window(x=None, y=None, width=1320, height=880):
    """Abre una ventana de DocGuard. Todas usan el mismo servidor: comparten documentos y pestañas."""
    import webview
    win = webview.create_window("DocGuard", APP_URL, js_api=Api(), width=width, height=height, x=x, y=y,
                                min_size=(700, 450))
    if sys.platform == "win32":
        def repaint():  # fuerza a WebView2 a repintar cuando la interfaz ya ha cargado
            win.resize(win.width + 1, win.height)
            win.resize(win.width - 1, win.height)
        win.events.loaded += repaint
    return win


def _screen():
    import webview
    sc = webview.screens[0] if webview.screens else None
    return (sc.width, sc.height) if sc else (1440, 900)


def new_window():
    import webview
    n = len(webview.windows)
    make_window(x=60 + 30 * n, y=60 + 30 * n)


def arrange(mode="mosaico"):
    """Coloca las ventanas en mosaico (repartidas por la pantalla) o en cascada."""
    import math

    import webview
    wins = list(webview.windows)
    if not wins:
        return
    W, H = _screen()
    top = 25 if sys.platform == "darwin" else 0  # barra de menús del Mac
    if mode == "cascada":
        w, h = int(W * 0.7), int((H - top) * 0.8)
        for i, win in enumerate(wins):
            win.resize(w, h)
            win.move(30 + 32 * i, top + 10 + 32 * i)
        return
    cols = math.ceil(math.sqrt(len(wins)))
    rows = math.ceil(len(wins) / cols)
    w, h = W // cols, (H - top) // rows
    for i, win in enumerate(wins):
        win.resize(max(700, w), max(450, h))
        win.move((i % cols) * w, top + (i // cols) * h)


class Api:
    """Funciones que la interfaz puede llamar dentro de la ventana nativa."""

    def new_window(self):
        new_window()

    def restart_to_update(self):
        """Cierra DocGuard; un script instala la versión descargada y la vuelve a abrir."""
        import updater

        import webview
        if updater.apply_on_exit():
            for w in list(webview.windows):
                w.destroy()
            return True
        return False

    def arrange(self, mode):
        arrange(mode)

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


def _selftest_markup_objects():
    """Resaltar por líneas seleccionadas, cambiar el aspecto de una forma y copiar/pegar un campo."""
    import pymupdf as fitz

    import editor
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((72, 100), "Primera línea del contrato", fontsize=12)
    p.insert_text((72, 118), "Segunda línea del contrato", fontsize=12)
    w = editor.reading_words(doc[0])
    rect = lambda a, b: [w[a]["bbox"][0], w[a]["bbox"][1], w[b]["bbox"][2], w[b]["bbox"][3]]
    editor.add_markup(doc, 0, "highlight", [rect(2, 3), rect(4, 5)], "#39ff14")
    editor.add_markup(doc, 0, "underline", [rect(4, 7)], "#1a4fd6")
    editor.add_shape(doc, 0, "rect", [100, 400, 200, 480], dash="discontinua", width=3)
    shape = next(a for a in editor.annotations(doc[0]) if a.get("style"))
    editor.style_annotation(doc, 0, shape["xref"], stroke="#1a4fd6", fill="#ffe066", dash="punteada", opacity=0.6)
    style = next(a for a in editor.annotations(doc[0]) if a.get("style"))["style"]
    editor.add_widget(doc, 0, "text", [100, 200, 250, 224], "nombre", value="Ana")
    spec = editor.copy_object(doc, 0, "widget", editor.widgets(doc[0])[0]["xref"])
    editor.paste_object(doc, 0, spec, 300, 200)
    fields = {x["name"]: x["value"] for x in editor.widgets(doc[0])}
    kinds = [a["type"] for a in editor.annotations(doc[0])]
    return (kinds.count("Ink") == 4 and "Underline" in kinds and fields == {"nombre": "Ana", "nombre_2": "Ana"}
            and style == {"stroke": "#1a4fd6", "fill": "#ffe066", "width": 3.0, "dash": "punteada", "opacity": 0.6})


def _selftest_shapes():
    """Mover una forma no la agranda y los extremos de una flecha se cambian conservando su punta."""
    import pymupdf as fitz

    import editor
    doc = fitz.open()
    doc.new_page()
    editor.add_shape(doc, 0, "rect", [300, 400, 380, 480], width=4)
    editor.add_shape(doc, 0, "arrow", None, points=[[100, 100], [300, 200]], width=3)
    rect, arrow = editor.annotations(doc[0])
    for _ in range(3):
        b = next(a for a in editor.annotations(doc[0]) if a["type"] == "Square")["bbox"]
        editor.move_annotation(doc, 0, rect["xref"], [b[0] + 10, b[1], b[2] + 10, b[3]])
    moved = next(a for a in editor.annotations(doc[0]) if a["type"] == "Square")["bbox"]
    editor.set_line(doc, 0, arrow["xref"], [[100, 100], [100, 300]])
    page = doc[0]
    line = next(a for a in editor.annotations(page) if a["type"] == "Line")
    ends = page.load_annot(line["xref"]).line_ends
    same_size = abs((moved[2] - moved[0]) - (rect["bbox"][2] - rect["bbox"][0])) < 0.5
    return same_size and abs(moved[0] - rect["bbox"][0] - 30) < 0.5 and line["points"] == [[100.0, 100.0], [100.0, 300.0]] and ends[1] != 0


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
        "formas: extremos y mover sin crecer": _selftest_shapes(),
        "resaltar texto, estilo de formas y copiar campos": _selftest_markup_objects(),
        "cambiar el tamaño del texto": (call("edit/scale_spans", {"id": info["id"], "n": 0, "indices": [0], "factor": 1.5,
                                                                  "anchor": [50, 60]}) is not None
                                        and call("edit/state", {"id": info["id"], "n": 0})["spans"][0]["size"] == 21.0
                                        and call("edit/undo", {"id": info["id"]}) is not None),
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
        original = call("track/check", {"id": call("open", raw=contrato, name="contrato.pdf")["id"]})
        checks["seguimiento de envíos a firmar"] = bool(seg["match"] and not seg["pending"] and len(seg["after"]) == 1
                                                        and seg["record"]["estado"] == "completo"
                                                        and not original["match"] and not original.get("mismatch"))
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
    import pdfa
    folio = scan.digitalize([(scan.process(foto, q, "a4", "color", 0, 1200)[0], "a4")], "paginas", ocr=False)
    archivo = pdfa.convert(folio, "Prueba PDF/A")
    firmado = _signing.sign_pdf(archivo, _test_p12(), "x", page=0, view_rect=[350, 760, 560, 820])
    checks["PDF/A-2b (también firmado)"] = not pdfa.problems(archivo) and not pdfa.problems(firmado) and bool(pdfa.problems(folio))
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


def _file_arg():
    """Archivo con el que se ha abierto DocGuard (doble clic, «Abrir con…»), o None."""
    return next((os.path.abspath(a) for a in sys.argv[1:] if not a.startswith("-") and os.path.isfile(a)), None)


def _open_in_window(win, path):
    """Carga el archivo como «Abrir…» y lo muestra en Editar PDF (cuando la interfaz ya está lista)."""
    import json
    import secrets
    try:
        with open(path, "rb") as f:
            data = f.read()
        with server.LOCK:
            did = secrets.token_urlsafe(8)
            server.DOCS[did] = server.Doc(os.path.basename(path), data)
            info = server.DOCS[did].info(did)
        win.evaluate_js(f"showTool('edit'); Edit.loadInfo({json.dumps(info)});")
    except Exception as ex:
        win.evaluate_js(f"toast({json.dumps('No se pudo abrir ' + os.path.basename(path) + ': ' + str(ex))}, 'err');")


def _mac_open_files(win, loaded):
    """macOS no pasa los archivos por la línea de órdenes: los envía a la aplicación (doble clic,
    «Abrir con…», arrastrar al icono), también cuando ya está abierta. Se atienden aquí."""
    import threading

    import objc
    from webview.platforms import cocoa
    pending = []

    def handle(path):
        if loaded["ok"]:  # evaluate_js no puede esperar en el hilo principal
            threading.Thread(target=_open_in_window, args=(win, path), daemon=True).start()
        else:
            pending.append(path)

    def application_openFiles_(self, app, filenames):
        for f in filenames:
            if os.path.isfile(str(f)):
                handle(str(f))
        app.replyToOpenOrPrint_(0)

    objc.classAddMethods(cocoa.BrowserView.AppDelegate, [
        objc.selector(application_openFiles_, selector=b"application:openFiles:", signature=b"v@:@@")])
    return pending


def main():
    if "--selftest" in sys.argv:
        if sys.platform == "win32":
            # En Windows la salida suele ser cp1252 (fallaba al imprimir «↔») y el ejecutable se quedaba
            # colgado al salir (en GitHub Actions, hasta el límite de 6 h): UTF-8 y salida inmediata.
            for s in (sys.stdout, sys.stderr):
                try:
                    s.reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass
            try:
                ok = selftest()
            except Exception:
                import traceback
                traceback.print_exc()
                ok = False
            for s in (sys.stdout, sys.stderr):
                try:
                    s.flush()
                except Exception:
                    pass
            os._exit(0 if ok else 1)
        sys.exit(0 if selftest() else 1)
    url, httpd = server.start()
    path = _file_arg()
    if "--browser" not in sys.argv:
        try:
            if sys.platform == "win32":
                # WebView2 a veces deja la ventana con un fotograma congelado (sin iconos y sin responder):
                # sin GPU no ocurre, y las páginas ya se dibujan en Python, así que no se pierde fluidez.
                os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--disable-gpu")
            import webview
            from webview.menu import Menu, MenuAction, MenuSeparator
            global APP_URL
            APP_URL = url
            win = make_window()
            if sys.platform == "darwin":
                loaded = {"ok": False}
                pending = _mac_open_files(win, loaded)
                if path:
                    pending.append(path)

                def open_pending():
                    win.events.loaded -= open_pending
                    loaded["ok"] = True
                    for p in dict.fromkeys(pending):
                        _open_in_window(win, p)
                win.events.loaded += open_pending
            elif path:
                def open_file():
                    win.events.loaded -= open_file  # solo la primera vez que carga la interfaz
                    _open_in_window(win, path)
                win.events.loaded += open_file
            webview.start(menu=[Menu("Ventana", [
                MenuAction("Nueva ventana", new_window), MenuSeparator(),
                MenuAction("Organizar en mosaico", lambda: arrange("mosaico")),
                MenuAction("Organizar en cascada", lambda: arrange("cascada"))])])
            import updater  # si se descargó una versión nueva y se cerró sin reiniciar, se instala ahora
            if updater.STATE.get("new") and not updater.STATE.get("applied"):
                updater.apply_on_exit()
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
