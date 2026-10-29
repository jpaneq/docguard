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


def _orient(info, page):
    """Cómo pasar los píxeles de la imagen a como se ven en pantalla (la imagen puede estar girada o
    volteada en la página, o la página girada): (intercambiar ejes, voltear horizontal, voltear vertical)."""
    m = fitz.Matrix(info["transform"]) * page.rotation_matrix
    vx, vy = (m.a, m.b), (m.c, m.d)  # hacia dónde van, en la vista, las columnas y las filas de píxeles
    if abs(vx[1]) > abs(vx[0]):
        return True, vy[0] < 0, vx[1] < 0
    return False, vx[0] < 0, vy[1] < 0


def _upright(a, o):
    """Array de píxeles (alto, ancho, ...) orientado como en pantalla."""
    swap, fx, fy = o
    if swap:
        a = a.swapaxes(0, 1)
    if fx:
        a = a[:, ::-1]
    if fy:
        a = a[::-1]
    return np.ascontiguousarray(a)


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


def _area_px(info, page, area, w, h):
    """Recuadro de la vista → recuadro de píxeles de la imagen (recortado a la imagen)."""
    a = [editor.point_from_view(page, area[0], area[1]), editor.point_from_view(page, area[2], area[3])]
    a += [fitz.Point(a[0].x, a[1].y), fitz.Point(a[1].x, a[0].y)]
    px = [_to_px(info, p, w, h) for p in a]
    x0, x1 = max(0, int(min(p[0] for p in px))), min(w, int(np.ceil(max(p[0] for p in px))))
    y0, y1 = max(0, int(min(p[1] for p in px))), min(h, int(np.ceil(max(p[1] for p in px))))
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def selection(doc, pno, view_pt, seeds, tol=60, gap=2, area=None):
    """seeds: [{x, y, op: 'add'|'sub'}] en coordenadas de la vista. Con area (recuadro de la vista)
    solo se selecciona dentro de él, y sin semillas se coge toda la tinta del recuadro.
    Devuelve (info, img, máscara) o None."""
    page = doc[pno]
    if area:
        p0, p1 = editor.point_from_view(page, area[0], area[1]), editor.point_from_view(page, area[2], area[3])
        r = fitz.Rect(p0, p1).normalize()
        infos = [i for i in page.get_image_info(xrefs=True) if i.get("xref") and fitz.Rect(i["bbox"]).intersects(r)]
        info = max(infos, key=lambda i: (fitz.Rect(i["bbox"]) & r).get_area()) if infos else None
    else:
        info = _image_at(page, editor.point_from_view(page, *view_pt))
    if not info:
        return None
    img = _load(doc, page, info)
    w, h = img.size
    ink = _ink(img)
    bw = max(1e-6, fitz.Rect(info["bbox"]).width)
    gap_px = max(0, round(float(gap) * w / bw))  # el hueco se da en puntos de la página
    clip = None
    if area:
        box = _area_px(info, page, area, w, h)
        if box is None:
            return info, img, None
        clip = np.zeros((h, w), bool)
        clip[box[1]:box[3], box[0]:box[2]] = True
    mask = np.zeros((h, w), bool)
    if clip is not None and not any(s.get("op") == "add" for s in seeds):  # (recortar, quitar y goma solo restan)
        mask = (ink > int(tol)) & clip  # sin clics: toda la tinta del recuadro
    for s in seeds:
        if s.get("op") in ("crop", "cut"):  # recortar (deja solo lo de dentro) o quitar una zona rectangular
            b = _area_px(info, page, s["rect"], w, h)
            keep = np.zeros((h, w), bool)
            if b:
                keep[b[1]:b[3], b[0]:b[2]] = True
            mask &= keep if s["op"] == "crop" else ~keep
            continue
        if s.get("op") == "erase":  # goma: trazo pintado encima en la lupa
            er = Image.new("L", (w, h), 0)
            dr = ImageDraw.Draw(er)
            rad = max(1, float(s.get("r", 4)) * w / bw)
            pts = [_to_px(info, editor.point_from_view(page, x, y), w, h) for x, y in s.get("pts", [])]
            for a, b in zip(pts, pts[1:]):
                dr.line([a, b], fill=255, width=int(round(2 * rad)))
            for x, y in pts:
                dr.ellipse([x - rad, y - rad, x + rad, y + rad], fill=255)
            mask &= ~(np.asarray(er) > 0)
            continue
        px = _to_px(info, editor.point_from_view(page, s["x"], s["y"]), w, h)
        comp = _component(ink, px, int(tol), gap_px, reach=max(12, round(6 * w / bw)))
        if comp is None:
            continue
        mask = (mask & ~comp) if s.get("op") == "sub" else (mask | comp)
    if clip is not None:
        mask &= clip
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


def _b64png(im):
    import base64
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def lupa(doc, pno, area, seeds, tol=60, gap=2, rot=0):
    """Para la ventana de lupa: el trozo del recuadro ampliado y, encima, la selección (mismo tamaño)."""
    res = selection(doc, pno, None, seeds, tol, gap, area)
    if res is None:
        return {"found": False, "reason": "noimage"}
    info, img, mask = res
    w, h = img.size
    box = _area_px(info, doc[pno], area, w, h)
    if box is None:
        return {"found": False, "reason": "noimage"}
    x0, y0, x1, y1 = box
    o = _orient(info, doc[pno])
    base = Image.fromarray(_upright(np.asarray(img.crop(box)), o))
    # lo no seleccionado queda tapado por un velo claro; lo seleccionado, teñido y con contorno
    over = np.full((y1 - y0, x1 - x0, 4), (255, 255, 255, 190), np.uint8)
    pixels = 0
    cut = None
    if mask is not None:
        crop = mask[y0:y1, x0:x1]
        pixels = int(crop.sum())
        over[crop] = (37, 99, 235, 90)
        m8 = Image.fromarray((crop * 255).astype(np.uint8))
        ring = (np.asarray(m8.filter(ImageFilter.MaxFilter(5))) > 0) & ~crop
        over[ring] = (255, 140, 0, 255)
        if pixels:
            cut = _b64png(Image.open(io.BytesIO(cutout_png(img, mask, _ink(img), int(tol), rot, o)[0])))
    ov = Image.fromarray(_upright(over, o), "RGBA")
    if max(base.size) > 1400:
        base.thumbnail((1400, 1400))
        ov = ov.resize(base.size)
    # parte del recuadro (en la vista) que cubre realmente la imagen, para situar los clics
    view = editor.to_view(doc[pno], _page_rect(info, box, w, h))
    return {"found": pixels > 0, "reason": "blank", "base": _b64png(base), "over": _b64png(ov), "view": view,
            "pixels": pixels, "cut": cut}


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


def cutout_png(img, mask, ink, tol, rot=0, orient=(False, False, False)):
    """La zona seleccionada como PNG con fondo transparente (bordes suaves según la tinta)."""
    box = _bbox(mask)
    rgb = np.asarray(img)[box[1]:box[3], box[0]:box[2]]
    m = mask[box[1]:box[3], box[0]:box[2]]
    k = ink[box[1]:box[3], box[0]:box[2]].astype(np.float32)
    lo = max(4, tol // 3)
    alpha = np.clip((k - lo) / max(1, (tol + 40) - lo), 0, 1) * 255
    alpha[~m] = 0
    out = Image.fromarray(_upright(np.dstack([rgb, alpha.astype(np.uint8)]), orient), "RGBA")
    if rot % 360:
        out = out.rotate(-(rot % 360), expand=True)  # rot en grados, en el sentido de las agujas del reloj
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue(), box


def _rot_rect(r, rot):
    """El recuadro donde va la imagen girada: mismo centro y, a 90/270°, ancho y alto cambiados."""
    if rot % 180 == 0:
        return r
    c = (r.tl + r.br) / 2
    return fitz.Rect(c.x - r.height / 2, c.y - r.width / 2, c.x + r.height / 2, c.y + r.width / 2)


def apply(doc, pno, view_pt, seeds, action, tol=60, gap=2, area=None, rot=0):
    """action: 'separar' (borrar de la imagen + imagen suelta movible), 'copiar' (imagen suelta
    encima, sin tocar el original) o 'borrar' (queda en blanco)."""
    res = selection(doc, pno, view_pt, seeds, tol, gap, area)
    if res is None or res[2] is None:
        raise ValueError("no hay nada seleccionado")
    info, img, mask = res
    page = doc[pno]
    w, h = img.size
    ink = _ink(img)
    png, box = cutout_png(img, mask, ink, int(tol), rot, _orient(info, page))
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
        # el PNG ya va derecho como se ve en pantalla; en una página girada hay que girarlo con ella
        page.insert_image(_rot_rect(_page_rect(info, box, w, h), rot), stream=png, keep_proportion=False,
                          rotate=page.rotation)
    return {"separar": "Separada como imagen", "copiar": "Copiada como imagen", "borrar": "Borrada"}.get(action, "")


def signature_png(doc, pno, view_pt, seeds, tol=60, gap=2, area=None, rot=0):
    """La selección como PNG con fondo transparente (para las firmas o el portapapeles)."""
    res = selection(doc, pno, view_pt, seeds, tol, gap, area)
    if res is None or res[2] is None:
        raise ValueError("no hay nada seleccionado")
    info, img, mask = res
    return cutout_png(img, mask, _ink(img), int(tol), rot, _orient(info, doc[pno]))[0]


def clip(doc, pno, view_pt, seeds, tol=60, gap=2, area=None, rot=0):
    """La selección para el portapapeles: PNG transparente y su recuadro en la vista."""
    res = selection(doc, pno, view_pt, seeds, tol, gap, area)
    if res is None or res[2] is None:
        raise ValueError("no hay nada seleccionado")
    info, img, mask = res
    png, box = cutout_png(img, mask, _ink(img), int(tol), rot, _orient(info, doc[pno]))
    w, h = img.size
    return png, editor.to_view(doc[pno], _rot_rect(_page_rect(info, box, w, h), rot))
