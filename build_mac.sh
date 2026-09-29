#!/bin/sh
# Genera dist/DocGuard.app  (requiere Python 3.10+).
# Firma opcional: CODESIGN_IDENTITY="Developer ID Application: Tu Nombre (XXXX)" ./build_mac.sh
set -e
cd "$(dirname "$0")"
# Homebrew Python a veces enlaza con una libexpat del sistema demasiado antigua.
if command -v brew >/dev/null 2>&1 && [ -d "$(brew --prefix expat 2>/dev/null)/lib" ]; then
  export DYLD_LIBRARY_PATH="$(brew --prefix expat)/lib"
fi
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt pyinstaller
.venv/bin/python -c "from rapidocr import RapidOCR; RapidOCR()"   # descarga los modelos OCR para incluirlos
.venv/bin/python make_icon.py
SIGN=""
[ -n "$CODESIGN_IDENTITY" ] && SIGN="--codesign-identity $CODESIGN_IDENTITY"
.venv/bin/pyinstaller --noconfirm --windowed --name DocGuard --icon icon.icns \
  --add-data "icon.png:." --collect-all tkinterdnd2 --collect-all rapidocr --collect-all onnxruntime \
  $SIGN docguard.py
echo "Listo: dist/DocGuard.app"
