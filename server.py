"""Servidor local de DocGuard: sirve la interfaz web y la API.

Solo escucha en 127.0.0.1 y exige un token aleatorio en cada llamada a la API,
así ninguna otra web ni otro usuario del equipo puede usarlo.
"""

import base64
import datetime
import hashlib
import contextlib
import io
import json
import os
import secrets
import shutil
import sys
import tempfile
import threading
import traceback
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pymupdf as fitz
from PIL import Image

import core
import compare
import convert
import editor
import idfields
import marcas_agua
import pdfa
import protect
import records
import scan
import signing
import status_icons
import tracking

TOKEN = secrets.token_urlsafe(18)
NO_LOCK = {"update/check", "update/download", "update/progress", "version", "verify"}
LOCK = threading.RLock()  # PyMuPDF no es seguro entre hilos: una operación a la vez
DOCS = {}
RESULTS = {}
WEB_DIR = core.resource_path("web")
MAX_UNDO = 25


class Doc:
    def __init__(self, name, data):
        self.name = name
        self.ext = core.ext_of(name)
        self.orig = data
        self.edited = False
        self.undo = []
        self.redo = []
        self.ocr = {}
        self.lines = {}
        self.idf = {}
        if self.ext == ".pdf":
            self.kind = "pdf"
        elif self.ext in core.IMAGE_EXTS:
            self.kind = "image"
        elif self.ext in core.OFFICE_EXTS:
            self.kind = "office"
        else:
            self.kind = "other"
        self.doc = None
        self.password = None
        if self.kind == "pdf":
            self.doc = fitz.open("pdf", data)
            self.encrypted = self.doc.needs_pass
        elif self.kind == "image":
            with fitz.open(stream=data, filetype=self.ext.lstrip(".")) as img:
                self.doc = fitz.open("pdf", img.convert_to_pdf())
            self.encrypted = False
        else:
            self.encrypted = False

    @property
    def base(self):
        return os.path.splitext(self.name)[0]

    def pdf_bytes(self):
        if self.kind == "pdf" and not self.edited and not self.password:
            return self.orig
        if self.password:  # abierto con su contraseña: se trabaja con la versión descifrada
            return self.doc.tobytes(garbage=3, deflate=True, encryption=fitz.PDF_ENCRYPT_NONE)
        return self.doc.tobytes(garbage=3, deflate=True)

    def info(self, did):
        pages = []
        if self.doc and not self.encrypted:
            pages = [[round(p.rect.width, 2), round(p.rect.height, 2)] for p in self.doc]
        return {"id": did, "name": self.name, "kind": self.kind, "pages": pages, "edited": self.edited,
                "encrypted": self.encrypted, "size": len(self.orig)}


@contextlib.contextmanager
def as_file(d):
    """Guarda el documento (con las ediciones) en un archivo temporal."""
    tmp = tempfile.mkdtemp(prefix="docguard_")
    try:
        if d.kind in ("pdf", "image") and (d.edited or d.kind == "pdf"):
            path = os.path.join(tmp, d.base + ".pdf")
            data = d.pdf_bytes()
        else:
            path = os.path.join(tmp, d.name)
            data = d.orig
        with open(path, "wb") as f:
            f.write(data)
        yield path, tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def store_result(files):
    """files = [(nombre, bytes)] -> id del resultado."""
    rid = secrets.token_urlsafe(8)
    RESULTS[rid] = files
    return {"rid": rid, "files": [{"name": n, "size": len(b)} for n, b in files]}


def read_outputs(folder, exclude=()):
    out = []
    for f in sorted(os.listdir(folder)):
        p = os.path.join(folder, f)
        if os.path.isfile(p) and p not in exclude:
            with open(p, "rb") as fh:
                out.append((f, fh.read()))
    return out


def get_doc(req):
    d = DOCS.get(req.get("id"))
    if not d:
        raise ValueError("Documento no encontrado. Vuelve a abrirlo.")
    return d


def need_pdf(d):
    if not d.doc:
        raise ValueError(f"«{d.name}» no es un PDF ni una imagen.")
    if d.encrypted:
        raise ValueError(f"«{d.name}» está protegido con contraseña. Quítala primero.")
    return d.doc


def rects(lst):
    return [fitz.Rect(r) for r in lst]


# --------------------------------------------------------------------------
# Operaciones
# --------------------------------------------------------------------------

def op_open_result(req):
    name, data = RESULTS[req["rid"]][req.get("index", 0)]
    did = secrets.token_urlsafe(8)
    DOCS[did] = Doc(name, data)
    return DOCS[did].info(did)


def op_close(req):
    DOCS.pop(req.get("id"), None)
    return {}


TABS = []  # documentos abiertos como pestañas (los comparten todas las ventanas)


def op_tabs_add(req):
    if req["id"] in DOCS and req["id"] not in TABS:
        TABS.append(req["id"])
    return {}


def op_tabs_list(req):
    TABS[:] = [t for t in TABS if t in DOCS]
    return {"tabs": [DOCS[t].info(t) for t in TABS]}


def op_tabs_close(req):
    if req["id"] in TABS:
        TABS.remove(req["id"])
    DOCS.pop(req["id"], None)
    return {}


def op_update_check(req):
    import updater
    return updater.check()


def op_update_download(req):
    import updater
    return updater.download(req)


EXTERNAL_OPEN = None  # la ventana de DocGuard abre aquí los archivos que llegan de Word


def op_external_open(req):
    """Abre en la ventana un PDF que ha llegado del botón de Word (solo rutas temporales de DocGuard)."""
    path = os.path.abspath(req["path"])
    folder = os.path.join(tempfile.gettempdir(), "DocGuard-Word")
    if not path.startswith(folder + os.sep) or not os.path.isfile(path) or not EXTERNAL_OPEN:
        raise ValueError("no se puede abrir")
    threading.Thread(target=EXTERNAL_OPEN, args=(path,), daemon=True).start()
    return {}


def op_update_progress(req):
    import updater
    return updater.STATE.get("progress") or {}


def op_info(req):
    return get_doc(req).info(req["id"])


# ---- marca de agua ----

def wm_params(req):
    p = req["params"]
    q = p.get("qr") or {}
    p = dict(p, text=(p.get("text", "").replace("{destinatario}", q.get("recipient", "").strip())
                      .replace("{finalidad}", q.get("purpose", "").strip())
                      .replace("{caducidad}", protect.until_date(q.get("until")) or "—")))
    base = wm_basic(p)
    base.update(level=p.get("level", "reforzada"), strike=bool(p.get("strike", True)))
    # capas contra la IA generativa
    who = q.get("recipient", "").strip()
    base.update(robust=bool(p.get("robust", True)), fingerprint=bool(p.get("fingerprint", True)),
                hide_label=(f"SOLO PARA {who.upper()}" if who else "USO RESTRINGIDO") if p.get("labels") else None,
                decoy_mrz=bool(p.get("labels")), stamp=bool(p.get("stamp")),
                stamp_text=f"Solo para {who}" if who else None, notice=bool(p.get("notice")),
                photo=p.get("photo") or None)
    return base


def limit_size(img, maxside):
    """Reduce la imagen si supera el tamaño máximo: legible, pero menos útil para falsificar."""
    if maxside and max(img.size) > maxside:
        k = maxside / max(img.size)
        img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)
    return img


def wm_qr(p, ref):
    q = p.get("qr") or {}
    if not q.get("enabled"):
        return None
    data = protect.qr_payload(q.get("mode", "vcard"), q.get("recipient", "").strip(), q.get("purpose", "").strip(),
                              ref, q.get("base_url", "").strip(), until=protect.until_date(q.get("until")) or None)
    return {"data": data, "size": float(q.get("size", 22)), "pos": q.get("pos", "abajo-derecha")}


def wm_basic(p):
    return dict(text=p.get("text", ""), angle=float(p.get("angle", 35)), size=float(p.get("size", 40)),
                gap_x=float(p.get("gap_x", 60)), gap_y=float(p.get("gap_y", 80)),
                opacity=float(p.get("opacity", 35)) / 100, color=tuple(int(p.get("color", "#c80000")[i:i + 2], 16)
                                                                        for i in (1, 3, 5)),
                hardened=bool(p.get("hardened", True)))


def doc_image(d, n, maxside=2200):
    """Imagen de una página (o de la imagen original) para analizarla."""
    if d.kind == "image" and not d.edited:
        from PIL import ImageOps
        return ImageOps.exif_transpose(Image.open(io.BytesIO(d.orig))).convert("RGB")
    page = need_pdf(d)[n]
    zoom = min(4.0, maxside / max(page.rect.width, page.rect.height))
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def id_fields(d, n):
    if n not in d.idf:
        d.idf[n] = idfields.detect(doc_image(d, n))
    return d.idf[n]


def op_idfields(req):
    d = get_doc(req)
    return id_fields(d, int(req.get("n", 0)))


def op_wm_preview(req):
    d = get_doc(req)
    n = int(req.get("n", 0))
    maxw = int(req.get("maxw", 900))
    if d.kind == "image" and not d.edited:
        img = Image.open(io.BytesIO(d.orig))
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img).convert("RGB")
    else:
        page = need_pdf(d)[n]
        zoom = min(3.0, maxw / page.rect.width)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img.thumbnail((maxw, maxw * 3))
    params = wm_params(req)
    params["ref"] = "XXXXXXXX"  # la referencia real se asigna al guardar
    if params["strike"] and params["level"] != "basica" and n not in d.lines:
        d.lines[n] = protect.detect_lines(img)
    out = protect.watermark(img, seed=1000 + n, lines=d.lines.get(n), qr=wm_qr(req["params"], "(al guardar)"),
                            hide=req["params"].get("hide_page"), **params)
    headers = {"X-Photo": "0"} if params.get("photo") and protect.LAST_PHOTO is None else {}
    band = req["params"].get("sign_band")
    if band:
        out, frac = preview_band(out, page_width_pt(d, n, int(req["params"].get("maxside") or 0)), band,
                                 req["params"].get("qr") or {})
        headers["X-Band"] = f"{frac:.5f}"
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=85)
    return ("image/jpeg", buf.getvalue(), headers)


def page_width_pt(d, n, maxside=0):
    """Ancho en puntos que tendrá la página en el PDF exportado."""
    if d.kind == "image" and not d.edited:
        from PIL import ImageOps
        w, h = ImageOps.exif_transpose(Image.open(io.BytesIO(d.orig))).size
        k = maxside / max(w, h) if maxside and max(w, h) > maxside else 1
        return w * k * 72 / core.RENDER_DPI
    return need_pdf(d)[n].rect.width


def _wrap(dr, text, font, width):
    lines, cur = [], ""
    for word in text.split():
        t = f"{cur} {word}".strip()
        if cur and dr.textlength(t, font=font) > width:
            lines.append(cur)
            cur = word
        else:
            cur = t
    return lines + ([cur] if cur else [])


def preview_band(img, width_pt, band, q):
    """Añade a la vista previa la franja de firma que irá debajo del documento."""
    from PIL import ImageDraw
    ack = bool(band.get("ack"))
    m = signing.band_metrics(width_pt, ack)
    k = img.width / width_pt
    bh = max(12, round(m["h"] * k))
    out = Image.new("RGB", (img.width, img.height + bh), "white")
    out.paste(img, (0, 0))
    dr = ImageDraw.Draw(out)
    y0 = img.height
    dr.line([(0, y0), (img.width, y0)], fill=(140, 140, 153), width=1)
    pad, fs = m["pad"] * k, max(6, round(m["fs"] * k))
    reg, bold = core.get_font(fs, bold=False), core.get_font(fs)
    top, bottom = y0 + pad * 0.55, y0 + bh - pad * 0.55
    sig = (img.width - pad - m["sig_w"] * k, top, img.width - pad, bottom)
    dr.rounded_rectangle(sig, radius=max(2, fs // 3), outline=(64, 102, 158), width=1)
    name = band.get("name") or "tu certificado o DNIe"
    for i, (t, f) in enumerate([("Firmado digitalmente por", reg), (name[:60], bold), ("fecha y hora al guardar", reg)]):
        dr.text((sig[0] + fs * 0.7, top + fs * 0.45 + i * fs * 1.22), t, font=f, fill=(31, 51, 80))
    x1 = sig[0] - pad
    if ack:
        a = (sig[0] - pad - m["ack_w"] * k, top, sig[0] - pad, bottom)
        for x in range(int(a[0]), int(a[2]), 6):
            dr.line([(x, a[1]), (min(x + 3, a[2]), a[1])], fill=(115, 128, 153))
            dr.line([(x, a[3]), (min(x + 3, a[2]), a[3])], fill=(115, 128, 153))
        for y in range(int(a[1]), int(a[3]), 6):
            dr.line([(a[0], y), (a[0], min(y + 3, a[3]))], fill=(115, 128, 153))
            dr.line([(a[2], y), (a[2], min(y + 3, a[3]))], fill=(115, 128, 153))
        x1 = a[0] - pad
    who = (q.get("recipient") or "").strip() or "—"
    what = (q.get("purpose") or "").strip() or "—"
    until = protect.until_date(q.get("until"))
    lines = [f"COPIA DE USO RESTRINGIDO · Ref. (al guardar) · {datetime.date.today():%d/%m/%Y}"
             + (f" · Válida hasta {until}" if until else ""),
             f"Solo para: {who} · Finalidad: {what}",
             "Firmada digitalmente: cualquier cambio la invalida. Compruébalo en Adobe Acrobat Reader, "
             "Autofirma o valide.redsara.es"]
    if ack:
        lines.append(f"Acuse de recibo: {who} recibe esta copia solo para la finalidad indicada, sin cederla a "
                     "terceros ni usarla para otros fines, y la destruirá cuando deje de ser necesaria. "
                     "Firme en el recuadro punteado.")
    size = fs
    while True:  # como en el PDF: la letra se reduce hasta que el texto cabe
        reg, bold = core.get_font(size, bold=False), core.get_font(size)
        wrapped = [(i, ln) for i, t in enumerate(lines) for ln in _wrap(dr, t, reg, x1 - pad)]
        if len(wrapped) * size * 1.22 <= bottom - top + size * 0.2 or size <= 6:
            break
        size -= 1
    y = top
    for i, ln in wrapped:
        dr.text((pad, y), ln, font=bold if i == 0 else reg, fill=(40, 44, 54))
        y += size * 1.22
    return out, bh / out.height


def op_wm_export(req):
    params = wm_params(req)
    fmt = req.get("fmt", "pdf").lower()
    w = int(req["width"]) if req.get("width") else None
    h = int(req["height"]) if req.get("height") else None
    p = req["params"]
    q = p.get("qr") or {}
    who, purpose = q.get("recipient", "").strip(), q.get("purpose", "").strip()
    until = protect.until_date(q.get("until"))
    pw = (p.get("password") or "").strip()
    sign = req.get("sign") or None
    if sign and fmt != "pdf":
        raise ValueError("La firma digital solo se puede añadir al guardar como PDF.")
    # dónde va la firma: "band" (franja añadida debajo, fuera de la imagen), "inside" (dentro
    # del documento, donde se haya colocado) o "invisible"
    place = (sign or {}).get("place", "band")
    ack = bool(sign and sign.get("ack")) and place == "band"
    want_pdfa = bool(req.get("pdfa")) and fmt == "pdf"
    if want_pdfa and pw:  # PDF/A no admite cifrado
        want_pdfa = False
        notes_pdfa = ["PDF/A no admite contraseña: se ha guardado como PDF normal"]
    else:
        notes_pdfa = []
    bottom = (lambda wpt: signing.band_metrics(wpt, ack)["h"]) if sign and place == "band" else None
    reason = "Copia de uso restringido" + (f" para {who}" if who else "") + (f" – {purpose}" if purpose else "")
    files, refs, notes, used, signed_by = [], [], [], None, None
    # con DNIe se abre una sola sesión: el PIN se usa una vez aunque haya varios archivos
    with (signing.open_signer(sign) if sign else contextlib.nullcontext()) as signer:
        if signer is not None:
            signed_by = signing.signer_display_name(signer)
        for did in req["ids"]:
            d = DOCS[did]
            ref = None
            if p.get("mark", True) or q.get("enabled") or sign:
                ref = protect.register(who, purpose, core.expand_placeholders(params["text"]), d.name)
                if until:
                    protect.update_registry(ref, caduca=until)
                refs.append(ref)
            extra = dict(params, qr=wm_qr(p, ref), mark=ref if p.get("mark", True) else None)
            hide_doc = (p.get("hide") or {}).get(did)

            def painter(img, seed, _d=d, _h=hide_doc, _ref=ref, **kw):
                page_no = seed - 1000
                img = limit_size(img, int(p.get("maxside") or 0))
                if _h is not None and str(page_no) in _h:
                    hide = _h[str(page_no)]
                elif p.get("autohide"):
                    hide = [{"r": r, "k": it["kind"]} for it in idfields.detect(img)["items"] for r in it["rects"]]
                else:
                    hide = None
                out = protect.watermark(img, seed=seed, hide=hide, ref=_ref, **kw)
                if _ref and kw.get("fingerprint") and protect.LAST_HIDE:
                    protect.register_fingerprint(_ref, protect.LAST_HIDE, page=page_no)
                return out
            with as_file(d) as (path, tmp):
                dst = os.path.join(tmp, "out", f"{d.base}_marca.{fmt}")
                os.makedirs(os.path.dirname(dst))
                core.export_watermarked(path, dst, extra, w, h, painter=painter, bottom=bottom)
                out = read_outputs(os.path.dirname(dst))
            done = []
            for name, data in out:
                if name.lower().endswith(".pdf"):
                    if sign:
                        # orden: franja → contraseña → firma (lo último, o la invalidaría)
                        if place == "band":
                            data, layout = signing.prepare_copy(data, {
                                "recipient": who, "purpose": purpose, "ref": ref, "until": until,
                                "date": datetime.date.today().strftime("%d/%m/%Y")}, ack=ack)
                        elif place == "inside":
                            layout = signing.inside_layout(data, sign.get("page", 0), sign.get("rect") or [0.6, 0.86, 0.97, 0.97])
                        else:
                            layout = {"page": 0, "sig": None, "ack": None, "fs": 6}
                        if want_pdfa:  # primero PDF/A y después la firma (que no rompe la norma)
                            data = pdfa.convert(data, f"Copia de uso restringido {ref or ''}".strip())
                        data = status_icons.mark_pdf(data, "protegido")  # para el icono de estado
                        if pw:
                            data = signing.encrypt_pdf_bytes(data, pw)
                        data, warn, used = signing.sign_copy(data, signer, layout, reason=reason[:150], password=pw or None,
                                                             tsa_url=sign.get("tsa") or None, ltv=bool(sign.get("ltv")))
                        notes += [x for x in warn if x not in notes]
                    else:
                        if want_pdfa:
                            data = pdfa.convert(data, f"Copia de uso restringido {ref or ''}".strip())
                        data = status_icons.mark_pdf(data, "protegido")  # para el icono de estado
                        if pw:  # el mismo cifrado que las copias firmadas (lo lee «Comprobar una copia»)
                            data = signing.encrypt_pdf_bytes(data, pw)
                done.append((name, data))
            if ref:
                rec = {"sha256": [hashlib.sha256(data).hexdigest() for _, data in done]}
                if sign:
                    rec["firma"] = {"por": signed_by, "sello": bool(used and used["tsa"]),
                                    "ltv": bool(used and used["ltv"]), "acuse": ack, "lugar": place}
                protect.update_registry(ref, **rec)
            files += done
    res = store_result(files)
    if refs:
        notes.insert(0, "Referencia: " + ", ".join(refs))
    if sign:
        how = []
        if used and used["tsa"]:
            how.append("sello de tiempo" + (" cualificado" if used["tsa"] == signing.TSA_ACCV else ""))
        if used and used["ltv"]:
            how.append("validación a largo plazo")
        notes.insert(1 if refs else 0, f"firmada por {signed_by}" + (" con " + " y ".join(how) if how else ""))
    if pw:
        notes.append("protegido con contraseña")
    if until:
        notes.append(f"válida hasta el {until}")
    if want_pdfa:
        notes.append("PDF/A-2b")
    notes += notes_pdfa
    res.update(notes=notes, refs=refs, signed=bool(sign), ack=ack, who=who, purpose=purpose, password=bool(pw), until=until)
    return res


def image_clip(page):
    """Zona de la imagen principal de la página, sin la franja de firma añadida debajo
    (las marcas se buscan sobre la imagen tal como se protegió)."""
    best = None
    with contextlib.suppress(Exception):
        for info in page.get_image_info():
            r = fitz.Rect(info["bbox"]) & page.rect
            if best is None or r.get_area() > best.get_area():
                best = r
    area = page.rect.get_area()
    if best is not None and 0.5 * area <= best.get_area() < area - 1:
        return best
    return None


def op_wm_check(req):
    """Identifica a quién se entregó una copia con todos los métodos disponibles, comprueba
    su huella exacta y sus firmas, y busca indicios de edición con IA en el propio archivo."""
    d = get_doc(req)
    pw = req.get("password") or ""
    delivered = [dict(x, record=protect.lookup(x["ref"])) for x in protect.match_delivery(d.orig)]
    sigs, sig_error = [], None
    if d.kind == "pdf":
        if d.encrypted:
            if not pw:
                return {"needs_password": True, "file": delivered, "found": [], "signatures": [], "hints": []}
            if not d.doc.authenticate(pw):
                raise ValueError("Contraseña incorrecta.")
            d.encrypted = False
        has_sigs = any(w.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE for p in d.doc for w in (p.widgets() or ()))
        try:
            sigs = signing.verify_pdf(d.orig, password=pw or None) if has_sigs else []
        except Exception as ex:
            sig_error = str(ex) or ex.__class__.__name__
    if d.kind == "image" and not d.edited:
        imgs = [Image.open(io.BytesIO(d.orig)).convert("RGB")]
    else:
        doc = need_pdf(d)
        imgs = []
        for page in list(doc)[:5]:
            # sin anotaciones: una firma colocada encima de la imagen no debe tapar las marcas
            pix = page.get_pixmap(dpi=150, alpha=False, clip=image_clip(page), annots=False)
            imgs.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    found = {}

    def add(ref, page, method, detail=""):
        e = found.setdefault(ref, {"ref": ref, "page": page, "methods": [], "record": protect.lookup(ref)})
        if method not in [m["name"] for m in e["methods"]]:
            e["methods"].append({"name": method, "detail": detail})
    for i, img in enumerate(imgs):
        ref, conf = protect.detect_mark(img)
        if ref:
            add(ref, i + 1, "Marca invisible", f"coincidencia {conf:.0%}")
        ids = protect.identify_robust(img)
        if ids and ids[0][1] >= 4.5 and (len(ids) < 2 or ids[0][1] - ids[1][1] >= 1.5):
            add(ids[0][0], i + 1, "Rastreo reforzado (resiste la regeneración por IA)",
                "certeza muy alta" if ids[0][1] >= 8 else "certeza alta")
        fps = protect.match_fingerprint(img)
        if fps and fps[0]["score"] >= 0.6 and (len(fps) < 2 or fps[0]["score"] - fps[1]["score"] >= 0.08):
            add(fps[0]["ref"], i + 1, "Huella de las zonas ocultas", f"coincidencia {fps[0]['score']:.0%}")
        for r in protect.read_refs(img):
            add(r, i + 1, "Referencia escrita en la copia")
    for x in delivered:
        add(x["ref"], 1, "Huella exacta del archivo" if x["exact"] else "Huella exacta de la parte entregada",
            "idéntico a la copia guardada" if x["exact"] else "con cambios añadidos después (p. ej. el acuse de recibo)")
    for e in found.values():  # copias con fecha de caducidad
        e["caducada"] = protect.expired((e.get("record") or {}).get("caduca"))
    result = {"found": sorted(found.values(), key=lambda e: -len(e["methods"])), "hints": protect.provenance_hints(d.orig),
              "file": delivered, "signatures": sigs, "sig_error": sig_error}
    # para el informe en PDF (sin volver a analizar)
    thumb = imgs[0].copy() if imgs else None
    if thumb is not None:
        thumb.thumbnail((1200, 1200))
        buf = io.BytesIO()
        thumb.save(buf, "PNG")
        d.check_img = buf.getvalue()
    d.check = result
    return result


def op_wm_report(req):
    """Informe de la última comprobación en PDF, con sello de tiempo si hay internet."""
    d = get_doc(req)
    if not getattr(d, "check", None):
        raise ValueError("Comprueba primero la copia.")
    import report
    pdf = report.build(d.check, d.name, d.orig, getattr(d, "check_img", None))
    stamped = False
    if req.get("tsa"):
        pdf, stamped = report.timestamp(pdf, req["tsa"])
    res = store_result([(f"informe_comprobacion_{d.base}_{datetime.date.today():%Y-%m-%d}.pdf", pdf)])
    res["notes"] = ["con sello de tiempo cualificado" if stamped else
                    ("sin sello de tiempo (sin conexión)" if req.get("tsa") else "sin sello de tiempo")]
    return res


def op_wm_registry(req):
    reg = protect._load_registry()
    st = records.settings()
    return {"items": [dict(ref=k, **v) for k, v in reversed(list(reg.items()))],
            "backup": {"folder": st.get("copia_historial", ""), "last": st.get("ultima_copia", ""),
                       "error": st.get("error_copia", ""), "damaged": st.get("error_historial", "")}}


def op_registry_export(req):
    data = json.dumps(records.export_data(), ensure_ascii=False, indent=2).encode()
    return store_result([(f"historial_DocGuard_{datetime.date.today():%Y-%m-%d}.json", data)])


def op_registry_import(req):
    d = get_doc(req)
    try:
        data = json.loads(d.orig.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError("El archivo no es un historial de DocGuard (.json).")
    return records.import_data(data)


def op_registry_delete(req):
    records.delete("entregas", req["ref"])
    return {}


def op_registry_backup(req):
    ok = records.set_backup_folder(req.get("folder", ""))
    if ok is False:
        raise ValueError("No se ha podido copiar en esa carpeta: " + records.settings().get("error_copia", ""))
    return op_wm_registry({})["backup"]


# ---- censura ----

def page_words(d, n):
    page = d.doc[n]
    words = core.native_words(page)
    return words if words else d.ocr.get(n, [])


def op_words(req):
    d = get_doc(req)
    n = int(req["n"])
    need_pdf(d)
    native = core.native_words(d.doc[n])
    words = native or d.ocr.get(n, [])
    page = d.doc[n]
    return {"words": [{"bbox": editor.to_view(page, r), "text": t} for r, t in words],
            "source": "pdf" if native else ("ocr" if n in d.ocr else "none")}


def op_pages_without_text(req):
    d = get_doc(req)
    need_pdf(d)
    return {"pages": [i for i in range(len(d.doc)) if i not in d.ocr and not core.native_words(d.doc[i])],
            "ocr_available": core.ocr_available()}


def op_ocr(req):
    d = get_doc(req)
    need_pdf(d)
    n = int(req["n"])
    d.ocr[n] = core.ocr_page_words(d.doc[n])
    return {"words": len(d.ocr[n])}


def op_detect(req):
    d = get_doc(req)
    need_pdf(d)
    found = {}
    for n in range(len(d.doc)):
        page = d.doc[n]
        for kind, groups in core.detect_sensitive(page_words(d, n)).items():
            for g in groups:
                text = " ".join(t for r, t in page_words(d, n) if any(r == q for q in g))
                found.setdefault(kind, []).append({"n": n, "rects": [editor.to_view(page, r) for r in g],
                                                   "text": text})
    # Datos de DNI / pasaporte (en documentos cortos, que es donde suelen estar)
    if len(d.doc) <= 6:
        for n in range(len(d.doc)):
            res = id_fields(d, n)
            W, H = d.doc[n].rect.width, d.doc[n].rect.height
            for it in res["items"]:
                key = "DNI/pasaporte · " + it["label"]
                found.setdefault(key, []).append({"n": n, "text": it["text"] or it["label"],
                                                  "rects": [[r[0] * W, r[1] * H, r[2] * W, r[3] * H] for r in it["rects"]]})
    return {"found": found}


def op_search(req):
    d = get_doc(req)
    need_pdf(d)
    term = req["term"].strip()
    low = term.lower()
    hits = []
    for n, page in enumerate(d.doc):
        rs = page.search_for(term) + [r for r, w in d.ocr.get(n, []) if low in w.lower()]
        if rs:
            hits.append({"n": n, "rects": [editor.to_view(page, r) for r in rs]})
    return {"hits": hits}


def marks_file(d):
    folder = os.path.join(core.config_dir(), "censuras")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, hashlib.sha256(d.orig).hexdigest()[:24] + ".json")


def op_marks_load(req):
    d = get_doc(req)
    try:
        with open(marks_file(d), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"marks": {}}


def op_marks_save(req):
    d = get_doc(req)
    path = marks_file(d)
    if not any(req.get("marks", {}).values()):
        if os.path.exists(path):
            os.remove(path)
        return {}
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"marks": req["marks"], "style": req.get("style", "")}, f)
    return {}


# ---- escáner ----

def scan_source(d, n):
    """Imagen original a buena resolución para escanear (en caché)."""
    if not hasattr(d, "scanimg"):
        d.scanimg = {}
    if n not in d.scanimg:
        d.scanimg[n] = doc_image(d, n, maxside=3200)
    return d.scanimg[n]


def op_scan_detect(req):
    d = get_doc(req)
    n = int(req.get("n", 0))
    img = scan_source(d, n)
    quad, conf = scan.detect_quad(img)
    return {"quad": quad, "conf": conf, "kind": scan.guess_kind(img, quad)}


def op_scan_preview(req):
    d = get_doc(req)
    n = int(req.get("n", 0))
    out, _ = scan.process(scan_source(d, n), req["quad"], req.get("kind", "auto"), req.get("mode", "auto"),
                          int(req.get("rot", 0)), max_side=int(req.get("maxw", 900)))
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=88)
    return ("image/jpeg", buf.getvalue())


def op_scan_export(req):
    pages, names = [], []
    for it in req["pages"]:
        d = DOCS[it["id"]]
        img, kind = scan.process(scan_source(d, int(it.get("n", 0))), it["quad"], req.get("kind", "auto"),
                                 req.get("mode", "auto"), int(it.get("rot", 0)), max_side=3000)
        pages.append((img, kind))
        names.append(d.base)
    base = (names[0] if len(set(names)) == 1 else "escaneo") + "_escaneado"
    fmt = req.get("fmt", "pdf")
    if fmt == "pdf":
        data = scan.digitalize(pages, req.get("layout", "paginas"), bool(req.get("ocr", True)))
        if req.get("pdfa"):
            data = pdfa.convert(data, base.replace("_", " "))
        res = store_result([(base + ".pdf", data)])
        import pymupdf as _f
        with _f.open("pdf", data) as _d:
            hojas = len(_d)
        res["notes"] = [f"{len(pages)} imagen(es) en {hojas} hoja(s)" + (" con texto reconocido" if req.get("ocr", True) else "")
                        + (" · PDF/A-2b" if req.get("pdfa") else "")]
        return res
    files = []
    for k, (img, _kind) in enumerate(pages):
        buf = io.BytesIO()
        img.save(buf, "PNG" if fmt == "png" else "JPEG", **({} if fmt == "png" else {"quality": 92}))
        files.append((f"{base}{'_' + str(k + 1) if len(pages) > 1 else ''}.{fmt}", buf.getvalue()))
    return store_result(files)


MOBILE = None  # sesión de «Escanear con el móvil» (servidor temporal aparte, solo en la red local)


def op_mobile_start(req):
    global MOBILE
    import mobile
    if MOBILE:
        MOBILE.stop()
    MOBILE = mobile.Session()
    import qrcode
    buf = io.BytesIO()
    qrcode.make(MOBILE.url, box_size=8, border=2).save(buf)
    return {"url": MOBILE.url, "qr": base64.b64encode(buf.getvalue()).decode(), "left": mobile.LIFETIME}


def op_mobile_status(req):
    if not MOBILE:
        return {"alive": False, "left": 0, "count": 0, "items": []}
    items = []
    for name, data in MOBILE.take():
        did = secrets.token_urlsafe(8)
        DOCS[did] = Doc(name, data)
        items.append(DOCS[did].info(did))
    import time
    return {"alive": MOBILE.alive, "left": int(max(0, MOBILE.expires - time.time())), "count": MOBILE.count, "items": items}


def op_mobile_stop(req):
    global MOBILE
    if MOBILE:
        MOBILE.stop()
        MOBILE = None
    return {}


def op_redact_preview(req):
    """Aplica la censura a una copia y la abre como documento para verla antes de guardar."""
    res = op_redact(req)
    name, data = RESULTS[res["rid"]][0]
    did = secrets.token_urlsafe(8)
    DOCS[did] = Doc(name, data)
    return {"info": DOCS[did].info(did), "rid": res["rid"]}


def op_search_many(req):
    """Busca en varios documentos a la vez. Devuelve, por documento, las páginas con
    coincidencias, sus recuadros y un fragmento de contexto."""
    term = req["term"].strip()
    low = term.lower()
    out = []
    total = 0
    for did in req["ids"]:
        d = DOCS.get(did)
        if not d or not d.doc or d.encrypted:
            continue
        pages = []
        for n, page in enumerate(d.doc):
            rects = page.search_for(term)
            if not rects:
                continue
            text = " ".join(page.get_text().split())
            i = text.lower().find(low)
            snippet = ("…" if i > 50 else "") + text[max(0, i - 50):i + len(term) + 70] + "…" if i >= 0 else ""
            pages.append({"n": n, "rects": [editor.to_view(page, r) for r in rects], "snippet": snippet})
            total += len(rects)
        out.append({"id": did, "pages": pages, "no_text": all(not p.get_text().strip() for p in d.doc)})
    return {"docs": out, "total": total}


def op_redact(req):
    d = get_doc(req)
    doc = need_pdf(d)
    marks = {}
    for n, lst in req["marks"].items():
        page = doc[int(n)]
        marks[int(n)] = [editor.from_view(page, r) for r in lst]
    with tempfile.TemporaryDirectory() as tmp:
        dst = os.path.join(tmp, f"{d.base}_censurado.pdf")
        core.redact_pdf(doc, marks, dst, core.REDACT_STYLES.get(req.get("style"), "black"))
        return store_result([(n, status_icons.mark_pdf(b, "censurado") if n.lower().endswith(".pdf") else b)
                             for n, b in read_outputs(tmp)])


# ---- páginas ----

def op_pages_save(req):
    d = get_doc(req)
    need_pdf(d)
    items = [(int(i), int(r)) for i, r in req["items"]]
    mode = req.get("mode", "one")
    with as_file(d) as (path, tmp):
        out = os.path.join(tmp, "out")
        os.makedirs(out)
        if mode == "one":
            core.save_pages(path, items, os.path.join(out, f"{d.base}_{req.get('suffix', 'editado')}.pdf"))
        elif mode == "each":
            for k, it in enumerate(items):
                core.save_pages(path, [it], os.path.join(out, f"{d.base}_p{k + 1:03d}.pdf"))
        elif mode == "ranges":
            for g in core.parse_ranges(req["ranges"], len(items)):
                label = f"{g[0] + 1}-{g[-1] + 1}" if len(g) > 1 else f"{g[0] + 1}"
                core.save_pages(path, [items[i] for i in g], os.path.join(out, f"{d.base}_{label}.pdf"))
        return store_result(read_outputs(out))


# ---- contraseña ----

def op_encrypt(req):
    d = get_doc(req)
    need_pdf(d)
    with as_file(d) as (path, tmp):
        dst = os.path.join(tmp, "out", f"{d.base}_protegido.pdf")
        os.makedirs(os.path.dirname(dst))
        core.encrypt_pdf(path, dst, req["user_pw"], req.get("owner_pw", ""), bool(req.get("print")),
                         bool(req.get("copy")), bool(req.get("edit")))
        return store_result(read_outputs(os.path.dirname(dst)))


def op_decrypt(req):
    d = get_doc(req)
    if d.kind != "pdf":
        raise ValueError("Solo se puede quitar la contraseña de un PDF.")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in.pdf")
        with open(src, "wb") as f:
            f.write(d.orig)
        dst = os.path.join(tmp, f"{d.base}_sin_clave.pdf")
        core.decrypt_pdf(src, dst, req.get("password", ""))
        return store_result(read_outputs(tmp, exclude=(src,)))


# ---- herramientas por lotes ----

def batch(req, func):
    files, notes, errors = [], [], []
    for did in req["ids"]:
        d = DOCS[did]
        try:
            with as_file(d) as (path, tmp):
                out = os.path.join(tmp, "out")
                os.makedirs(out)
                note = func(d, path, out)
                if note:
                    notes.append(note)
                files += read_outputs(out)
        except Exception as ex:
            errors.append(f"{d.name}: {ex}")
    res = store_result(files) if files else {"rid": None, "files": []}
    res.update(notes=notes, errors=errors)
    return res


def op_compress(req):
    def f(d, path, out):
        if core.ext_of(path) != ".pdf":
            raise ValueError("no es un PDF")
        before, after = core.compress_pdf(path, os.path.join(out, f"{d.base}_comprimido.pdf"), req["level"])
        return f"{d.name}: {before / 1024:.0f} KB → {after / 1024:.0f} KB"
    return batch(req, f)


def op_toimages(req):
    def f(d, path, out):
        if core.ext_of(path) != ".pdf":
            raise ValueError("no es un PDF")
        core.pdf_to_images(path, out, req.get("fmt", "png"), int(req.get("dpi", 200)))
    return batch(req, f)


def op_topdf(req):
    def f(d, path, out):
        core.merge_files([path], os.path.join(out, d.base + ".pdf"))
    return batch(req, f)


def op_todocx(req):
    def f(d, path, out):
        if core.ext_of(path) != ".pdf":
            raise ValueError("no es un PDF")
        convert.pdf_to_docx(path, os.path.join(out, d.base + ".docx"))
    return batch(req, f)


def op_doctopdf(req):
    def f(d, path, out):
        if core.ext_of(path) == ".pdf":
            raise ValueError("ya es un PDF")
        src = os.path.join(os.path.dirname(path), d.name)
        if not os.path.exists(src):
            with open(src, "wb") as fh:
                fh.write(d.orig)
        how = convert.document_to_pdf(src, os.path.join(out, d.base + ".pdf"))
        return f"{d.name}: {how}"
    return batch(req, f)


def op_sanitize(req):
    def f(d, path, out):
        src = path
        if d.kind in ("image", "office", "other") and not d.edited:
            src = os.path.join(os.path.dirname(path), d.name)
        core.sanitize_file(src, os.path.join(out, f"{d.base}_limpio{core.ext_of(src)}"))
    return batch(req, f)


def op_merge_pages(req):
    """Une páginas sueltas de varios documentos en el orden indicado: items = [[id, página, giro]]."""
    out = fitz.open()
    for did, idx, rot in req["items"]:
        d = DOCS[did]
        src = need_pdf(d)
        out.insert_pdf(src, from_page=int(idx), to_page=int(idx))
        p = out[-1]
        p.set_rotation((p.rotation + int(rot)) % 360)
    out.set_metadata({})
    data = out.tobytes(garbage=4, deflate=True)
    out.close()
    return store_result([(req.get("name") or "unido.pdf", data)])


def op_merge(req):
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for k, did in enumerate(req["ids"]):
            d = DOCS[did]
            need_pdf(d)
            p = os.path.join(tmp, f"{k:03d}.pdf")
            with open(p, "wb") as f:
                f.write(d.pdf_bytes())
            paths.append(p)
        dst = os.path.join(tmp, req.get("name") or "unido.pdf")
        core.merge_files(paths, dst)
        with open(dst, "rb") as f:
            return store_result([(os.path.basename(dst), f.read())])


# ---- edición ----

def op_edit_state(req):
    d = get_doc(req)
    doc = need_pdf(d)
    n = int(req["n"])
    page = doc[n]
    return {"spans": editor.spans(page), "images": editor.images(page), "annots": editor.annotations(page),
            "widgets": editor.widgets(page), "can_undo": bool(d.undo), "can_redo": bool(d.redo),
            "size": [page.rect.width, page.rect.height]}


def op_comments(req):
    return {"comments": editor.list_comments(need_pdf(get_doc(req)))}


def op_copy_object(req):
    d = get_doc(req)
    return editor.copy_object(need_pdf(d), int(req["n"]), req["kind"], int(req["xref"]))


def op_edit_words(req):
    """Palabras de la página en orden de lectura (para seleccionar texto al resaltar)."""
    d = get_doc(req)
    page = need_pdf(d)[int(req["n"])]
    words = editor.reading_words(page)
    return {"words": words, "has_text": bool(words), "rotation": page.rotation}


def op_outline(req):
    d = get_doc(req)
    return {"toc": [[lvl, title, page] for lvl, title, page in need_pdf(d).get_toc(simple=True) if page > 0]}


def op_compare(req):
    a, b = DOCS[req["a"]], DOCS[req["b"]]
    return compare.compare(need_pdf(a), need_pdf(b))


def op_fonts(req):
    return {"fonts": editor.font_choices()}


def rotate_pages(doc, deg, pages=None):
    """Gira las páginas (todas si no se indican) en múltiplos de 90°."""
    for i in (range(len(doc)) if pages is None else pages):
        doc[int(i)].set_rotation((doc[int(i)].rotation + int(deg)) % 360)


EDIT_OPS = {
    "rotate": lambda doc, r: rotate_pages(doc, r["deg"], r.get("pages")),
    "remove_watermarks": lambda doc, r: str(marcas_agua.remove(doc)),
    "replace_text": lambda doc, r: editor.replace_span(doc, r["n"], r["i"], r.get("text", ""), r.get("font", "auto"),
                                                      r.get("size"), r.get("color"), r.get("bold"), r.get("italic")),
    "add_text": lambda doc, r: editor.add_text(doc, r["n"], r["x"], r["y"], r["text"], r.get("font", "base:helv"),
                                              float(r.get("size", 12)), r.get("color", "#000000"),
                                              r.get("bold", False), r.get("italic", False)),
    "add_table": lambda doc, r: editor.add_table(doc, r["n"], r["rect"], r["cells"], float(r.get("size", 11)),
                                                r.get("color", "#000000"), r.get("stroke", "#000000"),
                                                float(r.get("width", 1)), bool(r.get("header", True)),
                                                r.get("fill", "#e8e8e8"), r.get("font", "base:helv")),
    "insert_image": lambda doc, r: editor.insert_image(doc, r["n"], r["rect"], base64.b64decode(r["data"])),
    "move_image": lambda doc, r: editor.move_image(doc, r["n"], r["xref"], r["rect"]),
    "delete_image": lambda doc, r: editor.delete_image(doc, r["n"], r["xref"]),
    "add_annot": lambda doc, r: editor.add_annotation(doc, r["n"], r["kind"], r["rect"], r.get("text", ""),
                                                     r.get("color", "#ffd400"), float(r.get("size", 12)), r.get("author", "")),
    "edit_comment": lambda doc, r: editor.edit_comment(doc, r["n"], r["xref"], r.get("text", "")),
    "add_ink": lambda doc, r: editor.add_ink(doc, r["n"], r["strokes"], r.get("color", "#1a4fd6"),
                                            float(r.get("width", 2))),
    "header_footer": lambda doc, r: editor.header_footer(
        doc, r.get("number", ""), r.get("number_pos", "abajo-centro"), r.get("header", ""), r.get("header_align", "centro"),
        r.get("footer", ""), r.get("footer_align", "izquierda"), float(r.get("size", 9)), r.get("color", "#444444"),
        int(r.get("start", 1)), bool(r.get("skip_first")),
        sorted({p for g in core.parse_ranges(r["ranges"], len(doc)) for p in g}) if r.get("ranges") else None,
        r.get("filename", "")),
    "move_spans": lambda doc, r: editor.move_spans(doc, r["n"], r["indices"], float(r["dx"]), float(r["dy"])),
    "scale_spans": lambda doc, r: editor.scale_spans(doc, r["n"], r["indices"], float(r["factor"]), r["anchor"]),
    "format_spans": lambda doc, r: editor.format_spans(doc, r["n"], r["indices"], r.get("font", "auto"), r.get("size"),
                                                      r.get("color"), r.get("bold"), r.get("italic")),
    "delete_spans": lambda doc, r: editor.delete_spans(doc, r["n"], r["indices"]),
    "add_shape": lambda doc, r: editor.add_shape(doc, r["n"], r["kind"], r.get("rect"), r.get("stroke", "#d62828"),
                                                r.get("fill"), float(r.get("width", 2)), r.get("points"),
                                                r.get("dash", "continua"), float(r.get("opacity", 1))),
    "paste_object": lambda doc, r: editor.paste_object(doc, r["n"], r["spec"], r["x"], r["y"]),
    "style_annot": lambda doc, r: editor.style_annotation(doc, r["n"], r["xref"], r.get("stroke"), r.get("fill", "keep"),
                                                         r.get("width"), r.get("dash"), r.get("opacity"), r.get("ends")),
    "add_markup": lambda doc, r: editor.add_markup(doc, r["n"], r["kind"], r["rects"], r.get("color", "#fff200"),
                                                  bool(r.get("area"))),
    "move_annot": lambda doc, r: editor.move_annotation(doc, r["n"], r["xref"], r["rect"]),
    "set_line": lambda doc, r: editor.set_line(doc, r["n"], r["xref"], r["points"]),
    "paste": lambda doc, r: editor.paste_region(doc, r["n"], CLIPBOARD["clip"], float(r["x"]), float(r["y"]),
                                               r.get("mode", "auto")),
    "paste_spans": lambda doc, r: editor.paste_spans(doc, r["n"], CLIPBOARD["spans"], float(r["x"]), float(r["y"])),
    "ocr": lambda doc, r: f"{sum(editor.ocr_page(doc, p, r.get('mode', 'editable')) for p in r['pages'])} líneas",
    "delete_annot": lambda doc, r: editor.delete_annotation(doc, r["n"], r["xref"]),
    "add_widget": lambda doc, r: editor.add_widget(doc, r["n"], r["type"], r["rect"], r["name"], r.get("value"),
                                                  r.get("options")),
    "update_widget": lambda doc, r: editor.update_widget(doc, r["n"], r["xref"], r.get("name"), r.get("value"),
                                                        r.get("options"), r.get("rect")),
    "delete_widget": lambda doc, r: editor.delete_widget(doc, r["n"], r["xref"]),
    "flatten": lambda doc, r: editor.flatten_forms(doc),
}


def op_edit(req, name):
    d = get_doc(req)
    doc = need_pdf(d)
    snapshot = doc.tobytes()
    result = EDIT_OPS[name](doc, req)
    d.undo.append(snapshot)
    del d.undo[:-MAX_UNDO]
    d.redo = []
    d.edited = True
    d.lines, d.ocr, d.idf = {}, {}, {}  # el texto puede haber cambiado
    # Recargar tras cada cambio mantiene coherentes las listas de texto/imágenes/campos.
    d.doc = fitz.open("pdf", doc.tobytes())
    return {"message": result if isinstance(result, str) else ""}


CLIPBOARD = {}


def op_copy(req):
    d = get_doc(req)
    clip, text, png = editor.copy_region(need_pdf(d), int(req["n"]), req["rect"])
    CLIPBOARD["clip"] = clip
    return {"text": text, "png": base64.b64encode(png).decode(), "size": clip["size"]}


def op_copy_spans(req):
    d = get_doc(req)
    clip, text = editor.copy_spans(need_pdf(d), int(req["n"]), req["indices"])
    CLIPBOARD["spans"] = clip
    return {"text": text}


def op_sign_margin(req):
    d = get_doc(req)
    doc = need_pdf(d)
    png = sigimg_bytes(req["sig"])
    img = Image.open(io.BytesIO(png))
    pages = None
    if req.get("ranges"):
        pages = sorted({p for g in core.parse_ranges(req["ranges"], len(doc)) for p in g})
    req = dict(req, n=0)

    def do(doc_, r):
        return f"{editor.sign_margin(doc_, png, r.get('side', 'derecha'), float(r.get('length', 22)), pages, img.width / img.height)} páginas firmadas"
    EDIT_OPS["_margin"] = do
    try:
        return op_edit(req, "_margin")
    finally:
        EDIT_OPS.pop("_margin", None)


def op_redo(req):
    d = get_doc(req)
    if d.redo:
        d.undo.append(d.doc.tobytes())
        d.doc = fitz.open("pdf", d.redo.pop())
        d.edited = True
        d.lines, d.ocr, d.idf = {}, {}, {}
    return {"can_undo": bool(d.undo), "can_redo": bool(d.redo)}


def op_undo(req):
    d = get_doc(req)
    if d.undo:
        d.redo.append(d.doc.tobytes())
        d.doc = fitz.open("pdf", d.undo.pop())
        d.lines, d.ocr, d.idf = {}, {}, {}
        d.edited = bool(d.undo) or d.kind != "pdf"
    return {"can_undo": bool(d.undo), "can_redo": bool(d.redo)}


def op_edit_export(req):
    d = get_doc(req)
    need_pdf(d)
    return store_result([(f"{d.base}_editado.pdf", d.doc.tobytes(garbage=3, deflate=True))])


# ---- firmas ----

def sig_dir():
    p = os.path.join(core.config_dir(), "firmas")
    os.makedirs(p, exist_ok=True)
    return p


def op_sigimgs(req):
    out = []
    for f in sorted(os.listdir(sig_dir())):
        if f.endswith(".png"):
            with open(os.path.join(sig_dir(), f), "rb") as fh:
                out.append({"id": f[:-4], "png": base64.b64encode(fh.read()).decode()})
    return {"items": out}


def op_sigimg_save(req):
    data = base64.b64decode(req["png"])
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    bbox = img.getbbox()
    if not bbox:
        raise ValueError("La firma está vacía.")
    img = img.crop(bbox)
    if req.get("remove_white"):  # imagen escaneada: el fondo blanco pasa a transparente
        px = [(r, g, b, 0 if r > 225 and g > 225 and b > 225 else a) for r, g, b, a in img.getdata()]
        img.putdata(px)
    sid = secrets.token_hex(6)
    img.save(os.path.join(sig_dir(), sid + ".png"))
    return {"id": sid}


def op_sigimg_delete(req):
    path = os.path.join(sig_dir(), os.path.basename(req["id"]) + ".png")
    if os.path.exists(path):
        os.remove(path)
    return {}


def sigimg_bytes(sid):
    with open(os.path.join(sig_dir(), os.path.basename(sid) + ".png"), "rb") as f:
        return f.read()


def op_place_sigimg(req):
    req = dict(req, data=base64.b64encode(sigimg_bytes(req["sig"])).decode())
    return op_edit(req, "insert_image")


def op_certinfo(req):
    return signing.cert_info(base64.b64decode(req["p12"]), req.get("password", ""))


def op_sign(req):
    d = get_doc(req)
    doc = need_pdf(d)
    img = sigimg_bytes(req["sig"]) if req.get("sig") else None
    data = d.pdf_bytes()
    opts = dict(page=int(req["n"]) if req.get("rect") is not None else None, view_rect=req.get("rect"), field_name=req.get("field") or None,
                reason=req.get("reason", ""), location=req.get("location", ""),
                contact=req.get("contact", ""), image_png=img, tsa_url=req.get("tsa") or None)
    if req.get("margin"):
        # firma pequeña en un margen añadido debajo de la página, fuera del contenido
        if any(f["signed"] for f in signing.list_signature_fields(data)):
            raise ValueError("El documento ya tiene firmas: añadir el margen las invalidaría. "
                             "Dibuja el recuadro de tu firma dentro de la página.")
        n = int(req.get("n") or 0)
        m = signing.band_metrics(doc[n].rect.width)
        data, band = signing.add_margin(data, n, m["h"])
        opts.update(page=n, field_name=None, font_size=max(5, round(m["fs"])), view_rect=[
            band[2] - m["pad"] - m["sig_w"], band[1] + m["pad"] * 0.55, band[2] - m["pad"], band[3] - m["pad"] * 0.55])
    notes = []
    opts.update(ltv=bool(req.get("ltv")), notes=notes)
    if req.get("source") == "card":
        if not req.get("pin"):
            raise ValueError("Escribe el PIN de la tarjeta.")
        out = signing.sign_pdf_pkcs11(data, req["module"], req["token"], req["cert_id"], req["pin"],
                                      token_serial=req.get("serial"), **opts)
    else:
        out = signing.sign_pdf(data, base64.b64decode(req["p12"]), req.get("password", ""), **opts)
    base = d.base if d.base.endswith("_firmado") else d.base + "_firmado"
    res = store_result([(f"{base}.pdf", out)])
    # seguimiento: si se envía a otro o aún faltan firmas, se anota la huella de lo que sale
    if req.get("track") or any(not f["signed"] for f in signing.list_signature_fields(out)):
        tracking.register(f"{base}.pdf", out)
        notes.append("anotado en «Documentos enviados a firmar»")
    res["notes"] = notes
    return res


def op_track_add(req):
    name, data = RESULTS[req["rid"]][0]
    return {"key": tracking.register(name, data)}


def op_track_check(req):
    d = get_doc(req)
    if d.kind != "pdf":
        return {"match": False}
    return tracking.check(d.name, d.pdf_bytes(), req.get("password"))


def op_track_list(req):
    return {"items": tracking.listing()}


def op_track_delete(req):
    tracking.delete(req["key"])
    return {}


def op_sign_batch(req):
    """Firma varios PDF con una sola sesión (el PIN del DNIe se usa una vez). Si el sello de tiempo
    o la validación fallan en uno, el resto se firma sin ellos (para no esperar a cada archivo)."""
    place = req.get("place", "margin_last")
    tsa, ltv = req.get("tsa") or None, bool(req.get("ltv"))
    files, errors, notes, names = [], [], [], set()
    with signing.open_signer(req) as signer:
        for did in req["ids"]:
            d = DOCS.get(did)
            if not d:
                continue
            try:
                doc = need_pdf(d)
                data, warn = d.pdf_bytes(), []
                opts = dict(reason=req.get("reason", ""), location=req.get("location", ""), contact=req.get("contact", ""),
                            tsa_url=tsa, ltv=ltv, notes=warn)
                if place.startswith("margin"):
                    if any(f["signed"] for f in signing.list_signature_fields(data)):
                        raise ValueError("ya tiene firmas y el margen las invalidaría (fírmalo dentro de la página)")
                    n = 0 if place == "margin_first" else len(doc) - 1
                    m = signing.band_metrics(doc[n].rect.width)
                    data, band = signing.add_margin(data, n, m["h"])
                    opts.update(page=n, font_size=max(5, round(m["fs"])), view_rect=[
                        band[2] - m["pad"] - m["sig_w"], band[1] + m["pad"] * 0.55, band[2] - m["pad"], band[3] - m["pad"] * 0.55])
                out = signing.sign_pdf(data, None, None, signer=signer, **opts)
                if warn:
                    notes.append(f"{d.name}: {'; '.join(warn)}; los siguientes se firman sin ello")
                    tsa, ltv = (None, False) if any("sello" in w for w in warn) else (tsa, False)
                base = d.base if d.base.endswith("_firmado") else d.base + "_firmado"
                name, k = f"{base}.pdf", 2
                while name in names:
                    name, k = f"{base}_{k}.pdf", k + 1
                names.add(name)
                files.append((name, out))
            except Exception as ex:
                if isinstance(ex, signing._PinError) or type(ex).__module__.split(".")[0] == "pkcs11":
                    raise  # PIN o tarjeta: se detiene todo
                errors.append(f"{d.name}: {ex}")
    if not files:
        raise ValueError("No se ha podido firmar ningún archivo. " + " · ".join(errors))
    res = store_result(files)
    res.update(errors=errors, notes=[f"{len(files)} PDF firmado(s)"] + notes)
    return res


def op_sign_test(req):
    """«Probar mi firma»: firma un PDF de prueba con el sello y la validación elegidos y
    devuelve un informe. No se anota en ningún historial."""
    notes = []
    tsa = req.get("tsa") or None
    with signing.open_signer(req) as signer:
        profile = signing.cert_profile(signer.signing_cert)
        out = signing.sign_pdf(signing.test_document(), None, None, signer=signer, page=0,
                               view_rect=[330, 700, 555, 770], reason="Prueba de firma", tsa_url=tsa,
                               ltv=bool(req.get("ltv")), notes=notes)
    sig = signing.verify_pdf(out)[0]
    res = store_result([("prueba_de_firma_DocGuard.pdf", out)])
    res.update(profile=profile, signature=sig, notes=notes, tsa_requested=bool(tsa), ltv_requested=bool(req.get("ltv")))
    return res


def op_sig_fields(req):
    d = get_doc(req)
    if d.kind != "pdf" or d.edited:
        return {"fields": signing.list_signature_fields(d.pdf_bytes())} if d.doc else {"fields": []}
    return {"fields": signing.list_signature_fields(d.orig)}


def op_sig_fields_add(req):
    d = get_doc(req)
    need_pdf(d)
    out = signing.add_signature_fields(d.pdf_bytes(), req["fields"])
    res = store_result([(f"{d.base}_para_firmar.pdf", out)])
    did = secrets.token_urlsafe(8)
    DOCS[did] = Doc(res["files"][0]["name"], out)
    return {"info": DOCS[did].info(did), "rid": res["rid"]}


def op_p11_modules(req):
    return {"modules": signing.pkcs11_modules()}


def op_p11_login(req):
    return signing.pkcs11_login(req["module"], req["token"], req["cert_id"], req["pin"], req.get("serial"))


def op_p11_list(req):
    return {"tokens": signing.pkcs11_list(req["module"])}


def op_verify(req):
    # Va en NO_LOCK: se copia el PDF con el bloqueo y se comprueba fuera, para que la comprobación
    # de firmas (que puede tardar más de medio segundo) no retrase el dibujo de las páginas.
    with LOCK:
        d = get_doc(req)
        if d.kind != "pdf":
            raise ValueError("Solo se pueden verificar PDFs.")
        data = d.orig if not d.edited else d.pdf_bytes()
        password = d.password if not d.edited else None
    return {"signatures": signing.verify_pdf(data, password=password, online=bool(req.get("online")))}


def op_unlock(req):
    """Abre un PDF con contraseña: se trabaja con él descifrado (el original sigue igual)."""
    d = get_doc(req)
    if d.kind != "pdf" or not d.encrypted:
        return d.info(req["id"])
    pw = req.get("password") or ""
    if not d.doc.authenticate(pw):
        raise ValueError("Contraseña incorrecta.")
    d.password = pw
    d.encrypted = False
    return d.info(req["id"])


def op_presets(req):
    return {"presets": core.load_presets()}


def op_presets_save(req):
    core.save_presets(req["presets"])
    return {}


def op_watermarks(req):
    """Marcas de agua que se pueden quitar (sin cambiar nada): [{n, kind, text}]."""
    return {"found": marcas_agua.find(need_pdf(get_doc(req)))}


def op_ui(req):
    """Preferencias de la interfaz (p. ej. barra lateral oculta). Se guardan en la configuración,
    porque la ventana nativa no conserva el almacenamiento del navegador entre sesiones."""
    ui = records.settings().get("ui", {})
    if isinstance(req.get("set"), dict):
        ui.update(req["set"])
        records.save_settings(ui=ui)
    return ui


# --------------------------------------------------------------------------
# Explorador de archivos del lateral: carpetas, abrir por ruta, recientes y carpetas fijadas
# --------------------------------------------------------------------------

FS_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
FS_MAX = 3000


def _fs_hidden(entry):
    if entry.name.startswith("."):
        return True
    if sys.platform == "win32":
        try:
            return bool(entry.stat(follow_symlinks=False).st_file_attributes & 0x2)  # oculto
        except OSError:
            return False
    return False


def _fs_drives():
    if sys.platform == "win32":
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()  # sin sondear las unidades (las de red pueden tardar)
        return [{"name": f"{chr(65 + i)}:", "path": f"{chr(65 + i)}:\\"} for i in range(26) if mask >> i & 1]
    drives = [{"name": "Equipo", "path": "/"}]
    if sys.platform == "darwin" and os.path.isdir("/Volumes"):
        for n in sorted(os.listdir("/Volumes")):
            if os.path.isdir(os.path.join("/Volumes", n)):
                drives.append({"name": n, "path": os.path.join("/Volumes", n)})
    return drives


def _fs_places():
    home = os.path.expanduser("~")
    places = [{"name": "Inicio", "path": home}]
    for label, names in (("Escritorio", ("Desktop", "Escritorio")), ("Documentos", ("Documents", "Documentos")),
                         ("Descargas", ("Downloads", "Descargas"))):
        found = next((p for base in (home, os.path.join(home, "OneDrive")) for n in names
                      for p in [os.path.join(base, n)] if os.path.isdir(p)), None)
        if found:
            places.append({"name": label, "path": found})
    return places


def _fs_crumbs(path):
    crumbs = [{"name": "Este equipo", "path": ""}] if sys.platform == "win32" else []
    if not path:
        return crumbs
    drive, rest = os.path.splitdrive(os.path.normpath(path))
    acc = (drive + os.sep) if drive else os.sep
    crumbs.append({"name": drive or os.sep, "path": acc})
    for part in [x for x in rest.split(os.sep) if x]:
        acc = os.path.join(acc, part)
        crumbs.append({"name": part, "path": acc})
    return crumbs


def _fs_pins():
    pins = [p for p in records.settings().get("ui", {}).get("fx_pins", []) if os.path.isdir(p)]
    return [{"name": os.path.basename(p.rstrip("\\/")) or p, "path": p} for p in pins]


def op_fs_list(req):
    ui = records.settings().get("ui", {})
    path = req.get("path")
    if path is None:
        path = ui.get("fx_path") or os.path.expanduser("~")
    if path and not os.path.isdir(path):
        path = os.path.expanduser("~")
    if not path and sys.platform != "win32":
        path = "/"
    out = {"places": _fs_places(), "drives": _fs_drives(), "pins": _fs_pins(), "sep": os.sep}
    entries, truncated = [], False
    if not path and sys.platform == "win32":  # «Este equipo»: las unidades
        entries = [{"name": d["name"], "path": d["path"], "kind": "dir"} for d in _fs_drives()]
        parent = None
    else:
        path = os.path.abspath(path)
        parent = os.path.dirname(path)
        parent = ("" if sys.platform == "win32" else None) if parent == path else parent
        try:
            with os.scandir(path) as it:
                for e in it:
                    if len(entries) >= FS_MAX:
                        truncated = True
                        break
                    try:
                        if _fs_hidden(e):
                            continue
                        if e.is_dir():
                            entries.append({"name": e.name, "path": e.path, "kind": "dir"})
                        elif os.path.splitext(e.name)[1].lower() in FS_EXTS:
                            st = e.stat()
                            ext = os.path.splitext(e.name)[1].lower()
                            entries.append({"name": e.name, "path": e.path, "kind": "pdf" if ext == ".pdf" else "img",
                                            "size": st.st_size, "mtime": st.st_mtime})
                    except OSError:
                        continue
        except OSError as ex:
            raise ValueError(f"No se puede abrir la carpeta: {ex.strerror or ex}")
        records.save_settings(ui={**ui, "fx_path": path})
    entries.sort(key=lambda x: (x["kind"] != "dir", x["name"].lower()))
    out.update(path=path, parent=parent, crumbs=_fs_crumbs(path), entries=entries, truncated=truncated,
               pinned=bool(path) and path in ui.get("fx_pins", []))
    return out


def _remember(path):
    s = records.settings()
    rec = [r for r in s.get("recientes", []) if r != path]
    records.save_settings(recientes=([path] + rec)[:15])


def op_fs_open(req):
    path = os.path.abspath(req["path"])
    if os.path.splitext(path)[1].lower() not in FS_EXTS or not os.path.isfile(path):
        raise ValueError("Solo se pueden abrir PDFs e imágenes.")
    with open(path, "rb") as f:
        data = f.read()
    did = secrets.token_urlsafe(8)
    DOCS[did] = Doc(os.path.basename(path), data)
    _remember(path)
    return DOCS[did].info(did)


def op_fs_pin(req):
    ui = records.settings().get("ui", {})
    pins = [p for p in ui.get("fx_pins", [])]
    p = req["path"]
    if req.get("pin", True):
        if p not in pins:
            pins.append(p)
    else:
        pins = [x for x in pins if x != p]
    records.save_settings(ui={**ui, "fx_pins": pins})
    return {"pins": _fs_pins(), "pinned": p in pins}


def op_recent(req):
    out = []
    for p in records.settings().get("recientes", []):
        try:
            st = os.stat(p)
        except OSError:
            continue
        out.append({"name": os.path.basename(p), "path": p, "folder": os.path.dirname(p), "mtime": st.st_mtime,
                    "size": st.st_size, "kind": "pdf" if p.lower().endswith(".pdf") else "img"})
    return {"files": out[:8]}


OPS = {
    "fs/list": op_fs_list, "fs/open": op_fs_open, "fs/pin": op_fs_pin, "recent": op_recent,
    "presets": op_presets, "presets/save": op_presets_save, "ui": op_ui, "watermarks": op_watermarks,
    "open_result": op_open_result, "close": op_close, "info": op_info,
    "update/check": op_update_check, "update/download": op_update_download, "version": lambda req: {"version": core.VERSION},
    "tabs/add": op_tabs_add, "tabs/list": op_tabs_list, "tabs/close": op_tabs_close,
    "wm/preview": op_wm_preview, "wm/export": op_wm_export, "wm/check": op_wm_check, "wm/report": op_wm_report,
    "wm/registry": op_wm_registry, "idfields": op_idfields, "registry/export": op_registry_export,
    "registry/import": op_registry_import, "registry/delete": op_registry_delete, "registry/backup": op_registry_backup,
    "words": op_words, "pages_without_text": op_pages_without_text, "ocr": op_ocr, "detect": op_detect,
    "search": op_search, "redact": op_redact, "redact/marks/load": op_marks_load, "redact/marks/save": op_marks_save,
    "compare": op_compare, "search_many": op_search_many,
    "scan/detect": op_scan_detect, "scan/preview": op_scan_preview, "scan/export": op_scan_export,
    "mobile/start": op_mobile_start, "mobile/status": op_mobile_status, "mobile/stop": op_mobile_stop, "sign/fields": op_sig_fields, "sign/fields/add": op_sig_fields_add,
    "todocx": op_todocx, "doctopdf": op_doctopdf, "redact/preview": op_redact_preview,
    "pages/save": op_pages_save, "encrypt": op_encrypt, "decrypt": op_decrypt,
    "compress": op_compress, "toimages": op_toimages, "topdf": op_topdf, "sanitize": op_sanitize, "merge": op_merge, "merge_pages": op_merge_pages,
    "edit/state": op_edit_state, "comments": op_comments, "edit/words": op_edit_words, "edit/copy_object": op_copy_object, "fonts": op_fonts, "outline": op_outline, "edit/undo": op_undo, "edit/redo": op_redo, "edit/export": op_edit_export,
    "sigimgs": op_sigimgs, "sigimg/save": op_sigimg_save, "sigimg/delete": op_sigimg_delete,
    "sigimg/place": op_place_sigimg, "sigimg/margin": op_sign_margin, "edit/copy": op_copy, "edit/copy_spans": op_copy_spans, "certinfo": op_certinfo, "sign": op_sign, "sign/test": op_sign_test, "sign/batch": op_sign_batch,
    "track/add": op_track_add, "track/check": op_track_check, "track/list": op_track_list, "track/delete": op_track_delete,
    "p11/modules": op_p11_modules, "p11/list": op_p11_list, "p11/login": op_p11_login, "verify": op_verify, "external/open": op_external_open, "update/progress": op_update_progress, "unlock": op_unlock,
}
for _name in EDIT_OPS:
    OPS["edit/" + _name] = (lambda nm: lambda req: op_edit(req, nm))(_name)


def zip_files(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files:
            z.writestr(name, data)
    return buf.getvalue()


def save_result_to(rid, target, is_folder):
    """Usado por la ventana nativa: guarda el resultado en el disco."""
    files = RESULTS[rid]
    if is_folder:
        paths = []
        for name, data in files:
            p = os.path.join(target, name)
            with open(p, "wb") as f:
                f.write(data)
            paths.append(p)
        return paths
    with open(target, "wb") as f:
        f.write(files[0][1] if len(files) == 1 else zip_files(files))
    return [target]


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def send(self, code, body, ctype="application/json", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def authorized(self, query):
        return secrets.compare_digest(self.headers.get("X-Token") or query.get("t", [""])[0], TOKEN)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        if url.path.startswith("/api/"):
            if not self.authorized(q):
                return self.send(403, {"error": "no autorizado"})
            try:
                with LOCK:
                    if url.path == "/api/page":
                        return self.page(q)
                    if url.path == "/api/result":
                        return self.result(q)
                    if url.path == "/api/font":
                        return self.font(q)
                    if url.path == "/api/pdf":
                        return self.pdf(q)
            except Exception as ex:
                return self.send(400, {"error": str(ex)})
            return self.send(404, {"error": "no encontrado"})
        name = "index.html" if url.path in ("/", "") else url.path.lstrip("/")
        path = os.path.realpath(os.path.join(WEB_DIR, name))
        if not path.startswith(os.path.realpath(WEB_DIR)) or not os.path.isfile(path):
            return self.send(404, b"no encontrado", "text/plain")
        with open(path, "rb") as f:
            self.send(200, f.read(), MIME.get(os.path.splitext(path)[1], "application/octet-stream"))

    def page(self, q):
        d = DOCS[q["id"][0]]
        doc = need_pdf(d)
        page = doc[int(q["n"][0])]
        zoom = max(0.05, min(float(q.get("zoom", ["1"])[0]), 6))
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False, annots=True)
        if q.get("fmt", [""])[0] == "fast" and pix.n == 3:
            # páginas grandes: PNG con compresión rápida (sin pérdida, misma imagen; se genera antes)
            buf = io.BytesIO()
            Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(buf, "PNG", compress_level=1)
            return self.send(200, buf.getvalue(), "image/png")
        self.send(200, pix.tobytes("png"), "image/png")

    def pdf(self, q):
        """El documento tal como está ahora (con las ediciones), para verlo e imprimirlo."""
        d = DOCS[q["id"][0]]
        need_pdf(d)
        disp = "inline; filename*=UTF-8''" + urllib.parse.quote(os.path.splitext(d.name)[0] + ".pdf")
        self.send(200, d.pdf_bytes(), "application/pdf", {"Content-Disposition": disp})

    def font(self, q):
        if "key" in q:
            data, ext = editor.font_file(q["key"][0])
        else:
            d = DOCS[q["id"][0]]
            data, ext = editor.font_data(need_pdf(d), int(q["n"][0]), q["name"][0])
        if not data:
            return self.send(404, {"error": "fuente no disponible"})
        self.send(200, data, "font/otf" if ext == "otf" else "font/ttf", {"Cache-Control": "max-age=3600"})

    def result(self, q):
        files = RESULTS[q["rid"][0]]
        if len(files) == 1:
            name, data = files[0]
        else:
            name, data = "docguard.zip", zip_files(files)
        disp = "attachment; filename*=UTF-8''" + urllib.parse.quote(name)
        self.send(200, data, "application/octet-stream", {"Content-Disposition": disp})

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if not url.path.startswith("/api/") or not self.authorized(urllib.parse.parse_qs(url.query)):
            return self.send(403, {"error": "no autorizado"})
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        op = url.path[len("/api/"):]
        if op in NO_LOCK:  # descargas de red: no bloquean el resto de DocGuard mientras duran
            try:
                return self.send(200, OPS[op](json.loads(body or b"{}")))
            except Exception as ex:
                return self.send(400, {"error": str(ex)})
        try:
            with LOCK:
                if op == "open":
                    name = urllib.parse.unquote(self.headers.get("X-Filename", "archivo"))
                    did = secrets.token_urlsafe(8)
                    DOCS[did] = Doc(os.path.basename(name), body)
                    return self.send(200, DOCS[did].info(did))
                if op not in OPS:
                    return self.send(404, {"error": f"operación desconocida: {op}"})
                res = OPS[op](json.loads(body or b"{}"))
            if isinstance(res, tuple):
                return self.send(200, res[1], res[0], res[2] if len(res) > 2 else None)
            return self.send(200, res)
        except Exception as ex:
            traceback.print_exc()
            msg = str(ex) or ex.__class__.__name__
            return self.send(400, {"error": msg})


def start(port=0):
    """Arranca el servidor en segundo plano. Devuelve la URL con el token."""
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_address[1]}/?t={TOKEN}", httpd
