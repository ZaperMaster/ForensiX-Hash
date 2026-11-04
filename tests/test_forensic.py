"""Firma, sello de tiempo, informe importable, imagen forense, E01 y sectores defectuosos."""

import base64
import hashlib
import json
import time
from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from forensix_hash import devices, engine, pdf, record as record_module, report, signing, store
from forensix_hash.hasher import Cancelled
from forensix_hash.progress import Progress
from web.server import app

from conftest import CASE

HEADERS = {"X-ForensiX": "1"}
SAMPLE = Path(__file__).parent / "data" / "muestra.E01"


@pytest.fixture
def blank_pdf(monkeypatch):
    def html_to_pdf(html, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        writer = PdfWriter()
        writer.add_blank_page(200, 200)
        writer.write(str(target))
        return target

    monkeypatch.setattr(pdf, "html_to_pdf", html_to_pdf)


# --- Firma ---------------------------------------------------------------------------------

def test_records_are_signed(evidence, isolated_home):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    stored = store.load_record(record["id"])
    assert signing.signature_status(stored) == "valid"
    assert stored["signature"]["fingerprint"] == signing.identity(isolated_home)["fingerprint"]

    stored["case"]["examiner"] = "Otra persona"
    assert signing.signature_status(stored) == "invalid"


def test_forged_signature_with_other_key_changes_fingerprint(evidence, tmp_path):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    original = record["signature"]["fingerprint"]
    other = tmp_path / "otro-equipo"
    other.mkdir()
    record["case"]["examiner"] = "Falsificador"
    record_module.seal(record)
    signing.sign_record(record, other)
    assert signing.signature_status(record) == "valid"  # Firma coherente...
    assert record["signature"]["fingerprint"] != original  # ...pero la huella delata otra clave


def test_key_is_not_stored_in_clear_on_windows(evidence, isolated_home):
    store.home()
    import os

    identity = signing.identity(isolated_home)
    assert signing.identity(isolated_home) == identity  # Se reutiliza
    assert len((isolated_home / signing.KEY_FILE).read_bytes()) > (32 if os.name == "nt" else 31)


def test_verification_keeps_signature_valid(evidence):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    engine.verify(record, examiner="Otra persona")
    assert signing.signature_status(store.load_record(record["id"])) == "valid"


# --- Sello de tiempo -----------------------------------------------------------------------

def fake_tsa(when=b"20261104083729Z", status=0, tamper=False):
    def post(url, body):
        digest = body[body.index(bytes.fromhex("0420")) + 2:][:32]
        nonce = body[body.rindex(b"\x02\x09") + 2:][:9]
        if tamper:
            digest = bytes(32)
        info = signing._der(0x04, digest) + signing._der(0x02, nonce) + signing._der(0x18, when)
        token = signing._der(0x30, info)
        return signing._der(0x30, signing._der(0x30, signing._der(0x02, bytes([status]))) + token)
    return post


def test_timestamp_is_added_and_does_not_break_the_seal(evidence):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    entry = signing.timestamp_record(record, post=fake_tsa())
    assert entry["time"] == "2026-11-04T08:37:29+00:00"
    assert entry["seal"] == record["seal"]["value"] and base64.b64decode(entry["token"])
    assert record_module.seal_ok(record) and signing.signature_status(record) == "valid"
    assert "2026-11-04T08:37:29" in report.to_html(record)


def test_timestamp_for_other_data_is_rejected(evidence):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    with pytest.raises(signing.TimestampError):
        signing.timestamp_record(record, post=fake_tsa(tamper=True))
    with pytest.raises(signing.TimestampError):
        signing.timestamp_record(record, post=fake_tsa(status=2))
    assert "timestamps" not in record


def test_no_internet_is_not_fatal_for_the_job(evidence, tmp_path, blank_pdf, monkeypatch):
    def offline(url, body):
        raise OSError("sin conexión")

    monkeypatch.setattr(signing, "_post", offline)
    client = TestClient(app)
    job = client.post("/api/jobs", headers=HEADERS, json={
        "kind": "file", "target": str(evidence / "a.txt"), "case": CASE, "output": str(tmp_path / "o"),
        "timestamp": True}).json()
    for _ in range(600):
        job = client.get(f"/api/jobs/{job['id']}", headers=HEADERS).json()
        if job["state"] != "running":
            break
        time.sleep(0.05)
    assert job["state"] == "done" and job["timestamp_error"] and job["pdf"]


# --- Informe PDF importable ------------------------------------------------------------------

def test_pdf_carries_the_record_and_can_be_imported_elsewhere(evidence, tmp_path, blank_pdf, monkeypatch):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    data = pdf.save_report(record, tmp_path / "informes").read_bytes()
    signature = record["signature"]["value"]

    monkeypatch.setenv("FORENSIX_HASH_HOME", str(tmp_path / "otro-equipo"))
    assert store.list_records() == []
    imported, existed = pdf.import_report(data)
    assert not existed and imported["id"] == record["id"]
    assert store.load_record(record["id"])["signature"]["value"] == signature  # Firma de origen intacta
    assert store.read_custody()[-1]["action"] == "imported"
    entry = engine.verify(store.load_record(record["id"]), examiner="Segundo perito")
    assert entry["result"] == "verified"

    verified = store.load_record(record["id"])
    assert entry["fingerprint"] == verified["signature"]["fingerprint"]  # Firma del segundo equipo...
    assert verified["environment"]["fingerprint"] == record["signature"]["fingerprint"]  # ...sin perder al creador
    assert entry["fingerprint"] != record["signature"]["fingerprint"]
    assert "Clave que creó el registro" in report.to_html(verified)


def test_tampered_or_foreign_reports_are_rejected(evidence, tmp_path, blank_pdf):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    tampered = json.loads(report.to_json(record))
    tampered["hashes"]["md5"] = "0" * 32
    with pytest.raises(pdf.ReportRejected):
        pdf.read_report(json.dumps(tampered).encode())

    resigned = json.loads(report.to_json(record))
    resigned["case"]["examiner"] = "Falsificador"
    record_module.seal(resigned)  # Sello recalculado, firma sin rehacer
    with pytest.raises(pdf.ReportRejected):
        pdf.read_report(json.dumps(resigned).encode())

    plain = tmp_path / "otro.pdf"
    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    writer.write(str(plain))
    for data in (plain.read_bytes(), b"%PDF-roto", b"{}", b"hola"):
        with pytest.raises(ValueError):
            pdf.read_report(data)


def test_pdf_written_after_the_browser_process_ends_is_still_found(tmp_path):
    from threading import Timer

    late = tmp_path / "tarde.pdf"
    timer = Timer(0.3, lambda: late.write_bytes(b"%PDF-1.7\n" + b"x" * 100 + b"\n%%EOF\n"))
    timer.start()
    assert pdf._wait_for_pdf(late, timeout=5) is True
    timer.join()


def test_incomplete_pdf_is_not_accepted(tmp_path):
    partial = tmp_path / "corto.pdf"
    partial.write_bytes(b"%PDF-1.7\n" + b"x" * 100)
    assert pdf._wait_for_pdf(partial, timeout=0.3) is False
    assert pdf._wait_for_pdf(tmp_path / "no-existe.pdf", timeout=0.3) is False


# --- Sectores defectuosos ------------------------------------------------------------------

class FlakyDisk:
    """Disco falso: fallan los sectores indicados, también al leerlos uno a uno."""

    def __init__(self, data: bytes, bad: set[int], sector: int = 512):
        self.data, self.bad, self.sector, self.position = data, bad, sector, 0

    def seek(self, offset):
        self.position = offset

    def read(self, size):
        first, last = self.position // self.sector, (self.position + size - 1) // self.sector
        if any(first <= sector <= last for sector in self.bad):
            raise OSError(23, "Error de datos (CRC)")
        chunk = self.data[self.position:self.position + size]
        self.position += size
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


def flaky(monkeypatch, data, bad):
    monkeypatch.setattr(devices, "device_size", lambda path: (len(data), 512))
    monkeypatch.setattr(devices, "open_device", lambda path: FlakyDisk(data, bad))


def test_bad_sectors_are_read_as_zeros_and_reported(tmp_path, monkeypatch):
    sectors = 20000  # Más de un bloque de lectura de 4 MiB
    data = bytes(range(256)) * 2 * sectors
    bad = {3, 9000, 9001}
    image = tmp_path / "disco.dd"
    image.write_bytes(b"x")
    flaky(monkeypatch, data, bad)

    record = engine.acquire("disk", str(image), ["sha256"], CASE)
    expected = bytearray(data)
    for sector in bad:
        expected[sector * 512:(sector + 1) * 512] = bytes(512)
    assert record["hashes"]["sha256"] == hashlib.sha256(expected).hexdigest()
    assert record["details"]["bad_sectors"] == {"count": 3, "first": [3, 9000, 9001]}
    assert record["verifications"][0]["result"] == "verified"
    assert "Sectores ilegibles" in report.to_html(record)


def test_sector_that_starts_failing_is_a_mismatch(tmp_path, monkeypatch):
    data = bytes(range(256)) * 2 * 100
    image = tmp_path / "disco.dd"
    image.write_bytes(b"x")
    flaky(monkeypatch, data, set())
    record = engine.acquire("disk", str(image), ["sha256"], CASE)
    flaky(monkeypatch, data, {50})
    assert engine.verify(record, examiner="Perito")["result"] == "mismatch"


# --- Imagen forense --------------------------------------------------------------------------

def test_image_is_created_and_verified(tmp_path):
    source = tmp_path / "pendrive.raw"
    data = bytes(range(256)) * 4096 * 9
    source.write_bytes(data)
    record = engine.acquire("disk", str(source), ["md5", "sha256"], CASE, image_folder=tmp_path / "imagenes")

    image = record["image"]
    created = Path(image["path"])
    assert created.suffix == ".dd" and created.read_bytes() == data
    assert image["result"] == "verified" and image["hashes"] == record["hashes"]
    assert not list(created.parent.glob("*.partial"))
    html = report.to_html(record)
    assert "Imagen forense" in html and created.name in html


def test_image_is_a_valid_copy_to_verify_against(tmp_path):
    source = tmp_path / "pendrive.raw"
    source.write_bytes(b"datos" * 4000)
    record = engine.acquire("disk", str(source), None, CASE, image_folder=tmp_path / "i")
    assert engine.verify(record, examiner="Perito", target=record["image"]["path"])["result"] == "verified"


def test_corrupted_image_is_a_mismatch(tmp_path, monkeypatch):
    source = tmp_path / "pendrive.raw"
    source.write_bytes(b"datos" * 4000)
    original = engine._write_image

    def corrupt(*args):
        result = original(*args)
        args[-1].write_bytes(b"corrupta" * 2500)
        return result

    monkeypatch.setattr(engine, "_write_image", corrupt)
    record = engine.acquire("disk", str(source), None, CASE, image_folder=tmp_path / "i")
    assert record["image"]["result"] == "mismatch"
    assert record_module.status(record) == "mismatch"


def test_cancelled_image_leaves_nothing(tmp_path):
    source = tmp_path / "pendrive.raw"
    source.write_bytes(b"datos" * 4000)
    cancel = Event()
    cancel.set()
    folder = tmp_path / "i"
    with pytest.raises(Cancelled):
        engine.acquire("disk", str(source), None, CASE, cancel=cancel, image_folder=folder)
    assert list(folder.iterdir()) == []


def test_image_needs_room_and_a_disk(tmp_path, evidence, monkeypatch):
    source = tmp_path / "pendrive.raw"
    source.write_bytes(b"datos" * 4000)
    with pytest.raises(ValueError):
        engine.check_image_destination("file", str(source), tmp_path / "i")
    monkeypatch.setattr(engine.shutil, "disk_usage", lambda path: type("U", (), {"free": 10})())
    with pytest.raises(ValueError, match="espacio"):
        engine.check_image_destination("disk", str(source), tmp_path / "i")


def test_image_does_not_fit_on_fat32(tmp_path, monkeypatch):
    monkeypatch.setattr(devices, "device_size", lambda path: (5 * 1024 ** 3, 512))
    monkeypatch.setattr(devices, "filesystem_of", lambda folder: "FAT32")
    monkeypatch.setattr(engine.shutil, "disk_usage", lambda path: type("U", (), {"free": 10 ** 13})())
    source = tmp_path / "x.raw"
    source.write_bytes(b"x")
    with pytest.raises(ValueError, match="FAT32"):
        engine.check_image_destination("disk", str(source), tmp_path / "i")


# --- Protección de escritura y disco del sistema -----------------------------------------------

def test_write_protection_and_system_disk_appear_in_the_report(tmp_path, monkeypatch):
    source = tmp_path / "d.raw"
    source.write_bytes(b"x" * 1024)
    monkeypatch.setattr(devices, "describe_device", lambda path: {
        "kind": "disk", "path": path, "model": "Disco", "write_protected": True, "system": True})
    record = engine.acquire("disk", str(source), None, CASE)
    html = report.to_html(record)
    assert "Protección contra escritura" in html and record["details"]["live_system"] is True
    assert "Disco del sistema en uso" in html


# --- E01 -----------------------------------------------------------------------------------

@pytest.mark.skipif(not SAMPLE.exists(), reason="Sin imagen E01 de muestra")
def test_real_e01_hashes_the_contents_and_matches_stored_hash():
    record = engine.acquire("disk", str(SAMPLE), ["md5", "sha1"], CASE)
    assert record["source"]["kind"] == "ewf"
    assert record["size"] > SAMPLE.stat().st_size or record["size"] > 0
    assert record["details"]["ewf"]["match"] is True
    assert record["verifications"][0]["result"] == "verified"
    assert "Coinciden con los calculados" in report.to_html(record)


def test_e01_with_wrong_stored_hash_is_a_mismatch():
    record = {"verifications": [{"result": "verified"}], "details": {"ewf": {"match": False}}}
    assert record_module.status(record) == "mismatch"
