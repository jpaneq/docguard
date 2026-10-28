"""Varita mágica de Editar PDF: sobre una imagen o una página escaneada, selecciona la zona de
color unida a donde se pincha (una firma, un sello, un logo), sin el fondo blanco, como la varita
de Photoshop. Mayús añade zonas y Alt las quita. Con la selección se puede separar como imagen
(para moverla o copiarla), borrar de la página o guardar como firma.

Todo se calcula sobre los píxeles de la propia imagen del PDF, a su resolución."""

import io

import numpy as np
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFilter

import editor


def _image_at(page, pt):
    """Imagen de la página bajo el punto (la de más arriba), con su información y su pixmap."""
    infos = [i for i in page.get_image_info(xrefs=True) if i.get("xref") and fitz.Rect(i["bbox"]).contains(pt)]
    if not infos:
        return None
    return infos[-1]


def _load(doc, page, info):
    pix = editor._pixmap(doc, page, info["xref"])
    mode = "RGBA" if pix.alpha else "RGB"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    if mode == "RGBA":  # lo transparente cuenta como blanco
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    return img


def _to_px(info, pt, w, h):
    """Punto de la página → píxel de la imagen (según cómo está colocada en la página)."""
    q = pt * ~fitz.Matrix(info["transform"])
    return q.x * w, q.y * h


def _to_page(info, x, y, w, h):
    return fitz.Point(x / w, y / h) * fitz.Matrix(info["transform"])


def _ink(img):
    """Cuánto se aleja cada píxel del blanco (0 = blanco, 255 = color pleno), por su canal más oscuro."""
    a = np.asarray(img, dtype=np.int16)
    return (255 - a.min(axis=2)).astype(np.uint8)


def _component(ink, seed, tol, gap, reach=12):
    """Zona de «tinta» unida a la semilla. gap (píxeles) une trazos separados por huecos pequeños."""
    fg = ink > tol
    h, w = fg.shape
    sx, sy = int(round(seed[0])), int(round(seed[1]))
    if not (0 <= sx < w and 0 <= sy < h):
        return None
    if not fg[sy, sx]:  # se pinchó en blanco: el píxel de tinta más cercano (unos 6 puntos alrededor)
        r = int(reach)
        ys, xs = np.nonzero(fg[max(0, sy - r):sy + r + 1, max(0, sx - r):sx + r + 1])
        if not len(xs):
            return None
        k = np.argmin((xs + max(0, sx - r) - sx) ** 2 + (ys + max(0, sy - r) - sy) ** 2)
        sx, sy = int(xs[k] + max(0, sx - r)), int(ys[k] + max(0, sy - r))
    grow = Image.fromarray((fg * 255).astype(np.uint8), "L").copy()
    g = int(gap)
    while g > 0:  # dilatación por pasos (MaxFilter admite tamaños impares pequeños)
        step = min(g, 4)
        grow = grow.filter(ImageFilter.MaxFilter(2 * step + 1))
        g -= step
    ImageDraw.floodfill(grow, (sx, sy), 128, thresh=0)
    region = np.asarray(grow) == 128
    # bordes suaves: también los píxeles claros que tocan la zona (antialias de los trazos)
    soft = ink > max(8, tol // 3)
    near = np.asarray(Image.fromarray((region * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
    return (region & fg) | (near & soft)


def selection(doc, pno, view_pt, seeds, tol=60, gap=2):
    """seeds: [{x, y, op: 'add'|'sub'}] en coordenadas de la vista. Devuelve (info, img, máscara) o None."""
    page = doc[pno]
    first = editor.point_from_view(page, *view_pt)
    info = _image_at(page, first)
    if not info:
        return None
    img = _load(doc, page, info)
    w, h = img.size
    ink = _ink(img)
    bw = max(1e-6, fitz.Rect(info["bbox"]).width)
    gap_px = max(0, round(float(gap) * w / bw))  # el hueco se da en puntos de la página
    mask = np.zeros((h, w), bool)
    for s in seeds:
        px = _to_px(info, editor.point_from_view(page, s["x"], s["y"]), w, h)
        comp = _component(ink, px, int(tol), gap_px, reach=max(12, round(6 * w / bw)))
        if comp is None:
            continue
        mask = (mask & ~comp) if s.get("op") == "sub" else (mask | comp)
    if not mask.any():
        return info, img, None
    return info, img, mask


def _bbox(mask):
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _page_rect(info, box, w, h):
    x0, y0, x1, y1 = box
    pts = [_to_page(info, x, y, w, h) for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
    return fitz.Rect(min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts))


def preview(doc, pno, view_pt, seeds, tol=60, gap=2):
    """Para la interfaz: recuadro (en la vista) y PNG semitransparente de la zona seleccionada."""
    import base64
    res = selection(doc, pno, view_pt, seeds, tol, gap)
    if res is None:
        return {"found": False, "reason": "noimage"}
    info, img, mask = res
    if mask is None:
        return {"found": False, "reason": "blank"}
    w, h = img.size
    box = _bbox(mask)
    crop = mask[box[1]:box[3], box[0]:box[2]]
    over = np.zeros(crop.shape + (4,), np.uint8)
    over[crop] = (37, 99, 235, 150)
    # contorno más intenso
    edge = crop & ~(np.asarray(Image.fromarray((crop * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))) > 0)
    over[edge] = (20, 60, 200, 255)
    o = Image.fromarray(over, "RGBA")
    if max(o.size) > 1200:
        o.thumbnail((1200, 1200))
    buf = io.BytesIO()
    o.save(buf, "PNG")
    page = doc[pno]
    rect = editor.to_view(page, _page_rect(info, box, w, h))
    return {"found": True, "rect": rect, "png": base64.b64encode(buf.getvalue()).decode(),
            "pixels": int(mask.sum())}


def cutout_png(img, mask, ink, tol):
    """La zona seleccionada como PNG con fondo transparente (bordes suaves según la tinta)."""
    box = _bbox(mask)
    rgb = np.asarray(img)[box[1]:box[3], box[0]:box[2]]
    m = mask[box[1]:box[3], box[0]:box[2]]
    k = ink[box[1]:box[3], box[0]:box[2]].astype(np.float32)
    lo = max(4, tol // 3)
    alpha = np.clip((k - lo) / max(1, (tol + 40) - lo), 0, 1) * 255
    alpha[~m] = 0
    out = np.dstack([rgb, alpha.astype(np.uint8)])
    buf = io.BytesIO()
    Image.fromarray(out, "RGBA").save(buf, "PNG")
    return buf.getvalue(), box


def apply(doc, pno, view_pt, seeds, action, tol=60, gap=2):
    """action: 'separar' (borrar de la imagen + imagen suelta movible), 'copiar' (imagen suelta
    encima, sin tocar el original) o 'borrar' (queda en blanco)."""
    res = selection(doc, pno, view_pt, seeds, tol, gap)
    if res is None or res[2] is None:
        raise ValueError("no hay nada seleccionado")
    info, img, mask = res
    page = doc[pno]
    w, h = img.size
    ink = _ink(img)
    png, box = cutout_png(img, mask, ink, int(tol))
    if action in ("separar", "borrar"):
        clean = np.asarray(img).copy()
        # se rellena (con un borde de 1 px, para no dejar el halo del antialias) con el color del papel
        # de alrededor, no con blanco puro: en un escaneo el papel suele ser algo gris o amarillento
        m8 = Image.fromarray((mask * 255).astype(np.uint8))
        wide = np.asarray(m8.filter(ImageFilter.MaxFilter(3))) > 0
        ring = (np.asarray(m8.filter(ImageFilter.MaxFilter(13))) > 0) & ~(np.asarray(m8.filter(ImageFilter.MaxFilter(5))) > 0)
        paper = ring & (ink <= tol)
        clean[wide] = np.median(clean[paper], axis=0).astype(np.uint8) if paper.sum() > 20 else 255
        buf = io.BytesIO()
        Image.fromarray(clean, "RGB").save(buf, "PNG")
        page.replace_image(info["xref"], stream=buf.getvalue())
    if action in ("separar", "copiar"):
        page.insert_image(_page_rect(info, box, w, h), stream=png, keep_proportion=False)
    return {"separar": "Separada como imagen", "copiar": "Copiada como imagen", "borrar": "Borrada"}.get(action, "")


def signature_png(doc, pno, view_pt, seeds, tol=60, gap=2):
    """La selección como imagen para guardarla entre las firmas manuscritas."""
    res = selection(doc, pno, view_pt, seeds, tol, gap)
    if res is None or res[2] is None:
        raise ValueError("no hay nada seleccionado")
    info, img, mask = res
    return cutout_png(img, mask, _ink(img), int(tol))[0]
