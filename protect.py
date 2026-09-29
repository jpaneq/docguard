"""Protección reforzada de documentos de identidad.

Capas (se combinan):
  - Marca principal con variaciones por letra (giro, tamaño, altura, color) y,
    en nivel máximo, una segunda capa cruzada.
  - Trama de seguridad: líneas onduladas finas por todo el documento.
  - Microtexto sobre los datos: cada línea de texto detectada por OCR queda
    atravesada por microtexto del color de la tinta. Para quitarlo hay que
    reescribir los datos, y una IA suele alterarlos al hacerlo.
  - Código QR con el uso autorizado.
  - Marca invisible de rastreo con una referencia guardada en un registro local.

Ninguna marca visible es imposible de quitar; la idea es que quitarla sea
costoso, deje huella y que el origen se pueda demostrar igualmente.
"""

import datetime
import json
import math
import os
import random
import secrets
import zlib
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

import core

LEVELS = ("basica", "reforzada", "maxima")


# --------------------------------------------------------------------------
# Detección de líneas de texto (para el microtexto)
# --------------------------------------------------------------------------

def detect_lines(img):
    """Cajas de las líneas de texto de la imagen, normalizadas a 0..1."""
    if not core.ocr_available():
        return []
    import io
    w, h = img.size
    scale = min(1.0, 1600 / max(w, h))
    small = img.resize((max(1, int(w * scale)), max(1, int(h * scale)))) if scale < 1 else img
    buf = io.BytesIO()
    small.convert("RGB").save(buf, "PNG")
    from rapidocr import RapidOCR
    if core._ocr_engine is None:
        core._ocr_engine = RapidOCR()
    res = core._ocr_engine(buf.getvalue())
    out = []
    if res.boxes is None:
        return out
    sw, sh = small.size
    for box, txt in zip(res.boxes, res.txts):
        if len(txt.strip()) < 2:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        out.append([min(xs) / sw, min(ys) / sh, max(xs) / sw, max(ys) / sh])
    return out


# --------------------------------------------------------------------------
# Capas visibles
# --------------------------------------------------------------------------

@lru_cache(maxsize=512)
def _glyph(ch, size, rgba):
    font = core.get_font(size)
    l, t, r, b = font.getbbox(ch)
    w, h = max(1, r - l + 4), max(1, b - t + 4)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 - l, 2 - t), ch, font=font, fill=rgba,
                            stroke_width=max(1, size // 30), stroke_fill=(255, 255, 255, rgba[3] // 3))
    adv = font.getlength(ch)
    return im, adv, t


def _variants(color, rnd):
    """Pequeñas variaciones del color elegido (más oscuro, más claro, desplazado)."""
    r, g, b = color
    k = rnd.uniform(0.65, 1.15)
    shift = rnd.randint(-25, 25)
    return (max(0, min(255, int(r * k) + shift)), max(0, min(255, int(g * k) - shift // 2)),
            max(0, min(255, int(b * k) + shift // 3)))


def _jitter_text_layer(size_px, text, angle, font_px, step_x, step_y, alpha, color, seed):
    """Mosaico de texto letra a letra con variaciones aleatorias. Devuelve capa RGBA."""
    W, H = size_px
    rnd = random.Random(seed)
    diag = int(math.hypot(W, H)) + 4
    layer = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    row = 0
    y = -step_y
    while y < diag + step_y:
        x = -step_x + (step_x / 2 if row % 2 else 0) + rnd.uniform(-0.1, 0.1) * step_x
        while x < diag + step_x:
            cx = x
            col = _variants(color, rnd)
            a = int(alpha * rnd.uniform(0.7, 1.0))
            wave_ph = rnd.uniform(0, math.tau)
            for i, ch in enumerate(text):
                fs = max(6, int(font_px * rnd.uniform(0.85, 1.15)))
                g, adv, top = _glyph(ch, fs, col + (a,))
                if ch.strip():
                    rot = g.rotate(rnd.uniform(-9, 9), resample=Image.BICUBIC, expand=True)
                    dy = math.sin(i / 3 + wave_ph) * font_px * 0.12 + rnd.uniform(-1, 1) * font_px * 0.05
                    layer.alpha_composite(rot, (int(cx), int(y + top + dy)))
                cx += adv * (fs / font_px) * rnd.uniform(0.95, 1.08)
            x += step_x
        y += step_y
        row += 1
    layer = layer.rotate(angle, resample=Image.BICUBIC)
    left, top = (diag - W) // 2, (diag - H) // 2
    return layer.crop((left, top, left + W, top + H))


def _guilloche(size_px, color, alpha, s, seed, dense=False):
    """Trama de líneas onduladas finas que cruzan todo el documento."""
    W, H = size_px
    rnd = random.Random(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    spacing = max(6, int((11 if dense else 16) * s))
    width = max(1, int(0.7 * s))
    for fam in range(2):
        p1, p2 = rnd.uniform(120, 260) * s, rnd.uniform(40, 90) * s
        a1, a2 = rnd.uniform(8, 20) * s, rnd.uniform(2, 6) * s
        ph = rnd.uniform(0, math.tau)
        slope = (0.25 if fam else -0.25)
        col = _variants(color, rnd) + (int(alpha),)
        step = max(2, int(4 * s))
        for y0 in range(-int(H * 0.4), int(H * 1.4), spacing):
            pts = [(x, y0 + slope * x + a1 * math.sin(x / p1 * math.tau + ph + y0 * 0.01)
                    + a2 * math.sin(x / p2 * math.tau)) for x in range(0, W + step, step)]
            d.line(pts, fill=col, width=width)
    return layer


def _composite(dst, src, x, y):
    """alpha_composite admitiendo posiciones parcialmente fuera de la imagen."""
    sx, sy = max(0, -x), max(0, -y)
    x, y = max(0, x), max(0, y)
    w = min(src.size[0] - sx, dst.size[0] - x)
    h = min(src.size[1] - sy, dst.size[1] - y)
    if w > 0 and h > 0:
        dst.alpha_composite(src.crop((sx, sy, sx + w, sy + h)), (x, y))


def _strike_lines(img, lines, text, color, s, seed):
    """Microtexto del color de la tinta atravesando cada línea de texto."""
    rnd = random.Random(seed)
    W, H = img.size
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    arr = np.asarray(img.convert("L"))
    rgb = np.asarray(img.convert("RGB"))
    micro = (text.strip() or "USO RESTRINGIDO") + " · "
    for nx0, ny0, nx1, ny1 in lines:
        x0, y0, x1, y1 = int(nx0 * W), int(ny0 * H), int(nx1 * W), int(ny1 * H)
        h = y1 - y0
        if h < 6 or x1 - x0 < 10:
            continue
        crop = arr[y0:y1, x0:x1]
        thr = np.percentile(crop, 12)
        mask = crop <= thr
        ink = rgb[y0:y1, x0:x1][mask].mean(axis=0) if mask.any() else np.array([30, 30, 30])
        ink = tuple(int(v) for v in ink)
        # altura real de la tinta (las cajas del OCR tienen margen)
        rows = np.where(mask.mean(axis=1) > 0.02)[0]
        if len(rows) >= 3:
            y0, y1 = y0 + int(rows.min()), y0 + int(rows.max())
            h = max(6, y1 - y0)
        fs = max(6, int(h * 0.36))
        font = core.get_font(fs)
        full = micro * (int((x1 - x0) / max(1, font.getlength(micro))) + 2)
        strip = Image.new("RGBA", (x1 - x0 + fs * 2, fs * 2), (0, 0, 0, 0))
        sd = ImageDraw.Draw(strip)
        sd.text((0, 0), full, font=font, fill=ink + (235,))
        bt, bb = sd.textbbox((0, 0), "Ag", font=font)[1::2]
        # ligera ondulación vertical de la tira de microtexto
        sw, sh = strip.size
        amp = fs * 0.5
        wavy = Image.new("RGBA", (sw, sh + int(amp) + 1), (0, 0, 0, 0))
        ph = rnd.uniform(0, math.tau)
        for cx in range(0, sw, 3):
            dy = int((math.sin(cx / (h * 1.7) + ph) + 1) * amp / 2)
            wavy.alpha_composite(strip.crop((cx, 0, min(sw, cx + 3), sh)), (cx, dy))
        text_mid = (bt + bb) / 2 + amp / 2          # centro del microtexto dentro de la tira
        off = text_mid - wavy.size[1] / 2
        w0 = wavy.size[0]
        wavy = wavy.rotate(rnd.uniform(-2.5, 2.5), resample=Image.BICUBIC, expand=True)
        target = y0 + h * rnd.uniform(0.45, 0.58)    # atraviesa el cuerpo de las letras
        px = x0 - fs - (wavy.size[0] - w0) // 2
        py = int(target - wavy.size[1] / 2 - off)
        _composite(layer, wavy, px, py)
        # fino trazo de color de la marca cruzando la línea
        d = ImageDraw.Draw(layer)
        yy = y0 + h * rnd.uniform(0.62, 0.78)
        pts = [(x, yy + math.sin(x / (h * 0.9) + ph) * h * 0.08) for x in range(x0 - fs, x1 + fs, 3)]
        d.line(pts, fill=tuple(color) + (170,), width=max(1, int(0.8 * s)))
    return layer


# --------------------------------------------------------------------------
# Código QR
# --------------------------------------------------------------------------

QR_POSITIONS = {"abajo-derecha", "abajo-izquierda", "arriba-derecha", "arriba-izquierda", "centro"}


def qr_text(recipient, purpose, ref, date=None):
    date = date or datetime.date.today().strftime("%d/%m/%Y")
    lines = ["USO RESTRINGIDO"]
    if recipient:
        lines.append(f"Para: {recipient}")
    if purpose:
        lines.append(f"Fin: {purpose}")
    lines.append(f"Fecha: {date}")
    if ref:
        lines.append(f"Ref: {ref}")
    lines.append("Otro uso NO autorizado")
    return "\n".join(lines)


def qr_payload(mode, recipient, purpose, ref, base_url="", date=None):
    """Contenido del QR.
    - 'vcard': ficha de contacto; el móvil la muestra como tarjeta, sin internet.
    - 'web': enlace a la página de verificación con los datos en el propio enlace (#).
    - 'texto': texto plano (algunos móviles lo buscan en Google)."""
    import base64
    date = date or datetime.date.today().strftime("%d/%m/%Y")
    if mode == "web" and base_url:
        data = json.dumps({"p": recipient, "f": purpose, "d": date, "r": ref}, ensure_ascii=False, separators=(",", ":"))
        return base_url.split("#")[0] + "#" + base64.urlsafe_b64encode(data.encode()).decode().rstrip("=")
    if mode == "vcard":
        e = lambda t: (t or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", " ")
        note = (f"Copia de documento de identidad de USO RESTRINGIDO. Autorizado a: {recipient or '-'}. "
                f"Finalidad: {purpose or '-'}. Fecha: {date}. Ref.: {ref}. Cualquier otro uso NO está autorizado.")
        return "\n".join(["BEGIN:VCARD", "VERSION:3.0", "N:;USO RESTRINGIDO;;;",
                          f"FN:USO RESTRINGIDO – {e(recipient) or 'copia autorizada'}",
                          f"ORG:{e(recipient)}", f"TITLE:{e('Finalidad: ' + (purpose or '-'))}",
                          f"NOTE:{e(note)}", "END:VCARD"])
    return qr_text(recipient, purpose, ref, date)


def _qr_image(data, px):
    import qrcode
    from qrcode.constants import ERROR_CORRECT_Q
    q = qrcode.QRCode(error_correction=ERROR_CORRECT_Q, border=3, box_size=1)
    q.add_data(data)
    q.make(fit=True)
    im = q.make_image(fill_color=(0, 0, 0), back_color=(255, 255, 255)).convert("RGB")
    k = max(2, px // im.size[0])  # módulos de tamaño entero: más fácil de leer
    return im.resize((im.size[0] * k, im.size[1] * k), Image.NEAREST)


def _place_qr(img, data, size_pct=22, pos="abajo-derecha"):
    W, H = img.size
    qr = _qr_image(data, max(90, int(min(W, H) * size_pct / 100)))
    px = qr.size[0]
    cap_h = max(12, px // 11)
    card = Image.new("RGBA", (px + 12, px + cap_h + 16), (255, 255, 255, 235))
    card.paste(qr, (6, 6))
    font = core.get_font(int(cap_h * 0.8))
    d = ImageDraw.Draw(card)
    cap = "Escanear: uso autorizado"
    tw = d.textlength(cap, font=font)
    d.text(((card.width - tw) / 2, px + 8), cap, font=font, fill=(40, 40, 40, 255))
    m = int(min(W, H) * 0.03)
    x = {"abajo-derecha": W - card.width - m, "arriba-derecha": W - card.width - m,
         "abajo-izquierda": m, "arriba-izquierda": m, "centro": (W - card.width) // 2}[pos]
    y = {"abajo-derecha": H - card.height - m, "abajo-izquierda": H - card.height - m,
         "arriba-derecha": m, "arriba-izquierda": m, "centro": (H - card.height) // 2}[pos]
    out = img.convert("RGBA")
    out.alpha_composite(card, (max(0, x), max(0, y)))
    return out.convert("RGB")


# --------------------------------------------------------------------------
# Marca invisible (rastreo)
# --------------------------------------------------------------------------

CANON_W = 1024
BITS = 40            # 32 bits de referencia + 8 de comprobación
_KEY = 0xD0C6A2D
_C1, _C2 = (2, 3), (3, 2)  # coeficientes DCT de frecuencia media


def _dct_matrix(n=8):
    m = np.zeros((n, n))
    for k in range(n):
        for i in range(n):
            m[k, i] = (math.sqrt(1 / n) if k == 0 else math.sqrt(2 / n)) * math.cos(math.pi * (2 * i + 1) * k / (2 * n))
    return m


_D = _dct_matrix()


def _blocks(y):
    h, w = y.shape
    return y[: h - h % 8, : w - w % 8].reshape(h // 8, 8, w // 8, 8).transpose(0, 2, 1, 3)


def _bit_map(nblocks):
    rnd = np.random.default_rng(_KEY)
    return rnd.integers(0, BITS, nblocks)


def _payload(ref_int):
    bits = [(ref_int >> (31 - i)) & 1 for i in range(32)]
    crc = zlib.crc32(ref_int.to_bytes(4, "big")) & 0xFF
    return bits + [(crc >> (7 - i)) & 1 for i in range(8)]


def _canon(img):
    w, h = img.size
    ch = max(8, round(h * CANON_W / w))
    return img.convert("RGB").resize((CANON_W, ch), Image.LANCZOS)


def embed_mark(img, ref_hex, strength=14.0):
    """Oculta la referencia (8 cifras hex) en la luminancia de la imagen."""
    bits = np.array(_payload(int(ref_hex, 16)))
    small = _canon(img)
    y = np.asarray(small.convert("YCbCr"), dtype=np.float64)[..., 0]
    b = _blocks(y.copy())
    coef = np.einsum("ij,abjk,lk->abil", _D, b, _D)
    nb = coef.shape[0] * coef.shape[1]
    want = bits[_bit_map(nb)].reshape(coef.shape[:2]) * 2 - 1   # +1 / -1
    c1 = coef[:, :, _C1[0], _C1[1]]
    c2 = coef[:, :, _C2[0], _C2[1]]
    diff = c1 - c2
    target = np.where(want * diff >= strength, diff, want * strength)
    adj = (target - diff) / 2
    coef[:, :, _C1[0], _C1[1]] += adj
    coef[:, :, _C2[0], _C2[1]] -= adj
    new = np.einsum("ji,abjk,kl->abil", _D, coef, _D)
    delta = np.zeros_like(y)
    hh, ww = new.shape[0] * 8, new.shape[1] * 8
    delta[:hh, :ww] = new.transpose(0, 2, 1, 3).reshape(hh, ww) - y[:hh, :ww]
    d_img = Image.fromarray(delta.astype(np.float32), mode="F").resize(img.size, Image.BICUBIC)
    arr = np.asarray(img.convert("RGB"), dtype=np.float64) + np.asarray(d_img)[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def detect_mark(img):
    """Busca una marca invisible. Devuelve (referencia_hex o None, confianza 0..1)."""
    y = np.asarray(_canon(img).convert("YCbCr"), dtype=np.float64)[..., 0]
    b = _blocks(y)
    coef = np.einsum("ij,abjk,lk->abil", _D, b, _D)
    diff = (coef[:, :, _C1[0], _C1[1]] - coef[:, :, _C2[0], _C2[1]]).ravel()
    idx = _bit_map(diff.size)
    votes = np.zeros(BITS)
    agree = np.zeros(BITS)
    for i in range(BITS):
        v = diff[idx == i]
        votes[i] = np.sum(np.sign(v))
        agree[i] = abs(votes[i]) / max(1, len(v))
    bits = (votes > 0).astype(int)
    ref = int("".join(map(str, bits[:32])), 2)
    crc = int("".join(map(str, bits[32:])), 2)
    conf = float(np.mean(agree))
    if (zlib.crc32(ref.to_bytes(4, "big")) & 0xFF) != crc:
        return None, conf
    return f"{ref:08X}", conf


# --------------------------------------------------------------------------
# Registro local de documentos marcados
# --------------------------------------------------------------------------

def _registry_path():
    return os.path.join(core.config_dir(), "registro_marcas.json")


def _load_registry():
    try:
        with open(_registry_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def register(recipient, purpose, text, filename):
    reg = _load_registry()
    while True:
        ref = f"{secrets.randbits(32):08X}"
        if ref not in reg:
            break
    reg[ref] = {"fecha": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "destinatario": recipient,
                "finalidad": purpose, "texto": text, "archivo": filename}
    with open(_registry_path(), "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
    return ref


def lookup(ref):
    return _load_registry().get(ref)


# --------------------------------------------------------------------------
# Orquestación
# --------------------------------------------------------------------------

def watermark(img, text, angle=35, size=40, gap_x=60, gap_y=80, opacity=0.35, color=(200, 0, 0),
              hardened=True, level="reforzada", strike=True, lines=None, qr=None, mark=None, seed=1, hide=None, **_):
    """Aplica todas las capas activadas. `qr` = {"data", "size", "pos"}; `mark` = referencia hex;
    `hide` = zonas a tapar en negro (0..1) antes de todo lo demás."""
    text = core.expand_placeholders(text or "")
    img = img.convert("RGB")
    if hide:
        img = img.copy()
        W0, H0 = img.size
        dr = ImageDraw.Draw(img)
        for x0, y0, x1, y1 in hide:
            dr.rectangle((x0 * W0, y0 * H0, x1 * W0, y1 * H0), fill=(0, 0, 0))
        if lines:
            inside = lambda l: any(h[0] <= (l[0] + l[2]) / 2 <= h[2] and h[1] <= (l[1] + l[3]) / 2 <= h[3] for h in hide)
            lines = [l for l in lines if not inside(l)]
    if level == "basica":
        out = core.apply_watermark(img, text, angle, size, gap_x, gap_y, opacity, color, hardened, seed)
    else:
        W, H = img.size
        s = W / 1000.0
        out = img.convert("RGBA")
        alpha = 255 * opacity
        out.alpha_composite(_guilloche((W, H), color, alpha * 0.45, s, seed, dense=level == "maxima"))
        font_px = size * s
        f = core.get_font(font_px)
        tw = f.getlength(text or " ")
        th = font_px
        out.alpha_composite(_jitter_text_layer((W, H), text or " ", angle, font_px,
                                               tw + max(1, gap_x * s), th + max(1, gap_y * s), alpha, color, seed))
        if level == "maxima":
            out.alpha_composite(_jitter_text_layer((W, H), text or " ", angle - 70, font_px * 0.6,
                                                   tw * 0.6 + gap_x * s * 0.7, th * 0.6 + gap_y * s * 0.9,
                                                   alpha * 0.6, color, seed + 7))
        out = out.convert("RGB")
    if strike and level != "basica":
        if lines is None:
            lines = detect_lines(img)
        if lines:
            base = out.convert("RGBA")
            base.alpha_composite(_strike_lines(img, lines, text, color, img.size[0] / 1000.0, seed))
            out = base.convert("RGB")
    if qr and qr.get("data"):
        out = _place_qr(out, qr["data"], qr.get("size", 22), qr.get("pos", "abajo-derecha"))
    if level != "basica":
        noise = Image.effect_noise(out.size, 18).convert("RGB")
        out = Image.blend(out, noise, 0.03)
    if mark:
        out = embed_mark(out, mark)
    return out
