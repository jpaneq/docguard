"""Seguimiento de los documentos enviados a firmar. Se guarda la huella exacta de lo que
enviaste; cuando vuelve, se comprueba que esa parte sigue intacta (las firmas de otros se
añaden detrás sin tocarla), quién ha firmado después y qué recuadros faltan."""

import datetime
import hashlib
import os
import re
import secrets

import protect
import records
import signing


def _base(name):
    base = os.path.splitext(os.path.basename(name or ""))[0].lower()
    return re.sub(r"(_firmado(_\d+)?|_para_firmar)+$", "", base)


def _fields(data):
    try:
        return signing.list_signature_fields(data)
    except Exception:
        return []


def register(name, data):
    """Anota un documento enviado a firmar (los bytes exactos que se guardaron o enviaron)."""
    env = records.load("envios")
    h = hashlib.sha256(data).hexdigest()
    for key, rec in env.items():
        if h in rec.get("sha256", []):
            return key
    fields = _fields(data)
    key = f"{secrets.randbits(32):08X}"
    env[key] = {"fecha": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "archivo": os.path.basename(name),
                "base": _base(name), "sha256": [h], "recuadros": [f["name"] for f in fields],
                "firmados": [f["name"] for f in fields if f["signed"]],
                "estado": "pendiente" if any(not f["signed"] for f in fields) else "enviado"}
    records.save("envios", env)
    return key


def check(name, data, password=None):
    """¿Es un documento que enviaste? Devuelve qué ha pasado desde entonces."""
    env = records.load("envios")
    index = {h: key for key, rec in env.items() for h in rec.get("sha256", [])}
    match = None
    for end in reversed(protect._revision_ends(data)):  # la versión enviada más reciente que contiene
        key = index.get(hashlib.sha256(data[:end]).hexdigest())
        if key:
            match = (key, end)
            break
    if not match:
        base = _base(name)
        for key, rec in env.items():
            if base and rec.get("base") == base:
                return {"match": False, "mismatch": True, "key": key, "record": rec}
        return {"match": False}
    key, end = match
    try:
        sigs = signing.verify_pdf(data, password=password)
    except Exception:
        sigs = []
    fields = _fields(data)
    pending = [f["name"] for f in fields if not f["signed"]]
    after = [s for s in sigs if (s.get("covered_end") or 0) > end]
    rec = env[key]
    rec.update(ultima_comprobacion=datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
               firmados=[f["name"] for f in fields if f["signed"]],
               estado="completo" if fields and not pending else ("pendiente" if pending else rec.get("estado", "enviado")))
    records.save("envios", env)
    return {"match": True, "key": key, "record": rec, "exact": end == len(data), "pending": pending,
            "after": [{"signer": s["signer"].replace("Common Name: ", ""), "time": s["time"], "field": s["field"],
                       "ok": bool(s["intact"] and s["valid"])} for s in after],
            "all_ok": all(s["intact"] and s["valid"] for s in sigs)}


def listing():
    return [dict(key=k, **v) for k, v in reversed(list(records.load("envios").items()))]


def delete(key):
    records.delete("envios", key)
