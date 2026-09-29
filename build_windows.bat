@echo off
REM Genera dist\DocGuard\DocGuard.exe (requiere Python 3.10+ de python.org)
cd /d "%~dp0"
if not exist .venv py -3.12 -m venv .venv
.venv\Scripts\pip install -q -r requirements.txt pyinstaller
.venv\Scripts\python -c "from rapidocr import RapidOCR; RapidOCR()"
.venv\Scripts\python make_icon.py
copy /y icon.png web\icon.png
.venv\Scripts\pyinstaller --noconfirm --windowed --name DocGuard --icon icon.ico --add-data "web;web" --collect-all rapidocr --collect-all onnxruntime --collect-all webview --collect-all pyhanko --collect-all pyhanko_certvalidator --hidden-import pkcs11 app.py
echo Listo: dist\DocGuard\DocGuard.exe
pause
