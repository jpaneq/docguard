"""Modo escáner: convierte fotos de documentos (DNI, pasaporte, folios…) en escaneos
limpios y los digitaliza (PDF a tamaño real, con texto reconocido por OCR).

1. detect_quad(): localiza el documento en la foto (sus 4 esquinas).
2. warp():        endereza la perspectiva (proporción de tarjeta ID-1, A4, Carta o la medida).
3. enhance():     quita sombras e iluminación desigual y mejora el color o lo pasa a B/N.
4. digitalize():  compone el PDF (una página por imagen o anverso y reverso en un A4) con OCR.
"""

import io

from PIL import Image


class _LazyNumpy:
    """numpy tarda ~0,6 s en cargarse: se importa la primera vez que se usa, no al arrancar DocGuard."""
    def __getattr__(self, name):
        import numpy
        globals()["np"] = numpy
        return getattr(numpy, name)


np = _LazyNumpy()

KINDS = {  # proporción (lado largo / lado corto) y tamaño físico en mm (ancho, alto en horizontal)
    "tarjeta": (85.60 / 53.98, (85.60, 53.98)),   # DNI, carné, tarjetas (ISO/IEC 7810 ID-1)
    "pasaporte": (125 / 88, (125.0, 88.0)),        # página de datos del pasaporte (ID-3)
    "a4": (297 / 210, (297.0, 210.0)),
    "carta": (279.4 / 215.9, (279.4, 215.9)),
}
MODES = ("auto", "color", "natural", "grises", "bn", "original")


# --------------------------------------------------------------------------
# 1. Detectar el documento
# --------------------------------------------------------------------------

def order_points(pts):
    """Ordena 4 puntos: arriba-izquierda, arriba-derecha, abajo-derecha, abajo-izquierda."""
    pts = np.asarray(pts, dtype=np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def _quad_from_contours(mask, min_area):
    import cv2
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:6]:
        area = cv2.contourArea(c)
        if area < min_area:
            break
        peri = cv2.arcLength(c, True)
        for eps in (0.02, 0.03, 0.05):
            approx = cv2.approxPolyDP(c, eps * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                return approx.reshape(4, 2), area
        # sin 4 vértices claros (esquinas redondeadas de las tarjetas): rectángulo mínimo
        rect = cv2.minAreaRect(c)
        if area / max(rect[1][0] * rect[1][1], 1) > 0.85:
            return cv2.boxPoints(rect), area
    return None, 0


def detect_quad(img):
    """Esquinas del documento (normalizadas 0..1) y confianza (0..1)."""
    import cv2
    w, h = img.size
    k = 900 / max(w, h)
    small = np.asarray(img.convert("RGB").resize((max(1, int(w * k)), max(1, int(h * k)))))
    sh, sw = small.shape[:2]
    min_area = sw * sh * 0.12
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    cands = []
    # a) bordes
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    for lo, hi in ((30, 90), (50, 150), (75, 200)):
        edges = cv2.dilate(cv2.Canny(blur, lo, hi), np.ones((3, 3), np.uint8), iterations=2)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        q, a = _quad_from_contours(edges, min_area)
        if q is not None:
            cands.append((q, a))
    # b) documento más claro / de otro color que el fondo
    lab = cv2.cvtColor(small, cv2.COLOR_RGB2LAB)
    for ch in (lab[..., 0], cv2.cvtColor(small, cv2.COLOR_RGB2HSV)[..., 1]):
        _, th = cv2.threshold(cv2.GaussianBlur(ch, (7, 7), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        for m in (th, 255 - th):
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
            q, a = _quad_from_contours(m, min_area)
            if q is not None and a < sw * sh * 0.98:
                cands.append((q, a))
    if not cands:
        return [[0, 0], [1, 0], [1, 1], [0, 1]], 0.0
    # el candidato más grande que no sea toda la imagen
    q, a = max(cands, key=lambda x: x[1])
    q = order_points(q)
    conf = min(1.0, a / (sw * sh) * 1.5)
    return [[float(x / sw), float(y / sh)] for x, y in q], round(conf, 2)


def guess_kind(img, quad):
    """Tipo de documento por la proporción de lo detectado."""
    w, h = img.size
    p = np.array([[x * w, y * h] for x, y in quad])
    ww = (np.linalg.norm(p[1] - p[0]) + np.linalg.norm(p[2] - p[3])) / 2
    hh = (np.linalg.norm(p[3] - p[0]) + np.linalg.norm(p[2] - p[1])) / 2
    ratio = max(ww, hh) / max(1, min(ww, hh))
    # el pasaporte (1,42) casi coincide con el A4 (1,41): en automático se elige A4
    auto = {k: v for k, v in KINDS.items() if k != "pasaporte"}
    best = min(auto, key=lambda k: abs(auto[k][0] - ratio))
    return best if abs(auto[best][0] - ratio) < 0.12 else "auto"


# --------------------------------------------------------------------------
# 2. Enderezar
# --------------------------------------------------------------------------

def warp(img, quad, kind="auto", max_side=2400, inset=0.004):
    import cv2
    w, h = img.size
    src = order_points([[x * w, y * h] for x, y in quad])
    c = src.mean(axis=0)
    src = c + (src - c) * (1 - 2 * inset)       # un poco hacia dentro: que no asome el fondo
    ww = max(np.linalg.norm(src[1] - src[0]), np.linalg.norm(src[2] - src[3]))
    hh = max(np.linalg.norm(src[3] - src[0]), np.linalg.norm(src[2] - src[1]))
    if kind in KINDS:
        ratio = KINDS[kind][0]
        if ww >= hh:
            hh = ww / ratio
        else:
            ww = hh / ratio
    k = min(1.0, max_side / max(ww, hh))
    ow, oh = max(8, int(round(ww * k))), max(8, int(round(hh * k)))
    dst = np.array([[0, 0], [ow - 1, 0], [ow - 1, oh - 1], [0, oh - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(np.asarray(img.convert("RGB")), M, (ow, oh), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(out)


# --------------------------------------------------------------------------
# 3. Mejorar
# --------------------------------------------------------------------------

def _illumination(gray):
    """Brillo del papel en cada zona (iluminación), sin dejarse engañar por el contenido oscuro:
    se toma lo más claro de cada bloque y los bloques de contenido (fotos, recuadros) se
    sustituyen por el valor de sus vecinos."""
    import cv2
    h, w = gray.shape
    bs = max(16, min(h, w) // 24)
    rows, cols = max(2, h // bs), max(2, w // bs)
    g = cv2.resize(gray, (cols * bs, rows * bs), interpolation=cv2.INTER_AREA)
    blocks = g.reshape(rows, bs, cols, bs).transpose(0, 2, 1, 3).reshape(rows, cols, -1)
    bg = np.percentile(blocks, 92, axis=2).astype(np.float32)
    for _ in range(4):   # bloques mucho más oscuros que sus vecinos = contenido, no sombra
        med = cv2.medianBlur(bg.astype(np.uint8), 3).astype(np.float32)
        bg = np.where(bg < med * 0.82, med, bg)
    bg = cv2.GaussianBlur(bg, (0, 0), 1.0)
    return cv2.resize(bg, (w, h), interpolation=cv2.INTER_CUBIC)


def _gray_world(rgb):
    """Balance de blancos tomando como referencia las zonas claras (el papel)."""
    lum = rgb.mean(axis=2)
    bright = rgb[lum > np.percentile(lum, 80)]
    ref = bright.mean(axis=0) if len(bright) else rgb.reshape(-1, 3).mean(axis=0)
    return np.clip(rgb * (ref.mean() / np.maximum(ref, 1)), 0, 255)


def enhance(img, mode="auto", kind="auto"):
    import cv2
    if mode == "original":
        return img
    if mode == "auto":
        mode = "color"
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    if mode == "natural":
        # tarjetas y fotos: balance de blancos, contraste local suave y nitidez; sin blanquear el fondo
        rgb = _gray_world(rgb)
        lab = cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2LAB)
        lab[..., 0] = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(lab[..., 0])
        out = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB).astype(np.float32)
    else:
        # documentos: se divide por la iluminación para quitar sombras y dejar el papel blanco
        lum = cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
        bg = np.maximum(_illumination(lum), 1)
        norm = np.clip(rgb * (250.0 / bg)[..., None], 0, 255)
        # negro de referencia: se oscurece un poco la tinta para ganar contraste
        dark = np.percentile(norm.mean(axis=2), 0.5)
        norm = np.clip((norm - dark * 0.6) * 255 / max(255 - dark * 0.6, 1), 0, 255)
        if mode in ("grises", "bn"):
            g = cv2.cvtColor(norm.astype(np.uint8), cv2.COLOR_RGB2GRAY)
            if mode == "bn":
                block = max(15, (min(g.shape) // 40) | 1)
                g = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 12)
                g = cv2.medianBlur(g, 3)
            return Image.fromarray(g).convert("RGB")
        hsv = cv2.cvtColor(norm.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
        hsv[..., 1] = np.clip(hsv[..., 1] * 1.15, 0, 255)
        out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
        out[out.min(axis=2) > 236] = 255          # papel blanco puro, como un escáner
    blur = cv2.GaussianBlur(out, (0, 0), 1.2)
    out = np.clip(out * 1.5 - blur * 0.5, 0, 255)     # enfoque suave
    return Image.fromarray(out.astype(np.uint8))


def round_corners(img, kind):
    """Las tarjetas tienen esquinas redondeadas (3,18 mm en ID-1): lo que asoma del fondo se pinta de blanco."""
    if kind not in ("tarjeta",):
        return img
    from PIL import ImageDraw
    w, h = img.size
    r = int(max(w, h) * 3.18 / 85.6)
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    out = Image.new("RGB", (w, h), (255, 255, 255))
    out.paste(img, (0, 0), m)
    return out


def rotate(img, deg):
    return img.rotate(-deg, expand=True) if deg % 360 else img


def process(img, quad, kind="auto", mode="auto", rot=0, max_side=2400):
    if kind == "auto":
        kind = guess_kind(img, quad)
    out = enhance(warp(img, quad, kind, max_side), mode, kind)
    if mode != "original":
        out = round_corners(out, kind)
    return rotate(out, rot), kind


# --------------------------------------------------------------------------
# 4. Digitalizar
# --------------------------------------------------------------------------

def _size_pt(img, kind):
    """Tamaño físico de la página en puntos (72 por pulgada)."""
    mm = 72 / 25.4
    if kind in KINDS:
        a, b = KINDS[kind][1]
        return (a * mm, b * mm) if img.width >= img.height else (b * mm, a * mm)
    long_mm = 210.0   # tamaño desconocido: se ajusta a un ancho de A4
    return (long_mm * mm, long_mm * mm * img.height / img.width)


def digitalize(pages, layout="paginas", ocr=True, quality=90):
    """pages = [(imagen, tipo)]. layout: 'paginas' (una por imagen, a tamaño real) o
    'a4' (tarjetas a tamaño real en hojas A4, dos por hoja: anverso y reverso).
    Devuelve los bytes del PDF."""
    import pymupdf as fitz
    doc = fitz.open()
    mm = 72 / 25.4

    def jpeg(im):
        b = io.BytesIO()
        im.convert("RGB").save(b, "JPEG", quality=quality)
        return b.getvalue()
    if layout == "a4":
        W, H = 210 * mm, 297 * mm
        page = None
        slot = 0
        for im, kind in pages:
            w, h = _size_pt(im, kind)
            if w > W - 40 * mm:            # no es una tarjeta: página propia ajustada a A4
                k = min((W - 30 * mm) / w, (H - 30 * mm) / h)
                w, h = w * k, h * k
                page = doc.new_page(width=W, height=H)
                page.insert_image(fitz.Rect((W - w) / 2, (H - h) / 2, (W + w) / 2, (H + h) / 2), stream=jpeg(im))
                page, slot = None, 0
                continue
            if page is None or slot == 2:
                page = doc.new_page(width=W, height=H)
                slot = 0
            cy = H * (0.3 if slot == 0 else 0.68)
            page.insert_image(fitz.Rect((W - w) / 2, cy - h / 2, (W + w) / 2, cy + h / 2), stream=jpeg(im))
            slot += 1
    else:
        for im, kind in pages:
            w, h = _size_pt(im, kind)
            page = doc.new_page(width=w, height=h)
            page.insert_image(page.rect, stream=jpeg(im))
    if ocr:
        import editor
        for n in range(len(doc)):
            try:
                editor.ocr_page(doc, n, "invisible")
            except Exception:
                pass
    doc.set_metadata({})
    doc.subset_fonts()  # la fuente del texto reconocido, solo con las letras usadas
    data = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return data
