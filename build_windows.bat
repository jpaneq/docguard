@echo off
REM Genera dist\DocGuard\DocGuard.exe (requiere Python 3.10+ de python.org)
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt pyinstaller
.venv\Scripts\pyinstaller --noconfirm --windowed --name DocGuard docguard.py
echo Listo: dist\DocGuard\DocGuard.exe
pause
