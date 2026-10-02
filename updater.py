"""Actualizaciones: al abrirse, DocGuard mira en GitHub si hay una versión publicada más nueva.
Si el usuario acepta, la descarga, comprueba su huella SHA-256 (publicada junto al programa),
y al cerrarse sustituye el programa por la versión nueva y la vuelve a abrir. La versión anterior
se guarda por si hubiera que volver atrás. Solo actúa en el programa compilado, no desde el código."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

import core

REPO = "jpaneq/docguard"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET = {"darwin": "DocGuard-mac.zip", "win32": "DocGuard-windows.zip"}.get(sys.platform)
STATE = {}  # versión descargada y lista para instalar al cerrar


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "DocGuard", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _ver(tag):
    return tuple(int(x) for x in tag.lstrip("vV").split(".") if x.isdigit())


def installed():
    """Ruta del programa instalado (la app .app en Mac, la carpeta en Windows), o None desde el código."""
    if not getattr(sys, "frozen", False) or not ASSET:
        return None
    exe = os.path.abspath(sys.executable)
    if sys.platform == "darwin":
        app = exe.split(".app/")[0] + ".app"
        return app if app.endswith(".app") else None
    return os.path.dirname(exe)


def check():
    """¿Hay versión nueva? Devuelve {available, version, notes} (sin internet: available False)."""
    out = {"current": core.VERSION, "available": False, "can_install": bool(installed())}
    try:
        rel = json.loads(_get(API))
    except Exception as ex:
        out["error"] = str(ex)
        return out
    tag = rel.get("tag_name", "")
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
    if ASSET in assets and _ver(tag) > _ver(core.VERSION):
        out.update(available=True, version=tag.lstrip("vV"), notes=(rel.get("body") or "")[:3000],
                   url=assets[ASSET], sha_url=assets.get(ASSET + ".sha256"))
    return out


def download(info):
    """Descarga y comprueba la versión nueva; queda lista para instalarse al cerrar DocGuard."""
    if not installed():
        raise ValueError("Las actualizaciones solo se instalan en el programa, no al ejecutarlo desde el código.")
    if not info.get("sha_url"):
        raise ValueError("La versión publicada no trae su huella SHA-256: por seguridad no se instala.")
    expected = _get(info["sha_url"]).decode().split()[0].strip().lower()
    tmp = tempfile.mkdtemp(prefix="docguard_update_")
    zpath = os.path.join(tmp, ASSET)
    h = hashlib.sha256()
    req = urllib.request.Request(info["url"], headers={"User-Agent": "DocGuard"})
    with urllib.request.urlopen(req, timeout=60) as r, open(zpath, "wb") as f:
        while chunk := r.read(1 << 20):
            h.update(chunk)
            f.write(chunk)
    if h.hexdigest() != expected:
        shutil.rmtree(tmp, ignore_errors=True)
        raise ValueError("La descarga no coincide con la huella publicada: no se instala.")
    dest = os.path.join(tmp, "nuevo")
    if sys.platform == "darwin":  # ditto conserva la firma y los permisos de la app
        subprocess.run(["ditto", "-x", "-k", zpath, dest], check=True)
        new = next(os.path.join(dest, d) for d in os.listdir(dest) if d.endswith(".app"))
    else:
        with zipfile.ZipFile(zpath) as z:
            z.extractall(dest)
        new = os.path.join(dest, "DocGuard") if os.path.isdir(os.path.join(dest, "DocGuard")) else dest
    STATE.update(new=new, version=info.get("version"))
    return {"ready": True, "version": info.get("version")}


def apply_on_exit():
    """Lanza un pequeño script que espera a que DocGuard se cierre, cambia el programa y lo abre."""
    new, old = STATE.get("new"), installed()
    if not new or not old:
        return False
    backup_dir = os.path.join(core.config_dir(), "versiones_anteriores")
    os.makedirs(backup_dir, exist_ok=True)
    backup = os.path.join(backup_dir, f"DocGuard-{core.VERSION}" + (".app" if sys.platform == "darwin" else ""))
    pid = os.getpid()
    if sys.platform == "darwin":
        script = os.path.join(tempfile.gettempdir(), "docguard_actualizar.sh")
        with open(script, "w") as f:
            f.write(f'''#!/bin/sh
while kill -0 {pid} 2>/dev/null; do sleep 0.5; done
rm -rf "{backup}"
mv "{old}" "{backup}" && mv "{new}" "{old}" || mv "{backup}" "{old}"
xattr -dr com.apple.quarantine "{old}" 2>/dev/null
open "{old}"
''')
        os.chmod(script, 0o755)
        subprocess.Popen(["/bin/sh", script], start_new_session=True)
        STATE["applied"] = True
        return True
    else:
        # El script se ejecuta desde %TEMP%: si su carpeta de trabajo fuera la del programa, Windows no
        # dejaría moverla. Reintenta unos segundos (antivirus, procesos que aún se cierran) y deja registro.
        tmp = tempfile.gettempdir()
        script = os.path.join(tmp, "docguard_actualizar.bat")
        log = os.path.join(tmp, "docguard_actualizar.log")
        exe = os.path.join(old, "DocGuard.exe")
        with open(script, "w", encoding="utf-8") as f:
            f.write(f'''@echo off
chcp 65001 >nul
cd /d "{tmp}"
echo Actualizando DocGuard > "{log}"
:espera
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul && (ping -n 2 127.0.0.1 >nul & goto espera)
ping -n 3 127.0.0.1 >nul
if exist "{backup}" rmdir /s /q "{backup}"
set n=0
:mover
move "{old}" "{backup}" >> "{log}" 2>&1 && goto nuevo
set /a n+=1
if %n% lss 15 (ping -n 3 127.0.0.1 >nul & goto mover)
echo No se pudo mover la version anterior >> "{log}"
start "" "{exe}"
exit /b 1
:nuevo
move "{new}" "{old}" >> "{log}" 2>&1 || (echo Fallo al instalar; se restaura >> "{log}" & move "{backup}" "{old}")
echo Hecho >> "{log}"
start "" "{exe}"
''')
        subprocess.Popen(["cmd", "/c", script], cwd=tmp, creationflags=0x08000000)  # sin ventana
    STATE["applied"] = True
    return True
