"""Historiales de DocGuard: copias entregadas (con su referencia, huellas y firma) y documentos
enviados a firmar. Son la prueba de a quién se entregó cada copia, así que se guardan de forma
segura (nunca quedan a medio escribir), se pueden exportar e importar y, si se elige una
carpeta (iCloud Drive, Google Drive, un USB…), se copian allí automáticamente."""

import datetime
import json
import os
import tempfile

import core

FILES = {"entregas": "registro_marcas.json", "envios": "envios_firma.json"}
SETTINGS = "ajustes.json"
KEEP_DAILY = 30


def _path(name):
    return os.path.join(core.config_dir(), name)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path, data):
    """Escribe en un temporal y lo renombra: un corte a mitad nunca deja el archivo roto."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def load(kind):
    return _read(_path(FILES[kind]))


def save(kind, data):
    _write(_path(FILES[kind]), data)
    backup()


def settings():
    return _read(_path(SETTINGS))


def save_settings(**changes):
    data = settings()
    data.update(changes)
    _write(_path(SETTINGS), data)
    return data


def export_data():
    return {"docguard": 1, "exportado": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "entregas": load("entregas"), "envios": load("envios")}


def backup():
    """Copia los historiales en la carpeta elegida: el último estado y uno por día (30 días)."""
    folder = settings().get("copia_historial")
    if not folder:
        return None
    try:
        if not os.path.isdir(folder):
            raise OSError(f"no existe la carpeta {folder}")
        data = export_data()
        _write(os.path.join(folder, "DocGuard_historial.json"), data)
        _write(os.path.join(folder, f"DocGuard_historial_{datetime.date.today():%Y-%m-%d}.json"), data)
        daily = sorted(f for f in os.listdir(folder) if f.startswith("DocGuard_historial_") and f.endswith(".json"))
        for old in daily[:-KEEP_DAILY]:
            os.remove(os.path.join(folder, old))
        save_settings(ultima_copia=datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), error_copia="")
        return True
    except OSError as ex:  # la copia nunca impide guardar el historial
        save_settings(error_copia=str(ex))
        return False


def set_backup_folder(folder):
    folder = (folder or "").strip()
    if folder and not os.path.isdir(folder):
        raise ValueError("Esa carpeta no existe.")
    save_settings(copia_historial=folder, ultima_copia="", error_copia="")
    return backup() if folder else None


def _merge(cur, rec):
    """Une dos registros de la misma referencia sin perder nada."""
    for k, v in rec.items():
        if k == "sha256" and isinstance(v, list):
            cur["sha256"] = list(dict.fromkeys(cur.get("sha256", []) + v))
        elif k == "huella" and isinstance(v, dict):
            for page, boxes in v.items():
                cur.setdefault("huella", {}).setdefault(page, boxes)
        elif k not in cur:
            cur[k] = v


def import_data(data):
    """Importa un historial exportado (o un registro antiguo): añade lo que falta y une lo común."""
    if not isinstance(data, dict):
        raise ValueError("El archivo no es un historial de DocGuard.")
    parts = {k: data.get(k) or {} for k in FILES} if ("entregas" in data or "envios" in data) else {"entregas": data}
    added = merged = 0
    for kind, incoming in parts.items():
        if not isinstance(incoming, dict):
            continue
        cur = load(kind)
        for key, rec in incoming.items():
            if not isinstance(rec, dict):
                continue
            if key in cur:
                _merge(cur[key], rec)
                merged += 1
            else:
                cur[key] = rec
                added += 1
        _write(_path(FILES[kind]), cur)
    backup()
    return {"added": added, "merged": merged}


def delete(kind, key):
    data = load(kind)
    if data.pop(key, None) is not None:
        save(kind, data)
