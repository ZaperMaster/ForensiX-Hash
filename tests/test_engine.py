"""Motor: hashes correctos, verificación, carpetas, imágenes de disco, sello y custodia."""

import hashlib
import json
from threading import Event

import pytest

from forensix_hash import engine, report, store
from forensix_hash.hasher import ALGORITHMS, Cancelled, MultiHasher, normalize_algorithms
from forensix_hash.record import compute_seal, seal_ok
from forensix_hash.sources import manifest_text

from conftest import CASE


def expected(data: bytes, algorithms=ALGORITHMS) -> dict:
    return {a: hashlib.new(a, data).hexdigest() for a in algorithms}


# --- Hasher ---------------------------------------------------------------------------

def test_known_vectors():
    with MultiHasher(["md5", "sha1", "sha256"]) as hasher:
        hasher.update(b"abc")
        assert hasher.digest() == {
            "md5": "900150983cd24fb0d6963f7d28e17f72",
            "sha1": "a9993e364706816aba3e25717850c26c9cd0d89d",
            "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        }
        # El hasher queda listo para otro flujo: el vacío da los hashes vacíos.
        assert hasher.digest()["md5"] == "d41d8cd98f00b204e9800998ecf8427e"


def test_all_algorithms_in_chunks():
    data = bytes(range(256)) * 5000
    with MultiHasher(ALGORITHMS) as hasher:
        for start in range(0, len(data), 7777):
            hasher.update(data[start:start + 7777])
        assert hasher.digest() == expected(data)


def test_normalize_algorithms():
    assert normalize_algorithms(["SHA256", "md5", "sha-1", "md5"]) == ("md5", "sha1", "sha256")
    assert normalize_algorithms(["SHA3-256"]) == ("sha3_256",)
    with pytest.raises(ValueError):
        normalize_algorithms(["crc32"])


# --- Archivo ----------------------------------------------------------------------------

def test_file_is_hashed_and_verified(evidence):
    target = evidence / "grande.bin"
    record = engine.acquire("file", str(target), ["md5", "sha1", "sha256", "sha512"], CASE)
    assert record["hashes"] == expected(target.read_bytes(), ["md5", "sha1", "sha256", "sha512"])
    assert record["size"] == target.stat().st_size
    assert record["case"]["examiner"] == "Perito de prueba"
    assert record["created"]["started"] <= record["created"]["finished"]

    automatic = record["verifications"][0]
    assert automatic["automatic"] is True
    assert automatic["result"] == "verified"
    assert automatic["hashes"] == record["hashes"]
    assert automatic["finished"] >= record["created"]["finished"]
    assert seal_ok(store.load_record(record["id"]))


def test_empty_file(evidence):
    record = engine.acquire("file", str(evidence / "vacio.dat"), ["md5"], CASE)
    assert record["hashes"]["md5"] == "d41d8cd98f00b204e9800998ecf8427e"
    assert record["verifications"][0]["result"] == "verified"


def test_examiner_is_required(evidence):
    with pytest.raises(ValueError):
        engine.acquire("file", str(evidence / "a.txt"), None, {"examiner": "  "})


def test_wrong_kind_or_missing_path(evidence):
    with pytest.raises(ValueError):
        engine.acquire("file", str(evidence), None, CASE)
    with pytest.raises(ValueError):
        engine.acquire("directory", str(evidence / "a.txt"), None, CASE)
    with pytest.raises(FileNotFoundError):
        engine.acquire("file", str(evidence / "no-existe"), None, CASE)


def test_later_verification_detects_change(evidence):
    target = evidence / "a.txt"
    record = engine.acquire("file", str(target), None, CASE)
    assert engine.verify(record, examiner="Otra persona")["result"] == "verified"

    target.write_bytes(b"hola!\n")
    entry = engine.verify(record, examiner="Otra persona")
    assert entry["result"] == "mismatch"
    assert entry["examiner"] == "Otra persona"
    assert len(store.load_record(record["id"])["verifications"]) == 3


def test_verify_copy_in_other_path(evidence, tmp_path):
    original = evidence / "sub" / "b.bin"
    record = engine.acquire("file", str(original), None, CASE)
    copy = tmp_path / "copia.bin"
    copy.write_bytes(original.read_bytes())
    entry = engine.verify(record, examiner="Perito", target=str(copy))
    assert entry["result"] == "verified"
    assert entry["target"] == str(copy.resolve())


def test_missing_evidence_gives_error_result(evidence):
    target = evidence / "a.txt"
    record = engine.acquire("file", str(target), None, CASE)
    target.unlink()
    entry = engine.verify(record, examiner="Perito")
    assert entry["result"] == "error"
    assert entry["error"]


def test_cancel(evidence):
    cancel = Event()
    cancel.set()
    with pytest.raises(Cancelled):
        engine.acquire("file", str(evidence / "grande.bin"), None, CASE, cancel=cancel)
    assert store.list_records() == []


# --- Carpeta ----------------------------------------------------------------------------

def test_directory_hash_is_manifest_hash(evidence):
    record = engine.acquire("directory", str(evidence), ["md5", "sha256"], CASE)
    files = record["details"]["files"]
    assert [f["path"] for f in files] == sorted(f["path"] for f in files)
    assert {f["path"] for f in files} == {"a.txt", "grande.bin", "sub/b.bin", "sub/más/ñandú.txt", "vacio.dat"}
    for item in files:
        assert item["hashes"] == expected((evidence / item["path"]).read_bytes(), ["md5", "sha256"])

    manifest = report.to_manifest(record, "sha256")
    assert manifest == manifest_text(files, "sha256")
    assert hashlib.sha256(manifest.encode()).hexdigest() == record["hashes"]["sha256"]
    assert record["size"] == sum((evidence / f["path"]).stat().st_size for f in files)
    assert record["verifications"][0]["result"] == "verified"


def test_directory_hash_does_not_depend_on_location(evidence, tmp_path):
    import shutil

    first = engine.acquire("directory", str(evidence), None, CASE)
    copy = tmp_path / "otra" / "copia"
    shutil.copytree(evidence, copy)
    second = engine.acquire("directory", str(copy), None, CASE)
    assert first["hashes"] == second["hashes"]


def test_directory_changes_are_listed(evidence):
    record = engine.acquire("directory", str(evidence), None, CASE)
    (evidence / "a.txt").write_bytes(b"modificado")
    (evidence / "vacio.dat").unlink()
    (evidence / "sub" / "nuevo.txt").write_bytes(b"nuevo")
    entry = engine.verify(record, examiner="Perito")
    assert entry["result"] == "mismatch"
    assert entry["differences"] == {"added": ["sub/nuevo.txt"], "removed": ["vacio.dat"], "modified": ["a.txt"]}


def test_renamed_file_changes_directory_hash(evidence):
    record = engine.acquire("directory", str(evidence), None, CASE)
    (evidence / "a.txt").rename(evidence / "a2.txt")
    assert engine.verify(record, examiner="Perito")["result"] == "mismatch"


# --- Imagen de disco ----------------------------------------------------------------------

def test_disk_image(tmp_path):
    image = tmp_path / "pendrive.dd"
    data = bytes(range(256)) * 4096 * 5  # 5 MiB, no múltiplo del bloque de lectura
    image.write_bytes(data)
    record = engine.acquire("disk", str(image), ["md5", "sha256"], CASE)
    assert record["hashes"] == expected(data, ["md5", "sha256"])
    assert record["source"]["kind"] == "image"
    assert record["details"]["sector_size"] == 512
    assert record["verifications"][0]["result"] == "verified"


def test_disk_rejects_folder(evidence):
    with pytest.raises(ValueError):
        engine.acquire("disk", str(evidence), None, CASE)


# --- Sello y cadena de custodia ------------------------------------------------------------

def test_seal_detects_edits(evidence):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    stored = store.load_record(record["id"])
    assert seal_ok(stored)
    stored["case"]["examiner"] = "Otra persona"
    assert not seal_ok(stored)
    stored["case"]["examiner"] = "Perito de prueba"
    stored["hashes"]["md5"] = "0" * 32
    assert not seal_ok(stored)


def test_custody_chain(evidence, isolated_home):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    engine.verify(record, examiner="Segunda persona")
    events = store.read_custody()
    assert [e["action"] for e in events] == ["created", "verified", "verified"]
    assert events[-1]["examiner"] == "Segunda persona"
    assert events[-1]["record_seal"] == compute_seal(store.load_record(record["id"]))
    assert store.check_custody() == {"ok": True, "events": 3, "broken_at": None, "reason": None}

    # Editar un evento rompe la cadena
    path = isolated_home / "custody.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    edited = json.loads(lines[1])
    edited["result"] = "mismatch"
    lines[1] = json.dumps(edited, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert store.check_custody() == {"ok": False, "events": 3, "broken_at": 2, "reason": "edited"}


def test_custody_detects_deleted_event(evidence, isolated_home):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    engine.verify(record, examiner="Perito")
    path = isolated_home / "custody.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:1] + lines[2:]) + "\n", encoding="utf-8")
    assert store.check_custody()["ok"] is False


def test_custody_detects_deleted_last_events(evidence, isolated_home):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    engine.verify(record, examiner="Perito")
    path = isolated_home / "custody.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")  # Quita solo el último
    assert store.check_custody() == {"ok": False, "events": 2, "broken_at": 3, "reason": "truncated"}


def test_custody_detects_truncation_even_without_the_anchor(evidence, isolated_home):
    engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    engine.acquire("file", str(evidence / "vacio.dat"), None, CASE)
    path = isolated_home / "custody.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")  # Quita la segunda evidencia
    (isolated_home / "custody.head.json").unlink()
    assert store.check_custody()["reason"] == "truncated"


def test_custody_without_anchor_from_older_version_is_valid(evidence, isolated_home):
    engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    (isolated_home / "custody.head.json").unlink()
    assert store.check_custody()["ok"] is True


def test_old_unsigned_record_without_event_does_not_break_the_chain(evidence, isolated_home):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    old = json.loads(json.dumps(record))
    del old["signature"]
    old["id"] = "a" * 32
    store.write_record(old)
    assert store.check_custody()["ok"] is True


def test_interrupted_save_never_leaves_a_record_without_its_event(evidence, monkeypatch):
    def killed(record):
        raise KeyboardInterrupt

    monkeypatch.setattr(store, "save_record", killed)
    with pytest.raises(KeyboardInterrupt):
        engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    assert [e["action"] for e in store.read_custody()] == ["created", "verified"]
    assert store.list_records() == []
    assert store.check_custody()["ok"] is True


def test_record_ids_are_validated():
    for bad in ("../custody", "x" * 32, ""):
        with pytest.raises(KeyError):
            store.load_record(bad)
