"""Comprueba las notas de la versión: python tools/check_novedades.py v1.36
Falla si falta novedades/<etiqueta>.md o no sigue el formato (ver novedades/LEEME.md)."""
import os
import re
import sys

tag = sys.argv[1] if len(sys.argv) > 1 else ""
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "novedades", f"{tag}.md")
if not os.path.exists(path):
    sys.exit(f"Falta novedades/{tag}.md: escribe las notas de la versión (copia novedades/_plantilla.md).")
lines = [l.strip() for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]
problems = []
if not lines or not lines[0].startswith("# "):
    problems.append("la primera línea debe ser el titular: «# Titular corto»")
items = [l for l in lines if re.match(r"[-*] ", l)]
if not 1 <= len(items) <= 8:
    problems.append(f"debe haber entre 1 y 8 tarjetas (hay {len(items)})")
icons = []
for l in items:
    m = re.match(r"[-*]\s+(\S+)\s+\*\*(.+?)\*\*\s*[—:-]\s*(\S.*)$", l)
    if not m:
        problems.append(f"tarjeta mal formada (usa «- 🔎 **Título** — explicación»): {l[:60]}")
        continue
    if m[1].isascii():
        problems.append(f"falta el icono emoji al principio: {l[:60]}")
    icons.append(m[1])
if len(set(icons)) != len(icons):
    problems.append("hay iconos repetidos: usa uno distinto en cada tarjeta")
if problems:
    sys.exit("Notas de la versión incorrectas (" + path + "):\n - " + "\n - ".join(problems))
print(f"Notas de {tag} correctas: {len(items)} tarjetas.")
