"""Detección de datos de DNI y pasaporte que no suele hacer falta compartir.

Propone ocultar:
  DNI anverso: firma, número de soporte (IDESP) y CAN.
  DNI reverso: zona MRZ, equipo de expedición, progenitores, domicilio y lugar de nacimiento.
  Pasaporte:   firma, MRZ, número personal, lugar de nacimiento y datos de expedición.

Todo se basa en OCR + etiquetas impresas + patrones, así que son propuestas:
el usuario revisa, quita o añade recuadros antes de guardar.
"""

import io
import re
import unicodedata

import core

KIND_LABELS = {
    "mrz": "Zona MRZ (líneas con <<)",
    "firma": "Firma manuscrita",
    "soporte": "Número de soporte (IDESP)",
    "can": "CAN (código de 6 cifras)",
    "equipo": "Equipo de expedición",
    "progenitores": "Nombres de los progenitores",
    "domicilio": "Domicilio",
    "lugar_nac": "Lugar de nacimiento",
    "personal": "Número personal adicional",
    "autoridad": "Autoridad / datos de expedición",
}

# (tipo, patrones de la etiqueta, líneas de valor como máximo)
LABELS = [
    ("lugar_nac", ["LUGAR DE NACIMIENTO", "PLACE OF BIRTH", "LIEU DE NAISSANCE"], 2),
    ("progenitores", ["HIJO/A DE", "HIJO/ADE", "HIJOA DE", "HIJO DE", "HIJA DE"], 2),
    ("domicilio", ["DOMICILIO", "ADDRESS"], 3),
    ("equipo", ["EQUIPO"], 1),
    ("autoridad", ["AUTORIDAD", "AUTHORITY", "EXPEDIDO POR", "LUGAR DE EXPEDICION"], 1),
    ("personal", ["N PERSONAL", "NO PERSONAL", "PERSONAL NO", "N. PERSONAL", "NUM PERSONAL"], 1),
    ("soporte", ["NUM SOPORT", "NUM. SOPORT", "SOPORTE", "IDESP"], 1),
]
SIGN_LABELS = ["FIRMA", "SIGNATURE", "SIGNATURA"]
# Otras etiquetas habituales: cortan la búsqueda de valores
OTHER_LABELS = ["APELLIDOS", "SURNAME", "NOMBRE", "GIVEN NAME", "SEXO", "SEX", "NACIONALIDAD", "NATIONALITY",
                "FECHA", "DATE", "VALIDEZ", "VALIDO", "EXPIRY", "DNI", "DOCUMENTO", "PASAPORTE", "PASSPORT", "TIPO",
                "CODIGO", "CODE", "CAN"]


def norm(t):
    t = unicodedata.normalize("NFD", t.upper())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("º", "").replace("°", "").replace("Nº", "N")
    return re.sub(r"\s+", " ", t).strip()


def _union(rects):
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[2] for r in rects)
    y1 = max(r[3] for r in rects)
    return [x0, y0, x1, y1]


def _sub_rect(rect, text, a, b):
    """Parte de la caja de una palabra que ocupan los caracteres a..b (proporcional)."""
    n = max(1, len(text))
    w = rect[2] - rect[0]
    return [rect[0] + w * a / n, rect[1], rect[0] + w * b / n, rect[3]]


def ocr_lines(img):
    """[(rect px, texto, [(rect px, palabra)])] de la imagen."""
    if not core.ocr_available():
        return []
    from rapidocr import RapidOCR
    if core._ocr_engine is None:
        core._ocr_engine = RapidOCR()
    w, h = img.size
    best = []
    for side in (2000, 1500, 2600):
        k = min(1.0, side / max(w, h)) if max(w, h) > side else side / max(w, h)
        small = img.convert("RGB").resize((max(1, int(w * k)), max(1, int(h * k))))
        buf = io.BytesIO()
        small.save(buf, "PNG")
        res = core._ocr_engine(buf.getvalue(), return_word_box=True)
        lines = []
        wr = res.word_results or ()
        for i, (box, txt) in enumerate(zip(res.boxes if res.boxes is not None else [], res.txts or [])):
            xs, ys = [p[0] / k for p in box], [p[1] / k for p in box]
            words = []
            if i < len(wr):
                for item in wr[i]:
                    if isinstance(item, (tuple, list)) and len(item) == 3 and item[2] is not None:
                        bx, by = [p[0] / k for p in item[2]], [p[1] / k for p in item[2]]
                        words.append(([min(bx), min(by), max(bx), max(by)], item[0]))
            lines.append(([min(xs), min(ys), max(xs), max(ys)], txt, words))
        if sum(len(l[1]) for l in lines) > sum(len(l[1]) for l in best):
            best = lines
        if len(best) >= 4:
            break
    return best


def _is_mrz(text):
    t = text.replace(" ", "").upper().replace("«", "<")
    if len(t) < 20:
        return False
    return t.count("<") >= 3 or (re.fullmatch(r"[A-Z0-9<]{25,}", t) is not None and t.count("<") >= 1)


def _label_kind(ntext):
    for kind, pats, _ in LABELS:
        for p in pats:
            if p in ntext:
                return kind, p
    return None, None


def _is_any_label(ntext):
    if _label_kind(ntext)[0]:
        return True
    if any(s in ntext for s in SIGN_LABELS):
        return True
    words = ntext.split()
    return bool(words) and any(ntext.startswith(o) for o in OTHER_LABELS) and len(ntext) < 40


def detect(img):
    """Devuelve {"doc": 'dni'|'pasaporte'|'desconocido', "items": [{kind, label, text, rects (0..1)}]}."""
    W, H = img.size
    lines = ocr_lines(img)
    texts = [norm(t) for _, t, _ in lines]
    joined = " ".join(texts)
    mrz_idx = [i for i, (_, t, _) in enumerate(lines) if _is_mrz(t)]
    is_pass = "PASAPORTE" in joined or "PASSPORT" in joined or any(
        lines[i][1].replace(" ", "").upper().startswith("P<") for i in mrz_idx)
    doc = "pasaporte" if is_pass else ("dni" if ("DNI" in joined or "DOCUMENTO NACIONAL" in joined or "IDESP" in joined
                                                  or mrz_idx) else "desconocido")
    items = []

    def add(kind, rects, text=""):
        pad = []
        for r in rects:
            hh = r[3] - r[1]
            p = max(2, hh * 0.25)
            pad.append([float(max(0, r[0] - p) / W), float(max(0, r[1] - p) / H),
                        float(min(W, r[2] + p) / W), float(min(H, r[3] + p) / H)])
        items.append({"kind": kind, "label": KIND_LABELS[kind], "text": text, "rects": pad})

    # 1. Zona MRZ (todas sus líneas juntas)
    if mrz_idx:
        add("mrz", [_union([lines[i][0] for i in mrz_idx])], " / ".join(lines[i][1] for i in mrz_idx))
    used = set(mrz_idx)

    # 2. Etiqueta + valor
    for i, (rect, text, words) in enumerate(lines):
        if i in used:
            continue
        nt = texts[i]
        kind, pat = _label_kind(nt)
        if not kind or (kind == "soporte" and doc == "pasaporte"):
            continue
        maxl = next(m for k, _, m in LABELS if k == kind)
        value_rects, value_text = [], []
        # valor en la misma línea, detrás de la etiqueta
        rest = nt.split(pat, 1)[1] if pat in nt else ""
        rest = re.sub(r"^[\s/:.\-]*([A-Z' ]*(BIRTH|AUTHORITY|NO\.?|ADDRESS)\b)?[\s/:.\-]*", "", rest)
        if len(re.sub(r"[^A-Z0-9]", "", rest)) >= 3 and words:
            n_label = len(pat.split())
            vw = [w for w in words if norm(w[1]) and norm(w[1]) not in pat and not pat.startswith(norm(w[1]))]
            vw = [w for w in words[n_label:]] if len(words) > n_label else vw
            if vw:
                value_rects.append(_union([w[0] for w in vw]))
                value_text.append(" ".join(w[1] for w in vw))
        # valor en las líneas de debajo
        if not value_rects:
            prev = rect
            for j in sorted(range(len(lines)), key=lambda j: lines[j][0][1]):
                if len(value_rects) >= maxl or j == i or j in used:
                    continue
                r2, t2, _ = lines[j]
                if r2[1] < prev[1] + (prev[3] - prev[1]) * 0.5:
                    continue
                gap = r2[1] - prev[3]
                hh = max(r2[3] - r2[1], prev[3] - prev[1])
                if gap > hh * (1.6 if prev is rect else 1.2):
                    break
                if r2[2] < rect[0] - W * 0.03 or r2[0] > rect[0] + W * 0.45:
                    continue
                if _is_any_label(texts[j]) or _is_mrz(t2):
                    break
                value_rects.append(r2)
                value_text.append(t2)
                used.add(j)
                prev = r2
        if value_rects:
            add(kind, value_rects, " ".join(value_text))
            used.add(i)

    # 3. CAN (6 cifras) y número de soporte por patrón
    for i, (rect, text, words) in enumerate(lines):
        if i in mrz_idx:
            continue
        line_alone = re.fullmatch(r"\d{6}", texts[i].replace(" ", "")) is not None
        for wrect, w in words or [(rect, text)]:
            t = norm(w).replace(" ", "")
            if re.fullmatch(r"\d{6}", t) and (re.search(r"\bCAN\b", texts[i]) or line_alone):
                if not any(it["kind"] == "can" for it in items):
                    add("can", [wrect], w)
            if doc != "pasaporte" and re.fullmatch(r"[A-Z]{3}\d{6}", t):
                if not any(it["kind"] == "soporte" and it["text"] == w for it in items):
                    add("soporte", [wrect], w)

    # 3b. Pasaporte: número personal (= número de DNI) aunque el OCR lo pegue a otro texto
    if doc == "pasaporte" and not any(it["kind"] == "personal" for it in items):
        for i, (rect, text, words) in enumerate(lines):
            if i in mrz_idx:
                continue
            for wrect, w in words or [(rect, text)]:
                m = re.search(r"[XYZ]?\d{7,8}[A-Z]", w.upper())
                if m:
                    cw = (wrect[2] - wrect[0]) / max(1, len(w))
                    sr = _sub_rect(wrect, w, m.start(), m.end())
                    add("personal", [[sr[0] - cw * 1.2, sr[1], sr[2] + cw * 0.5, sr[3]]], m.group())
                    break

    # 4. Firma: zona junto a la etiqueta «FIRMA»
    for i, (rect, text, _) in enumerate(lines):
        nt = texts[i]
        if any(s in nt for s in SIGN_LABELS) and not _label_kind(nt)[0]:
            lh = rect[3] - rect[1]
            if rect[3] + H * 0.18 <= H:
                zone = [max(0, rect[0] - W * 0.01), rect[1], min(W, rect[0] + W * 0.34), min(H, rect[3] + H * 0.2)]
            else:
                zone = [rect[2], max(0, rect[1] - H * 0.1), min(W, rect[2] + W * 0.3), min(H, rect[3] + H * 0.1)]
            # no tapar otros datos: la zona se recorta antes del primer texto que invada su franja
            for j, (r2, t2, _) in enumerate(lines):
                if j == i or j in mrz_idx or len(texts[j].replace(" ", "")) < 3:
                    continue
                if r2[1] < zone[3] and r2[3] > zone[1] and r2[2] > zone[0] and r2[0] < zone[2]:
                    if r2[0] > zone[0] + W * 0.05:
                        zone[2] = min(zone[2], r2[0] - W * 0.005)
                    elif r2[1] > rect[3]:
                        zone[3] = min(zone[3], r2[1] - 2)
            items.append({"kind": "firma", "label": KIND_LABELS["firma"], "text": "",
                          "rects": [[float(zone[0] / W), float(zone[1] / H), float(zone[2] / W), float(zone[3] / H)]]})
            break
    return {"doc": doc, "items": items}
