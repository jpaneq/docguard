"""Firma digital de PDF con certificado (.p12/.pfx) y verificación de firmas."""

import datetime
import io
import logging
import os

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


def sign_pdf(pdf_bytes, p12_bytes, password, page=None, view_rect=None, reason="", location="",
             contact="", image_png=None, tsa_url=None, signer=None):
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
        if page is not None and view_rect:
            pg = doc[page]
            r = fitz.Rect(view_rect) * pg.derotation_matrix * ~pg.transformation_matrix
            r.normalize()
            box = (r.x0, r.y0, r.x1, r.y1)
        clean = doc.tobytes(garbage=1, deflate=True) if not any(
            (w.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE) for p in doc for w in (p.widgets() or ())) else pdf_bytes

    n = 1
    while f"Firma{n}" in existing:
        n += 1
    field = f"Firma{n}"
    writer = IncrementalPdfFileWriter(io.BytesIO(clean))
    if box:
        fields.append_signature_field(writer, fields.SigFieldSpec(field, on_page=page, box=box))

    meta = signers.PdfSignatureMetadata(field_name=field, reason=reason or None, location=location or None,
                                        contact_info=contact or None, md_algorithm="sha256")
    style = None
    if box:
        stamp_text = "Firmado digitalmente por:\n%(signer)s\nFecha: %(ts)s"
        if reason:
            stamp_text += "\nMotivo: " + reason.replace("%", "%%")
        kwargs = dict(stamp_text=stamp_text, border_width=0,
                      text_box_style=text.TextBoxStyle(font_size=8),
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


def verify_pdf(pdf_bytes):
    """Lista las firmas del PDF y si el documento se ha modificado después."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    reader = PdfFileReader(io.BytesIO(pdf_bytes))
    results = []
    for sig in reader.embedded_signatures:
        error = None
        try:
            st = validate_pdf_signature(sig)
            intact, valid, trusted = st.intact, st.valid, st.trusted
            coverage = st.coverage.name if st.coverage else ""
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
            "reason": (sig.sig_object.get("/Reason") or ""),
            "error": error,
        })
    return results
