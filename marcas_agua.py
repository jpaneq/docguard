"""Quitar marcas de agua de un PDF («BORRADOR», «COPIA», «CONFIDENCIAL»…).

Se quitan solo las órdenes de dibujo de la marca, sin tapar nada (borrar con un recuadro, como hace
Editar con el texto, se llevaría también el contenido que queda debajo de una palabra en diagonal):

- texto en diagonal (girado entre 10° y 80°, en cualquier cuadrante): el bloque BT…ET entero;
- contenido marcado como marca de agua (/Artifact … /Watermark … BDC … EMC) o en una capa (OCG)
  cuyo nombre contiene «watermark», «marca de agua», «borrador» o «draft»;
- anotaciones de tipo Watermark.

Se revisan el contenido de cada página y los XObject de formulario que dibuja (un nivel), porque
muchas marcas de agua van dentro de uno de ellos. El texto vertical (90°) u horizontal no se toca.
"""

import math
import re

import pymupdf as fitz

OCG_WORDS = ("watermark", "marca de agua", "marca_de_agua", "borrador", "draft")
_DELIM = b"()<>[]{}/%"
_WS = b" \t\r\n\f\x00"


def _tokens(data):
    """Divide un contenido de página en (inicio, fin, tipo, valor). Tipos: op, num, name, str, other.
    Respeta cadenas (con paréntesis anidados y escapes), cadenas hex, diccionarios y comentarios."""
    i, n = 0, len(data)
    out = []
    while i < n:
        c = data[i:i + 1]
        if c in (b" ", b"\t", b"\r", b"\n", b"\f", b"\x00"):
            i += 1
        elif c == b"%":
            while i < n and data[i:i + 1] not in (b"\r", b"\n"):
                i += 1
        elif c == b"(":
            j, depth = i + 1, 1
            while j < n and depth:
                ch = data[j:j + 1]
                if ch == b"\\":
                    j += 2
                    continue
                depth += (ch == b"(") - (ch == b")")
                j += 1
            out.append((i, j, "str", data[i:j]))
            i = j
        elif data[i:i + 2] == b"<<" or data[i:i + 2] == b">>":
            out.append((i, i + 2, "other", data[i:i + 2]))
            i += 2
        elif c == b"<":
            j = data.find(b">", i)
            j = n if j < 0 else j + 1
            out.append((i, j, "str", data[i:j]))
            i = j
        elif c in (b"[", b"]", b"{", b"}"):
            out.append((i, i + 1, "other", c))
            i += 1
        elif c == b"/":
            j = i + 1
            while j < n and data[j:j + 1] not in _WS and data[j:j + 1] not in _DELIM:
                j += 1
            out.append((i, j, "name", data[i:j]))
            i = j
        else:
            j = i
            while j < n and data[j:j + 1] not in _WS and data[j:j + 1] not in _DELIM:
                j += 1
            if j == i:  # carácter suelto inesperado
                j = i + 1
            tok = data[i:j]
            kind = "num" if re.fullmatch(rb"[+-]?(\d+\.?\d*|\.\d+)", tok) else "op"
            out.append((i, j, kind, tok))
            i = j
    return out


def _mul(m, n):
    """Producto de matrices PDF [a b c d e f] (primero m, luego n)."""
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return [a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F]


def _diagonal(m):
    """¿La matriz gira el texto en diagonal (entre 10° y 80° en algún cuadrante)?"""
    a, b = m[0], m[1]
    if abs(a) < 1e-9 and abs(b) < 1e-9:
        return False
    ang = abs(math.degrees(math.atan2(b, a))) % 90
    return 10 <= ang <= 80


def _ocg_watermark_names(doc, resources_xref):
    """Nombres de propiedades (/OC /Nombre BDC) que apuntan a capas de marca de agua."""
    names = set()
    try:
        ocgs = doc.get_ocgs() or {}
    except Exception:
        ocgs = {}
    wm_xrefs = {x for x, o in ocgs.items() if any(w in (o.get("name") or "").lower() for w in OCG_WORDS)}
    if not wm_xrefs or not resources_xref:
        return names
    try:
        props = doc.xref_get_key(resources_xref, "Properties")
        if props[0] == "dict":
            for name, ref in re.findall(r"/([^\s/<>\[\]()]+)\s+(\d+)\s+0\s+R", props[1]):
                if int(ref) in wm_xrefs:
                    names.add(("/" + name).encode())
    except Exception:
        pass
    return names


def _scan(data, ocg_names=()):
    """Rangos (inicio, fin, motivo) a quitar de un contenido de página."""
    toks = _tokens(data)
    ranges = []
    ctm, stack = [1, 0, 0, 1, 0, 0], []
    operands = []
    i = 0
    while i < len(toks):
        s, e, kind, val = toks[i]
        if kind != "op":
            operands.append(toks[i])
            i += 1
            continue
        if val == b"q":
            stack.append(ctm)
        elif val == b"Q":
            ctm = stack.pop() if stack else [1, 0, 0, 1, 0, 0]
        elif val == b"cm":
            nums = [float(t[3]) for t in operands[-6:] if t[2] == "num"]
            if len(nums) == 6:
                ctm = _mul(nums, ctm)
        elif val in (b"BDC", b"BMC"):
            ops = b" ".join(t[3] for t in operands)
            is_wm = b"/Watermark" in ops or (b"/OC" in ops and any(n in ops for n in ocg_names))
            if is_wm:  # hasta el EMC que le corresponde (los BDC/BMC se anidan)
                depth, j = 1, i + 1
                while j < len(toks) and depth:
                    if toks[j][2] == "op":
                        depth += toks[j][3] in (b"BDC", b"BMC")
                        depth -= toks[j][3] == b"EMC"
                    j += 1
                start = operands[0][0] if operands else s
                ranges.append((start, toks[j - 1][1], "contenido marcado como marca de agua"))
                operands = []
                i = j
                continue
        elif val == b"BT":
            j, diag = i + 1, False
            ops2, local = [], ctm
            while j < len(toks) and not (toks[j][2] == "op" and toks[j][3] == b"ET"):
                t = toks[j]
                if t[2] == "op":
                    nums = [float(x[3]) for x in ops2[-6:] if x[2] == "num"]
                    if t[3] == b"cm" and len(nums) == 6:  # algunos programas (p. ej. PyMuPDF) giran dentro del BT
                        local = _mul(nums, local)
                    elif t[3] == b"Tm" and len(nums) == 6 and _diagonal(_mul(nums, local)):
                        diag = True
                    ops2 = []
                else:
                    ops2.append(t)
                j += 1
            if not diag and _diagonal(local):
                diag = True  # el giro viene de un «cm» (antes del BT o dentro, sin Tm)
            if diag and j < len(toks):
                ranges.append((s, toks[j][1], "texto en diagonal"))
            operands = []
            i = j + 1
            continue
        operands = []
        i += 1
    return ranges


def _cut(data, ranges):
    out, last = [], 0
    for s, e, _ in sorted(ranges):
        if s < last:
            continue
        out.append(data[last:s])
        out.append(b" ")
        last = e
    out.append(data[last:])
    return b"".join(out)


def _diagonal_texts(page):
    """Textos en diagonal de la página, para enseñar al usuario qué se va a quitar."""
    texts = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            dx, dy = line["dir"]
            if _diagonal([dx, -dy, 0, 0, 0, 0]):
                t = "".join(s["text"] for s in line["spans"]).strip()
                if t:
                    texts.append(t)
    return texts


def _targets(doc, page):
    """(xref del contenido, datos, rangos) del contenido de la página y de sus XObject de formulario."""
    res = []
    contents = page.get_contents()
    if contents:
        data = b"".join(doc.xref_stream(x) or b"" for x in contents)
        names = _ocg_watermark_names(doc, _resources_xref(doc, page.xref))
        res.append((contents, data, _scan(data, names)))
    for xref, name, *_ in page.get_xobjects():
        try:
            if doc.xref_get_key(xref, "Subtype")[1] != "/Form":
                continue
            data = doc.xref_stream(xref) or b""
        except Exception:
            continue
        names = _ocg_watermark_names(doc, _resources_xref(doc, xref))
        res.append(([xref], data, _scan(data, names)))
    return res


def _resources_xref(doc, xref):
    kind, val = doc.xref_get_key(xref, "Resources")
    if kind == "xref":
        return int(val.split()[0])
    return xref if kind == "dict" else None


def find(doc):
    """Lista de lo que se quitaría: [{"n": página, "kind": ..., "text": ...}]."""
    found = []
    for n, page in enumerate(doc):
        reasons = [r for _, _, ranges in _targets(doc, page) for *_, r in ranges]
        diag = _diagonal_texts(page)
        if "texto en diagonal" in reasons:
            for t in diag or ["(texto)"]:
                found.append({"n": n, "kind": "texto en diagonal", "text": t[:60]})
        for r in sorted(set(reasons) - {"texto en diagonal"}):
            found.append({"n": n, "kind": r, "text": ""})
        for a in page.annots() or ():
            if a.type[0] == fitz.PDF_ANNOT_WATERMARK:
                found.append({"n": n, "kind": "anotación de marca de agua", "text": (a.info.get("content") or "")[:60]})
    return found


def remove(doc):
    """Quita las marcas de agua de todas las páginas. Devuelve cuántos elementos se han quitado."""
    count = 0
    done = set()
    for page in doc:
        for xrefs, data, ranges in _targets(doc, page):
            if not ranges or xrefs[0] in done:
                continue
            done.add(xrefs[0])
            doc.update_stream(xrefs[0], _cut(data, ranges))
            for x in xrefs[1:]:  # contenido repartido en varios flujos: queda todo en el primero
                doc.update_stream(x, b"")
            count += len(ranges)
        for a in list(page.annots() or ()):
            if a.type[0] == fitz.PDF_ANNOT_WATERMARK:
                page.delete_annot(a)
                count += 1
    return count
