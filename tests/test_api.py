"""API web: flujo completo, protecciones de la API local e importación de informes."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from web.server import app

from conftest import CASE

HEADERS = {"X-ForensiX": "1"}


@pytest.fixture
def client():
    return TestClient(app)


def wait_job(client, job_id):
    for _ in range(200):
        job = client.get(f"/api/jobs/{job_id}", headers=HEADERS).json()
        if job["state"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("La operación no terminó")


def acquire(client, target, kind="directory"):
    response = client.post("/api/jobs", headers=HEADERS,
                           json={"kind": kind, "target": str(target), "algorithms": ["md5", "sha256"], "case": CASE})
    assert response.status_code == 200, response.text
    job = wait_job(client, response.json()["id"])
    assert job["state"] == "done", job
    return job


def test_index_and_info(client):
    assert client.get("/").status_code == 200
    info = client.get("/api/info", headers=HEADERS).json()
    assert info["app"] == "ForensiX Hash"
    assert {a["id"] for a in info["algorithms"] if a["default"]} == {"md5", "sha1", "sha256"}


def test_api_requires_header_and_local_host(client):
    assert client.get("/api/info").status_code == 403
    assert client.get("/api/info", headers={**HEADERS, "Host": "evil.example"}).status_code == 403
    assert client.get("/api/info", headers={**HEADERS, "Host": "127.0.0.1:8000"}).status_code == 200
    assert client.get("/api/info", headers={**HEADERS, "Host": "[::1]:8000"}).status_code == 200


def test_full_flow(client, evidence):
    job = acquire(client, evidence)
    assert job["result"] == "verified"
    record_id = job["record_id"]

    records = client.get("/api/records", headers=HEADERS).json()
    assert records[0]["id"] == record_id and records[0]["status"] == "verified" and records[0]["seal_ok"]

    detail = client.get(f"/api/records/{record_id}", headers=HEADERS).json()
    assert detail["seal_ok"] and len(detail["custody"]) == 2

    (evidence / "a.txt").write_bytes(b"cambio")
    response = client.post(f"/api/records/{record_id}/verify", headers=HEADERS, json={"examiner": "Segunda"})
    assert wait_job(client, response.json()["id"])["result"] == "mismatch"

    export = client.post(f"/api/records/{record_id}/export", headers=HEADERS, json={"format": "html", "lang": "en"}).json()
    assert "MISMATCH" in export["content"] and export["filename"].endswith(".html")
    assert client.post(f"/api/records/{record_id}/export", headers=HEADERS,
                       json={"format": "pdf"}).json() == {"logged": True}
    page = client.get(f"/report/{record_id}?print=1")
    assert page.status_code == 200 and "print()" in page.text

    custody = client.get("/api/custody", headers=HEADERS).json()
    assert custody["check"]["ok"]
    assert [e["action"] for e in custody["events"]] == ["created", "verified", "verified", "exported", "exported"]


def test_validation_errors(client, evidence):
    no_examiner = {"kind": "file", "target": str(evidence / "a.txt"), "case": {"examiner": ""}}
    assert client.post("/api/jobs", headers=HEADERS, json=no_examiner).status_code == 400
    missing = {"kind": "file", "target": str(evidence / "x"), "case": CASE}
    assert client.post("/api/jobs", headers=HEADERS, json=missing).status_code == 404
    bad_kind = {"kind": "memory", "target": "x", "case": CASE}
    assert client.post("/api/jobs", headers=HEADERS, json=bad_kind).status_code == 422
    assert client.get("/api/records/../../etc", headers=HEADERS).status_code == 404
    assert client.get("/api/records/" + "a" * 32, headers=HEADERS).status_code == 404


def test_import_report(client, evidence):
    job = acquire(client, evidence / "a.txt", kind="file")
    record = client.get(f"/api/records/{job['record_id']}", headers=HEADERS).json()["record"]
    client.delete(f"/api/records/{job['record_id']}", headers=HEADERS)

    tampered = json.loads(json.dumps(record))
    tampered["hashes"]["md5"] = "0" * 32
    response = client.post("/api/import", headers=HEADERS, content=json.dumps(tampered))
    assert response.status_code == 422

    response = client.post("/api/import", headers=HEADERS, content=json.dumps(record))
    assert response.status_code == 200 and response.json()["seal_ok"]
    assert client.post("/api/import", headers=HEADERS, content=b"{nope").status_code == 400


def test_browse(client, evidence):
    roots = client.get("/api/browse", headers=HEADERS).json()
    assert roots["entries"]
    listing = client.get("/api/browse", params={"path": str(evidence)}, headers=HEADERS).json()
    names = [e["name"] for e in listing["entries"]]
    assert names[0] == "sub" and "a.txt" in names
