@echo off
rem Crea dist\ForensiX-Hash.exe (app de escritorio) con PyInstaller y su SHA256SUMS.txt.
rem Se ejecuta desde cualquier sitio: trabaja en la raíz del proyecto.
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -m pip install -r desktop\requirements.txt
if errorlevel 1 goto :error

".venv\Scripts\python.exe" desktop\make_icon.py
if errorlevel 1 goto :error

rem --paths: raíz del proyecto, para importar forensix_hash, web y desktop.
rem --icon: icono del .exe.  web\static: interfaz.  desktop\assets: icono de la ventana.
".venv\Scripts\python.exe" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --onefile ^
    --name ForensiX-Hash ^
    --paths . ^
    --collect-all webview ^
    --icon desktop\assets\app.ico ^
    --version-file desktop\version_info.txt ^
    --add-data "web\static;web\static" ^
    --add-data "desktop\assets\app.ico;desktop\assets" ^
    desktop\__main__.py
if errorlevel 1 goto :error

rem Hash del ejecutable para la Release (como en Lumen: SHA256SUMS.txt).
powershell -NoProfile -Command "$h = (Get-FileHash dist\ForensiX-Hash.exe -Algorithm SHA256).Hash.ToLower(); Set-Content -Encoding ascii dist\SHA256SUMS.txt \"$h  ForensiX-Hash.exe\""
if errorlevel 1 goto :error

echo.
echo Listo: dist\ForensiX-Hash.exe y dist\SHA256SUMS.txt
exit /b 0

:error
echo.
echo No se pudo crear el ejecutable. Revisa el error anterior.
pause
exit /b 1
