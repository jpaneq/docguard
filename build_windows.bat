@echo off
REM Genera dist\DocGuard\DocGuard.exe (requiere Python 3.10+ de python.org)
cd /d "%~dp0"
if not exist .venv py -3.12 -m venv .venv
.venv\Scripts\pip install -q -r requirements.txt pyinstaller
.venv\Scripts\python -c "from rapidocr import RapidOCR; RapidOCR()"
.venv\Scripts\python make_icon.py
.venv\Scripts\python status_icons.py
copy /y icon.png web\icon.png
REM Miniaturas del Explorador: necesita g++ de MinGW-w64 (si no está, se compila sin ellas)
set THUMBS=
where g++ >nul 2>nul && g++ -shared -O2 -s -static -static-libgcc -static-libstdc++ -o winthumbs\dg_thumbs.dll winthumbs\dg_thumbs.cpp winthumbs\dg_thumbs.def -lole32 -lwindowscodecs -lshlwapi -luuid -lgdi32 && set THUMBS=--add-binary "winthumbs\dg_thumbs.dll;."
.venv\Scripts\pyinstaller --noconfirm --windowed --name DocGuard --icon icon.ico --add-data "web;web" --add-data "extension;extension" --add-data "iconos_estado;iconos_estado" %THUMBS% --collect-all rapidocr --collect-all onnxruntime --collect-all webview --collect-all pyhanko --collect-all pyhanko_certvalidator --hidden-import pkcs11 app.py
echo Listo: dist\DocGuard\DocGuard.exe
pause
