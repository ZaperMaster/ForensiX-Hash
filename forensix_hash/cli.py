"""Línea de comandos de ForensiX Hash.

    python -m forensix_hash file  RUTA      --examiner "Nombre" [--case C-1] [--pdf CARPETA]
    python -m forensix_hash dir   CARPETA   --examiner "Nombre"
    python -m forensix_hash disk  \\\\.\\PhysicalDrive1 --examiner "Nombre"   (como administrador)
    python -m forensix_hash verify ID       --examiner "Nombre" [--target COPIA]
    python -m forensix_hash import informe.pdf          (registro de otro equipo)
    python -m forensix_hash list | disks | custody
"""

import argparse
import sys
from pathlib import Path
from threading import Event, Thread

from . import APP_NAME, __version__, devices, engine, pdf, report, signing, store
from .hasher import ALGORITHMS, DEFAULT_ALGORITHMS, Cancelled
from .progress import Progress
from .report import human_size

KIND_BY_COMMAND = {"file": "file", "dir": "directory", "disk": "disk"}
RESULT_TEXT = {"verified": "VERIFICADO", "mismatch": "NO COINCIDE", "error": "ERROR", "pending": "SIN VERIFICAR"}


def _show_progress(progress: Progress, done: Event) -> None:
    labels = {"scanning": "Listando", "hashing": "Calculando", "verifying": "Verificando"}
    while not done.wait(0.5):
        snap = progress.snapshot()
        if snap["phase"] not in labels:
            continue
        speed = snap["speed"] / 1024 / 1024
        files = f" {snap['files_done']}/{snap['files_total']} archivos" if snap["files_total"] > 1 else ""
        sys.stderr.write(f"\r{labels[snap['phase']]:<11} {snap['percent']:5.1f} %  {speed:7.1f} MB/s{files}   ")
        sys.stderr.flush()
    sys.stderr.write("\r" + " " * 70 + "\r")


def _run_with_progress(func, progress: Progress):
    done = Event()
    painter = Thread(target=_show_progress, args=(progress, done), daemon=True)
    painter.start()
    try:
        return func()
    finally:
        done.set()
        painter.join()


def _print_record(record: dict) -> None:
    print(f"\n{record['label']}")
    print(f"  Ruta       : {record['target']}")
    print(f"  Tamaño     : {human_size(record['size'])}")
    for algorithm in record["algorithms"]:
        print(f"  {ALGORITHMS[algorithm]:<11}: {record['hashes'][algorithm]}")
    last = record["verifications"][-1]
    print(f"  Resultado  : {RESULT_TEXT[last['result']]} ({last['finished']}, {last['examiner']})")
    if record.get("image"):
        print(f"  Imagen     : {RESULT_TEXT.get(record['image'].get('result'), '?')} {record['image']['path']}")
    print(f"  Registro   : {record['id']}")
    print(f"  Firma      : {signing.signature_status(record)} · {(record.get('signature') or {}).get('fingerprint', '')}")


def _write_reports(record: dict, outputs: list[str], lang: str) -> None:
    for output in outputs or []:
        path = Path(output)
        fmt = path.suffix.lstrip(".").lower()
        if fmt not in report.EXPORTS:
            raise SystemExit(f"Formato no soportado: {path.suffix} (usa {', '.join(report.EXPORTS)})")
        # newline="\n": el manifiesto debe dar el mismo hash que la carpeta también en Windows.
        path.write_text(report.export(record, fmt, store.record_custody(record["id"]), lang),
                        encoding="utf-8", newline="\n")
        store.log_event("exported", record, format=fmt)
        print(f"  Informe    : {path.resolve()}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forensix-hash", description=f"{APP_NAME}: hashes forenses verificados.")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (("file", "hash de un archivo"), ("dir", "hash de una carpeta"),
                               ("disk", "hash de un disco, volumen o imagen de disco")):
        sub = commands.add_parser(command, help=help_text)
        sub.add_argument("target")
        sub.add_argument("--examiner", required=True, help="quién realiza el hash")
        sub.add_argument("--case", default="", help="número de caso")
        sub.add_argument("--evidence", default="", help="número de evidencia")
        sub.add_argument("--organization", default="")
        sub.add_argument("--description", default="")
        sub.add_argument("--notes", default="")
        sub.add_argument("--algorithms", default=",".join(DEFAULT_ALGORITHMS),
                         help=f"separados por comas: {', '.join(ALGORITHMS)}")
        sub.add_argument("--pdf", metavar="CARPETA", help="guardar el informe PDF en esta carpeta")
        sub.add_argument("--timestamp", action="store_true", help="pedir un sello de tiempo externo (RFC 3161)")
        if command == "disk":
            sub.add_argument("--image", metavar="CARPETA", help="crear además la imagen forense .dd en esta carpeta")
        sub.add_argument("--out", action="append", help="informe a generar (.html, .txt, .json, .csv, .sha256…)")
        sub.add_argument("--lang", default="es", choices=["es", "en"])

    verify = commands.add_parser("verify", help="volver a verificar un registro")
    verify.add_argument("record_id")
    verify.add_argument("--examiner", required=True)
    verify.add_argument("--target", help="comprobar una copia en otra ruta")
    verify.add_argument("--notes", default="")
    verify.add_argument("--out", action="append")
    verify.add_argument("--lang", default="es", choices=["es", "en"])

    imported = commands.add_parser("import", help="importar un informe PDF de otro equipo")
    imported.add_argument("report")

    commands.add_parser("list", help="registros guardados")
    commands.add_parser("disks", help="discos y volúmenes del equipo")
    commands.add_parser("custody", help="comprobar la cadena de custodia")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    progress, cancel = Progress(), Event()

    try:
        if args.command in KIND_BY_COMMAND:
            case = {"examiner": args.examiner, "case_number": args.case, "evidence_number": args.evidence,
                    "organization": args.organization, "description": args.description, "notes": args.notes}
            kind = KIND_BY_COMMAND[args.command]
            folder = pdf.check_destination(kind, engine._resolve_target(kind, args.target), args.pdf) if args.pdf else None
            image = getattr(args, "image", None)
            record = _run_with_progress(lambda: engine.acquire(
                kind, args.target, args.algorithms.split(","), case, progress, cancel, image_folder=image), progress)
            _print_record(record)
            if args.timestamp:
                stamp = signing.timestamp_record(record)
                store.write_record(record)
                store.log_event("timestamped", record, tsa=stamp["tsa"], stamped=stamp["time"])
                print(f"  Sello tiempo: {stamp['time']} ({stamp['tsa']})")
            if folder:
                print(f"  Informe PDF: {pdf.save_report(record, folder, args.lang)}")
            _write_reports(record, args.out, args.lang)
            return 0 if record["verifications"][-1]["result"] == "verified" else 2

        if args.command == "verify":
            record = store.load_record(args.record_id)
            entry = _run_with_progress(lambda: engine.verify(
                record, args.examiner, args.target, progress, cancel, notes=args.notes), progress)
            _print_record(record)
            _write_reports(record, args.out, args.lang)
            return 0 if entry["result"] == "verified" else 2

        if args.command == "import":
            record, existing = pdf.import_report(Path(args.report).read_bytes())
            print(f"{'Ya estaba' if existing else 'Importado'}: {record['id']}  {record['label']}")
            return 0

        if args.command == "list":
            for item in store.list_records():
                print(f"{item['id']}  {RESULT_TEXT[item['status']]:<13} {item['created']}  {item['label']}")
            return 0

        if args.command == "disks":
            for disk in devices.list_devices():
                print(f"{disk['path']:<22} {disk['model']} · {disk['bus']} · {human_size(disk['size'])}"
                      f"{' · SISTEMA' if disk['system'] else ''}")
                for volume in disk["volumes"]:
                    print(f"    {volume['path']:<18} {volume['label']} {volume['filesystem']}")
            return 0

        if args.command == "custody":
            check = store.check_custody()
            print(f"Cadena de custodia: {'ÍNTEGRA' if check['ok'] else 'ROTA en el evento ' + str(check['broken_at'])}"
                  f" ({check['events']} eventos)")
            return 0 if check["ok"] else 2
    except KeyboardInterrupt:
        cancel.set()
        print("\nCancelado.", file=sys.stderr)
        return 130
    except Cancelled:
        return 130
    except (OSError, ValueError, KeyError, RuntimeError, signing.TimestampError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0
