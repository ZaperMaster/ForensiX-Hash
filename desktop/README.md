# ForensiX Hash · app de escritorio (Windows)

Ventana WebView2 sin marco con la interfaz de `web/static` y su barra de título propia:

- Se abre a **pantalla completa** (maximizada, sin tapar la barra de tareas).
- Diálogos de Windows para elegir archivo, carpeta, imagen de disco y la carpeta del informe PDF.
- **Actualizaciones automáticas firmadas**: descarga el `.exe` nuevo, comprueba la firma Ed25519 de
  `SHA256SUMS.txt` y el hash, sustituye el `.exe` y vuelve a abrirse (ver `forensix_hash/updater.py`).
- Botón **Reiniciar como administrador** para leer discos completos (UAC).

```bash
python -m pip install -r desktop\requirements.txt
python -m desktop                     # en desarrollo
desktop\build_windows.bat             # dist\: ForensiX-Hash.exe, instalador y SHA256SUMS.txt
```

Requisitos: Windows 10/11 con **Microsoft Edge WebView2 Runtime** y Microsoft Edge (vienen con Windows 11).

**Instalador** (`installer.iss`, Inno Setup 6: `winget install JRSoftware.InnoSetup`): se instala para el usuario
actual sin pedir administrador en `%LOCALAPPDATA%\Programs\ForensiX Hash` (así la app puede actualizarse sola),
con accesos en el menú Inicio y el escritorio, en español o inglés. El desinstalador conserva los registros.

`make_icon.py` dibuja el logo y genera `assets/app.ico`, `docs/icon.png`, `docs/favicon.png`,
`docs/social.png` y las imágenes del asistente de instalación. `version_info.txt` son los datos de versión del `.exe`.
