"""Firma digital de los registros y sello de tiempo externo.

- Firma: cada equipo y usuario tiene su propia clave Ed25519, que se crea la primera
  vez. Firma el sello del registro, así que cubre todo su contenido. En Windows la
  clave privada se guarda cifrada con DPAPI, ligada a la cuenta del usuario. La huella
  de la clave pública sale en el informe: quien falsifique un registro en otro equipo
  tendrá otra huella.
- Sello de tiempo (RFC 3161): una autoridad externa firma que ese sello ya existía en
  esa fecha, así que la fecha no depende del reloj del equipo. Solo se envía un hash,
  nunca datos de la evidencia. El token se guarda y se puede comprobar con
  `openssl ts -verify`.

Quien controle la cuenta del usuario podría firmar con su clave. Pero no podría
conseguir un sello de tiempo con fecha anterior.
"""

import base64
import ctypes
import hashlib
import os
import re
import secrets
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import __version__
from .record import compute_seal

KEY_FILE = "signing-key.bin"
PURPOSE = b"forensix-hash/1:"
TSA_URLS = ("http://timestamp.digicert.com", "https://freetsa.org/tsr")
TSA_TIMEOUT = 10
SHA256_OID = bytes.fromhex("608648016503040201")


class TimestampError(Exception):
    pass


# --- Clave ------------------------------------------------------------------------------

def _dpapi(data: bytes, protect: bool) -> bytes:
    """Cifra o descifra con la cuenta del usuario de Windows (DPAPI)."""

    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_char))]

    buffer = ctypes.create_string_buffer(data, len(data))
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    target = Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    call = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not call(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)):
        raise OSError(ctypes.get_last_error(), "No se pudo acceder a la clave de firma.")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.WinDLL("kernel32").LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


def _private_key(home: Path) -> Ed25519PrivateKey:
    path = home / KEY_FILE
    if path.exists():
        raw = path.read_bytes()
        return Ed25519PrivateKey.from_private_bytes(_dpapi(raw, False) if os.name == "nt" else raw)
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                            serialization.NoEncryption())
    path.write_bytes(_dpapi(raw, True) if os.name == "nt" else raw)
    if os.name != "nt":
        path.chmod(0o600)
    return key


def fingerprint(public_key: bytes) -> str:
    digest = hashlib.sha256(public_key).hexdigest()[:32].upper()
    return " ".join(digest[i:i + 4] for i in range(0, 32, 4))


def identity(home: Path) -> dict:
    public = _private_key(home).public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {"algorithm": "ed25519", "public_key": base64.b64encode(public).decode(), "fingerprint": fingerprint(public)}


# --- Firma ------------------------------------------------------------------------------

def sign_record(record: dict, home: Path) -> dict:
    """Firma el sello actual del registro."""

    message = PURPOSE + bytes.fromhex(record["seal"]["value"])
    record["signature"] = {**identity(home), "value": base64.b64encode(_private_key(home).sign(message)).decode()}
    return record


def signature_status(record: dict) -> str:
    """valid | invalid | missing. Comprueba firma y sello contra el contenido actual."""

    signature = record.get("signature")
    if not signature:
        return "missing"
    try:
        public = base64.b64decode(signature["public_key"])
        message = PURPOSE + bytes.fromhex(compute_seal(record))
        Ed25519PublicKey.from_public_bytes(public).verify(base64.b64decode(signature["value"]), message)
    except (InvalidSignature, ValueError, KeyError, TypeError):
        return "invalid"
    return "valid" if signature.get("fingerprint") == fingerprint(public) else "invalid"


# --- Sello de tiempo (RFC 3161) -------------------------------------------------------------

def _der(tag: int, content: bytes) -> bytes:
    size = len(content)
    if size < 0x80:
        return bytes([tag, size]) + content
    encoded = size.to_bytes((size.bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(encoded)]) + encoded + content


def build_request(digest: bytes, nonce: bytes) -> bytes:
    algorithm = _der(0x30, _der(0x06, SHA256_OID) + _der(0x05, b""))
    imprint = _der(0x30, algorithm + _der(0x04, digest))
    return _der(0x30, _der(0x02, b"\x01") + imprint + _der(0x02, nonce) + _der(0x01, b"\xff"))


def _read_header(data: bytes, offset: int) -> tuple[int, int, int]:
    """(etiqueta, inicio del contenido, longitud) de un elemento DER."""

    tag, first = data[offset], data[offset + 1]
    if first < 0x80:
        return tag, offset + 2, first
    count = first & 0x7F
    return tag, offset + 2 + count, int.from_bytes(data[offset + 2:offset + 2 + count], "big")


def parse_response(data: bytes, digest: bytes, nonce: bytes) -> tuple[bytes, str]:
    """Comprueba la respuesta de la autoridad y devuelve (token, fecha ISO en UTC)."""

    try:
        tag, start, _ = _read_header(data, 0)
        status_tag, status_start, status_size = _read_header(data, start)
        int_tag, int_start, int_size = _read_header(data, status_start)
        if tag != 0x30 or status_tag != 0x30 or int_tag != 0x02:
            raise TimestampError("Respuesta de sello de tiempo no válida.")
        status = int.from_bytes(data[int_start:int_start + int_size], "big")
        token = data[status_start + status_size:]
    except IndexError as error:
        raise TimestampError("Respuesta de sello de tiempo no válida.") from error
    if status not in (0, 1) or not token:
        raise TimestampError("La autoridad de sellado rechazó la petición.")
    position = token.find(digest)
    if position < 0 or nonce not in token:
        raise TimestampError("El sello de tiempo no corresponde a este registro.")
    moment = re.search(rb"\x18[\x0f-\x18](\d{14})(?:\.\d+)?Z", token[position:])
    if not moment:
        raise TimestampError("Respuesta de sello de tiempo no válida.")
    when = datetime.strptime(moment.group(1).decode(), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    return token, when.isoformat(timespec="seconds")


def _post(url: str, body: bytes) -> bytes:
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/timestamp-query", "User-Agent": f"ForensiX-Hash/{__version__}"})
    with urllib.request.urlopen(request, timeout=TSA_TIMEOUT) as response:  # noqa: S310 (URL fija)
        return response.read(1024 * 1024)


def timestamp_record(record: dict, post=None) -> dict:
    """Pide un sello de tiempo para el sello actual y lo añade al registro."""

    post = post or _post
    seal_value = record["seal"]["value"]
    digest = bytes.fromhex(seal_value)
    last_error = None
    for url in TSA_URLS:
        nonce = b"\x01" + secrets.token_bytes(8)
        try:
            token, when = parse_response(post(url, build_request(digest, nonce)), digest, nonce)
        except (OSError, TimestampError) as error:
            last_error = error
            continue
        entry = {"seal": seal_value, "tsa": url, "time": when, "token": base64.b64encode(token).decode()}
        record.setdefault("timestamps", []).append(entry)
        return entry
    raise TimestampError(f"No se pudo obtener el sello de tiempo: {last_error}")
