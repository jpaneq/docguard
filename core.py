"""Lógica de procesamiento de DocGuard (sin interfaz gráfica)."""

import datetime
import io
import json
import math
import os
import random
import re
import secrets
import sys
import zipfile
from functools import lru_cache

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

APP_NAME = "DocGuard"
VERSION = "1.35"  # al publicar, la etiqueta de git debe coincidir (v1.17)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
OFFICE_EXTS = {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}
RENDER_DPI = 200

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
REGULAR_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def resource_path(name):
    """Ruta a un recurso incluido (funciona también dentro del ejecutable)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def config_dir():
    if os.environ.get("DOCGUARD_CONFIG"):  # pruebas: configuración aparte
        os.makedirs(os.environ["DOCGUARD_CONFIG"], exist_ok=True)
        return os.environ["DOCGUARD_CONFIG"]
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


@lru_cache(maxsize=64)
def get_font(size, bold=True):
    size = max(6, int(size))
    for path in (FONT_CANDIDATES if bold else REGULAR_FONTS + FONT_CANDIDATES):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default(size=size)


def ext_of(path):
    return os.path.splitext(path)[1].lower()


def suffixed(path, suffix, new_ext=None):
    base, ext = os.path.splitext(path)
    return f"{base}_{suffix}{new_ext or ext}"


def open_as_pdf(path):
    """Abre un PDF o una imagen como documento PDF."""
    doc = fitz.open(path)
    if not doc.is_pdf:
        pdf = doc.convert_to_pdf()
        doc.close()
        doc = fitz.open("pdf", pdf)
    return doc


# --------------------------------------------------------------------------
# Carga de documentos como imágenes
# --------------------------------------------------------------------------

def page_count(path):
    if ext_of(path) == ".pdf":
        with fitz.open(path) as doc:
            return len(doc)
    return 1


def load_page(path, index=0, dpi=RENDER_DPI):
    """Devuelve (PIL.Image RGB, (ancho_pt, alto_pt) o None) de una página."""
    if ext_of(path) == ".pdf":
        with fitz.open(path) as doc:
            page = doc[index]
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            return img, (page.rect.width, page.rect.height)
    img = Image.open(path)
    return ImageOps.exif_transpose(img).convert("RGB"), None


def load_pages(path, dpi=RENDER_DPI):
    return [load_page(path, i, dpi) for i in range(page_count(path))]


# --------------------------------------------------------------------------
# Marca de agua
# --------------------------------------------------------------------------

def expand_placeholders(text, now=None):
    """Sustituye {fecha} y {hora} por la fecha y hora actuales."""
    now = now or datetime.datetime.now()
    return (text.replace("{fecha}", now.strftime("%d/%m/%Y"))
                .replace("{hora}", now.strftime("%H:%M")))


def apply_watermark(img, text, angle=35, size=40, gap_x=60, gap_y=80,
                    opacity=0.35, color=(200, 0, 0), hardened=True, seed=1):
    """Aplica una marca de agua en mosaico.

    Los tamaños se expresan en milésimas del ancho de la imagen, así la vista
    previa y el resultado final se ven igual a cualquier resolución.
    Con `hardened` se añaden variaciones aleatorias (posición, opacidad,
    tamaño), líneas onduladas entrelazadas y ruido, lo que dificulta mucho
    que herramientas de IA puedan eliminar la marca limpiamente.
    """
    text = expand_placeholders(text) or " "
    rnd = random.Random(seed)
    base = img.convert("RGBA")
    W, H = base.size
    s = W / 1000.0
    diag = int(math.hypot(W, H)) + 4
    layer = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font = get_font(size * s)
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - t
    step_x = tw + max(1, gap_x * s)
    step_y = th + max(1, gap_y * s)
    a_max = int(255 * opacity)

    row = 0
    y = -step_y
    while y < diag + step_y:
        x = -step_x + (step_x / 2 if row % 2 else 0)
        while x < diag + step_x:
            jx = jy = 0
            f = font
            alpha = a_max
            if hardened:
                jx = rnd.uniform(-0.05, 0.05) * step_x
                jy = rnd.uniform(-0.25, 0.25) * th
                alpha = int(a_max * rnd.uniform(0.7, 1.0))
                f = get_font(size * s * rnd.uniform(0.9, 1.1))
            draw.text((x + jx, y + jy), text, font=f, fill=tuple(color) + (alpha,),
                      stroke_width=max(1, int(s)) if hardened else 0,
                      stroke_fill=(255, 255, 255, alpha // 3) if hardened else None)
            x += step_x
        if hardened:
            # Línea ondulada entre filas: rompe patrones regulares fáciles de borrar.
            ly = y + th + (step_y - th) / 2
            amp = max(2.0, (step_y - th) * 0.3)
            period = max(20.0, step_x / 2)
            phase = rnd.uniform(0, math.tau)
            pts = [(px, ly + amp * math.sin(px / period * math.tau + phase))
                   for px in range(0, diag, max(2, int(3 * s)))]
            draw.line(pts, fill=tuple(color) + (int(a_max * 0.45),), width=max(1, int(1.5 * s)))
        y += step_y
        row += 1

    layer = layer.rotate(angle, resample=Image.BICUBIC)
    left, top = (diag - W) // 2, (diag - H) // 2
    layer = layer.crop((left, top, left + W, top + H))
    out = Image.alpha_composite(base, layer).convert("RGB")

    if hardened:
        noise = Image.effect_noise((W, H), 24).convert("RGB")
        out = Image.blend(out, noise, 0.035)
    return out


def fit_size(img, width=None, height=None):
    """Redimensiona a width x height píxeles. Si solo se da uno, mantiene la proporción."""
    if not width and not height:
        return img
    w = width or round(img.width * height / img.height)
    h = height or round(img.height * width / img.width)
    return img.resize((max(1, int(w)), max(1, int(h))), Image.LANCZOS)


def export_watermarked(src, dst, params, width=None, height=None, painter=None, bottom=None):
    """Exporta con marca de agua. El formato sale de la extensión de `dst`
    (.pdf, .png, .jpg). Si el origen tiene varias páginas y se exporta como
    imagen, se guarda un archivo por página (_p1, _p2...). Devuelve las rutas.
    En PDF, bottom(ancho_pt) -> alto_pt añade una franja en blanco bajo cada
    página (para la firma), fuera de la imagen."""
    pages = load_pages(src)
    fmt = ext_of(dst)
    painter = painter or apply_watermark
    marked = [(painter(fit_size(img, width, height), seed=1000 + i, **params), size_pt)
              for i, (img, size_pt) in enumerate(pages)]
    if fmt == ".pdf":
        out = fitz.open()
        for wm, size_pt in marked:
            buf = io.BytesIO()
            wm.save(buf, "JPEG", quality=90)
            if size_pt is None or width or height:
                size_pt = (wm.width * 72 / RENDER_DPI, wm.height * 72 / RENDER_DPI)
            extra = bottom(size_pt[0]) if bottom else 0
            page = out.new_page(width=size_pt[0], height=size_pt[1] + extra)
            page.insert_image(fitz.Rect(0, 0, size_pt[0], size_pt[1]), stream=buf.getvalue())
        out.set_metadata({})
        out.save(dst, garbage=4, deflate=True)
        out.close()
        return [dst]
    paths = []
    for i, (wm, _) in enumerate(marked):
        path = dst if len(marked) == 1 else suffixed(dst, f"p{i + 1}")
        if fmt in (".jpg", ".jpeg"):
            wm.save(path, "JPEG", quality=92)
        else:
            wm.save(path, "PNG")
        paths.append(path)
    return paths


# --------------------------------------------------------------------------
# Plantillas de marca de agua
# --------------------------------------------------------------------------

def presets_file():
    return os.path.join(config_dir(), "plantillas.json")


def load_presets():
    try:
        with open(presets_file(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_presets(presets):
    with open(presets_file(), "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# Texto de las páginas (nativo u OCR) y detección de datos sensibles
# --------------------------------------------------------------------------

_ocr_engine = None


def ocr_available():
    try:
        import rapidocr  # noqa: F401
        return True
    except ImportError:
        return False


def ocr_page_words(page):
    """Reconoce el texto de una página escaneada. Devuelve [(fitz.Rect, palabra)]
    en coordenadas de página (sin rotar), igual que page.get_text('words').

    El detector del OCR es sensible a la resolución (a veces no ve nada a una y
    todo a otra), así que se prueban varias (lado mayor en píxeles) y se usa la
    que reconoce más texto."""
    best = []
    for i, side in enumerate((2200, 1600, 1100, 3000)):
        words = _ocr_at(page, side / max(page.rect.width, page.rect.height))
        if sum(len(w) for _, w in words) > sum(len(w) for _, w in best):
            best = words
        if best and i >= 1:
            break
    return best


def _ocr_at(page, zoom):
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr import RapidOCR
        _ocr_engine = RapidOCR()
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    result = _ocr_engine(pix.tobytes("png"), return_word_box=True)
    scale = 1 / zoom
    words = []
    for line in result.word_results or ():
        for item in line:
            if not isinstance(item, (tuple, list)) or len(item) != 3 or item[2] is None:
                continue  # resultado vacío: (('', 1.0, None),)
            text, _score, box = item
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            r = fitz.Rect(min(xs), min(ys), max(xs), max(ys)) * scale
            pad = r.height * 0.3  # las cajas del OCR son justas: margen para no dejar bordes visibles
            r = fitz.Rect(r.x0 - pad, r.y0 - pad * 0.4, r.x1 + pad, r.y1 + pad * 0.4)
            words.append((r * page.derotation_matrix, text))
    return words


def ocr_page_lines(page):
    """OCR por líneas: [(Rect, texto, [(Rect, palabra)])] en coordenadas de página, sin margen."""
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr import RapidOCR
        _ocr_engine = RapidOCR()
    best = []
    for i, side in enumerate((2200, 1600, 1100, 3000)):
        zoom = side / max(page.rect.width, page.rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        res = _ocr_engine(pix.tobytes("png"), return_word_box=True)
        lines = []
        for words in res.word_results or ():
            ws = []
            for item in words:
                if not isinstance(item, (tuple, list)) or len(item) != 3 or item[2] is None:
                    continue
                t, _sc, box = item
                xs, ys = [q[0] for q in box], [q[1] for q in box]
                ws.append((fitz.Rect(min(xs), min(ys), max(xs), max(ys)) * (1 / zoom) * page.derotation_matrix, t))
            if ws:
                r = fitz.Rect(ws[0][0])
                for w, _ in ws[1:]:
                    r |= w
                lines.append((r, " ".join(t for _, t in ws), ws))
        if sum(len(l[1]) for l in lines) > sum(len(l[1]) for l in best):
            best = lines
        if best and i >= 1:
            break
    return best


def native_words(page):
    return [(fitz.Rect(w[:4]), w[4]) for w in page.get_text("words", sort=True)]


def _dni_ok(s):
    s = s.upper()
    num = s[:-1].replace("X", "0").replace("Y", "1").replace("Z", "2")
    return num.isdigit() and "TRWAGMYFPDXBNJZSQVHLCKE"[int(num) % 23] == s[-1]


def _iban_ok(s):
    s = re.sub(r"\s", "", s).upper()
    if len(s) < 15:
        return False
    digits = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    return int(digits) % 97 == 1


def _luhn_ok(s):
    d = [int(c) for c in re.sub(r"\D", "", s)][::-1]
    return len(d) >= 13 and sum(x if i % 2 == 0 else (x * 2 - 9 if x > 4 else x * 2)
                                for i, x in enumerate(d)) % 10 == 0


SENSITIVE_PATTERNS = [
    ("DNI / NIE", re.compile(r"\b[XYZxyz]?\d{7,8}[\s-]?[A-Za-z]\b"),
     lambda m: _dni_ok(re.sub(r"[\s-]", "", m))),
    ("IBAN / cuenta", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b"), _iban_ok),
    ("Tarjeta bancaria", re.compile(r"\b(?:\d{4}[\s-]?){3}\d{1,4}\b"), _luhn_ok),
    ("Teléfono", re.compile(r"(?<!\d)(?:\+34\s?)?[6789]\d{2}\s?\d{2,3}\s?\d{2,3}\s?\d{0,2}(?!\d)"),
     lambda m: len(re.sub(r"\D", "", m)) in (9, 11)),
    ("Email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), None),
    ("Fecha", re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"), None),
]


def detect_sensitive(words):
    """Busca datos sensibles en una lista de palabras [(Rect, texto)].
    Devuelve {tipo: [[Rect, ...], ...]} (un grupo de rectángulos por hallazgo)."""
    text, spans = "", []
    for rect, w in words:
        start = len(text)
        text += w
        spans.append((start, len(text), rect))
        text += " "
    found = {}
    for name, rx, check in SENSITIVE_PATTERNS:
        for m in rx.finditer(text):
            if check and not check(m.group()):
                continue
            rects = [r for a, b, r in spans if a < m.end() and b > m.start()]
            if rects:
                found.setdefault(name, []).append(rects)
    return found


# --------------------------------------------------------------------------
# Censura
# --------------------------------------------------------------------------

REDACT_STYLES = {"Cuadro negro": "black", "Pixelado": "pixel", "Difuminado": "blur"}


def _obscure_region(page, rect, style):
    pix = page.get_pixmap(dpi=150, clip=rect, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    block = max(6, min(img.size) // 2)
    if style == "pixel":
        small = img.resize((max(1, img.width // block), max(1, img.height // block)), Image.BILINEAR)
        img = small.resize(img.size, Image.NEAREST)
    else:
        img = img.filter(ImageFilter.GaussianBlur(block)).filter(ImageFilter.GaussianBlur(block))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def redact_pdf(doc, marks, dst, style="black"):
    """Censura de forma definitiva: el texto y los píxeles bajo cada rectángulo
    se eliminan del archivo. `marks` = {nº página: [Rect, ...]}."""
    with fitz.open("pdf", doc.tobytes()) as out:
        for pno, rects in marks.items():
            if not rects:
                continue
            page = out[pno]
            covers = [(r, _obscure_region(page, r, style)) for r in rects] if style != "black" else []
            for r in rects:
                page.add_redact_annot(r, fill=(0, 0, 0) if style == "black" else (1, 1, 1))
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
            for r, png in covers:
                page.insert_image(r, stream=png)
        out.scrub()
        out.set_metadata({})
        out.save(dst, garbage=4, deflate=True, clean=True)


# --------------------------------------------------------------------------
# Limpieza de metadatos
# --------------------------------------------------------------------------

EMPTY_CORE = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
    'metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/'
    'dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/>'
)
EMPTY_ODF_META = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:'
    'office:1.0" office:version="1.2"><office:meta/></office:document-meta>'
)


def sanitize_file(src, dst):
    ext = ext_of(src)
    if ext == ".pdf":
        with fitz.open(src) as doc:
            doc.scrub()  # metadatos, XMP, JavaScript, adjuntos, miniaturas, texto oculto...
            doc.set_metadata({})
            doc.del_xml_metadata()
            doc.save(dst, garbage=4, deflate=True, clean=True)
    elif ext in IMAGE_EXTS:
        img = Image.open(src)
        img = ImageOps.exif_transpose(img)
        clean = img.copy()
        # Solo se conservan los píxeles (y la transparencia); fuera EXIF, XMP, ICC, textos...
        clean.info = {k: v for k, v in img.info.items() if k == "transparency"}
        if ext in (".jpg", ".jpeg"):
            clean.convert("RGB").save(dst, "JPEG", quality=95)
        else:
            clean.save(dst)
    elif ext in OFFICE_EXTS:
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "docProps/core.xml":
                    data = EMPTY_CORE.encode()
                elif item.filename == "meta.xml":
                    data = EMPTY_ODF_META.encode()
                info = zipfile.ZipInfo(item.filename, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED if item.filename == "mimetype" else zipfile.ZIP_DEFLATED
                zout.writestr(info, data)
    else:
        raise ValueError(f"Formato no soportado: {ext}")


# --------------------------------------------------------------------------
# Unión, páginas, compresión, conversión, contraseñas
# --------------------------------------------------------------------------

def merge_files(paths, dst):
    out = fitz.open()
    for p in paths:
        with open_as_pdf(p) as d:
            out.insert_pdf(d)
    out.set_metadata({})
    out.save(dst, garbage=4, deflate=True)
    out.close()


def save_pages(src, pages, dst):
    """Guarda un PDF con las páginas indicadas. `pages` = [(índice_original, giro_extra)]."""
    with open_as_pdf(src) as doc, fitz.open() as out:
        for idx, rot in pages:
            out.insert_pdf(doc, from_page=idx, to_page=idx)
            p = out[-1]
            p.set_rotation((p.rotation + rot) % 360)
        out.set_metadata({})
        out.save(dst, garbage=4, deflate=True)


def parse_ranges(spec, n):
    """'1-3, 5, 7-' -> [[0,1,2],[4],[6..n-1]] (páginas empiezan en 1)."""
    groups = []
    for part in spec.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a = int(a) if a.strip() else 1
            b = int(b) if b.strip() else n
        else:
            a = b = int(part)
        if not (1 <= a <= b <= n):
            raise ValueError(f"Rango no válido: {part} (el documento tiene {n} páginas)")
        groups.append(list(range(a - 1, b)))
    if not groups:
        raise ValueError("No se ha indicado ningún rango.")
    return groups


COMPRESS_LEVELS = {"Baja (mejor calidad)": (200, 85), "Media": (150, 70), "Alta (menor tamaño)": (100, 50)}


def compress_pdf(src, dst, level="Media"):
    dpi, quality = COMPRESS_LEVELS[level]
    with fitz.open(src) as doc:
        doc.rewrite_images(dpi_threshold=dpi + 10, dpi_target=dpi, quality=quality)
        try:
            doc.subset_fonts()
        except Exception:
            pass
        doc.scrub()
        doc.set_metadata({})
        doc.save(dst, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True,
                 clean=True, use_objstms=1)
    return os.path.getsize(src), os.path.getsize(dst)


def pdf_to_images(src, folder, fmt="png", dpi=200):
    base = os.path.join(folder, os.path.splitext(os.path.basename(src))[0])
    paths = []
    with fitz.open(src) as doc:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            path = f"{base}_p{i + 1}.{fmt}" if len(doc) > 1 else f"{base}.{fmt}"
            img.save(path, "JPEG" if fmt == "jpg" else "PNG", **({"quality": 92} if fmt == "jpg" else {}))
            paths.append(path)
    return paths


def encrypt_pdf(src, dst, user_pw, owner_pw="", allow_print=True, allow_copy=False, allow_edit=False):
    perms = fitz.PDF_PERM_ACCESSIBILITY
    if allow_print:
        perms |= fitz.PDF_PERM_PRINT | fitz.PDF_PERM_PRINT_HQ
    if allow_copy:
        perms |= fitz.PDF_PERM_COPY
    if allow_edit:
        perms |= fitz.PDF_PERM_MODIFY | fitz.PDF_PERM_ANNOTATE | fitz.PDF_PERM_FORM | fitz.PDF_PERM_ASSEMBLE
    with open_as_pdf(src) as doc:
        doc.save(dst, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=user_pw,
                 owner_pw=owner_pw or secrets.token_urlsafe(24), permissions=perms,
                 garbage=4, deflate=True)


def decrypt_pdf(src, dst, password):
    with fitz.open(src) as doc:
        if doc.needs_pass and not doc.authenticate(password):
            raise ValueError("Contraseña incorrecta.")
        doc.save(dst, encryption=fitz.PDF_ENCRYPT_NONE, garbage=4, deflate=True)
