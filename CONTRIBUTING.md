# Cómo contribuir

ForensiX Hash es código abierto (licencia [MIT](LICENSE)) y las contribuciones son bienvenidas.

- **Errores e ideas:** abre una [issue](https://github.com/ZaperMaster/ForensiX-Hash/issues/new/choose). No adjuntes
  datos de evidencias reales.
- **Fallos de seguridad:** se informan en privado, como explica [SECURITY.md](SECURITY.md).
- **Cambios en el código:** haz un fork, crea una rama y abre un pull request. Antes, comprueba que pasan las pruebas:

```bash
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest
```

Un cambio en cómo se calculan o verifican los hashes debe llevar su prueba: en esta herramienta, un resultado incorrecto
es el peor fallo posible.
