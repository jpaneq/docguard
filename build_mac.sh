#!/bin/sh
# Genera dist/DocGuard.app  (requiere Python 3.10+ de python.org)
set -e
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pyinstaller
.venv/bin/pyinstaller --noconfirm --windowed --name DocGuard docguard.py
echo "Listo: dist/DocGuard.app"
