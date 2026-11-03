"""Informes: contenido, escapado de HTML, formatos y CLI."""

import csv
import io
import json

from forensix_hash import cli, engine, report, store

from conftest import CASE


def test_html_report_contains_everything(evidence):
    case = {**CASE, "organization": "Lab", "description": "Pendrive <b>rojo</b>"}
    record = engine.acquire("file", str(evidence / "a.txt"), None, case)
    html = report.to_html(record, store.record_custody(record["id"]), "es")
    for text in ("VERIFICADO", "Perito de prueba", "T-1", "EV-1", record["hashes"]["sha256"],
                 record["seal"]["value"], "Cadena de custodia", "Firma de quien realiza el hash"):
        assert text in html
    assert "<b>rojo</b>" not in html and "&lt;b&gt;rojo&lt;/b&gt;" in html
    assert "<script" not in html


def test_english_report(evidence):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    html = report.to_html(record, None, "en")
    assert "VERIFIED" in html and "Performed by" in html


def test_mismatch_is_shown(evidence):
    record = engine.acquire("file", str(evidence / "a.txt"), None, CASE)
    (evidence / "a.txt").write_bytes(b"cambiado")
    engine.verify(record, examiner="Perito")
    assert "NO COINCIDE" in report.to_html(record)
    assert "NO COINCIDE" in report.to_text(record)


def test_json_csv_and_manifest(evidence):
    record = engine.acquire("directory", str(evidence), ["md5", "sha256"], CASE)
    assert json.loads(report.to_json(record))["id"] == record["id"]

    rows = list(csv.reader(io.StringIO(report.to_csv(record)), delimiter=";"))
    assert rows[0] == ["path", "size", "MD5", "SHA-256", "error"]
    assert len(rows) == 1 + len(record["details"]["files"])

    manifest = report.to_manifest(record, "md5").splitlines()
    assert manifest[0].endswith("  a.txt") and len(manifest[0].split("  ")[0]) == 32


def test_filename_is_safe(evidence):
    record = engine.acquire("file", str(evidence / "a.txt"), None, {**CASE, "evidence_number": "EV/1:<x>"})
    name = report.filename(record, "html")
    assert name.endswith(".html") and "/" not in name and ":" not in name and "<" not in name


def test_cli_file_and_reports(evidence, tmp_path, capsys):
    out = tmp_path / "informe.html"
    code = cli.main(["file", str(evidence / "a.txt"), "--examiner", "Perito CLI", "--case", "C-9",
                     "--out", str(out), "--out", str(tmp_path / "informe.sha256")])
    assert code == 0
    printed = capsys.readouterr().out
    assert "VERIFICADO" in printed
    assert "Perito CLI" in out.read_text(encoding="utf-8")
    assert (tmp_path / "informe.sha256").read_text().endswith("  a.txt\n")

    record_id = store.list_records()[0]["id"]
    (evidence / "a.txt").write_bytes(b"otro")
    assert cli.main(["verify", record_id, "--examiner", "Perito CLI"]) == 2
    assert cli.main(["custody"]) == 0


def test_cli_manifest_hash_matches_folder_hash(evidence, tmp_path):
    import hashlib

    manifest = tmp_path / "carpeta.sha256"
    assert cli.main(["dir", str(evidence), "--examiner", "Perito", "--out", str(manifest)]) == 0
    record = store.load_record(store.list_records()[0]["id"])
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == record["hashes"]["sha256"]


def test_cli_errors(tmp_path, capsys):
    assert cli.main(["file", str(tmp_path / "nada"), "--examiner", "X"]) == 1
    assert "Error" in capsys.readouterr().err
