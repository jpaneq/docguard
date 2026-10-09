"""PDF → Word «fiel a la página».

Cada página del PDF es una sección de Word con EXACTAMENTE su tamaño (sin márgenes). Por dentro:
  · el fondo de la página (imágenes, líneas, formas, sellos…) como imagen detrás, sin el texto;
  · el texto, línea a línea, en cuadros de texto de Word colocados en la posición exacta, con su
    fuente, tamaño, color, negrita y cursiva, sin ajuste de línea: se puede editar y no se mueve nada.
Las páginas escaneadas (texto invisible del OCR) quedan como imagen con el texto oculto, buscable."""

import io
import re

import pymupdf as fitz
from docx import Document
from docx.oxml import parse_xml

EMU = 12700   # EMU por punto
TW = 20       # twips por punto

NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"')

# Nombre de la fuente del PDF → familia de Word (las que no están se limpian del prefijo y estilo)
FAMILIES = [("arial", "Arial"), ("helvetica", "Arial"), ("timesnewroman", "Times New Roman"), ("times", "Times New Roman"),
            ("couriernew", "Courier New"), ("courier", "Courier New"), ("calibri", "Calibri"), ("cambria", "Cambria"),
            ("verdana", "Verdana"), ("tahoma", "Tahoma"), ("georgia", "Georgia"), ("segoeui", "Segoe UI"),
            ("trebuchet", "Trebuchet MS"), ("garamond", "Garamond"), ("palatino", "Palatino Linotype"),
            ("comicsans", "Comic Sans MS"), ("symbol", "Symbol"), ("opensans", "Open Sans"), ("roboto", "Roboto"),
            ("lato", "Lato"), ("montserrat", "Montserrat"), ("consolas", "Consolas")]
STYLE_WORDS = re.compile(r"(bold|italic|oblique|regular|roman|semibold|light|medium|black|narrow|condensed|mt|ps|psmt)", re.I)


def family(raw, flags):
    name = raw.split("+", 1)[-1]
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    for k, fam in FAMILIES:
        if key.startswith(k):
            return fam
    base = STYLE_WORDS.sub("", re.split(r"[-,]", name)[0])
    base = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", base).strip()
    return base or ("Times New Roman" if flags & 4 else "Arial")


# Caracteres que XML no admite (controles, sustitutos sueltos, U+FFFE/U+FFFF): algunos PDF los traen en su texto
BAD_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


def clean(t):
    return BAD_XML.sub("", t or "")


def esc(t):
    return clean(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _run(span, hidden):
    size = max(1.0, span["size"])
    flags = span["flags"]
    fam = esc(family(span["font"], flags))
    bold = bool(flags & 16) or bool(re.search(r"bold|black|heavy", span["font"], re.I))
    italic = bool(flags & 2) or bool(re.search(r"italic|oblique", span["font"], re.I))
    col = "%06X" % (span["color"] & 0xFFFFFF)
    half = max(2, int(round(size * 2)))
    rpr = (f'<w:rFonts w:ascii="{fam}" w:hAnsi="{fam}" w:cs="{fam}" w:eastAsia="{fam}"/>'
           f'{"<w:b/><w:bCs/>" if bold else ""}{"<w:i/><w:iCs/>" if italic else ""}'
           f'<w:color w:val="{col}"/><w:sz w:val="{half}"/><w:szCs w:val="{half}"/>{"<w:vanish/>" if hidden else ""}')
    return f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{esc(span["text"])}</w:t></w:r>'


def _textbox(n, z, x, y, w, h, spans, hidden):
    runs = "".join(_run(s, hidden) for s in spans)
    cx, cy = int(w * EMU), int(h * EMU)
    return (
        f'<w:r {NS}><w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="{z}" '
        f'behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1"><wp:simplePos x="0" y="0"/>'
        f'<wp:positionH relativeFrom="page"><wp:posOffset>{int(x * EMU)}</wp:posOffset></wp:positionH>'
        f'<wp:positionV relativeFrom="page"><wp:posOffset>{int(y * EMU)}</wp:posOffset></wp:positionV>'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
        f'<wp:docPr id="{n}" name="Texto {n}"/><wp:cNvGraphicFramePr/>'
        f'<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        f'<wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></wps:spPr>'
        f'<wps:txbx><w:txbxContent><w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
        f'<w:ind w:left="0" w:right="0"/><w:jc w:val="left"/></w:pPr>{runs}</w:p></w:txbxContent></wps:txbx>'
        f'<wps:bodyPr rot="0" vert="horz" wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" anchor="t" anchorCtr="0">'
        f'<a:noAutofit/></wps:bodyPr></wps:wsp></a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>')


def _picture(n, rid, w, h):
    cx, cy = int(w * EMU), int(h * EMU)
    return (
        f'<w:r {NS}><w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="0" '
        f'behindDoc="1" locked="0" layoutInCell="1" allowOverlap="1"><wp:simplePos x="0" y="0"/>'
        f'<wp:positionH relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionH>'
        f'<wp:positionV relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionV>'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
        f'<wp:docPr id="{n}" name="Fondo de la página {n}"/><wp:cNvGraphicFramePr/>'
        f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{n}" name="fondo{n}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>')


def _sectpr(w, h):
    orient = ' w:orient="landscape"' if w > h else ""
    return (f'<w:sectPr><w:type w:val="nextPage"/><w:pgSz w:w="{int(round(w * TW))}" w:h="{int(round(h * TW))}"{orient}/>'
            f'<w:pgMar w:top="0" w:right="0" w:bottom="0" w:left="0" w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>')


def _invisible_text(page):
    """True si casi todo el texto de la página es invisible (capa de OCR sobre un escaneo)."""
    try:
        tr = page.get_texttrace()
    except Exception:
        return False
    total = sum(len(t.get("chars", ())) for t in tr)
    hidden = sum(len(t.get("chars", ())) for t in tr if t.get("type") == 3 or (t.get("opacity", 1) == 0))
    return total > 0 and hidden > 0.5 * total


def _lines(page):
    """Líneas horizontales con texto: [(bbox, spans)]. El texto girado se queda en el fondo."""
    out = []
    for b in page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT & ~fitz.TEXT_PRESERVE_IMAGES)["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            dx, dy = ln["dir"]
            spans = [dict(s, text=clean(s["text"])) for s in ln["spans"] if clean(s["text"]) != ""]
            if not spans or not "".join(s["text"] for s in spans).strip() or abs(dy) > 0.02 or dx < 0.98:
                continue
            out.append((fitz.Rect(ln["bbox"]), spans))
    return out


def _background(doc, i, lines, dpi):
    """Imagen de la página sin el texto que va a ir en cuadros. Devuelve (bytes, extensión)."""
    tmp = fitz.open()
    tmp.insert_pdf(doc, from_page=i, to_page=i)
    p = tmp[0]
    for bb, _ in lines:
        h = bb.height
        p.add_redact_annot(fitz.Rect(bb.x0, bb.y0 + h * 0.2, bb.x1, bb.y1 - h * 0.2), fill=False)
    if lines:
        try:
            p.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                               text=fitz.PDF_REDACT_TEXT_REMOVE)
        except TypeError:
            p.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    has_img = bool(p.get_images())
    pix = p.get_pixmap(dpi=dpi, alpha=False)
    tmp.close()
    if has_img:
        return pix.tobytes("jpg", jpg_quality=90), "jpg"
    return pix.tobytes("png"), "png"


def pdf_to_docx_fiel(src, dst, dpi=200, password=None, progress=None):
    doc = fitz.open(src)
    if doc.needs_pass and password:
        doc.authenticate(password)
    word = Document()
    body = word.element.body
    last_sect = body.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sectPr")
    n_id = [1]

    def nid():
        n_id[0] += 1
        return n_id[0]

    n_pages = len(doc)
    for i in range(n_pages):
        page = doc[i]
        w, h = page.rect.width, page.rect.height
        text_ok = page.rotation == 0
        lines = _lines(page) if text_ok else []
        hidden = text_ok and _invisible_text(page)
        data, ext = _background(doc, i, lines, dpi)
        rid, _img = word.part.get_or_add_image(io.BytesIO(data))
        parts = [_picture(nid(), rid, w, h)]
        for z, (bb, spans) in enumerate(lines, start=1):
            asc = max((s.get("ascender") or 0.9) * s["size"] for s in spans)
            desc = max(abs(s.get("descender") or -0.25) * s["size"] for s in spans)
            baseline = spans[0]["origin"][1]
            parts.append(_textbox(nid(), z, spans[0]["origin"][0], baseline - asc, bb.width + 2, asc + desc, spans, hidden))
        last = i == n_pages - 1
        ppr = '<w:pPr><w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/>' + ("" if last else _sectpr(w, h)) + "</w:pPr>"
        p = parse_xml(f'<w:p {NS}>{ppr}{"".join(parts)}</w:p>')
        if last:
            body.insert(list(body).index(last_sect), p)
            body.remove(last_sect)
            body.append(parse_xml(_sectpr(w, h).replace("<w:sectPr>", f"<w:sectPr {NS}>", 1)))
        else:
            last_sect.addprevious(p)
        if progress:
            progress(i + 1, n_pages)
    word.core_properties.title = clean((doc.metadata or {}).get("title"))
    word.save(dst)
    doc.close()
