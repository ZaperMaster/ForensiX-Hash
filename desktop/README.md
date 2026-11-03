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
desktop\build_windows.bat             # dist\ForensiX-Hash.exe y dist\SHA256SUMS.txt
```

Requisitos: Windows 10/11 con **Microsoft Edge WebView2 Runtime** y Microsoft Edge (vienen con Windows 11).

`make_icon.py` dibuja el logo y genera `assets/app.ico`, `docs/icon.png`, `docs/favicon.png` y
`docs/social.png`. `version_info.txt` son los datos de versión del `.exe`.
