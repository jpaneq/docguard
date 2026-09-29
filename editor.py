"""Edición de PDF: texto, imágenes, anotaciones, formularios y firmas manuscritas.

Todas las coordenadas que entran y salen de este módulo son "de pantalla":
puntos PDF con la rotación de la página ya aplicada (origen arriba a la izquierda),
que es como se ve la página renderizada.
"""

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
    if n in idx:
        return idx[n]
    fam = re.sub(r"(bold|italic|oblique|regular|semibold|black|light)+$", "", n)
    style = ("bold" if bold else "") + ("italic" if italic else "")
    for cand in (fam + style, fam + ("bd" if bold else "") + ("i" if italic else ""), fam):
        if cand in idx:
            return idx[cand]
    return None


def _covers(font, text):
    return all(font.has_glyph(ord(c)) for c in text if not c.isspace())


def resolve_font(doc, page, name, flags, text, choice="auto"):
    """Elige la fuente para `text`. Devuelve (kwargs para insert_text, etiqueta).

    Con choice="auto": 1) la fuente incrustada en el PDF si es completa y tiene
    todas las letras; 2) la misma familia instalada en el sistema; 3) la
    incrustada aunque sea parcial, si cubre el texto; 4) Helvetica/Times/Courier."""
    bold, italic = bool(flags & 16), bool(flags & 2)
    if choice.startswith("base:"):
        fam = choice[5:]
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
    """Fragmentos de texto horizontales de la página, con fuente, tamaño y color."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            if abs(line["dir"][1]) > 0.01:
                continue
            for s in line["spans"]:
                if not s["text"].strip():
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


def replace_span(doc, pno, index, new_text, font="auto", size=None, color=None, bold=None, italic=None):
    page = doc[pno]
    s = spans(page)[index]
    flags = s["flags"]
    if bold is not None:
        flags = (flags | 16) if bold else (flags & ~16)
    if italic is not None:
        flags = (flags | 2) if italic else (flags & ~2)
    rect = fitz.Rect(from_view(page, s["bbox"]))
    h = rect.height
    _erase_text(page, fitz.Rect(rect.x0, rect.y0 + h * 0.2, rect.x1, rect.y1 - h * 0.2))
    if not new_text:
        return "texto eliminado"
    kw, label = resolve_font(doc, page, s["rawfont"], flags, new_text, font)
    page.insert_text(fitz.Point(s["origin"]), new_text, fontsize=size or s["size"],
                     color=rgb(color or s["color"]), rotate=page.rotation, **kw)
    return label


def add_text(doc, pno, x, y, text, font="base:helv", size=12, color="#000000", bold=False, italic=False):
    page = doc[pno]
    flags = (16 if bold else 0) | (2 if italic else 0)
    kw, label = resolve_font(doc, page, "", flags, text, font)
    p = point_from_view(page, x, y + size * 0.8)
    page.insert_text(p, text, fontsize=size, color=rgb(color), rotate=page.rotation, **kw)
    return label


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
    return [{"xref": a.xref, "type": a.type[1], "label": ANNOT_LABELS.get(a.type[1], a.type[1]),
             "bbox": to_view(page, a.rect), "content": a.info.get("content", "")}
            for a in page.annots() or ()]


def add_annotation(doc, pno, kind, rect, text="", color="#ffd400", size=12):
    page = doc[pno]
    r = from_view(page, rect)
    col = rgb(color)
    if kind in ("highlight", "underline", "strikeout"):
        quads = [fitz.Rect(w[:4]) for w in page.get_text("words") if fitz.Rect(w[:4]).intersects(r)]
        if not quads:
            raise ValueError("No hay texto en esa zona.")
        a = {"highlight": page.add_highlight_annot, "underline": page.add_underline_annot,
             "strikeout": page.add_strikeout_annot}[kind](quads)
        a.set_colors(stroke=col)
    elif kind == "note":
        a = page.add_text_annot(r.tl, text or "Nota")
        a.set_colors(stroke=col)
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


def add_ink(doc, pno, strokes, color="#1a4fd6", width=2):
    page = doc[pno]
    pts = [[tuple(point_from_view(page, x, y)) for x, y in s] for s in strokes if len(s) > 1]
    if pts:
        a = page.add_ink_annot(pts)
        a.set_colors(stroke=rgb(color))
        a.set_border(width=width)
        a.update()


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
    page.delete_widget(_find_widget(page, xref))


def flatten_forms(doc):
    """Convierte campos de formulario y anotaciones en contenido fijo (ya no editable)."""
    doc.bake(annots=True, widgets=True)
