@echo off
REM Genera dist\DocGuard\DocGuard.exe (requiere Python 3.10+ de python.org)
cd /d "%~dp0"
if not exist .venv py -m venv .venv
.venv\Scripts\pip install -q -r requirements.txt pyinstaller
.venv\Scripts\python -c "from rapidocr import RapidOCR; RapidOCR()"
.venv\Scripts\python make_icon.py
.venv\Scripts\pyinstaller --noconfirm --windowed --name DocGuard --icon icon.ico --add-data "icon.png;." --collect-all tkinterdnd2 --collect-all rapidocr --collect-all onnxruntime docguard.py
echo Listo: dist\DocGuard\DocGuard.exe
pause
