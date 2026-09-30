"""Firma digital de PDF con certificado (.p12/.pfx) y verificación de firmas."""

import base64
import contextlib
import datetime
import html
import io
import logging
import os
import re
import secrets

import pymupdf as fitz
from PIL import Image

logging.getLogger("pyhanko").setLevel(logging.CRITICAL)
logging.getLogger("pyhanko_certvalidator").setLevel(logging.CRITICAL)


def _load_signer(p12_bytes, password):
    from pyhanko.sign import signers
    from cryptography.hazmat.primitives.serialization import pkcs12
    pw = password.encode() if password else None
    try:
        key, cert, extra = pkcs12.load_key_and_certificates(p12_bytes, pw)
    except ValueError:
        raise ValueError("No se pudo abrir el certificado: contraseña incorrecta o archivo no válido.")
    if key is None or cert is None:
        raise ValueError("El archivo no contiene una clave privada y un certificado.")
    from asn1crypto import keys as asn1_keys, x509 as asn1_x509
    from cryptography.hazmat.primitives import serialization
    from pyhanko_certvalidator.registry import SimpleCertificateStore
    key_der = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    cert_asn1 = asn1_x509.Certificate.load(cert.public_bytes(serialization.Encoding.DER))
    others = [asn1_x509.Certificate.load(c.public_bytes(serialization.Encoding.DER)) for c in extra or ()]
    return signers.SimpleSigner(
        signing_cert=cert_asn1, signing_key=asn1_keys.PrivateKeyInfo.load(key_der),
        cert_registry=SimpleCertificateStore.from_certs([cert_asn1] + others))


def cert_info(p12_bytes, password):
    signer = _load_signer(p12_bytes, password)
    c = signer.signing_cert
    return {"subject": c.subject.human_friendly, "issuer": c.issuer.human_friendly,
            "valid_from": c["tbs_certificate"]["validity"]["not_before"].native.strftime("%d/%m/%Y"),
            "valid_to": c["tbs_certificate"]["validity"]["not_after"].native.strftime("%d/%m/%Y")}


def _signer_name(signer):
    name = signer.signing_cert.subject.native
    return name.get("common_name") or signer.signing_cert.subject.human_friendly


def signer_display_name(signer):
    """Nombre del titular para mostrar (sin el «(FIRMA)» que añade el DNIe)."""
    return re.sub(r"\s*\((FIRMA|AUTENTICACI[OÓ]N)\)\s*$", "", _signer_name(signer), flags=re.I)


def sign_pdf(pdf_bytes, p12_bytes, password, page=None, view_rect=None, reason="", location="",
             contact="", image_png=None, tsa_url=None, signer=None, field_name=None, font_size=8):
    """Firma el PDF. Si se indica página y rectángulo (coordenadas de pantalla),
    la firma es visible, con el texto del firmante y opcionalmente la imagen
    de la firma manuscrita. Devuelve los bytes del PDF firmado."""
    from pyhanko import stamp
    from pyhanko.pdf_utils import images, text
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers, timestamps

    signer = signer or _load_signer(p12_bytes, password)
    with fitz.open("pdf", pdf_bytes) as doc:
        if doc.needs_pass or doc.is_encrypted:
            raise ValueError("Quita primero la contraseña del PDF (pestaña Contraseña).")
        existing = {w.field_name for p in doc for w in (p.widgets() or ())}
        # PyMuPDF normaliza el archivo para que pyHanko pueda añadir la firma de forma incremental.
        box = None
        existing_box = None
        if field_name:
            for p in doc:
                for w in p.widgets() or ():
                    if w.field_name == field_name and w.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
                        r = fitz.Rect(w.rect) * ~p.transformation_matrix
                        r.normalize()
                        existing_box = (r.x0, r.y0, r.x1, r.y1)
            if existing_box is None:
                raise ValueError(f"No existe el recuadro de firma «{field_name}».")
        if page is not None and view_rect and not field_name:
            pg = doc[page]
            r = fitz.Rect(view_rect) * pg.derotation_matrix * ~pg.transformation_matrix
            r.normalize()
            box = (r.x0, r.y0, r.x1, r.y1)
        clean = doc.tobytes(garbage=1, deflate=True) if not any(
            (w.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE) for p in doc for w in (p.widgets() or ())) else pdf_bytes

    n = 1
    while f"Firma{n}" in existing:
        n += 1
    field = field_name or f"Firma{n}"
    writer = IncrementalPdfFileWriter(io.BytesIO(clean if not field_name else pdf_bytes))
    if box:
        fields.append_signature_field(writer, fields.SigFieldSpec(field, on_page=page, box=box))
    box = box or existing_box

    meta = signers.PdfSignatureMetadata(field_name=field, reason=reason or None, location=location or None,
                                        contact_info=contact or None, md_algorithm="sha256")
    style = None
    if box:
        stamp_text = "Firmado digitalmente por:\n%(signer)s\nFecha: %(ts)s"
        if reason:
            stamp_text += "\nMotivo: " + reason.replace("%", "%%")
        kwargs = dict(stamp_text=stamp_text, border_width=0,
                      text_box_style=text.TextBoxStyle(font_size=int(font_size)),
                      timestamp_format="%d/%m/%Y %H:%M:%S")
        if image_png:
            from pyhanko.pdf_utils.layout import AxisAlignment, Margins, SimpleBoxLayoutRule
            half = (box[2] - box[0]) / 2
            img = Image.open(io.BytesIO(image_png)).convert("RGBA")
            kwargs["background"] = images.PdfImage(img)
            kwargs["background_opacity"] = 1.0
            kwargs["background_layout"] = SimpleBoxLayoutRule(
                x_align=AxisAlignment.ALIGN_MIN, y_align=AxisAlignment.ALIGN_MID,
                margins=Margins(left=2, right=half + 2, top=2, bottom=2))
            kwargs["inner_content_layout"] = SimpleBoxLayoutRule(
                x_align=AxisAlignment.ALIGN_MIN, y_align=AxisAlignment.ALIGN_MID,
                margins=Margins(left=half + 4, right=2, top=2, bottom=2))
        style = stamp.TextStampStyle(**kwargs)
    tsa = timestamps.HTTPTimeStamper(tsa_url) if tsa_url else None
    pdf_signer = signers.PdfSigner(meta, signer=signer, stamp_style=style, timestamper=tsa)
    out = pdf_signer.sign_pdf(writer, appearance_text_params={"signer": _signer_name(signer)})
    return out.getvalue()


# --------------------------------------------------------------------------
# DNIe y tarjetas criptográficas (PKCS#11)
# --------------------------------------------------------------------------

PKCS11_CANDIDATES = {
    "darwin": [
        "/Library/Libpkcs11-dnie/lib/libpkcs11-dnie.so",      # módulo oficial del DNIe
        "/usr/local/lib/libpkcs11-dnie.so",
        "/Library/OpenSC/lib/opensc-pkcs11.so",               # OpenSC (instalador oficial)
        "/opt/homebrew/lib/opensc-pkcs11.so",
        "/usr/local/lib/opensc-pkcs11.so",
        "/opt/homebrew/lib/pkcs11/opensc-pkcs11.so",
    ],
    "win32": [
        r"C:\Windows\System32\UsrPkcs11.dll",                 # DNIe (Dirección General de la Policía)
        r"C:\Windows\System32\DNIe_P11_priv.dll",
        r"C:\Program Files\OpenSC Project\OpenSC\pkcs11\opensc-pkcs11.dll",
        r"C:\Windows\System32\opensc-pkcs11.dll",
    ],
    "linux": [
        "/usr/lib/libpkcs11-dnie.so",
        "/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so",
        "/usr/lib/opensc-pkcs11.so",
        "/usr/lib64/opensc-pkcs11.so",
    ],
}

_libs = {}


def _lib(path):
    import pkcs11
    if path not in _libs:
        if not os.path.exists(path):
            raise ValueError(f"No existe el módulo PKCS#11: {path}")
        _libs[path] = pkcs11.lib(path)
    return _libs[path]


def pkcs11_modules():
    """Módulos PKCS#11 instalados en el equipo (DNIe, OpenSC...)."""
    import sys
    key = "win32" if sys.platform == "win32" else ("darwin" if sys.platform == "darwin" else "linux")
    extra = [p for p in os.environ.get("DOCGUARD_PKCS11", "").split(os.pathsep) if p]
    return [p for p in extra + PKCS11_CANDIDATES[key] if os.path.exists(p)]


def pkcs11_list(module):
    """Tarjetas conectadas y sus certificados (no hace falta el PIN para verlos)."""
    import pkcs11
    from asn1crypto import x509 as asn1_x509
    from pkcs11 import Attribute, ObjectClass
    lib = _lib(module)
    try:
        slots = lib.get_slots(token_present=True)
    except pkcs11.exceptions.PKCS11Error as ex:
        raise ValueError(f"No se pudo leer el lector de tarjetas: {ex!r}")
    tokens = []
    for slot in slots:
        try:
            token = slot.get_token()
            certs = []
            with token.open() as session:
                for obj in session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
                    c = asn1_x509.Certificate.load(obj[Attribute.VALUE])
                    certs.append({
                        "label": obj[Attribute.LABEL], "id": bytes(obj[Attribute.ID]).hex(),
                        "subject": c.subject.native.get("common_name") or c.subject.human_friendly,
                        "issuer": c.issuer.native.get("common_name") or c.issuer.human_friendly,
                        "valid_to": c["tbs_certificate"]["validity"]["not_after"].native.strftime("%d/%m/%Y"),
                        "signing": "firma" in obj[Attribute.LABEL].lower() or "sign" in obj[Attribute.LABEL].lower(),
                    })
            certs.sort(key=lambda c: not c["signing"])  # primero el certificado de firma
            tokens.append({"token": token.label.strip(), "certs": certs})
        except pkcs11.exceptions.PKCS11Error:
            continue
    return tokens


class _PinError(ValueError):
    pass


def pkcs11_signer(module, token_label, cert_id, pin):
    """Abre la tarjeta con el PIN y devuelve (firmante, sesión). Cierra la sesión al terminar."""
    import pkcs11
    from pyhanko.sign.pkcs11 import PKCS11Signer
    lib = _lib(module)
    try:
        token = lib.get_token(token_label=token_label)
        session = token.open(user_pin=pin)
    except pkcs11.exceptions.PinIncorrect:
        raise _PinError("PIN incorrecto. Cuidado: el DNIe se bloquea tras 3 intentos fallidos.")
    except pkcs11.exceptions.PinLocked:
        raise _PinError("La tarjeta está bloqueada por demasiados PIN erróneos. Desbloquéala en un punto de actualización del DNIe.")
    except pkcs11.exceptions.NoSuchToken:
        raise ValueError("No se encuentra la tarjeta. ¿Está en el lector?")
    cid = bytes.fromhex(cert_id)
    return PKCS11Signer(session, cert_id=cid, key_id=cid), session


def pkcs11_login(module, token_label, cert_id, pin):
    """Comprueba el PIN abriendo sesión en la tarjeta (y la cierra)."""
    signer, session = pkcs11_signer(module, token_label, cert_id, pin)
    try:
        c = signer.signing_cert
        return {"subject": c.subject.native.get("common_name") or c.subject.human_friendly}
    finally:
        session.close()


def sign_pdf_pkcs11(pdf_bytes, module, token_label, cert_id, pin, **kwargs):
    signer, session = pkcs11_signer(module, token_label, cert_id, pin)
    try:
        return sign_pdf(pdf_bytes, None, None, signer=signer, **kwargs)
    finally:
        session.close()


def add_signature_fields(pdf_bytes, specs):
    """Crea recuadros de firma vacíos, uno por firmante: specs = [{name, page, rect (pantalla)}]."""
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields
    with fitz.open("pdf", pdf_bytes) as doc:
        has_sigs = any(w.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE and w.field_value
                       for p in doc for w in (p.widgets() or ()))
        boxes = []
        for sp in specs:
            pg = doc[int(sp["page"])]
            r = fitz.Rect(sp["rect"]) * pg.derotation_matrix * ~pg.transformation_matrix
            r.normalize()
            boxes.append((sp["name"], int(sp["page"]), (r.x0, r.y0, r.x1, r.y1)))
        base = pdf_bytes if has_sigs else doc.tobytes(garbage=1, deflate=True)
    writer = IncrementalPdfFileWriter(io.BytesIO(base))
    for name, page, box in boxes:
        fields.append_signature_field(writer, fields.SigFieldSpec(name, on_page=page, box=box))
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def list_signature_fields(pdf_bytes):
    """Recuadros de firma del documento y si ya están firmados."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.fields import enumerate_sig_fields
    signed = {}
    try:
        for name, value, _ref in enumerate_sig_fields(PdfFileReader(io.BytesIO(pdf_bytes))):
            signed[name] = value is not None
    except Exception:
        pass
    out = []
    with fitz.open("pdf", pdf_bytes) as doc:
        for n, p in enumerate(doc):
            for w in p.widgets() or ():
                if w.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
                    r = fitz.Rect(w.rect) * p.rotation_matrix
                    out.append({"name": w.field_name, "page": n, "rect": [r.x0, r.y0, r.x1, r.y1],
                                "signed": signed.get(w.field_name, False)})
    return out


class NeedsPassword(ValueError):
    pass


def _plain(value):
    """Texto de un objeto PDF (en un PDF cifrado llega como proxy aún sin descifrar)."""
    value = getattr(value, "decrypted", value)
    return str(value) if value else ""


def verify_pdf(pdf_bytes, password=None):
    """Lista las firmas del PDF y si el documento se ha modificado después."""
    from pyhanko.pdf_utils.crypt import AuthStatus
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    reader = PdfFileReader(io.BytesIO(pdf_bytes))
    if reader.encrypted:
        if not password:
            raise NeedsPassword("El PDF está protegido con contraseña.")
        if reader.decrypt(password).status == AuthStatus.FAILED:
            raise ValueError("Contraseña incorrecta.")
    dss = "/DSS" in reader.root
    results = []
    for sig in reader.embedded_signatures:
        error = None
        tsa = None
        try:
            st = validate_pdf_signature(sig)
            intact, valid, trusted = st.intact, st.valid, st.trusted
            coverage = st.coverage.name if st.coverage else ""
            ts = st.timestamp_validity
            if ts is not None:
                tsa = {"time": ts.timestamp.astimezone().strftime("%d/%m/%Y %H:%M:%S"),
                       "ok": bool(ts.intact and ts.valid), "trusted": bool(ts.trusted),
                       "by": ts.signing_cert.subject.native.get("common_name", "") if ts.signing_cert else ""}
        except Exception as ex:
            intact = valid = trusted = False
            coverage = None
            error = f"{ex.__class__.__name__}: {ex}"
        when = sig.self_reported_timestamp
        results.append({
            "field": sig.field_name,
            "signer": sig.signer_cert.subject.human_friendly if sig.signer_cert else "?",
            "issuer": sig.signer_cert.issuer.human_friendly if sig.signer_cert else "?",
            "time": when.astimezone().strftime("%d/%m/%Y %H:%M") if isinstance(when, datetime.datetime) else "",
            "intact": bool(intact), "valid": bool(valid), "trusted": bool(trusted),
            "whole_file": coverage == "ENTIRE_FILE",
            "modified_after": coverage not in ("ENTIRE_FILE", "ENTIRE_REVISION") if coverage else None,
            "reason": _plain(sig.sig_object.get("/Reason")),
            "certified": sig.docmdp_level is not None,
            "timestamp": tsa, "ltv": dss,
            "error": error,
        })
    return results


# --------------------------------------------------------------------------
# Copias firmadas: la firma va en una franja añadida debajo de cada página,
# fuera de la imagen del documento, y cubre todo (imagen, marcas, destinatario,
# finalidad, fecha y referencia). Cualquier cambio posterior la invalida.
# --------------------------------------------------------------------------

TSA_ACCV = "http://tss.accv.es:8318/tsa"   # cualificado; gratuito para uso personal
COPY_FIELD = "Firma de la copia"
ACK_FIELD = "Acuse de recibo"


def band_metrics(width, ack=False):
    """Medidas (en puntos) de la franja de firma para una página de ese ancho."""
    fs = max(5.0, min(7.0, width / 100))
    lead = fs * 1.3
    pad = fs
    rows = 5.2 if ack else 3.6
    return {"fs": round(fs, 2), "pad": pad, "h": round(rows * lead + 2 * pad, 2),
            "sig_w": min(width * 0.36, fs * 34), "ack_w": min(width * 0.26, fs * 26) if ack else 0}


def _short(text, n):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def _pdf_rect(page, r):
    r = fitz.Rect(r) * page.derotation_matrix * ~page.transformation_matrix
    r.normalize()
    return [round(v, 2) for v in (r.x0, r.y0, r.x1, r.y1)]


def prepare_copy(pdf_bytes, info, ack=False):
    """Rellena la franja añadida bajo cada página (ya tiene el alto de band_metrics): uso
    autorizado de la copia y, en la primera página, los huecos de la firma y del acuse de
    recibo. info = {recipient, purpose, ref, date}. Devuelve (pdf, disposición de la firma)."""
    who = html.escape(_short(info.get("recipient"), 70) or "—")
    what = html.escape(_short(info.get("purpose"), 90) or "—")
    ref, date = html.escape(info.get("ref") or ""), html.escape(info.get("date") or "")
    layout = None
    with fitz.open("pdf", pdf_bytes) as doc:
        for n, page in enumerate(doc):
            W, H = page.rect.width, page.rect.height
            m = band_metrics(W, ack)
            fs, pad = m["fs"], m["pad"]
            band = fitz.Rect(0, H - m["h"], W, H)
            page.draw_rect(band, color=None, fill=(1, 1, 1), overlay=True)
            page.draw_line((0, band.y0), (W, band.y0), color=(0.55, 0.55, 0.6), width=0.4)
            inner = fitz.Rect(band.x0 + pad, band.y0 + pad * 0.55, band.x1 - pad, band.y1 - pad * 0.55)
            text_r = fitz.Rect(inner)
            if n == 0:
                sig = fitz.Rect(inner.x1 - m["sig_w"], inner.y0, inner.x1, inner.y1)
                text_r.x1 = sig.x0 - pad
                ack_r = None
                if ack:
                    ack_r = fitz.Rect(sig.x0 - pad - m["ack_w"], inner.y0, sig.x0 - pad, inner.y1)
                    text_r.x1 = ack_r.x0 - pad
                    page.draw_rect(ack_r, color=(0.45, 0.5, 0.6), width=0.5, dashes="[2 1.5] 0")
                layout = {"page": 0, "sig": _pdf_rect(page, sig), "ack": _pdf_rect(page, ack_r) if ack_r else None,
                          "fs": fs}
            lines = [f"<b>COPIA DE USO RESTRINGIDO</b> · Ref. {ref} · {date}",
                     f"Solo para: <b>{who}</b> · Finalidad: <b>{what}</b>"]
            if n == 0:
                lines.append("Firmada digitalmente: cualquier cambio la invalida. "
                             "Compruébalo en Adobe Acrobat Reader, Autofirma o valide.redsara.es")
                if ack:
                    lines.append(f"<b>Acuse de recibo:</b> {who} recibe esta copia solo para la finalidad indicada, "
                                 "sin cederla a terceros ni usarla para otros fines, y la destruirá cuando deje de "
                                 "ser necesaria. Firme en el recuadro punteado.")
            else:
                lines.append("Firmada digitalmente (la firma está en la primera página).")
            css = (f"* {{font-family: sans-serif; font-size: {fs}px; line-height: 1.25; color: #3a3f4a; margin: 0}}"
                   " b {color: #111}")
            page.insert_htmlbox(text_r, "<br>".join(lines), css=css)
        out = doc.tobytes(garbage=3, deflate=True)
    return out, layout


def _nums(v):
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?|-?\.\d+", v)]


def add_margin(pdf_bytes, pno, height):
    """Añade un margen en blanco de `height` puntos debajo de la página `pno` (tal como se ve)
    sin tapar nada. Solo usa coordenadas positivas, que todos los visores muestran bien: si
    hace falta, sube el contenido y las anotaciones. Devuelve (pdf, margen en la página)."""
    with fitz.open("pdf", pdf_bytes) as doc:
        page = doc[pno]
        rot = page.rotation % 360
        xref = page.xref
        mb = page.mediabox
        kind, val = doc.xref_get_key(xref, "CropBox")
        cb = _nums(val) if kind == "array" else [mb.x0, mb.y0, mb.x1, mb.y1]
        x0, y0, x1, y1 = min(cb[0], cb[2]), min(cb[1], cb[3]), max(cb[0], cb[2]), max(cb[1], cb[3])
        # el borde de abajo (tal como se ve) es: 0° → y0, 90° → x1, 180° → y1, 270° → x0
        dx, dy = {0: (0, height), 270: (height, 0)}.get(rot, (0, 0))
        if dx or dy:
            pre, post = doc.get_new_xref(), None
            doc.update_object(pre, "<<>>")
            doc.update_stream(pre, f"q 1 0 0 1 {dx:.3f} {dy:.3f} cm\n".encode())
            post = doc.get_new_xref()
            doc.update_object(post, "<<>>")
            doc.update_stream(post, b"\nQ\n")
            kind, val = doc.xref_get_key(xref, "Contents")
            inner = val.strip()[1:-1] if kind == "array" else (val if kind == "xref" else "")
            doc.xref_set_key(xref, "Contents", f"[{pre} 0 R {inner} {post} 0 R]")
            # las anotaciones (enlaces, campos, comentarios…) se mueven con el contenido
            shift = lambda v: [x + (dy if i % 2 else dx) for i, x in enumerate(v)]
            for ax in page.annot_xrefs():
                for key in ("Rect", "QuadPoints", "Vertices", "L", "CL"):
                    kind, val = doc.xref_get_key(ax[0], key)
                    if kind == "array":
                        doc.xref_set_key(ax[0], key, "[" + " ".join(f"{x:.3f}" for x in shift(_nums(val))) + "]")
                kind, val = doc.xref_get_key(ax[0], "InkList")
                if kind == "array":
                    strokes = ["[" + " ".join(f"{x:.3f}" for x in shift(_nums(st))) + "]"
                               for st in re.findall(r"\[([^\[\]]*)\]", val)]
                    doc.xref_set_key(ax[0], "InkList", "[" + " ".join(strokes) + "]")
        if rot in (0, 180):
            y1 += height
        else:
            x1 += height
        doc.xref_set_key(xref, "MediaBox", f"[{x0:.3f} {y0:.3f} {x1:.3f} {y1:.3f}]")
        for key in ("CropBox", "TrimBox", "BleedBox", "ArtBox"):
            doc.xref_set_key(xref, key, "null")
        page = doc.reload_page(page)
        r = page.rect
        band = [r.x0, r.y1 - height, r.x1, r.y1]
        out = doc.tobytes(garbage=1, deflate=True)
    return out, band


def encrypt_pdf_bytes(pdf_bytes, password):
    """Cifra con AES-256 permitiendo imprimir y firmar el acuse de recibo, de forma que
    pyHanko pueda firmar después (el cifrado de PyMuPDF no lo admite)."""
    from pyhanko.pdf_utils.crypt.permissions import StandardPermissions as P
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.pdf_utils.writer import copy_into_new_writer
    w = copy_into_new_writer(PdfFileReader(io.BytesIO(pdf_bytes)))
    perms = (P.ALLOW_PRINTING | P.ALLOW_HIGH_QUALITY_PRINTING | P.ALLOW_ASSISTIVE_TECHNOLOGY
             | P.ALLOW_FORM_FILLING | P.TOLERATE_MISSING_PDF_MAC)
    w.encrypt(secrets.token_urlsafe(24), password, perms=perms, pdf_mac=False)
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


@contextlib.contextmanager
def open_signer(cred):
    """Firmante con las credenciales de la interfaz. Con DNIe se abre una sola sesión (un
    solo uso del PIN) para todos los archivos."""
    if cred.get("source") == "card":
        if not cred.get("pin"):
            raise ValueError("Escribe el PIN de la tarjeta.")
        signer, session = pkcs11_signer(cred["module"], cred["token"], cred["cert_id"], cred["pin"])
        try:
            yield signer
        finally:
            session.close()
    else:
        if not cred.get("p12"):
            raise ValueError("Elige el certificado (.p12 / .pfx).")
        yield _load_signer(base64.b64decode(cred["p12"]), cred.get("password", ""))


def _ltv_context(signer):
    """Contexto para incluir en la firma los datos de validación a largo plazo (OCSP/CRL)."""
    from pyhanko_certvalidator import ValidationContext
    from pyhanko_certvalidator.fetchers.requests_fetchers import RequestsFetcherBackend
    certs = [signer.signing_cert]
    with contextlib.suppress(Exception):
        certs += [c for c in signer.cert_registry if c != signer.signing_cert]
    roots = [c for c in certs if c.self_signed != "no"]
    return ValidationContext(extra_trust_roots=roots or None, other_certs=certs, allow_fetching=True,
                             fetcher_backend=RequestsFetcherBackend(per_request_timeout=8))


def _appearance(path, box, name, fs, tsa, opaque=False):
    """Aspecto visible de la firma (PDF del tamaño del recuadro), con letra de palo seco.
    Dentro del documento lleva fondo blanco casi opaco para que se lea sobre la imagen."""
    w, h = int(box[2] - box[0]), int(box[3] - box[1])  # pyHanko recorta el aspecto a medidas enteras
    when = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    with fitz.open() as doc:
        page = doc.new_page(width=w, height=h)
        page.draw_rect(fitz.Rect(0.5, 0.5, w - 0.5, h - 0.5), color=(0.25, 0.4, 0.62), width=0.6, radius=0.08,
                       fill=(1, 1, 1) if opaque else None, fill_opacity=0.88 if opaque else 1)
        css = (f"* {{font-family: sans-serif; font-size: {fs}px; line-height: 1.22; color: #1f3350; margin: 0}}"
               " b {color: #0d1b2e}")
        body = (f"✔ Firmado digitalmente por<br><b>{html.escape(_short(name, 60))}</b><br>{when}"
                + (" · con sello de tiempo" if tsa else ""))
        page.insert_htmlbox(fitz.Rect(fs * 0.7, fs * 0.45, w - fs * 0.6, h - fs * 0.35), body, css=css)
        doc.save(path)


def _sign_copy_once(pdf_bytes, signer, layout, reason, password, tsa_url, ltv):
    import tempfile
    from pyhanko.pdf_utils import content, layout as pdf_layout
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers, timestamps
    from pyhanko.stamp import StaticStampStyle
    w = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
    if password:
        w.encrypt(password)
    if layout.get("ack"):
        fields.append_signature_field(w, fields.SigFieldSpec(ACK_FIELD, on_page=layout["page"], box=tuple(layout["ack"])))
    # sin recuadro («sig» vacío) la firma es invisible: está en el PDF pero no se dibuja
    fields.append_signature_field(w, fields.SigFieldSpec(COPY_FIELD, on_page=layout["page"],
                                                         box=tuple(layout["sig"]) if layout.get("sig") else None))
    # firma de aprobación (PAdES), no de certificación: así otras personas pueden firmar después
    # (el acuse de recibo o sus propios recuadros) sin que la tuya deje de ser válida
    meta = signers.PdfSignatureMetadata(
        field_name=COPY_FIELD, reason=reason or None, md_algorithm="sha256", subfilter=fields.SigSeedSubFilter.PADES,
        embed_validation_info=ltv, validation_context=_ltv_context(signer) if ltv else None)
    tsa = timestamps.HTTPTimeStamper(tsa_url, timeout=10) if tsa_url else None
    if not layout.get("sig"):
        return signers.PdfSigner(meta, signer=signer, timestamper=tsa).sign_pdf(w).getvalue()
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    try:
        _appearance(tmp.name, layout["sig"], signer_display_name(signer), layout["fs"], tsa_url, layout.get("opaque"))
        style = StaticStampStyle(background=content.ImportedPdfPage(tmp.name), border_width=0, background_opacity=1.0,
                                 background_layout=pdf_layout.SimpleBoxLayoutRule(
                                     x_align=pdf_layout.AxisAlignment.ALIGN_MID, y_align=pdf_layout.AxisAlignment.ALIGN_MID,
                                     margins=pdf_layout.Margins.uniform(0)))
        out = signers.PdfSigner(meta, signer=signer, stamp_style=style, timestamper=tsa).sign_pdf(w)
    finally:
        os.unlink(tmp.name)
    return out.getvalue()


def inside_layout(pdf_bytes, page_no, rect):
    """Firma dentro del documento: `rect` normalizado (0..1) sobre la página tal como se ve."""
    with fitz.open("pdf", pdf_bytes) as doc:
        page = doc[min(max(0, int(page_no)), len(doc) - 1)]
        W, H = page.rect.width, page.rect.height
        x0, y0, x1, y1 = [min(1.0, max(0.0, float(v))) for v in rect]
        r = fitz.Rect(min(x0, x1) * W, min(y0, y1) * H, max(x0, x1) * W, max(y0, y1) * H)
        fs = band_metrics(W)["fs"]
        if r.width < fs * 12 or r.height < fs * 3.2:  # mínimo legible: se agranda hacia arriba y a la izquierda
            r = fitz.Rect(max(0, r.x1 - max(r.width, fs * 12)), max(0, r.y1 - max(r.height, fs * 3.2)), r.x1, r.y1)
        return {"page": page.number, "sig": _pdf_rect(page, r), "ack": None, "fs": fs, "opaque": True}


def _why(ex):
    """Motivo breve y comprensible de un fallo del sello de tiempo o de la validación."""
    import sys
    print(f"[firma] {ex!r}", file=sys.stderr)
    txt = f"{type(ex).__name__} {ex}".lower()
    if any(k in txt for k in ("timeout", "timed out", "connect", "resolve", "unreachable", "network", "clienterror")):
        return "sin conexión o el servidor no respondió"
    if any(k in txt for k in ("certificate", "path", "trust", "revocation", "validat", "purpose", "usage")):
        return "no se pudo validar la cadena de confianza del certificado"
    if any(k in txt for k in ("timestamp", "http")):
        return "el servidor del sello de tiempo no respondió bien"
    return "error inesperado"


def sign_copy(pdf_bytes, signer, layout, reason="", password=None, tsa_url=None, ltv=False):
    """Firma la copia en su franja. Si el sello de tiempo o la validación a largo plazo fallan
    (sin internet, servidor caído…), firma sin ellos y lo indica. Nunca repite un PIN erróneo.
    Devuelve (pdf, avisos, {"tsa", "ltv"} usados)."""
    attempts = [(tsa_url, ltv)]
    if ltv:
        attempts.append((tsa_url, False))
    if tsa_url:
        attempts.append((None, False))
    notes, last = [], None
    for tsa, lt in attempts:
        try:
            out = _sign_copy_once(pdf_bytes, signer, layout, reason, password, tsa, lt)
            if len(notes) == 2 and notes[0].split("(")[1] == notes[1].split("(")[1]:  # mismo motivo: un solo aviso
                notes = ["sin sello de tiempo ni validación a largo plazo (" + notes[1].split("(", 1)[1]]
            return out, notes, {"tsa": tsa, "ltv": lt}
        except _PinError:
            raise
        except Exception as ex:
            if type(ex).__module__.split(".")[0] == "pkcs11":  # errores de la tarjeta: no se reintenta
                raise
            last = ex
            why = _why(ex)
            notes.append(f"sin validación a largo plazo ({why})" if lt else f"sin sello de tiempo ({why})")
    raise last
