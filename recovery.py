"""Copias de recuperación (autoguardado). NO son un guardado: el archivo del usuario no se toca.
Mientras hay cambios sin guardar, cada cierto tiempo se deja una copia del documento en la carpeta
de configuración; si DocGuard se cae, al abrirse ofrece recuperarlas. Se borran al guardar el PDF,
al cerrar el documento o al descartarlas (y a los 14 días)."""

import json
import os
import time

import core

MAX_AGE = 14 * 86400
DEFAULTS = {"enabled": True, "seconds": 30}


def _dir():
    d = os.path.join(core.config_dir(), "recuperacion")
    os.makedirs(d, exist_ok=True)
    return d


def settings():
    try:
        with open(os.path.join(core.config_dir(), "autosave.json"), encoding="utf-8") as f:
            s = {**DEFAULTS, **json.load(f)}
    except (OSError, ValueError):
        s = dict(DEFAULTS)
    s["seconds"] = min(600, max(10, int(s["seconds"])))
    s["enabled"] = bool(s["enabled"])
    return s


def set_settings(enabled, seconds):
    s = {"enabled": bool(enabled), "seconds": min(600, max(10, int(seconds)))}
    with open(os.path.join(core.config_dir(), "autosave.json"), "w", encoding="utf-8") as f:
        json.dump(s, f)
    return s


def write(did, name, data, pages):
    """Deja (o actualiza) la copia de recuperación de un documento."""
    base = os.path.join(_dir(), did)
    tmp = base + ".pdf.tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, base + ".pdf")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump({"id": did, "name": name, "saved": time.time(), "pages": pages, "size": len(data)}, f)


def remove(did):
    for ext in (".pdf", ".json", ".pdf.tmp"):
        try:
            os.remove(os.path.join(_dir(), did + ext))
        except OSError:
            pass


def read(did):
    with open(os.path.join(_dir(), did + ".pdf"), "rb") as f:
        return f.read()


def entries(skip=()):
    """Copias guardadas (las más recientes primero). Se ignoran las de documentos abiertos ahora."""
    out = []
    for fn in os.listdir(_dir()):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(_dir(), fn), encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, ValueError):
            continue
        if time.time() - m.get("saved", 0) > MAX_AGE or not os.path.exists(os.path.join(_dir(), m["id"] + ".pdf")):
            remove(m.get("id", fn[:-5]))
            continue
        if m["id"] not in skip:
            out.append(m)
    return sorted(out, key=lambda m: -m["saved"])


def clear_all(skip=()):
    for m in entries(skip):
        remove(m["id"])
