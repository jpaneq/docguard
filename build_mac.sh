#!/bin/sh
# Genera dist/DocGuard.app
# Firma opcional: CODESIGN_IDENTITY="Developer ID Application: Tu Nombre (XXXX)" ./build_mac.sh
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  if command -v uv >/dev/null 2>&1; then uv venv -q --python 3.12 .venv; else python3 -m venv .venv; fi
fi
if command -v uv >/dev/null 2>&1; then uv pip install -q --python .venv -r requirements.txt pyinstaller
else .venv/bin/pip install -q -r requirements.txt pyinstaller; fi
.venv/bin/python -c "from rapidocr import RapidOCR; RapidOCR()" >/dev/null   # descarga los modelos OCR para incluirlos
.venv/bin/python make_icon.py
cp icon.png web/icon.png
SIGN=""
[ -n "$CODESIGN_IDENTITY" ] && SIGN="--codesign-identity $CODESIGN_IDENTITY"
.venv/bin/pyinstaller --noconfirm --windowed --name DocGuard --icon icon.icns \
  --add-data "web:web" \
  --collect-all rapidocr --collect-all onnxruntime --collect-all webview \
  --collect-all pyhanko --collect-all pyhanko_certvalidator --hidden-import pkcs11 \
  $SIGN app.py
dist/DocGuard.app/Contents/MacOS/DocGuard --selftest
echo "Listo: dist/DocGuard.app"
