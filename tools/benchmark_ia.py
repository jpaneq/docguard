"""Banco de pruebas: ¿cuánto resiste la protección del DNI a los eliminadores de marcas con IA?

No forma parte de la app. Se ejecuta en un entorno aparte con PyTorch:

    uv venv --python 3.12 .bench && uv pip install --python .bench -r tools/requirements-bench.txt
    .bench/bin/python tools/benchmark_ia.py [--salida carpeta] [--variantes a,b,c]

Qué hace:
  1. Genera un DNI FICTICIO (cara dibujada, fondo con trama, datos inventados).
  2. Lo protege con cada variante de DocGuard.
  3. Lo ataca:
       - LaMa (el modelo de relleno que usan muchas webs de «quitar marca de agua»)
         con la máscara PERFECTA de la marca: el mejor caso posible para el atacante.
       - Regeneración con el VAE de Stable Diffusion (imita a las IA que redibujan la imagen).
       - LaMa + regeneración.
       - Redes sociales: reducción y JPEG.
  4. Mide:
       - marca_quitada: % de la marca eliminada (100 % = no queda nada)
       - datos_ok: % de datos clave (nombre, número, fechas) que siguen legibles por OCR
         (el falsificador necesita que sea alto)
       - foto_parecido: parecido (SSIM) de la foto con la original (el falsificador lo quiere alto)
       - rastreo: si DocGuard sigue identificando a quién se entregó la copia
"""

import argparse
import io
import math
import os
import random
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import core  # noqa: E402
import idfields  # noqa: E402
import protect  # noqa: E402

FUENTE = "/System/Library/Fonts/Supplemental/Arial.ttf"
FUENTE_B = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


# --------------------------------------------------------------------------
# DNI ficticio
# --------------------------------------------------------------------------

def _font(size, bold=False):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(FUENTE_B if bold else FUENTE, size)
    except OSError:
        return core.get_font(size)


def _cara(w, h, seed=3):
    """Retrato dibujado (no es una persona real) con sombreado y textura de foto."""
    rnd = random.Random(seed)
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (int(205 - y * 0.05), int(212 - y * 0.05), int(222 - y * 0.03))
    d = ImageDraw.Draw(im)
    d.ellipse((w * 0.02, h * 0.72, w * 0.98, h * 1.4), fill=(46, 56, 78))           # hombros
    d.rectangle((w * 0.40, h * 0.55, w * 0.60, h * 0.8), fill=(214, 168, 140))       # cuello
    cx, cy, rx, ry = w * 0.5, h * 0.42, w * 0.27, h * 0.25
    for k in range(18, 0, -1):                                                      # cabeza sombreada
        t = k / 18
        col = (int(170 + 60 * (1 - t)), int(125 + 55 * (1 - t)), int(100 + 50 * (1 - t)))
        d.ellipse((cx - rx * t, cy - ry * t, cx + rx * t, cy + ry * t), fill=col)
    d.pieslice((cx - rx * 1.08, cy - ry * 1.15, cx + rx * 1.08, cy + ry * 0.55), 180, 360, fill=(58, 40, 30))  # pelo
    for sx in (-1, 1):                                                              # ojos y cejas
        ex = cx + sx * rx * 0.42
        ey = cy - ry * 0.05
        d.ellipse((ex - rx * 0.17, ey - ry * 0.07, ex + rx * 0.17, ey + ry * 0.07), fill=(245, 245, 240))
        d.ellipse((ex - rx * 0.08, ey - ry * 0.07, ex + rx * 0.08, ey + ry * 0.07), fill=(70, 90, 60))
        d.ellipse((ex - rx * 0.035, ey - ry * 0.03, ex + rx * 0.035, ey + ry * 0.03), fill=(15, 15, 15))
        d.line((ex - rx * 0.2, ey - ry * 0.2, ex + rx * 0.18, ey - ry * 0.24), fill=(60, 42, 32), width=max(2, w // 60))
    d.line((cx, cy + ry * 0.02, cx - rx * 0.07, cy + ry * 0.33, cx + rx * 0.05, cy + ry * 0.36), fill=(150, 100, 80), width=max(2, w // 90))
    d.arc((cx - rx * 0.32, cy + ry * 0.38, cx + rx * 0.32, cy + ry * 0.66), 15, 165, fill=(160, 70, 70), width=max(3, w // 50))
    im = im.filter(ImageFilter.GaussianBlur(w / 220))
    arr = np.asarray(im, dtype=np.int16) + np.random.default_rng(seed).normal(0, 6, (h, w, 1)).astype(np.int16)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def dni_ficticio(seed=7):
    """Devuelve (imagen, datos_clave, caja_foto) de un DNI inventado, parecido a uno real."""
    W, H = 1600, 1010
    rnd = random.Random(seed)
    im = Image.new("RGB", (W, H), (222, 232, 238))
    d = ImageDraw.Draw(im)
    for k in range(0, 260, 3):                                                      # trama de seguridad del fondo
        ph = rnd.uniform(0, 6.28)
        pts = [(x, k * 4.2 + 30 * math.sin(x / 90 + ph) + 12 * math.sin(x / 23)) for x in range(0, W + 8, 8)]
        d.line(pts, fill=(205, 218, 228) if k % 2 else (212, 222, 214), width=2)
    d.ellipse((1050, 250, 1450, 650), outline=(200, 212, 222), width=6)            # emblema tenue
    d.rounded_rectangle((2, 2, W - 3, H - 3), radius=48, outline=(150, 165, 180), width=4)
    d.text((60, 36), "ESPAÑA", font=_font(46, True), fill=(160, 30, 45))
    d.text((300, 44), "DOCUMENTO NACIONAL DE IDENTIDAD", font=_font(38, True), fill=(160, 30, 45))
    foto = (70, 170, 470, 690)
    im.paste(_cara(foto[2] - foto[0], foto[3] - foto[1]), foto[:2])
    d.rounded_rectangle((520, 600, 610, 670), radius=10, fill=(214, 186, 110))     # chip
    datos = {}
    y = 170
    campos = [("APELLIDOS", "GARCÍA EJEMPLO", "ap1"), ("", "MARTÍNEZ", "ap2"), ("NOMBRE", "LUCÍA", "nombre"),
              ("SEXO    NACIONALIDAD", "F         ESP", None), ("FECHA DE NACIMIENTO", "14 03 1990", "nac"),
              ("NUM SOPORT", "CAA123456", None), ("VALIDEZ", "22 07 2031", "val")]
    for lab, val, key in campos:
        if lab:
            d.text((650, y), lab, font=_font(24), fill=(90, 95, 105))
            y += 30
        d.text((650, y), val, font=_font(44, True), fill=(25, 25, 35))
        if key:
            datos[key] = val
        y += 58
    d.text((650, y + 8), "DNI 99999999R", font=_font(58, True), fill=(25, 25, 35))
    datos["dni"] = "99999999R"
    d.text((80, 720), "FIRMA / SIGNATURA", font=_font(22), fill=(90, 95, 105))
    firma = [(100 + i * 6, 820 + 38 * math.sin(i / 4) + 14 * math.sin(i / 1.3)) for i in range(60)]
    d.line(firma, fill=(25, 35, 95), width=5)
    d.text((1290, 905), "CAN 654321", font=_font(40, True), fill=(25, 25, 35))
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    return im, datos, foto


# --------------------------------------------------------------------------
# Ataques
# --------------------------------------------------------------------------

_lama = None
_vae = None


def _device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


def mascara_oraculo(protegida, limpia, excluir=()):
    """Máscara PERFECTA de la marca (donde la copia difiere del original), sin las zonas tapadas."""
    import cv2
    a = np.asarray(protegida, dtype=np.int16)
    b = np.asarray(limpia.resize(protegida.size), dtype=np.int16)
    m = (np.abs(a - b).max(axis=2) > 18).astype(np.uint8) * 255
    m = cv2.dilate(m, np.ones((3, 3), np.uint8), iterations=2)
    W, H = protegida.size
    for x0, y0, x1, y1 in excluir:
        m[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)] = 0
    return Image.fromarray(m)


def ataque_lama(img, mascara):
    global _lama
    if _lama is None:
        from simple_lama_inpainting import SimpleLama
        _lama = SimpleLama()
    return _lama(img.convert("RGB"), mascara.convert("L")).crop((0, 0) + img.size)


def ataque_regenerar(img, ancho=1024):
    """Codifica y decodifica con el VAE de Stable Diffusion (regeneración de la imagen)."""
    global _vae
    import torch
    from diffusers import AutoencoderKL
    if _vae is None:
        _vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse").to(_device()).eval()
    w, h = img.size
    nh = int(round(h * ancho / w / 8)) * 8
    x = np.asarray(img.convert("RGB").resize((ancho, nh), Image.LANCZOS), dtype=np.float32) / 127.5 - 1
    t = torch.from_numpy(x).permute(2, 0, 1)[None].to(_device())
    with torch.no_grad():
        out = _vae.decode(_vae.encode(t).latent_dist.mean).sample
    y = ((out[0].permute(1, 2, 0).clamp(-1, 1).cpu().numpy() + 1) * 127.5).astype(np.uint8)
    return Image.fromarray(y).resize((w, h), Image.LANCZOS)


def ataque_redes(img):
    small = img.resize((img.width * 6 // 10, img.height * 6 // 10), Image.LANCZOS)
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=70)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


# --------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------

def _norm(t):
    import unicodedata
    t = unicodedata.normalize("NFD", t.upper())
    return "".join(c for c in t if c.isalnum())


def datos_legibles(img, datos):
    lines = idfields.ocr_lines(img)
    texto = _norm(" ".join(t for _, t, _ in lines))
    ok = [k for k, v in datos.items() if _norm(v) in texto]
    return len(ok) / len(datos), ok


def parecido_foto(img, limpia, foto):
    from skimage.metrics import structural_similarity
    a = np.asarray(img.resize(limpia.size).crop(foto).convert("L"), dtype=np.float32)
    b = np.asarray(limpia.crop(foto).convert("L"), dtype=np.float32)
    return float(structural_similarity(a, b, data_range=255))


def marca_quitada(atacada, protegida, limpia, mascara):
    m = np.asarray(mascara) > 0
    if not m.any():
        return 1.0
    c = np.asarray(limpia.resize(protegida.size), dtype=np.float32)
    antes = np.abs(np.asarray(protegida, dtype=np.float32) - c)[m].mean()
    despues = np.abs(np.asarray(atacada.resize(protegida.size), dtype=np.float32) - c)[m].mean()
    return float(max(0.0, 1 - despues / max(antes, 1e-6)))


def rastreo(img, ref):
    """¿Sigue DocGuard identificando la copia? Prueba cada método por separado."""
    res = []
    found, _ = protect.detect_mark(img)
    if found == ref:
        res.append("invisible")
    ids = protect.identify_robust(img)
    if ids and ids[0][0] == ref and ids[0][1] >= 4.5 and (len(ids) < 2 or ids[0][1] - ids[1][1] >= 1.5):
        res.append(f"reforzado z={ids[0][1]:.0f}")
    m = protect.match_fingerprint(img)
    if m and m[0]["ref"] == ref:
        res.append(f"huella {m[0]['score']:.0%}" + (f" (2ª {m[1]['score']:.0%})" if len(m) > 1 else ""))
    if ref in protect.read_refs(img):
        res.append("REF legible")
    return " + ".join(res) or "—"


# --------------------------------------------------------------------------
# Variantes a comparar
# --------------------------------------------------------------------------

def variantes():
    base = dict(text="Solo para Inmobiliaria Sol – 30/09/2026", angle=35, size=40, gap_x=60, gap_y=80,
                opacity=0.35, color=(200, 0, 0), hardened=True, strike=True)
    antes = dict(robust=False, fingerprint=False)          # comportamiento de la v1.7
    capas = dict(robust=True, fingerprint=True, hide_label="SOLO PARA INMOBILIARIA SOL", decoy_mrz=True,
                 stamp=True, stamp_text="Solo para Inmobiliaria Sol", notice=True)
    return {
        "basica": dict(base, level="basica", strike=False, **antes),
        "reforzada": dict(base, level="reforzada", **antes),
        "maxima": dict(base, level="maxima", **antes),
        "reforzada+capas": dict(base, level="reforzada", **capas),
        "maxima+capas": dict(base, level="maxima", **capas),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default=os.path.join(RAIZ, "tools", "bench_out"))
    ap.add_argument("--variantes", default="")
    ap.add_argument("--sin-regenerar", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    limpia, datos, foto = dni_ficticio()
    limpia.save(os.path.join(args.salida, "00_limpia.png"))
    ocr_limpia, _ = datos_legibles(limpia, datos)
    print(f"DNI ficticio: datos legibles sin proteger = {ocr_limpia:.0%}")
    items = idfields.detect(limpia)["items"]
    hide_items = [{"r": r, "k": it["kind"]} for it in items for r in it["rects"]]
    lines = protect.detect_lines(limpia)
    # historial de pruebas aparte (no toca el de la app) con 60 entregas ficticias de relleno
    import shutil
    os.environ["DOCGUARD_CONFIG"] = os.path.join(args.salida, "historial_pruebas")
    shutil.rmtree(os.environ["DOCGUARD_CONFIG"], ignore_errors=True)
    for i in range(60):
        r = f"{random.Random(i).randrange(1 << 32):08X}"
        H0 = limpia.size[1]
        fp = protect.fingerprint_items(hide_items, r, lines, protect.locate_face(limpia),
                                       [[0.0, 1 - (max(14, H0 * 0.032) + H0 * 0.012) / H0 - 0.005, 1.0, 1.0]],
                                       H0 / limpia.size[0])
        protect.register_fingerprint(r, [h["r"] for h in fp], destinatario=f"relleno {i}")
    elegir = set(filter(None, args.variantes.split(",")))
    filas = []
    for nombre, kw in variantes().items():
        if elegir and nombre not in elegir:
            continue
        t0 = time.time()
        ref = f"{random.randrange(1 << 32):08X}"
        qr = {"data": protect.qr_payload("vcard", "Inmobiliaria Sol", "Alquiler", ref), "size": 22,
              "pos": "auto" if "capas" in nombre else "abajo-derecha"}
        kw = dict(kw)
        prot = protect.watermark(limpia, lines=lines, qr=qr, mark=ref, seed=1000, hide=hide_items, ref=ref, **kw)
        if kw.get("fingerprint"):
            protect.register_fingerprint(ref, protect.LAST_HIDE, destinatario=nombre)
        prot.save(os.path.join(args.salida, f"{nombre}_0_protegida.jpg"), quality=92)
        excl = protect.LAST_HIDE
        mask = mascara_oraculo(prot, limpia, excl)
        ataques = {"sin atacar": prot, "LaMa (máscara perfecta)": ataque_lama(prot, mask),
                   "redes (60 %, JPEG 70)": ataque_redes(prot)}
        if not args.sin_regenerar:
            ataques["regeneración (VAE)"] = ataque_regenerar(prot)
            ataques["LaMa + regeneración"] = ataque_regenerar(ataques["LaMa (máscara perfecta)"])
        for i, (an, img) in enumerate(ataques.items()):
            img.save(os.path.join(args.salida, f"{nombre}_{i}_{an.split()[0]}.jpg"), quality=90)
            leg, _ = datos_legibles(img, datos)
            filas.append((nombre, an, marca_quitada(img, prot, limpia, mask) if an != "sin atacar" else 0.0,
                          leg, parecido_foto(img, limpia, foto), rastreo(img, ref)))
            print(f"  {nombre:12s} {an:26s} marca_quitada={filas[-1][2]:5.0%} datos_ok={leg:5.0%} "
                  f"foto_parecido={filas[-1][4]:.2f} rastreo={filas[-1][5]}")
        print(f"  ({time.time() - t0:.0f} s)")
    with open(os.path.join(args.salida, "resultados.md"), "w", encoding="utf-8") as f:
        f.write("| Variante | Ataque | Marca quitada | Datos legibles | Parecido foto | Rastreo |\n|---|---|---|---|---|---|\n")
        for n, a, q, leg, s, r in filas:
            f.write(f"| {n} | {a} | {q:.0%} | {leg:.0%} | {s:.2f} | {r} |\n")
    print("Resultados en", os.path.join(args.salida, "resultados.md"))


if __name__ == "__main__":
    main()
