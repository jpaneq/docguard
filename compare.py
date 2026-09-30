"""Comparar dos versiones de un PDF: qué texto se ha quitado, añadido o cambiado."""

import difflib

import pymupdf as fitz

import core
import editor


def _words(doc):
    """Palabras de todo el documento en orden de lectura: [(página, Rect pantalla, palabra)]."""
    out = []
    for n, page in enumerate(doc):
        words = core.native_words(page)
        for r, w in words:
            out.append((n, editor.to_view(page, r), w))
    return out


def compare(doc_a, doc_b):
    """Devuelve los cambios y los recuadros a marcar en cada documento."""
    wa, wb = _words(doc_a), _words(doc_b)
    ta = [w for _, _, w in wa]
    tb = [w for _, _, w in wb]
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    marks_a, marks_b, changes = {}, {}, []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        for n, r, _ in wa[i1:i2]:
            marks_a.setdefault(n, []).append({"r": r, "t": tag})
        for n, r, _ in wb[j1:j2]:
            marks_b.setdefault(n, []).append({"r": r, "t": tag})
        changes.append({
            "type": {"replace": "cambiado", "delete": "quitado", "insert": "añadido"}[tag],
            "old": " ".join(ta[i1:i2])[:300], "new": " ".join(tb[j1:j2])[:300],
            "page_a": wa[i1][0] if i1 < len(wa) else (wa[-1][0] if wa else 0),
            "page_b": wb[j1][0] if j1 < len(wb) else (wb[-1][0] if wb else 0),
        })
    no_text = not wa or not wb
    return {"changes": changes, "marks_a": marks_a, "marks_b": marks_b,
            "similarity": round(sm.ratio() * 100, 1), "no_text": no_text,
            "pages": [len(doc_a), len(doc_b)]}
