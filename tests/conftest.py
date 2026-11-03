import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Cada test usa su propia carpeta de datos (registros y cadena de custodia)."""

    home = tmp_path / "home"
    monkeypatch.setenv("FORENSIX_HASH_HOME", str(home))
    return home


@pytest.fixture
def evidence(tmp_path):
    """Carpeta de prueba con subcarpetas, un archivo vacío, Unicode y un archivo grande."""

    root = tmp_path / "evidencia"
    (root / "sub" / "más").mkdir(parents=True)
    (root / "a.txt").write_bytes(b"hola\n")
    (root / "sub" / "b.bin").write_bytes(bytes(range(256)) * 100)
    (root / "sub" / "más" / "ñandú.txt").write_text("unicode", encoding="utf-8")
    (root / "vacio.dat").write_bytes(b"")
    (root / "grande.bin").write_bytes(b"\xab" * (9 * 1024 * 1024 + 123))  # Más de dos bloques
    return root


CASE = {"examiner": "Perito de prueba", "case_number": "T-1", "evidence_number": "EV-1"}
