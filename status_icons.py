"""Iconos de estado de los PDF: rojo normal, o con insignias si están firmados, con contraseña,
censurados o protegidos (copia con marca de agua). El estado se lee del propio PDF, así que vale
en cualquier equipo:
  - firmado: lleva una firma digital (/ByteRange);
  - contraseña: está cifrado (/Encrypt);
  - censurado / protegido: DocGuard lo anota al guardarlo (/DocGuardCensurado, /DocGuardProtegido),
    sin tocar nada visible.

Genera las imágenes (python status_icons.py) y aplica el icono a cada archivo en Mac; en Windows
lo hace el pequeño componente de miniaturas (winthumbs/), que usa las mismas imágenes."""

import os
import re
import subprocess
import sys

import core

FLAGS = ("firmado", "contrasena", "censurado", "protegido")
TAGS = {"firmado": ("Firmado", 2), "contrasena": ("Con contraseña", 4), "censurado": ("Censurado", 1),
        "protegido": ("Protegido", 6)}  # colores de etiqueta del Finder: 1 gris, 2 verde, 4 azul, 6 rojo
MARKS = {"censurado": b"/DocGuardCensurado", "protegido": b"/DocGuardProtegido"}


def status(data):
    """Estados de un PDF a partir de sus bytes."""
    found = []
    if b"/ByteRange" in data and re.search(rb"/Type\s*/Sig\b", data):
        found.append("firmado")
    if b"/Encrypt" in data[-200000:] or b"/Encrypt" in data[:4096]:
        found.append("contrasena")
    for k in ("censurado", "protegido"):
        if MARKS[k] in data:
            found.append(k)
    return found


def icon_name(flags):
    return "pdf" + "".join("_" + f for f in FLAGS if f in flags)


def icon_path(flags):
    return core.resource_path(os.path.join("iconos_estado", icon_name(flags) + ".png"))


def mark_pdf(data, kind):
    """Anota en el PDF que DocGuard lo ha censurado o protegido (clave invisible en su información)."""
    import pymupdf as fitz
    with fitz.open("pdf", data) as doc:
        if doc.needs_pass:
            return data
        kind_, val = doc.xref_get_key(-1, "Info")
        if kind_ != "xref":
            doc.set_metadata({"producer": doc.metadata.get("producer") or ""})
            kind_, val = doc.xref_get_key(-1, "Info")
        if kind_ != "xref":
            return data
        doc.xref_set_key(int(val.split()[0]), MARKS[kind].decode()[1:], "true")
        return doc.tobytes(garbage=1, deflate=True)


# --------------------------------------------------------------------------
# Mac: icono propio en cada archivo y etiquetas de color del Finder
# --------------------------------------------------------------------------

def mark_file(path, tags=True):
    """Pone al PDF el icono de su estado (y etiquetas). Solo en Mac; en Windows lo hace el Explorador."""
    if sys.platform != "darwin" or not path.lower().endswith(".pdf") or not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        flags = status(f.read())
    try:
        from AppKit import NSImage, NSWorkspace
        img = NSImage.alloc().initWithContentsOfFile_(icon_path(flags))
        NSWorkspace.sharedWorkspace().setIcon_forFile_options_(img, path, 0)
    except Exception:
        return None
    if tags:
        _set_tags(path, flags)
    return flags


def _set_tags(path, flags):
    import plistlib
    try:  # se conservan las etiquetas que no son de DocGuard
        out = subprocess.run(["xattr", "-px", "com.apple.metadata:_kMDItemUserTags", path], capture_output=True, text=True)
        current = plistlib.loads(bytes.fromhex(out.stdout.replace(" ", "").replace("\n", ""))) if out.returncode == 0 else []
    except Exception:
        current = []
    ours = {name for name, _ in TAGS.values()}
    keep = [t for t in current if t.split("\n")[0] not in ours]
    new = keep + [f"{TAGS[f][0]}\n{TAGS[f][1]}" for f in FLAGS if f in flags]
    data = plistlib.dumps(new, fmt=plistlib.FMT_BINARY).hex()
    subprocess.run(["xattr", "-wx", "com.apple.metadata:_kMDItemUserTags", data, path], capture_output=True)


def mark_folder(folder):
    n = 0
    for root, _dirs, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".pdf") and mark_file(os.path.join(root, f)) is not None:
                n += 1
    return n


# --------------------------------------------------------------------------
# Windows: miniaturas del Explorador (componente pequeño, registrado solo para el usuario, sin
# permisos de administrador). Se copia fuera de la carpeta del programa para que una
# actualización pueda sustituir el programa aunque el Explorador tenga el componente en uso.
# --------------------------------------------------------------------------

CLSID = "{7A3E6C2B-4F1D-4C8B-9B8E-2D1F5A6C9E31}"
THUMB_IID = "{E357FCCD-A995-4576-B01F-234630154E96}"


def windows_register(enable=True):
    if sys.platform != "win32":
        return False
    import shutil
    import winreg
    base = r"Software\Classes"
    if not enable:
        for key in (rf"{base}\.pdf\ShellEx\{THUMB_IID}", rf"{base}\CLSID\{CLSID}\InprocServer32", rf"{base}\CLSID\{CLSID}"):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
            except OSError:
                pass
        _notify()
        return True
    src = core.resource_path("dg_thumbs.dll")
    if not os.path.exists(src):
        return False
    dest_dir = _dll_dir()
    os.makedirs(dest_dir, exist_ok=True)
    dll = os.path.join(dest_dir, "dg_thumbs.dll")
    try:
        shutil.copy2(src, dll)
    except OSError:
        pass  # ya está y en uso: vale la copia de esta versión
    shutil.copytree(core.resource_path("iconos_estado"), os.path.join(dest_dir, "iconos_estado"), dirs_exist_ok=True)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{base}\CLSID\{CLSID}") as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, "DocGuard: iconos de estado de los PDF")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{base}\CLSID\{CLSID}\InprocServer32") as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, dll)
        winreg.SetValueEx(k, "ThreadingModel", 0, winreg.REG_SZ, "Apartment")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{base}\.pdf\ShellEx\{THUMB_IID}") as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, CLSID)
    _notify()
    return True


def _dll_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", core.config_dir()), "DocGuard", "miniaturas", core.VERSION)


def windows_machine_status():
    """¿Están registradas las miniaturas para todo el equipo (HKLM)? En muchos Windows el Explorador
    solo usa los componentes de miniaturas registrados ahí, no los de HKCU."""
    if sys.platform != "win32":
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"Software\Classes\CLSID\{CLSID}\InprocServer32") as k:
            dll = winreg.QueryValueEx(k, None)[0]
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"Software\Classes\.pdf\ShellEx\{THUMB_IID}") as k:
            ok = winreg.QueryValueEx(k, None)[0].upper() == CLSID.upper()
        return ok and os.path.exists(dll)
    except OSError:
        return False


def windows_register_machine(enable=True):
    """Registra (o quita) las miniaturas para todo el equipo: Windows pide permiso de administrador
    una sola vez (regedit con un archivo .reg). Devuelve True si queda hecho."""
    if sys.platform != "win32":
        return False
    import tempfile
    base = r"HKEY_LOCAL_MACHINE\Software\Classes"
    if enable:
        windows_register(True)  # copia la DLL y las imágenes a su carpeta
        dll = os.path.join(_dll_dir(), "dg_thumbs.dll").replace("\\", "\\\\")
        body = (f'[{base}\\CLSID\\{CLSID}]\r\n@="DocGuard: iconos de estado de los PDF"\r\n\r\n'
                f'[{base}\\CLSID\\{CLSID}\\InprocServer32]\r\n@="{dll}"\r\n"ThreadingModel"="Apartment"\r\n\r\n'
                f'[{base}\\.pdf\\ShellEx\\{THUMB_IID}]\r\n@="{CLSID}"\r\n')
    else:
        body = (f'[-{base}\\.pdf\\ShellEx\\{THUMB_IID}]\r\n\r\n[-{base}\\CLSID\\{CLSID}]\r\n')
    reg = os.path.join(tempfile.gettempdir(), "docguard_miniaturas.reg")
    with open(reg, "w", encoding="utf-16", newline="") as f:
        f.write("Windows Registry Editor Version 5.00\r\n\r\n" + body)
    ps = f"Start-Process regedit.exe -Verb RunAs -Wait -ArgumentList '/s','\"{reg}\"'"
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, creationflags=0x08000000)
    try:
        os.remove(reg)
    except OSError:
        pass
    _notify()
    return windows_machine_status() == bool(enable)


def _notify():
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
    except Exception:
        pass


# --------------------------------------------------------------------------
# Imágenes de los iconos (todas las combinaciones de insignias)
# --------------------------------------------------------------------------

def _badge(kind, size):
    from PIL import Image, ImageDraw
    s = size
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bg = {"firmado": (31, 157, 85), "contrasena": (37, 99, 217), "censurado": (30, 30, 34), "protegido": (230, 140, 0)}[kind]
    d.ellipse((0, 0, s - 1, s - 1), fill=bg + (255,), outline=(255, 255, 255, 255), width=max(2, s // 14))
    w = (255, 255, 255, 255)
    k = s / 100
    if kind == "contrasena":  # candado
        d.rounded_rectangle((28 * k, 46 * k, 72 * k, 78 * k), radius=6 * k, fill=w)
        d.arc((34 * k, 22 * k, 66 * k, 60 * k), 180, 360, fill=w, width=int(8 * k))
        d.line((34 * k, 41 * k, 34 * k, 50 * k), fill=w, width=int(8 * k))
        d.line((66 * k, 41 * k, 66 * k, 50 * k), fill=w, width=int(8 * k))
    elif kind == "firmado":  # firma manuscrita
        pts = [(22, 64), (32, 42), (40, 66), (50, 38), (58, 62), (66, 46), (78, 58)]
        d.line([(x * k, y * k) for x, y in pts], fill=w, width=int(7 * k), joint="curve")
        d.line((22 * k, 74 * k, 78 * k, 74 * k), fill=w, width=int(4 * k))
    elif kind == "censurado":  # líneas tapadas
        for y in (30, 46, 62):
            d.rounded_rectangle((24 * k, y * k, 76 * k, (y + 9) * k), radius=2 * k, fill=w if y == 46 else (150, 150, 155, 255))
    else:  # escudo
        d.polygon([(50 * k, 18 * k), (78 * k, 30 * k), (74 * k, 62 * k), (50 * k, 82 * k), (26 * k, 62 * k), (22 * k, 30 * k)], fill=w)
        d.line([(36 * k, 50 * k), (46 * k, 60 * k), (64 * k, 40 * k)], fill=bg + (255,), width=int(8 * k))
    return im


def _base(S=512):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = S / 512
    # hoja con la esquina doblada, en rojo, con «PDF» (un poco a la derecha: a la izquierda van las insignias)
    x0, y0, x1, y1, fold = 120 * k, 40 * k, 440 * k, 472 * k, 90 * k
    d.polygon([(x0, y0), (x1 - fold, y0), (x1, y0 + fold), (x1, y1), (x0, y1)], fill=(214, 40, 45, 255))
    d.polygon([(x1 - fold, y0), (x1, y0 + fold), (x1 - fold, y0 + fold)], fill=(245, 160, 160, 255))
    f = core.get_font(int(118 * k))
    tw = d.textlength("PDF", font=f)
    d.text(((x0 + x1) / 2 - tw / 2, 250 * k), "PDF", font=f, fill=(255, 255, 255, 255))
    return img


def build():
    """Genera iconos_estado/pdf*.png (512 px) con todas las combinaciones."""
    from itertools import combinations
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iconos_estado")
    os.makedirs(out, exist_ok=True)
    S = 512
    for n in range(len(FLAGS) + 1):
        for combo in combinations(FLAGS, n):
            img = _base(S)
            # insignias en columna a la izquierda, de arriba abajo: la esquina inferior queda
            # libre para las marcas de Google Drive, OneDrive, iCloud…
            size = 170 if n <= 2 else 128
            step = int(size * 0.92)
            for i, kind in enumerate([f for f in FLAGS if f in combo]):
                img.alpha_composite(_badge(kind, size), (2, 4 + i * step))
            img.save(os.path.join(out, icon_name(combo) + ".png"))
    return out


if __name__ == "__main__":
    print("iconos en", build())
