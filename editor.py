"""Edición de PDF: texto, imágenes, anotaciones, formularios y firmas manuscritas.

Todas las coordenadas que entran y salen de este módulo son "de pantalla":
puntos PDF con la rotación de la página ya aplicada (origen arriba a la izquierda),
que es como se ve la página renderizada.
"""

import contextlib
import os
import re
import sys
from functools import lru_cache

import pymupdf as fitz

# --------------------------------------------------------------------------
# Coordenadas
# --------------------------------------------------------------------------


def to_view(page, rect):
    r = fitz.Rect(rect) * page.rotation_matrix
    return [round(v, 2) for v in (r.x0, r.y0, r.x1, r.y1)]


def from_view(page, rect):
    return (fitz.Rect(rect) * page.derotation_matrix).normalize()


def point_from_view(page, x, y):
    return fitz.Point(x, y) * page.derotation_matrix


def hex_color(c):
    if isinstance(c, int):
        return "#%06x" % c
    if not c:
        return "#000000"
    return "#%02x%02x%02x" % tuple(int(v * 255) for v in c[:3])


def rgb(hex_str):
    h = (hex_str or "#000000").lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


# --------------------------------------------------------------------------
# Fuentes: reconocer la del PDF y buscar la más parecida
# --------------------------------------------------------------------------

BASE14 = {
    "helv": {(0, 0): "helv", (1, 0): "hebo", (0, 1): "heit", (1, 1): "hebi"},
    "tiro": {(0, 0): "tiro", (1, 0): "tibo", (0, 1): "tiit", (1, 1): "tibi"},
    "cour": {(0, 0): "cour", (1, 0): "cobo", (0, 1): "coit", (1, 1): "cobi"},
}
BASE_LABELS = {"helv": "Helvetica", "tiro": "Times", "cour": "Courier"}


def norm_font(name):
    """'ABCDEF+Arial-BoldMT' -> 'arialbold'."""
    name = (name or "").split("+", 1)[-1].lower()
    name = re.sub(r"[^a-z0-9]", "", name)
    for suffix in ("psmt", "mt", "ps"):
        if name.endswith(suffix) and len(name) > len(suffix) + 2:
            name = name[: -len(suffix)]
    return name


def font_dirs():
    if sys.platform == "win32":
        return [os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")]
    if sys.platform == "darwin":
        return ["/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts",
                os.path.expanduser("~/Library/Fonts")]
    return ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts")]


@lru_cache(maxsize=1)
def system_fonts():
    """Índice {nombre_normalizado: ruta} de las fuentes instaladas (.ttf/.otf)."""
    index = {}
    for d in font_dirs():
        for root, _, files in os.walk(d) if os.path.isdir(d) else ():
            for f in files:
                if not f.lower().endswith((".ttf", ".otf")):
                    continue
                path = os.path.join(root, f)
                index.setdefault(norm_font(os.path.splitext(f)[0]), path)
                try:
                    index.setdefault(norm_font(fitz.Font(fontfile=path).name), path)
                except Exception:
                    pass
    return index


COMMON_FAMILIES = ["Arial", "Helvetica", "Times New Roman", "Calibri", "Cambria", "Verdana",
                   "Georgia", "Tahoma", "Trebuchet MS", "Courier New", "Garamond", "Roboto", "Open Sans"]


def font_choices():
    """Fuentes que se ofrecen al usuario para texto nuevo."""
    out = [{"key": f"base:{k}", "label": v} for k, v in BASE_LABELS.items()]
    idx = system_fonts()
    for fam in COMMON_FAMILIES:
        path = idx.get(norm_font(fam))
        if path:
            out.append({"key": f"sys:{path}", "label": fam})
    return out


def _base14_for(flags, name, bold, italic):
    n = (name or "").lower()
    if flags & 8 or "cour" in n or "mono" in n:
        fam = "cour"
    elif flags & 4 or any(s in n for s in ("times", "roman", "serif", "georgia", "garamond", "cambria")):
        fam = "tiro"
    else:
        fam = "helv"
    return BASE14[fam][(int(bold), int(italic))]


def _system_match(name, bold, italic):
    idx = system_fonts()
    n = norm_font(name)
    fam = re.sub(r"(bold|italic|oblique|regular|semibold|black|light)+$", "", n)
    style = ("bold" if bold else "") + ("italic" if italic else "")
    if style and n == fam:  # familia sin estilo en el nombre («Arial»): buscar antes su negrita/cursiva
        for cand in (fam + style, fam + ("bd" if bold else "") + ("i" if italic else "")):
            if cand in idx:
                return idx[cand]
    if n in idx:
        return idx[n]
    for cand in (fam + style, fam + ("bd" if bold else "") + ("i" if italic else ""), fam):
        if cand in idx:
            return idx[cand]
    return None


def _covers(font, text):
    return all(font.has_glyph(ord(c)) for c in text if not c.isspace())


def _kw(page, kw):
    """Page.insert_text no admite fontbuffer: se registra la fuente en la página y se pasa solo su nombre."""
    if "fontbuffer" not in kw:
        return kw
    kw = dict(kw)
    page.insert_font(fontname=kw["fontname"], fontbuffer=kw.pop("fontbuffer"))
    return kw


def resolve_font(doc, page, name, flags, text, choice="auto"):
    """Elige la fuente para `text`. Devuelve (kwargs para insert_text, etiqueta).

    Con choice="auto": 1) la fuente incrustada en el PDF si es completa y tiene
    todas las letras; 2) la misma familia instalada en el sistema; 3) la
    incrustada aunque sea parcial, si cubre el texto; 4) Helvetica/Times/Courier."""
    bold, italic = bool(flags & 16), bool(flags & 2)
    if choice.startswith("base:"):
        fam = choice[5:]
        # Helvetica/Times/Courier estándar no tienen símbolos como • o –: se usa la equivalente instalada
        sys_name = {"helv": "Arial", "tiro": "Times New Roman", "cour": "Courier New"}[fam]
        path = _system_match(sys_name, bold, italic)
        if path:
            return {"fontname": "DG" + norm_font(os.path.basename(path))[:20], "fontfile": path}, sys_name
        return {"fontname": BASE14[fam][(int(bold), int(italic))]}, BASE_LABELS[fam]
    if choice.startswith("sys:"):
        path = choice[4:]
        return {"fontname": "DG" + norm_font(os.path.basename(path))[:20], "fontfile": path}, os.path.basename(path)

    embedded = None
    for xref, ext, _type, basefont, *_ in page.get_fonts(full=True):
        if norm_font(basefont) == norm_font(name) and ext in ("ttf", "otf", "cff", "t1", "pfa", "pfb"):
            try:
                buf = doc.extract_font(xref)[3]
                if buf:
                    embedded = (basefont, buf, fitz.Font(fontbuffer=buf))
                    break
            except Exception:
                pass
    fname = "DG" + norm_font(name)[:20]
    if embedded and "+" not in embedded[0] and _covers(embedded[2], text):
        return {"fontname": fname, "fontbuffer": embedded[1]}, f"{name} (del PDF)"
    path = _system_match(name, bold, italic)
    if path:
        try:
            if _covers(fitz.Font(fontfile=path), text):
                return {"fontname": fname + "s", "fontfile": path}, f"{os.path.basename(path)} (del sistema)"
        except Exception:
            pass
    if embedded and _covers(embedded[2], text):
        return {"fontname": fname, "fontbuffer": embedded[1]}, f"{name} (del PDF, parcial)"
    base = _base14_for(flags, name, bold, italic)
    return {"fontname": base}, f"{base} (sustituta)"


# --------------------------------------------------------------------------
# Texto
# --------------------------------------------------------------------------

def spans(page):
    """Fragmentos de texto horizontales de la página, con fuente, tamaño y color.
    No incluye el texto que se ve dentro de los campos de formulario."""
    out = []
    fields = [fitz.Rect(w.rect) for w in (page.widgets() or ())]
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            if abs(line["dir"][1]) > 0.01:
                continue
            for s in line["spans"]:
                if not s["text"].strip():
                    continue
                c = fitz.Point((s["bbox"][0] + s["bbox"][2]) / 2, (s["bbox"][1] + s["bbox"][3]) / 2)
                if any(c in f for f in fields):
                    continue
                out.append({"text": s["text"].replace("\xa0", " "), "bbox": to_view(page, s["bbox"]),
                            "origin": list(s["origin"]), "font": s["font"].split("+", 1)[-1],
                            "rawfont": s["font"], "size": round(s["size"], 2),
                            "color": hex_color(s["color"]), "flags": s["flags"],
                            "bold": bool(s["flags"] & 16), "italic": bool(s["flags"] & 2)})
    out.sort(key=lambda s: (round(s["bbox"][1] / 3), s["bbox"][0]))
    for i, s in enumerate(out):
        s["i"] = i
    return out


def _erase_text(page, rect):
    """Borra solo el texto dentro de rect (sin tocar imágenes ni dibujos)."""
    page.add_redact_annot(rect)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                          graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                          text=fitz.PDF_REDACT_TEXT_REMOVE)


def _span_flags(s, bold=None, italic=None):
    flags = s["flags"]
    if bold is not None:
        flags = (flags | 16) if bold else (flags & ~16)
    if italic is not None:
        flags = (flags | 2) if italic else (flags & ~2)
    return flags


def _erase_spans(page, sel):
    """Borra el texto de varios fragmentos de una vez (solo texto)."""
    for s in sel:
        r = fitz.Rect(from_view(page, s["bbox"]))
        h = r.height
        page.add_redact_annot(fitz.Rect(r.x0, r.y0 + h * 0.2, r.x1, r.y1 - h * 0.2))
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                          graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                          text=fitz.PDF_REDACT_TEXT_REMOVE)


def _line_height(all_spans, s):
    """Interlineado del documento junto al fragmento (distancia a la línea de debajo)."""
    best = None
    for o in all_spans:
        if o is s or o["bbox"][0] > s["bbox"][2] or o["bbox"][2] < s["bbox"][0]:
            continue
        d = o["bbox"][1] - s["bbox"][1]
        if s["size"] * 0.9 < d < s["size"] * 2.5 and (best is None or d < best):
            best = d
    return best or s["size"] * 1.25


def replace_span(doc, pno, index, new_text, font="auto", size=None, color=None, bold=None, italic=None, push=True):
    """Sustituye el texto de un fragmento. Si el texto nuevo tiene varias líneas, se escriben
    una debajo de otra con el interlineado del documento y el texto de debajo baja (push)."""
    page = doc[pno]
    all_spans = spans(page)
    s = all_spans[index]
    flags = _span_flags(s, bold, italic)
    lines = new_text.split("\n") if new_text else []
    # La fuente se resuelve ANTES de borrar: después puede dejar de estar en la página.
    kw, label = resolve_font(doc, page, s["rawfont"], flags, new_text.replace("\n", ""), font) if new_text else ({}, "")
    lh = _line_height(all_spans, s) * ((size or s["size"]) / s["size"])
    extra = max(0, len(lines) - 1)
    below = []
    if push and extra:
        x0, x1 = s["bbox"][0], s["bbox"][2]
        below = [o for o in all_spans if o is not s and o["bbox"][1] >= s["bbox"][3] - 1
                 and o["bbox"][0] < x1 + 40 and o["bbox"][2] > x0 - 40]
    below_fonts = [resolve_font(doc, page, o["rawfont"], o["flags"], o["text"])[0] for o in below]
    _erase_spans(page, [s] + below)
    down = point_from_view(page, 0, 1) - point_from_view(page, 0, 0)  # un punto hacia abajo
    for i, line in enumerate(lines):
        if line.strip():
            page.insert_text(fitz.Point(s["origin"]) + down * (lh * i), line, fontsize=size or s["size"],
                             color=rgb(color or s["color"]), rotate=page.rotation, **_kw(page, kw))
    for o, okw in zip(below, below_fonts):
        page.insert_text(fitz.Point(o["origin"]) + down * (lh * extra), o["text"], fontsize=o["size"],
                         color=rgb(o["color"]), rotate=page.rotation, **_kw(page, okw))
    if not new_text:
        return "texto eliminado"
    return label


def move_spans(doc, pno, indices, dx, dy):
    """Mueve los fragmentos indicados dx, dy puntos (en coordenadas de pantalla)."""
    page = doc[pno]
    all_spans = spans(page)
    sel = [all_spans[i] for i in sorted(set(indices))]
    fonts = [resolve_font(doc, page, s["rawfont"], s["flags"], s["text"])[0] for s in sel]
    shift = point_from_view(page, dx, dy) - point_from_view(page, 0, 0)
    _erase_spans(page, sel)
    for s, kw in zip(sel, fonts):
        page.insert_text(fitz.Point(s["origin"]) + shift, s["text"], fontsize=s["size"],
                         color=rgb(s["color"]), rotate=page.rotation, **_kw(page, kw))


def scale_spans(doc, pno, indices, factor, anchor):
    """Cambia el tamaño de los fragmentos indicados (letra e interlineado) por `factor`,
    dejando fija la esquina `anchor` (x, y de pantalla) de la selección."""
    factor = max(0.2, min(8.0, float(factor)))
    page = doc[pno]
    all_spans = spans(page)
    sel = [all_spans[i] for i in sorted(set(indices))]
    fonts = [resolve_font(doc, page, s["rawfont"], s["flags"], s["text"])[0] for s in sel]
    a = point_from_view(page, float(anchor[0]), float(anchor[1]))
    _erase_spans(page, sel)
    for s, kw in zip(sel, fonts):
        o = fitz.Point(s["origin"])
        page.insert_text(a + (o - a) * factor, s["text"], fontsize=max(1.0, s["size"] * factor),
                         color=rgb(s["color"]), rotate=page.rotation, **_kw(page, kw))


def format_spans(doc, pno, indices, font="auto", size=None, color=None, bold=None, italic=None):
    """Cambia el formato de varios fragmentos manteniendo su texto y posición."""
    page = doc[pno]
    all_spans = spans(page)
    sel = [all_spans[i] for i in sorted(set(indices))]
    plan = []
    for s in sel:
        flags = _span_flags(s, bold, italic)
        plan.append((s, resolve_font(doc, page, s["rawfont"], flags, s["text"], font or "auto")))
    _erase_spans(page, sel)
    labels = set()
    for s, (kw, label) in plan:
        page.insert_text(fitz.Point(s["origin"]), s["text"], fontsize=size or s["size"],
                         color=rgb(color or s["color"]), rotate=page.rotation, **_kw(page, kw))
        labels.add(label)
    return ", ".join(sorted(labels))


def delete_spans(doc, pno, indices):
    page = doc[pno]
    all_spans = spans(page)
    _erase_spans(page, [all_spans[i] for i in sorted(set(indices))])


def font_data(doc, pno, rawfont):
    """Bytes de la fuente incrustada (TTF/OTF) para mostrarla en el navegador."""
    page = doc[pno]
    for xref, ext, _type, basefont, *_ in page.get_fonts(full=True):
        if basefont == rawfont or norm_font(basefont) == norm_font(rawfont):
            if ext in ("ttf", "otf"):
                buf = doc.extract_font(xref)[3]
                if buf:
                    return buf, ext
    path = _system_match(rawfont, False, False)
    if path:
        with open(path, "rb") as f:
            return f.read(), os.path.splitext(path)[1].lstrip(".").lower()
    return None, None


def font_file(key):
    """Bytes de una fuente elegida por el usuario (clave 'sys:ruta')."""
    if key.startswith("sys:") and key[4:] in system_fonts().values():
        with open(key[4:], "rb") as f:
            return f.read(), os.path.splitext(key)[1].lstrip(".").lower()
    return None, None


def add_text(doc, pno, x, y, text, font="base:helv", size=12, color="#000000", bold=False, italic=False):
    page = doc[pno]
    flags = (16 if bold else 0) | (2 if italic else 0)
    kw, label = resolve_font(doc, page, "", flags, text, font)
    p = point_from_view(page, x, y + size * 0.8)
    page.insert_text(p, text, fontsize=size, color=rgb(color), rotate=page.rotation, **_kw(page, kw))
    return label


def _wrap(text, width, size):
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for word in para.split(" "):
            t = f"{cur} {word}".strip()
            if cur and fitz.get_text_length(t, "helv", size) * 1.1 > width:
                lines.append(cur)
                cur = word
            else:
                cur = t
        lines.append(cur)
    return lines


def add_table(doc, pno, rect, cells, size=11, color="#000000", stroke="#000000", width=1.0, header=True,
              fill="#e8e8e8", font="base:helv"):
    """Dibuja una tabla (líneas y texto) dentro de `rect` (vista). cells = lista de filas de textos."""
    page = doc[pno]
    rows, cols = len(cells), max(len(r) for r in cells)
    x0, y0, x1, y1 = rect
    cw, ch = (x1 - x0) / cols, (y1 - y0) / rows
    pt = lambda x, y: point_from_view(page, x, y)
    sh = page.new_shape()
    if header and rows > 1 and fill:
        sh.draw_quad(fitz.Quad(pt(x0, y0), pt(x1, y0), pt(x0, y0 + ch), pt(x1, y0 + ch)))
        sh.finish(color=None, fill=rgb(fill))
    for i in range(rows + 1):
        sh.draw_line(pt(x0, y0 + i * ch), pt(x1, y0 + i * ch))
    for j in range(cols + 1):
        sh.draw_line(pt(x0 + j * cw, y0), pt(x0 + j * cw, y1))
    sh.finish(color=rgb(stroke), width=float(width))
    sh.commit()
    pad = 3
    for i, row in enumerate(cells):
        bold = header and i == 0 and rows > 1
        for j, text in enumerate(row):
            text = str(text or "").strip()
            if not text:
                continue
            s = float(size)
            while True:
                lines = _wrap(text, cw - 2 * pad, s)
                fits = len(lines) * s * 1.2 <= ch - 2 * pad and all(fitz.get_text_length(l, "helv", s) * 1.1 <= cw - 2 * pad for l in lines)
                if fits or s <= 5:
                    break
                s -= 0.5
            kw, _ = resolve_font(doc, page, "", 16 if bold else 0, "".join(lines), font)
            kw = _kw(page, kw)
            top = y0 + i * ch + (ch - len(lines) * s * 1.2) / 2  # centrado en vertical
            for k, line in enumerate(lines):
                page.insert_text(pt(x0 + j * cw + pad, top + k * s * 1.2 + s * 0.95), line, fontsize=s,
                                 color=rgb(color), rotate=page.rotation, **kw)
    return f"Tabla de {rows}×{cols}"


# --------------------------------------------------------------------------
# Imágenes
# --------------------------------------------------------------------------

def images(page):
    out = []
    for info in page.get_image_info(xrefs=True):
        if info.get("xref"):
            out.append({"xref": info["xref"], "bbox": to_view(page, info["bbox"])})
    return out


def _pixmap(doc, page, xref):
    smask = next((im[1] for im in page.get_images(full=True) if im[0] == xref), 0)
    pix = fitz.Pixmap(doc, xref)
    if pix.colorspace and pix.colorspace.n > 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    if smask:
        try:
            pix = fitz.Pixmap(pix, fitz.Pixmap(doc, smask))
        except Exception:
            pass
    return pix


def _remove_image(page, xref):
    """Elimina del todo la imagen (page.delete_image deja un hueco transparente)."""
    for info in page.get_image_info(xrefs=True):
        if info.get("xref") == xref:
            r = fitz.Rect(info["bbox"])
            c = (r.tl + r.br) / 2
            page.add_redact_annot(fitz.Rect(c.x - 0.5, c.y - 0.5, c.x + 0.5, c.y + 0.5))
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE,
                          graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                          text=fitz.PDF_REDACT_TEXT_NONE)


def delete_image(doc, pno, xref):
    _remove_image(doc[pno], xref)


def move_image(doc, pno, xref, rect):
    page = doc[pno]
    pix = _pixmap(doc, page, xref)
    _remove_image(page, xref)
    page.insert_image(from_view(page, rect), pixmap=pix, keep_proportion=False)


def insert_image(doc, pno, rect, data):
    page = doc[pno]
    page.insert_image(from_view(page, rect), stream=data, keep_proportion=True)


# --------------------------------------------------------------------------
# Anotaciones
# --------------------------------------------------------------------------

ANNOT_LABELS = {"Highlight": "Resaltado", "Underline": "Subrayado", "StrikeOut": "Tachado",
                "Text": "Nota", "Square": "Rectángulo", "Circle": "Elipse", "FreeText": "Cuadro de texto",
                "Ink": "Dibujo", "Line": "Línea"}


def annotations(page):
    out = []
    for a in page.annots() or ():
        d = {"xref": a.xref, "type": a.type[1],
             "label": "Resaltado (fosforito)" if a.info.get("subject") == "Fosforito" else ANNOT_LABELS.get(a.type[1], a.type[1]),
             "bbox": to_view(page, a.rect), "content": a.info.get("content", "")}
        if a.type[1] == "Line" and a.vertices and len(a.vertices) >= 2:  # extremos, para moverlos por separado
            d["points"] = [[round(v, 2) for v in fitz.Point(p) * page.rotation_matrix] for p in a.vertices[:2]]
        if a.type[1] in SHAPE_TYPES and a.info.get("subject") != "Fosforito":
            border = a.border or {}
            cols = a.colors or {}
            d["style"] = {"stroke": hex_rgb(cols.get("stroke")), "fill": hex_rgb(cols.get("fill")),
                          "width": round(border.get("width") or 0, 2), "dash": _dash_name(border.get("dashes")),
                          "opacity": round(a.opacity if a.opacity is not None and a.opacity >= 0 else 1, 2)}
            if a.type[1] == "Line":
                d["style"]["ends"] = list(a.line_ends or (0, 0))
        out.append(d)
    return out


def reading_words(page):
    """Palabras en orden de lectura, con la línea a la que pertenecen (para seleccionar texto
    arrastrando, como en cualquier lector de PDF)."""
    return [{"bbox": to_view(page, w[:4]), "text": w[4], "line": f"{w[5]}-{w[6]}"}
            for w in page.get_text("words", sort=True)]


def add_markup(doc, pno, kind, rects, color="#fff200", area=False):
    """Resaltar, subrayar o tachar el texto seleccionado: `rects` = un recuadro por línea
    (pantalla). Con `area` (páginas escaneadas sin texto), se marca la zona dibujada."""
    page = doc[pno]
    col = rgb(color)
    rs = [from_view(page, r) for r in rects if r[2] - r[0] > 0.5 and r[3] - r[1] > 0.5]
    if not rs:
        raise ValueError("No hay nada seleccionado.")
    if area:
        for r in rs:
            if kind == "highlight":  # recuadro de rotulador fosforito, que deja leer lo de debajo
                a = page.add_rect_annot(r)
                a.set_colors(stroke=col, fill=col)
                a.set_border(width=0)
                a.set_opacity(0.45)
                with contextlib.suppress(Exception):
                    a.set_blendmode(fitz.PDF_BM_Multiply)
                a.set_info(title="DocGuard", subject="Fosforito")
            else:
                y = r.y1 - r.height * 0.08 if kind == "underline" else (r.y0 + r.y1) / 2
                a = page.add_line_annot(fitz.Point(r.x0, y), fitz.Point(r.x1, y))
                a.set_colors(stroke=col)
                a.set_border(width=max(1.0, r.height * 0.06))
                a.set_info(title="DocGuard", subject="Subrayado" if kind == "underline" else "Tachado")
            a.update()
        return
    if kind == "highlight":
        return _marker_lines(page, rs, col, seed=int(rs[0].x0 * 7 + rs[0].y0 * 13))
    a = {"underline": page.add_underline_annot, "strikeout": page.add_strikeout_annot}[kind](rs)
    a.set_colors(stroke=col)
    a.update()


def add_annotation(doc, pno, kind, rect, text="", color="#ffd400", size=12, author=""):
    page = doc[pno]
    r = from_view(page, rect)
    col = rgb(color)
    if kind == "highlight":
        return _marker(page, r, col)
    if kind in ("underline", "strikeout"):
        quads = [fitz.Rect(w[:4]) for w in page.get_text("words") if fitz.Rect(w[:4]).intersects(r)]
        if not quads:
            raise ValueError("No hay texto en esa zona.")
        a = {"highlight": page.add_highlight_annot, "underline": page.add_underline_annot,
             "strikeout": page.add_strikeout_annot}[kind](quads)
        a.set_colors(stroke=col)
    elif kind == "note":
        a = page.add_text_annot(r.tl, text or "Comentario")
        a.set_colors(stroke=col)
        a.set_info(title=(author or "Usuario")[:60], subject="Comentario", creationDate=fitz.get_pdf_now())
    elif kind == "rect":
        a = page.add_rect_annot(r)
        a.set_colors(stroke=col)
        a.set_border(width=2)
    elif kind == "circle":
        a = page.add_circle_annot(r)
        a.set_colors(stroke=col)
        a.set_border(width=2)
    elif kind == "freetext":
        a = page.add_freetext_annot(r, text or "Texto", fontsize=size, text_color=col,
                                    fill_color=(1, 1, 1))
    else:
        raise ValueError(f"Tipo de anotación desconocido: {kind}")
    a.update()


NEON = {"amarillo": "#fff200", "verde": "#39ff14", "rosa": "#ff3fa4", "naranja": "#ff9a1f", "azul": "#1ee3ff", "lila": "#c86bff"}


def _marker(page, r, col):
    """Resaltado estilo rotulador fosforito: un trazo por línea, de punta redondeada y un
    poco irregular, semitransparente y en modo «multiplicar» para que el texto se lea."""
    words = [fitz.Rect(w[:4]) for w in page.get_text("words") if fitz.Rect(w[:4]).intersects(r)]
    if not words:
        raise ValueError("No hay texto en esa zona.")
    words.sort(key=lambda w: (round(w.y0), w.x0))
    lines = []
    for w in words:  # agrupar palabras por línea
        if lines and abs((lines[-1].y0 + lines[-1].y1) / 2 - (w.y0 + w.y1) / 2) < w.height * 0.5:
            lines[-1] |= w
        else:
            lines.append(fitz.Rect(w))
    return _marker_lines(page, lines, col, seed=int(r.x0 * 7 + r.y0 * 13))


def _marker_lines(page, lines, col, seed=1):
    """Un trazo de rotulador fosforito por cada línea (recuadros de página)."""
    import math
    import random
    rnd = random.Random(seed)
    for ln in lines:
        h = ln.height
        cy = (ln.y0 + ln.y1) / 2 + h * 0.04
        x0, x1 = ln.x0 - h * 0.15, ln.x1 + h * 0.15
        n = max(6, int((x1 - x0) / 6))
        tilt = rnd.uniform(-0.06, 0.06) * h
        ph = rnd.uniform(0, 6.28)
        # dos pasadas: el trazo principal y una veta más fina, como un rotulador real
        for width, dy, shrink, alpha in ((0.92, 0.0, 0.0, 0.62), (0.5, -0.14, 0.04, 0.45)):
            xa, xb = x0 + (x1 - x0) * shrink, x1 - (x1 - x0) * shrink * 0.5
            pts = [(xa + (xb - xa) * i / n, cy + dy * h + tilt * (i / n - 0.5) + math.sin(i / 2.2 + ph + dy * 9) * h * 0.035)
                   for i in range(n + 1)]
            a = page.add_ink_annot([pts])
            a.set_colors(stroke=col)
            a.set_border(width=h * width)
            a.set_opacity(alpha)
            try:
                a.set_blendmode(fitz.PDF_BM_Multiply)
            except Exception:
                pass
            a.set_info(title="DocGuard", subject="Fosforito")
            a.update()


def add_ink(doc, pno, strokes, color="#1a4fd6", width=2):
    page = doc[pno]
    pts = [[tuple(point_from_view(page, x, y)) for x, y in s] for s in strokes if len(s) > 1]
    if pts:
        a = page.add_ink_annot(pts)
        a.set_colors(stroke=rgb(color))
        a.set_border(width=width)
        a.update()


def edit_comment(doc, pno, xref, text):
    """Cambia el texto de un comentario (nota) ya puesto."""
    page = doc[pno]  # la página debe seguir viva mientras se usa la anotación
    a = _find_annot(page, xref)
    a.set_info(content=text, modDate=fitz.get_pdf_now())
    a.update()


def _pdf_date(s):
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?", s or "")
    return f"{m[3]}/{m[2]}/{m[1]}" + (f" {m[4]}:{m[5] or '00'}" if m[4] else "") if m else ""


def list_comments(doc):
    """Todos los comentarios del documento (notas y cualquier anotación con texto), por página."""
    out = []
    for n, page in enumerate(doc):
        for a in page.annots() or ():
            info = a.info
            if a.type[1] == "Popup" or not (info.get("content") or a.type[1] == "Text"):
                continue
            out.append({"n": n, "xref": a.xref, "type": a.type[1], "label": ANNOT_LABELS.get(a.type[1], a.type[1]),
                        "author": info.get("title", ""), "date": _pdf_date(info.get("modDate") or info.get("creationDate")),
                        "content": info.get("content", ""), "bbox": to_view(page, a.rect)})
    return out


def delete_annotation(doc, pno, xref):
    page = doc[pno]
    for a in page.annots() or ():
        if a.xref == xref:
            page.delete_annot(a)
            return
    raise ValueError("Anotación no encontrada.")


# --------------------------------------------------------------------------
# Formularios
# --------------------------------------------------------------------------

WIDGET_TYPES = {"text": fitz.PDF_WIDGET_TYPE_TEXT, "checkbox": fitz.PDF_WIDGET_TYPE_CHECKBOX,
                "combobox": fitz.PDF_WIDGET_TYPE_COMBOBOX, "listbox": fitz.PDF_WIDGET_TYPE_LISTBOX,
                "radio": fitz.PDF_WIDGET_TYPE_RADIOBUTTON}
WIDGET_NAMES = {v: k for k, v in WIDGET_TYPES.items()}
WIDGET_NAMES[fitz.PDF_WIDGET_TYPE_SIGNATURE] = "signature"


def widgets(page):
    out = []
    for w in page.widgets() or ():
        kind = WIDGET_NAMES.get(w.field_type, "other")
        value = w.field_value
        if kind in ("checkbox", "radio"):
            value = value not in (False, None, "", "Off")
        out.append({"xref": w.xref, "name": w.field_name, "type": kind, "bbox": to_view(page, w.rect),
                    "value": value, "options": list(w.choice_values or []),
                    "fontsize": w.text_fontsize, "readonly": bool(w.field_flags & 1)})
    return out


def _find_widget(page, xref):
    for w in page.widgets() or ():
        if w.xref == xref:
            return w
    raise ValueError("Campo no encontrado.")


def add_widget(doc, pno, kind, rect, name, value=None, options=None, fontsize=0):
    page = doc[pno]
    existing = {w.field_name for p in doc for w in (p.widgets() or ())}
    if kind != "radio" and name in existing:
        raise ValueError(f"Ya existe un campo llamado «{name}».")
    w = fitz.Widget()
    w.field_type = WIDGET_TYPES[kind]
    w.field_name = name
    w.rect = from_view(page, rect)
    w.text_fontsize = fontsize or 0
    w.border_color = (0.45, 0.45, 0.55)
    w.border_width = 1
    w.fill_color = (0.94, 0.96, 1)
    if kind in ("combobox", "listbox"):
        w.choice_values = options or ["Opción 1"]
        w.field_value = value if value in w.choice_values else w.choice_values[0]
    elif kind == "text":
        w.field_value = value or ""
    elif kind in ("checkbox", "radio"):
        w.field_value = bool(value)
    page.add_widget(w)


def copy_object(doc, pno, kind, xref):
    """Datos para pegar un campo de formulario, una forma o un dibujo como objeto (no como captura)."""
    page = doc[pno]
    if kind == "widget":
        w = _find_widget(page, xref)
        if w.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
            raise ValueError("Los recuadros de firma digital no se copian.")
        k = WIDGET_NAMES.get(w.field_type, "text")
        value = w.field_value
        if k in ("checkbox", "radio"):
            value = value not in (False, None, "", "Off")
        return {"kind": "widget", "type": k, "name": w.field_name, "rect": to_view(page, w.rect), "value": value,
                "options": list(w.choice_values or []), "fontsize": w.text_fontsize,
                "border_color": list(w.border_color or []), "fill_color": list(w.fill_color or []),
                "text_color": list(w.text_color or []), "border_width": w.border_width}
    a = _find_annot(page, xref)
    t = a.type[1]
    if t not in SHAPE_TYPES:
        raise ValueError("Este elemento no se puede copiar como objeto.")
    view = lambda p: [round(v, 2) for v in fitz.Point(p) * page.rotation_matrix]
    spec = {"kind": "annot", "type": t, "rect": to_view(page, a.rect), "colors": a.colors or {},
            "border": {"width": (a.border or {}).get("width") or 0, "dashes": list((a.border or {}).get("dashes") or [])},
            "opacity": a.opacity if a.opacity is not None and a.opacity >= 0 else 1, "info": dict(a.info)}
    if t == "Line":
        spec["points"], spec["ends"] = [view(p) for p in a.vertices[:2]], list(a.line_ends or (0, 0))
    elif t == "Ink":
        spec["strokes"] = [[view(p) for p in stroke] for stroke in a.vertices]
    elif t in ("Polygon", "PolyLine"):
        spec["points"] = [view(p) for p in a.vertices]
    return spec


def paste_object(doc, pno, spec, x, y):
    """Pega lo copiado con copy_object con su esquina superior izquierda en (x, y) de pantalla.
    Un campo pegado recibe otro nombre (salvo los botones de opción, que siguen en su grupo)."""
    page = doc[pno]
    dx, dy = float(x) - spec["rect"][0], float(y) - spec["rect"][1]
    shift = lambda p: point_from_view(page, p[0] + dx, p[1] + dy)
    moved = lambda r: from_view(page, [r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy])
    if spec["kind"] == "widget":
        existing = {w.field_name for p in doc for w in (p.widgets() or ())}
        name = spec["name"]
        if spec["type"] != "radio":
            base, k = re.sub(r"_\d+$", "", name), 2
            while f"{base}_{k}" in existing:
                k += 1
            name = f"{base}_{k}"
        w = fitz.Widget()
        w.field_type = WIDGET_TYPES[spec["type"]]
        w.field_name = name
        w.rect = moved(spec["rect"])
        w.text_fontsize = spec.get("fontsize") or 0
        w.border_width = spec.get("border_width") or 1
        for key in ("border_color", "fill_color", "text_color"):
            if spec.get(key):
                setattr(w, key, tuple(spec[key]))
        if spec["type"] in ("combobox", "listbox"):
            w.choice_values = spec.get("options") or ["Opción 1"]
            w.field_value = spec["value"] if spec.get("value") in w.choice_values else w.choice_values[0]
        elif spec["type"] == "text":
            w.field_value = spec.get("value") or ""
        elif spec["type"] in ("checkbox", "radio"):
            w.field_value = bool(spec.get("value")) and spec["type"] == "checkbox"
        page.add_widget(w)
        return name
    t = spec["type"]
    if t in ("Square", "Circle"):
        bw = (spec["border"].get("width") or 0) / 2  # como al mover: el borde no se suma dos veces
        r = moved(spec["rect"])
        r = fitz.Rect(r.x0 + bw, r.y0 + bw, r.x1 - bw, r.y1 - bw)
        a = page.add_rect_annot(r) if t == "Square" else page.add_circle_annot(r)
    elif t == "Line":
        a = page.add_line_annot(shift(spec["points"][0]), shift(spec["points"][1]))
        a.set_line_ends(*spec.get("ends", (0, 0)))
    elif t == "Ink":
        a = page.add_ink_annot([[shift(p) for p in stroke] for stroke in spec["strokes"]])
    else:
        pts = [shift(p) for p in spec["points"]]
        a = page.add_polygon_annot(pts) if t == "Polygon" else page.add_polyline_annot(pts)
    cols = spec.get("colors") or {}
    a.set_colors(stroke=cols.get("stroke"), fill=cols.get("fill") or [])
    dashes = [int(v) for v in spec["border"].get("dashes") or []]
    if dashes:
        a.set_border(width=spec["border"].get("width") or 1, dashes=dashes)
    else:
        a.set_border(width=spec["border"].get("width") or 1)
    if spec.get("opacity", 1) < 1:
        a.set_opacity(spec["opacity"])
    a.set_info(spec.get("info") or {})
    if (spec.get("info") or {}).get("subject") == "Fosforito":
        with contextlib.suppress(Exception):
            a.set_blendmode(fitz.PDF_BM_Multiply)
    a.update()
    return t


def update_widget(doc, pno, xref, name=None, value=None, options=None, rect=None, fontsize=None):
    page = doc[pno]
    w = _find_widget(page, xref)
    if name is not None and name != w.field_name:
        w.field_name = name
    if options is not None and w.field_type in (fitz.PDF_WIDGET_TYPE_COMBOBOX, fitz.PDF_WIDGET_TYPE_LISTBOX):
        w.choice_values = options
    if rect is not None:
        w.rect = from_view(page, rect)
    if fontsize is not None:
        w.text_fontsize = fontsize
    if value is not None:
        if w.field_type in (fitz.PDF_WIDGET_TYPE_CHECKBOX, fitz.PDF_WIDGET_TYPE_RADIOBUTTON):
            w.field_value = w.on_state() if value else "Off"
        else:
            w.field_value = value
    w.update()


def delete_widget(doc, pno, xref):
    page = doc[pno]
    w = _find_widget(page, xref)
    if w.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
        raise ValueError("Las firmas digitales no se pueden borrar.")
    page.delete_widget(w)


def flatten_forms(doc):
    """Convierte campos de formulario y anotaciones en contenido fijo (ya no editable)."""
    doc.bake(annots=True, widgets=True)


# --------------------------------------------------------------------------
# Formas (como anotaciones, igual que en Acrobat: se pueden mover y borrar)
# --------------------------------------------------------------------------

SHAPE_TYPES = ("Square", "Circle", "Line", "Ink", "Polygon", "PolyLine")
DASHES = {"continua": None, "discontinua": [6, 3], "punteada": [1, 3], "rayas-largas": [12, 4]}


def hex_rgb(c):
    """Color de PyMuPDF (0..1) a #rrggbb (None si no hay)."""
    if not c:
        return None
    return "#" + "".join(f"{max(0, min(255, round(v * 255))):02x}" for v in c[:3])


def _dash_name(dashes):
    if not dashes:
        return "continua"
    ratio = dashes[0] / max(1, dashes[1]) if len(dashes) > 1 else 1  # el patrón se reconoce por su proporción
    return min((k for k, v in DASHES.items() if v), key=lambda k: abs(DASHES[k][0] / DASHES[k][1] - ratio))


def _border(a, width, dash):
    pattern = DASHES.get(dash or "continua")
    if pattern:  # PDF solo guarda guiones enteros; se escalan con el grosor
        k = max(1, round(width / 2))
        a.set_border(width=width, dashes=[max(1, round(v * k)) for v in pattern])
    else:
        a.set_border(width=width, style="S", dashes=[])


def style_annotation(doc, pno, xref, stroke=None, fill="keep", width=None, dash=None, opacity=None, ends=None):
    """Cambia el aspecto de una forma ya dibujada: contorno, relleno (None = sin relleno),
    grosor, tipo de línea, opacidad y, en las líneas, sus extremos (flechas)."""
    page = doc[pno]
    a = _find_annot(page, xref)
    t = a.type[1]
    if t not in SHAPE_TYPES:
        raise ValueError("Solo se pueden cambiar así las formas y los dibujos.")
    cols = a.colors or {}
    stroke_c = rgb(stroke) if stroke else cols.get("stroke")
    if t == "Line":
        fill_c = stroke_c  # las puntas de flecha se rellenan del color de la línea
    elif fill == "keep":
        fill_c = cols.get("fill")
    else:
        fill_c = rgb(fill) if fill else []
    a.set_colors(stroke=stroke_c, fill=fill_c if fill_c else [])
    border = a.border or {}
    w = float(width) if width is not None else (border.get("width") or 1)
    _border(a, w, dash if dash is not None else _dash_name(border.get("dashes")))
    if opacity is not None:
        a.set_opacity(max(0.05, min(1.0, float(opacity))))
    if t == "Line" and ends is not None:
        a.set_line_ends(int(ends[0]), int(ends[1]))
    a.update()


def add_shape(doc, pno, kind, rect, stroke="#d62828", fill=None, width=2, points=None, dash="continua", opacity=1.0):
    page = doc[pno]
    col = rgb(stroke)
    fcol = rgb(fill) if fill else None
    if kind in ("rect", "ellipse"):
        r = from_view(page, rect)
        a = page.add_rect_annot(r) if kind == "rect" else page.add_circle_annot(r)
        a.set_colors(stroke=col, fill=fcol)
    elif kind in ("line", "arrow"):
        p1 = point_from_view(page, *points[0])
        p2 = point_from_view(page, *points[1])
        a = page.add_line_annot(p1, p2)
        a.set_colors(stroke=col, fill=col)
        if kind == "arrow":
            a.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_CLOSED_ARROW)
    else:
        raise ValueError(f"Forma desconocida: {kind}")
    _border(a, width, dash)
    if opacity is not None and float(opacity) < 1:
        a.set_opacity(max(0.05, float(opacity)))
    a.set_info(title="DocGuard", subject="Forma")
    a.update()


def _find_annot(page, xref):
    for a in page.annots() or ():
        if a.xref == xref:
            return a
    raise ValueError("Anotación no encontrada.")


def _replace_line(page, a, p1, p2):
    """Rehace una línea (o flecha) con otros extremos, conservando color, grosor y puntas."""
    colors, width, ends, info = a.colors, (a.border or {}).get("width", 2), a.line_ends, a.info
    b = page.add_line_annot(p1, p2)
    b.set_line_ends(*ends)
    b.set_colors(stroke=colors.get("stroke"), fill=colors.get("fill"))
    b.set_border(width=width)
    b.set_info(info)
    b.update()
    page.delete_annot(a)


def set_line(doc, pno, xref, points):
    """Mueve los extremos de una línea o flecha (coordenadas de pantalla)."""
    page = doc[pno]
    a = _find_annot(page, xref)
    if a.type[1] != "Line":
        raise ValueError("Solo las líneas y flechas tienen extremos.")
    _replace_line(page, a, point_from_view(page, *points[0]), point_from_view(page, *points[1]))


def move_annotation(doc, pno, xref, rect):
    """Mueve o redimensiona una anotación al rectángulo indicado (pantalla)."""
    page = doc[pno]
    a = _find_annot(page, xref)
    old = fitz.Rect(a.rect)
    new = from_view(page, rect)
    t = a.type[1]
    if t in ("Highlight", "Underline", "StrikeOut", "Squiggly"):
        raise ValueError("Los resaltados van unidos al texto y no se pueden mover.")
    if t in ("Line", "Ink", "PolyLine", "Polygon"):
        sx = new.width / old.width if old.width else 1
        sy = new.height / old.height if old.height else 1
        f = lambda p: fitz.Point(new.x0 + (p[0] - old.x0) * sx, new.y0 + (p[1] - old.y0) * sy)
        colors, width = a.colors, (a.border or {}).get("width", 2)
        if t == "Line":
            v = a.vertices
            _replace_line(page, a, f(v[0]), f(v[1]))
            return
        elif t == "Ink":
            b = page.add_ink_annot([[f(p) for p in stroke] for stroke in a.vertices])
        else:
            pts = [f(p) for p in a.vertices]
            b = page.add_polyline_annot(pts) if t == "PolyLine" else page.add_polygon_annot(pts)
        b.set_colors(stroke=colors.get("stroke"), fill=colors.get("fill"))
        b.set_border(width=width)
        b.set_info(a.info)
        b.update()
        page.delete_annot(a)
        return
    if t in ("Square", "Circle"):
        # el recuadro que se ve incluye medio borde por cada lado y update() lo vuelve a añadir:
        # se descuenta para que la forma no crezca cada vez que se mueve
        bw = ((a.border or {}).get("width") or 0) / 2
        new = fitz.Rect(new.x0 + bw, new.y0 + bw, new.x1 - bw, new.y1 - bw)
    a.set_rect(new)
    a.update()


# --------------------------------------------------------------------------
# Copiar y pegar zonas del documento
# --------------------------------------------------------------------------

def copy_region(doc, pno, rect):
    """Devuelve (datos para pegar, texto, png) de una zona de la página."""
    page = doc[pno]
    r = from_view(page, rect)
    text = page.get_textbox(r).strip()
    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=r * page.rotation_matrix if page.rotation else r, alpha=False)
    png = pix.tobytes("png")
    clip = {"pdf": doc.tobytes(), "pno": pno, "rect": tuple(r), "text": text, "png": png,
            "size": (rect[2] - rect[0], rect[3] - rect[1])}
    return clip, text, png


def paste_region(doc, pno, clip, x, y, mode="auto"):
    """Pega la zona copiada con su esquina en x, y.
    mode='vector': tal cual (texto, dibujos e imágenes, sin perder calidad).
    mode='image': como captura (una imagen que luego se puede mover y redimensionar).
    mode='auto': captura si la zona no tiene texto (gráficas, fotos...), vectorial si lo tiene."""
    page = doc[pno]
    w, h = clip["size"]
    target = from_view(page, [x, y, x + w, y + h])
    if mode == "image" or (mode == "auto" and not clip.get("text")):
        page.insert_image(target, stream=clip["png"], keep_proportion=False)
        return "pegado como imagen"
    with fitz.open("pdf", clip["pdf"]) as src:
        page.show_pdf_page(target, src, clip["pno"], clip=fitz.Rect(clip["rect"]))
    return "pegado"


def copy_spans(doc, pno, indices):
    """Copia textos seleccionados conservando fuente, tamaño, color y posición relativa."""
    page = doc[pno]
    all_spans = spans(page)
    sel = [all_spans[i] for i in sorted(set(indices))]
    x0 = min(s["bbox"][0] for s in sel)
    y0 = min(s["bbox"][1] for s in sel)
    items = []
    for s in sel:
        o = fitz.Point(s["origin"]) * page.rotation_matrix
        items.append({k: s[k] for k in ("text", "rawfont", "flags", "size", "color")} | {"dx": o.x - x0, "dy": o.y - y0})
    sel_sorted = sorted(sel, key=lambda s: (round(s["bbox"][1]), s["bbox"][0]))
    text = "\n".join(s["text"] for s in sel_sorted)
    return {"items": items, "pdf": doc.tobytes(), "pno": pno}, text


def paste_spans(doc, pno, clip, x, y):
    page = doc[pno]
    with fitz.open("pdf", clip["pdf"]) as src:
        spage = src[clip["pno"]]
        fonts = [resolve_font(src, spage, it["rawfont"], it["flags"], it["text"])[0] for it in clip["items"]]
    for it, kw in zip(clip["items"], fonts):
        page.insert_text(point_from_view(page, x + it["dx"], y + it["dy"]), it["text"], fontsize=it["size"],
                         color=rgb(it["color"]), rotate=page.rotation, **_kw(page, kw))


# --------------------------------------------------------------------------
# OCR: hacer seleccionable o editable el texto de un escaneo
# --------------------------------------------------------------------------

def _fit_size(text, width, height, font="helv"):
    fs = height * 0.82
    tl = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return fs * min(1.0, width / tl) if tl > 0 else fs


def ocr_page(doc, pno, mode="editable"):
    """mode='invisible': añade una capa de texto invisible (se puede buscar y copiar).
    mode='editable': sustituye la imagen del texto por texto real editable."""
    import core
    page = doc[pno]
    lines = core.ocr_page_lines(page)
    if not lines:
        return 0
    if mode == "invisible":
        # una línea completa (con sus espacios) por línea reconocida: así buscar y copiar funcionan bien.
        # Fuente incrustada (se reduce luego a las letras usadas): lo exige PDF/A y evita sustituciones.
        page.insert_font(fontname="DGocr", fontbuffer=fitz.Font("helv").buffer)
        for r, text, _words in lines:
            page.insert_text(fitz.Point(r.x0, r.y1 - r.height * 0.2), text, fontname="DGocr",
                             fontsize=_fit_size(text, r.width, r.height), render_mode=3)
        return len(lines)
    zoom = 2
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    import numpy as np
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3]
    for r, text, _w in lines:
        vr = r * page.rotation_matrix * zoom
        x0, y0 = max(0, int(vr.x0)), max(0, int(vr.y0))
        x1, y1 = min(pix.width, int(vr.x1) + 1), min(pix.height, int(vr.y1) + 1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        box = arr[y0:y1, x0:x1].reshape(-1, 3)
        lum = box.mean(axis=1)
        ink = box[lum <= np.percentile(lum, 15)].mean(axis=0) / 255
        ring = np.concatenate([arr[max(0, y0 - 2):y0, x0:x1].reshape(-1, 3), arr[y1:y1 + 2, x0:x1].reshape(-1, 3),
                               arr[y0:y1, max(0, x0 - 2):x0].reshape(-1, 3), arr[y0:y1, x1:x1 + 2].reshape(-1, 3)])
        bg = (np.median(ring, axis=0) if len(ring) else np.array([255, 255, 255])) / 255
        pad = r.height * 0.12
        page.draw_rect(fitz.Rect(r.x0 - pad, r.y0 - pad, r.x1 + pad, r.y1 + pad), color=None, fill=tuple(bg), overlay=True)
        page.insert_text(fitz.Point(r.x0, r.y1 - r.height * 0.2), text, fontsize=_fit_size(text, r.width, r.height),
                         fontname="helv", color=tuple(ink), rotate=page.rotation)
    return len(lines)


# --------------------------------------------------------------------------
# Firma manuscrita al margen de varias páginas
# --------------------------------------------------------------------------

def sign_margin(doc, png, side="derecha", length_pct=22, pages=None, ratio=3.0):
    """Coloca la firma en el margen de cada página. En los laterales va en vertical."""
    count = 0
    for pno in (pages if pages is not None else range(len(doc))):
        page = doc[pno]
        W, H = page.rect.width, page.rect.height
        m = min(W, H) * 0.025
        if side in ("derecha", "izquierda"):
            length = H * length_pct / 100
            thick = length / ratio
            x0 = W - m - thick if side == "derecha" else m
            y0 = (H - length) / 2
            rect, rot = [x0, y0, x0 + thick, y0 + length], 90
        else:
            length = W * length_pct / 100
            thick = length / ratio
            x0 = {"pie-derecha": W - m - length, "pie-izquierda": m}.get(side, (W - length) / 2)
            rect, rot = [x0, H - m - thick, x0 + length, H - m], 0
        page.insert_image(from_view(page, rect), stream=png, keep_proportion=True, rotate=rot)
        count += 1
    return count


# --------------------------------------------------------------------------
# Numeración de páginas, encabezados y pies
# --------------------------------------------------------------------------

def header_footer(doc, number="Página {n} de {total}", number_pos="abajo-centro", header="", header_align="centro",
                  footer="", footer_align="izquierda", size=9, color="#444444", start=1, skip_first=False,
                  pages=None, filename=""):
    """Escribe numeración, encabezado y pie en las páginas indicadas.
    Admite {n}, {total}, {fecha} y {archivo} en los textos."""
    import datetime
    fecha = datetime.date.today().strftime("%d/%m/%Y")
    targets = list(pages) if pages is not None else list(range(len(doc)))
    if skip_first and targets and targets[0] == 0:
        targets = targets[1:]
    total = len(targets) + start - 1
    col = rgb(color)
    count = 0
    for k, pno in enumerate(targets):
        page = doc[pno]
        W, H = page.rect.width, page.rect.height
        m = max(18.0, min(W, H) * 0.035)
        fill = lambda t: (t.replace("{n}", str(start + k)).replace("{total}", str(total))
                          .replace("{fecha}", fecha).replace("{archivo}", filename))
        items = []
        if number:
            v, hpos = number_pos.split("-")
            items.append((fill(number), v, hpos))
        if header:
            items.append((fill(header), "arriba", header_align))
        if footer:
            items.append((fill(footer), "abajo", footer_align))
        for text, v, hpos in items:
            kw, _ = resolve_font(doc, page, "", 0, text, "base:helv")
            font = fitz.Font(fontfile=kw["fontfile"]) if "fontfile" in kw else fitz.Font(kw["fontname"])
            tw = font.text_length(text, fontsize=size)
            x = {"izquierda": m, "centro": (W - tw) / 2, "derecha": W - m - tw}[hpos]
            y = m + size if v == "arriba" else H - m
            page.insert_text(point_from_view(page, x, y), text, fontsize=size, color=col, rotate=page.rotation, **_kw(page, kw))
        count += 1
    return f"{count} páginas"
