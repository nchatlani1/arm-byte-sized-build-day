@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv-companion
if errorlevel 1 goto failed
.venv-companion\Scripts\python.exe -m pip install -r companion\desktop_requirements.txt
if errorlevel 1 goto failed
.venv-companion\Scripts\python.exe tools\build_companion.py
if errorlevel 1 goto failed
explorer dist\companion
exit /b 0
:failed
echo Build failed. Read the error above. Use Python 3.9 through 3.12 on Windows.
pause
exit /b 1
