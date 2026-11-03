"""Publica una versión: firma SHA256SUMS.txt y crea la Release en GitHub.

    python scripts/release.py --init-key            # una sola vez: crea la clave de firma
    desktop\\build_windows.bat                       # dist\\ForensiX-Hash.exe + SHA256SUMS.txt
    python scripts/release.py --notes notas.md      # firma y publica vX.Y.Z (de forensix_hash/__init__.py)
    python scripts/release.py --dry-run             # solo firma, sin publicar
    python scripts/release.py --replace             # sustituye los archivos de la Release ya publicada

La clave privada vive en %USERPROFILE%\\.forensix\\update-ed25519.pem y NUNCA se sube al
repositorio. Guarda una copia de seguridad: sin ella las apps instaladas no aceptarán
actualizaciones nuevas. La clave pública está en forensix_hash/updater.py.
"""

import argparse
import base64
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from forensix_hash import __version__  # noqa: E402
from forensix_hash.updater import ASSET, PUBLIC_KEY, SIGNATURE, SUMS  # noqa: E402

KEY = Path.home() / ".forensix" / "update-ed25519.pem"
DIST = ROOT / "dist"


def init_key() -> None:
    if KEY.exists():
        sys.exit(f"Ya existe {KEY}. No se sobrescribe.")
    KEY.parent.mkdir(parents=True, exist_ok=True)
    private = Ed25519PrivateKey.generate()
    KEY.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    print(f"Clave privada: {KEY}  (haz una copia de seguridad)")
    print(f"Clave pública para forensix_hash/updater.py: PUBLIC_KEY = \"{base64.b64encode(public).decode()}\"")


def sign() -> Path:
    private = serialization.load_pem_private_key(KEY.read_bytes(), password=None)
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    if base64.b64encode(public).decode() != PUBLIC_KEY:
        sys.exit("La clave privada no corresponde a PUBLIC_KEY de forensix_hash/updater.py.")
    sums = DIST / SUMS
    if not (DIST / ASSET).exists() or not sums.exists():
        sys.exit("Falta dist\\ForensiX-Hash.exe o dist\\SHA256SUMS.txt: ejecuta desktop\\build_windows.bat.")
    signature = DIST / SIGNATURE
    signature.write_text(base64.b64encode(private.sign(sums.read_bytes())).decode() + "\n", encoding="ascii")
    print(f"Firmado: {signature}")
    return signature


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--init-key", action="store_true")
    parser.add_argument("--notes", help="archivo con las novedades")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true", help="sustituir los archivos de la Release de esta versión")
    args = parser.parse_args()

    if args.init_key:
        init_key()
        return
    signature = sign()
    if args.dry_run:
        return
    tag = f"v{__version__}"
    installer = DIST / f"ForensiX-Hash_{__version__}_x64-setup.exe"
    if not installer.exists():
        sys.exit(f"Falta {installer.name}: ejecuta desktop\\build_windows.bat.")
    files = [str(installer), str(DIST / ASSET), str(DIST / SUMS), str(signature)]
    if args.replace:
        # Misma versión: se sustituyen los archivos de la Release existente.
        subprocess.run(["gh", "release", "upload", tag, *files, "--clobber"], check=True)
        if args.notes:
            subprocess.run(["gh", "release", "edit", tag, "--notes-file", args.notes], check=True)
        return
    command = ["gh", "release", "create", tag, *files, "--title", f"ForensiX Hash {tag}"]
    command += ["--notes-file", args.notes] if args.notes else ["--generate-notes"]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
