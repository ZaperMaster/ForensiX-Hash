"""Informe PDF (destino seguro y creación) y actualizaciones firmadas."""

import base64
import hashlib
import json
import os
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from forensix_hash import engine, pdf, store, updater
from web.server import app

from conftest import CASE

HEADERS = {"X-ForensiX": "1"}


@pytest.fixture
def fake_pdf(monkeypatch):
    """Sustituye Edge por una función que escribe un PDF mínimo con el HTML dentro."""

    def html_to_pdf(html, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"%PDF-1.7\n" + html.encode("utf-8"))
        return target

    monkeypatch.setattr(pdf, "html_to_pdf", html_to_pdf)


# --- Destino del informe -----------------------------------------------------------------

def test_report_cannot_go_inside_hashed_folder(evidence, tmp_path):
    with pytest.raises(ValueError):
        pdf.check_destination("directory", str(evidence), evidence)
    with pytest.raises(ValueError):
        pdf.check_destination("directory", str(evidence), evidence / "sub")
    assert pdf.check_destination("directory", str(evidence), tmp_path / "informes") == (tmp_path / "informes").resolve()
    # Un archivo no cambia porque se guarde un PDF a su lado
    assert pdf.check_destination("file", str(evidence / "a.txt"), evidence)


@pytest.mark.skipif(os.name != "nt", reason="Rutas de red de Windows")
def test_network_paths_are_rejected(tmp_path):
    from forensix_hash import paths

    for network in (r"\\servidor\recurso\evidencia.dd", r"\\?\UNC\servidor\recurso"):
        with pytest.raises(ValueError):
            paths.local_path(network)
        with pytest.raises(ValueError):
            engine.acquire("file", network, None, CASE)
    assert paths.local_path(str(tmp_path)) == os.path.normpath(str(tmp_path))
    client = TestClient(app)
    assert client.get("/api/browse", params={"path": r"\\servidor\recurso"}, headers=HEADERS).status_code == 400


def test_unknown_disk_is_rejected():
    with pytest.raises(FileNotFoundError):
        engine.acquire("disk", r"\\.\PhysicalDrive99" if os.name == "nt" else "/dev/nodisk99", None, CASE)


@pytest.mark.skipif(os.name != "nt", reason="Letras de unidad de Windows")
def test_report_cannot_go_on_hashed_volume(monkeypatch):
    monkeypatch.setattr(pdf.paths, "local_roots", lambda: ["C:\\", "D:\\"])
    monkeypatch.setattr(pdf.devices, "is_raw_device", lambda path: True)
    monkeypatch.setattr(pdf.devices, "letters_of", lambda path: {"D", "E"})
    with pytest.raises(ValueError):
        pdf.check_destination("disk", r"\\.\PhysicalDrive1", "D:\\informes")
    monkeypatch.setattr(pdf.devices, "letters_of", lambda path: set())
    assert pdf.check_destination("disk", r"\\.\PhysicalDrive1", "D:\\informes")


def test_save_report_logs_custody(evidence, tmp_path, fake_pdf):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    path = pdf.save_report(record, tmp_path / "out")
    assert path.exists() and path.suffix == ".pdf" and path.read_bytes().startswith(b"%PDF")
    assert "VERIFICADO" in path.read_text(encoding="utf-8", errors="ignore")
    event = store.read_custody()[-1]
    assert event["action"] == "exported" and event["format"] == "pdf" and event["path"] == str(path)


@pytest.mark.skipif(pdf.find_browser() is None, reason="Sin Edge ni Chrome en este equipo")
def test_real_pdf_with_browser(evidence, tmp_path):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    path = pdf.save_report(record, tmp_path)
    data = path.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 5000


def test_api_job_creates_pdf_in_folder(evidence, tmp_path, fake_pdf):
    client = TestClient(app)
    out = tmp_path / "comprobantes"
    job = client.post("/api/jobs", headers=HEADERS, json={
        "kind": "directory", "target": str(evidence), "case": CASE, "output": str(out), "lang": "en"}).json()
    for _ in range(200):
        job = client.get(f"/api/jobs/{job['id']}", headers=HEADERS).json()
        if job["state"] != "running":
            break
        time.sleep(0.05)
    assert job["state"] == "done" and job["result"] == "verified", job
    assert job["pdf"] and job["pdf"].startswith(str(out)) and "VERIFIED" in open(job["pdf"], encoding="utf-8", errors="ignore").read()

    detail = client.get(f"/api/records/{job['record_id']}", headers=HEADERS).json()
    assert detail["reports"] == [{"path": job["pdf"], "exists": True}]

    inside = client.post("/api/jobs", headers=HEADERS, json={
        "kind": "directory", "target": str(evidence), "case": CASE, "output": str(evidence / "sub")})
    assert inside.status_code == 400

    # Solo se abren informes creados por la app
    assert client.post("/api/open", headers=HEADERS, json={"path": str(evidence / "a.txt")}).status_code == 404


# --- Actualizaciones -----------------------------------------------------------------------

@pytest.fixture
def signed_release():
    """Una Release falsa firmada con una clave de prueba."""

    key = Ed25519PrivateKey.generate()
    public = base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    exe = b"MZ nueva version" * 1000
    sums = f"{hashlib.sha256(exe).hexdigest()}  ForensiX-Hash.exe\n".encode()
    signature = base64.b64encode(key.sign(sums)) + b"\n"
    base = "https://github.com/ZaperMaster/ForensiX-Hash/releases/download/v9.9.9/"
    files = {
        updater.API: json.dumps({"tag_name": "v9.9.9", "html_url": "https://github.com/x", "assets": [
            {"name": name, "browser_download_url": base + name} for name in (updater.ASSET, updater.SUMS, updater.SIGNATURE)
        ]}).encode(),
        base + updater.ASSET: exe, base + updater.SUMS: sums, base + updater.SIGNATURE: signature,
    }
    return {"files": files, "public": public, "exe": exe, "fetch": lambda url, limit=0: files[url]}


def test_version_compare():
    assert updater.parse_version("v1.10.0") > updater.parse_version("1.9.9")
    assert updater.parse_version("1.0.0") == updater.parse_version("v1.0.0")
    assert updater.parse_version("rubbish") == (0,)


def test_check_finds_new_version(signed_release):
    info = updater.check(fetch=signed_release["fetch"])
    assert info["available"] and info["latest"] == "9.9.9"
    assert info["can_install"] is False  # En los tests no es el .exe


def test_download_verified(signed_release, tmp_path):
    info = updater.check(fetch=signed_release["fetch"])
    path = updater.download_verified(info, tmp_path, signed_release["fetch"], signed_release["public"])
    assert path.read_bytes() == signed_release["exe"]


def test_bad_signature_is_rejected(signed_release, tmp_path):
    info = updater.check(fetch=signed_release["fetch"])
    other = Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    with pytest.raises(updater.UpdateError):
        updater.download_verified(info, tmp_path, signed_release["fetch"], base64.b64encode(other).decode())
    assert not list(tmp_path.iterdir())


def test_tampered_exe_is_rejected(signed_release, tmp_path):
    files = dict(signed_release["files"])
    url = next(u for u in files if u.endswith(updater.ASSET))
    files[url] = b"MZ malicioso"
    fetch = lambda url, limit=0: files[url]  # noqa: E731
    info = updater.check(fetch=fetch)
    with pytest.raises(updater.UpdateError):
        updater.download_verified(info, tmp_path, fetch, signed_release["public"])


def test_install_replaces_running_exe(signed_release, tmp_path, monkeypatch):
    current = tmp_path / "ForensiX-Hash.exe"
    current.write_bytes(b"MZ version vieja")
    launched = []
    monkeypatch.setattr(updater.sys, "frozen", True, raising=False)
    monkeypatch.setattr(updater.sys, "executable", str(current))
    monkeypatch.setattr(updater, "_get", signed_release["fetch"])
    monkeypatch.setattr(updater, "PUBLIC_KEY", signed_release["public"])
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kw: launched.append(args))

    updater.install(updater.check(fetch=signed_release["fetch"]))
    assert current.read_bytes() == signed_release["exe"]
    assert (tmp_path / "ForensiX-Hash.exe.old").read_bytes() == b"MZ version vieja"
    assert launched == [[str(current)]]
    updater.cleanup()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ForensiX-Hash.exe"]


def test_only_https():
    with pytest.raises(updater.UpdateError):
        updater._get("http://example.com/update.exe")
