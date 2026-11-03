@echo off
rem Crea la app de escritorio y su instalador, como en Lumen:
rem   dist\ForensiX-Hash.exe                    programa (también lo usan las actualizaciones automáticas)
rem   dist\ForensiX-Hash_X.Y.Z_x64-setup.exe    instalador (Inno Setup 6)
rem   dist\SHA256SUMS.txt                       hashes de los dos (scripts\release.py los firma)
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

rem Instalador con Inno Setup 6 (winget install JRSoftware.InnoSetup).
set "ISCC="
for %%I in (ISCC.exe) do if not "%%~$PATH:I"=="" set "ISCC=%%~$PATH:I"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo No se encuentra Inno Setup 6. Instalalo con: winget install JRSoftware.InnoSetup
    goto :error
)
for /f "usebackq delims=" %%V in (`.venv\Scripts\python.exe -c "import forensix_hash; print(forensix_hash.__version__)"`) do set "VERSION=%%V"
if not defined VERSION goto :error
del /q "dist\ForensiX-Hash_*_x64-setup.exe" 2>nul
"%ISCC%" /Q /DAppVersion=%VERSION% desktop\installer.iss
if errorlevel 1 goto :error

rem Hashes de la Release (como en Lumen: SHA256SUMS.txt).
powershell -NoProfile -Command "Get-ChildItem dist\*.exe | ForEach-Object { '{0}  {1}' -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name } | Set-Content -Encoding ascii dist\SHA256SUMS.txt"
if errorlevel 1 goto :error

echo.
echo Listo: dist\ForensiX-Hash.exe, dist\ForensiX-Hash_%VERSION%_x64-setup.exe y dist\SHA256SUMS.txt
exit /b 0

:error
echo.
echo No se pudo crear la app o el instalador. Revisa el error anterior.
pause
exit /b 1