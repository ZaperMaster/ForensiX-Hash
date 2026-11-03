"""Informes de un registro: HTML (imprimible y para PDF), texto, JSON, CSV y manifiestos.

El HTML no carga nada de fuera: se puede abrir sin conexión, adjuntar a un
expediente o imprimir a PDF tal cual.
"""

import csv
import io
import json
from datetime import datetime
from html import escape

from . import APP_NAME, REPO_URL, __version__
from .hasher import ALGORITHMS
from .record import seal_ok, status
from .sources import manifest_text

TEXTS = {
    "es": {
        "title": "Informe de hash forense",
        "subtitle": "Cálculo y verificación de la integridad de una evidencia digital",
        "generated": "Informe generado",
        "result": "Resultado",
        "verified": "VERIFICADO", "mismatch": "NO COINCIDE", "error": "ERROR DE LECTURA", "pending": "SIN VERIFICAR",
        "verified_text": "La evidencia se ha vuelto a leer y da exactamente los mismos hashes.",
        "mismatch_text": "La evidencia ha cambiado: los hashes no coinciden con los originales.",
        "error_text": "No se pudo leer la evidencia para verificarla.",
        "pending_text": "Todavía no se ha verificado.",
        "case": "Datos del caso",
        "case_number": "Nº de caso", "evidence_number": "Nº de evidencia", "examiner": "Realizado por",
        "organization": "Organización / unidad", "description": "Descripción", "notes": "Notas",
        "evidence": "Evidencia",
        "kind": "Tipo", "file": "Archivo", "directory": "Carpeta", "disk": "Disco o imagen",
        "image": "Imagen de disco", "volume": "Volumen",
        "path": "Ruta", "size": "Tamaño", "model": "Modelo", "serial": "Nº de serie", "bus": "Conexión",
        "sector_size": "Tamaño de sector", "partition_style": "Tabla de particiones", "filesystem": "Sistema de archivos",
        "label": "Etiqueta", "created_fs": "Creado (sistema de archivos)", "modified_fs": "Modificado (sistema de archivos)",
        "accessed_fs": "Último acceso (sistema de archivos)", "files": "Archivos", "hashed": "Hasheados",
        "errors": "Errores de lectura", "links": "Enlaces (no seguidos)", "bad_sectors": "Sectores ilegibles (leídos como ceros)",
        "changed": "El archivo cambió mientras se leía",
        "hashes": "Hashes", "algorithm": "Algoritmo", "value": "Valor",
        "dir_hash_note": "En una carpeta, cada hash es el del manifiesto (archivo «hash  ruta» ordenado por ruta) "
                         "que se adjunta al final y que se puede exportar como .md5/.sha1/.sha256.",
        "timeline": "Cronología",
        "acquisition": "Cálculo del hash", "verification": "Verificación", "automatic": "automática",
        "started": "Inicio", "finished": "Fin", "duration": "Duración", "by": "Por", "host": "Equipo",
        "checked_target": "Evidencia comprobada",
        "differences": "Diferencias", "added": "Añadidos", "removed": "Eliminados", "modified": "Modificados",
        "environment": "Equipo y herramienta", "tool": "Herramienta", "user": "Usuario del sistema",
        "os": "Sistema operativo", "admin": "Administrador", "yes": "Sí", "no": "No",
        "custody": "Cadena de custodia", "event": "Evento", "time": "Fecha y hora",
        "created": "Hash creado", "verified_event": "Verificado", "exported": "Informe exportado",
        "imported": "Informe importado", "deleted": "Registro eliminado",
        "seal": "Sello del registro", "seal_ok": "Íntegro: el registro no se ha modificado desde que se creó.",
        "seal_bad": "MODIFICADO: el contenido del registro no coincide con su sello.",
        "seal_note": "SHA-256 del registro en JSON canónico. Sirve para detectar cambios en el informe JSON.",
        "manifest": "Manifiesto de archivos", "file_error": "error",
        "signatures": "Firmas", "sign_examiner": "Firma de quien realiza el hash", "sign_witness": "Firma del testigo / custodio",
        "footer": "Generado con {app} {version}",
        "record_id": "Identificador del registro",
    },
    "en": {
        "title": "Forensic hash report",
        "subtitle": "Calculation and verification of the integrity of digital evidence",
        "generated": "Report generated",
        "result": "Result",
        "verified": "VERIFIED", "mismatch": "MISMATCH", "error": "READ ERROR", "pending": "NOT VERIFIED",
        "verified_text": "The evidence was read again and produced exactly the same hashes.",
        "mismatch_text": "The evidence has changed: the hashes do not match the originals.",
        "error_text": "The evidence could not be read to verify it.",
        "pending_text": "Not verified yet.",
        "case": "Case details",
        "case_number": "Case number", "evidence_number": "Evidence number", "examiner": "Performed by",
        "organization": "Organization / unit", "description": "Description", "notes": "Notes",
        "evidence": "Evidence",
        "kind": "Type", "file": "File", "directory": "Folder", "disk": "Disk or image",
        "image": "Disk image", "volume": "Volume",
        "path": "Path", "size": "Size", "model": "Model", "serial": "Serial number", "bus": "Bus",
        "sector_size": "Sector size", "partition_style": "Partition table", "filesystem": "File system",
        "label": "Label", "created_fs": "Created (file system)", "modified_fs": "Modified (file system)",
        "accessed_fs": "Last accessed (file system)", "files": "Files", "hashed": "Hashed",
        "errors": "Read errors", "links": "Links (not followed)", "bad_sectors": "Unreadable sectors (read as zeros)",
        "changed": "The file changed while being read",
        "hashes": "Hashes", "algorithm": "Algorithm", "value": "Value",
        "dir_hash_note": "For a folder, each hash is the hash of the manifest (a \"hash  path\" file sorted by path) "
                         "attached at the end, which can be exported as .md5/.sha1/.sha256.",
        "timeline": "Timeline",
        "acquisition": "Hash calculation", "verification": "Verification", "automatic": "automatic",
        "started": "Start", "finished": "End", "duration": "Duration", "by": "By", "host": "Computer",
        "checked_target": "Evidence checked",
        "differences": "Differences", "added": "Added", "removed": "Removed", "modified": "Modified",
        "environment": "Computer and tool", "tool": "Tool", "user": "System user",
        "os": "Operating system", "admin": "Administrator", "yes": "Yes", "no": "No",
        "custody": "Chain of custody", "event": "Event", "time": "Date and time",
        "created": "Hash created", "verified_event": "Verified", "exported": "Report exported",
        "imported": "Report imported", "deleted": "Record deleted",
        "seal": "Record seal", "seal_ok": "Intact: the record has not been modified since it was created.",
        "seal_bad": "MODIFIED: the record content does not match its seal.",
        "seal_note": "SHA-256 of the record as canonical JSON. Used to detect changes to the JSON report.",
        "manifest": "File manifest", "file_error": "error",
        "signatures": "Signatures", "sign_examiner": "Signature of the person performing the hash",
        "sign_witness": "Signature of the witness / custodian",
        "footer": "Generated with {app} {version}",
        "record_id": "Record ID",
    },
}


def texts(lang: str) -> dict:
    return TEXTS.get(lang, TEXTS["es"])


def human_size(size: int | None, lang: str = "es") -> str:
    if size is None:
        return ""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            text = f"{value:.0f} {unit}" if unit == "B" else f"{value:.2f} {unit}"
            return (text.replace(".", ",") if lang == "es" else text) + f" ({size:,} bytes)".replace(
                ",", "." if lang == "es" else ",")
        value /= 1024
    return str(size)


def human_duration(seconds: float | None) -> str:
    if seconds is None:
        return ""
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}h {minutes:02d}m {secs:02d}s" if hours else f"{minutes}m {secs:02d}s"


def _generated() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _action(event: dict, t: dict) -> str:
    action = event.get("action")
    if action == "created":
        return t["created"]
    if action == "verified":
        text = f"{t['verified_event']}: {t.get(event.get('result'), event.get('result'))}"
        return text + (f" ({t['automatic']})" if event.get("automatic") else "")
    if action == "exported":
        return f"{t['exported']} ({event.get('format', '')})"
    if action in ("imported", "deleted"):
        return t[action]
    return str(action)


def evidence_rows(record: dict, t: dict, lang: str) -> list[tuple[str, str]]:
    source = record.get("source") or {}
    kind = record["kind"]
    kind_label = t[kind]
    if kind == "disk":
        kind_label = {"image": t["image"], "volume": t["volume"]}.get(source.get("kind"), t["disk"])
    rows = [(t["kind"], kind_label), (t["path"], record["target"]), (t["size"], human_size(record.get("size"), lang))]
    for key in ("model", "serial", "bus", "partition_style", "filesystem", "label"):
        if source.get(key):
            rows.append((t[key], str(source[key])))
    if source.get("disk"):
        disk = source["disk"]
        rows.append((t["disk"], f"{disk.get('model', '')} · {t['serial']} {disk.get('serial', '')} · {disk.get('path', '')}"))
    details = record.get("details") or {}
    if details.get("sector_size"):
        rows.append((t["sector_size"], f"{details['sector_size']} bytes"))
    times = source.get("times") or {}
    for key, label in (("created", "created_fs"), ("modified", "modified_fs"), ("accessed", "accessed_fs")):
        if times.get(key):
            rows.append((t[label], times[key]))
    totals = details.get("totals")
    if totals:
        rows += [(t["files"], str(totals["files"])), (t["hashed"], str(totals["hashed"])),
                 (t["errors"], str(totals["errors"])), (t["links"], str(totals["links"]))]
    if details.get("bad_sectors"):
        rows.append((t["bad_sectors"], str(details["bad_sectors"]["count"])))
    if details.get("changed_while_reading"):
        rows.append((t["changed"], t["yes"]))
    return rows


# --- HTML ----------------------------------------------------------------------------

_CSS = """
:root{--ink:#0f172a;--muted:#5b6476;--line:#dfe3ea;--soft:#f5f7fa;--accent:#0e7c86;--ok:#0f7b48;--bad:#b42318;--warn:#a15c07}
*{box-sizing:border-box}body{margin:0;background:#fff;color:var(--ink);font:13px/1.5 "Segoe UI",system-ui,-apple-system,sans-serif}
main{max-width:960px;margin:0 auto;padding:32px 36px}
header{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;border-bottom:3px solid var(--ink);padding-bottom:16px}
.brand{display:flex;gap:12px;align-items:center}.brand b{font-size:20px;letter-spacing:.3px}.brand span{color:var(--accent)}
h1{font-size:22px;margin:18px 0 2px}.sub{color:var(--muted);margin:0}
.meta{text-align:right;color:var(--muted);font-size:12px}
.verdict{display:flex;gap:16px;align-items:center;margin:22px 0;padding:14px 18px;border-radius:10px;border:1px solid var(--line);background:var(--soft)}
.badge{font-weight:700;letter-spacing:.6px;padding:6px 12px;border-radius:6px;color:#fff;white-space:nowrap}
.verified .badge{background:var(--ok)}.mismatch .badge,.error .badge{background:var(--bad)}.pending .badge{background:var(--warn)}
h2{font-size:14px;text-transform:uppercase;letter-spacing:.8px;color:var(--accent);margin:26px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;padding:6px 8px;border-bottom:1px solid var(--line)}
th{width:32%;color:var(--muted);font-weight:600}thead th{width:auto;background:var(--soft)}
.mono,code{font-family:Consolas,"Cascadia Mono",monospace;font-size:12px;word-break:break-all}
.note{color:var(--muted);font-size:12px;margin:6px 0 0}
.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}
.sign{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-top:12px}.sign div{border-top:1px solid var(--ink);padding-top:6px;margin-top:56px;color:var(--muted)}
footer{margin-top:32px;color:var(--muted);font-size:11px;border-top:1px solid var(--line);padding-top:10px}
.manifest td{font-size:11px;padding:3px 6px}
@media print{main{padding:0}h2{break-after:avoid}tr{break-inside:avoid}.verdict{break-inside:avoid}}
@page{margin:16mm 14mm}
"""

LOGO_SVG = (
    '<svg width="40" height="40" viewBox="0 0 64 64" aria-hidden="true">'
    '<rect width="64" height="64" rx="14" fill="#0b1220"/>'
    '<path d="M32 9 50 16v14c0 12-7.6 21-18 25-10.4-4-18-13-18-25V16z" fill="none" stroke="#2dd4bf" stroke-width="3.5" stroke-linejoin="round"/>'
    '<path d="M27 22l-3 20M38 22l-3 20M21 28h22M20 36h22" stroke="#e2e8f0" stroke-width="3.2" stroke-linecap="round"/>'
    '</svg>'
)


def _rows(rows) -> str:
    return "".join(f"<tr><th>{escape(k)}</th><td>{escape(str(v))}</td></tr>" for k, v in rows if v not in (None, ""))


def to_html(record: dict, custody: list[dict] | None = None, lang: str = "es",
            include_manifest: bool = True) -> str:
    t = texts(lang)
    result = status(record)
    hashes_rows = "".join(
        f"<tr><th>{escape(ALGORITHMS[a])}</th><td class='mono'>{escape(record['hashes'][a])}</td></tr>"
        for a in record["algorithms"]
    )
    case = record["case"]
    case_rows = _rows((t[name], case.get(name)) for name in
                      ("case_number", "evidence_number", "examiner", "organization", "description", "notes"))

    created = record["created"]
    timeline = [
        f"<tr><td>{escape(t['acquisition'])}</td><td>{escape(created['started'])}</td>"
        f"<td>{escape(created['finished'])}</td><td>{human_duration(created.get('duration'))}</td>"
        f"<td>{escape(case.get('examiner', ''))}</td><td>—</td></tr>"
    ]
    differences_html = ""
    for entry in record.get("verifications", []):
        label = f"{t['verification']} {entry['number']}" + (f" ({t['automatic']})" if entry.get("automatic") else "")
        css = "ok" if entry["result"] == "verified" else "bad"
        timeline.append(
            f"<tr><td>{escape(label)}</td><td>{escape(entry['started'])}</td><td>{escape(entry['finished'])}</td>"
            f"<td>{human_duration(entry.get('duration'))}</td><td>{escape(entry.get('examiner', ''))}</td>"
            f"<td class='{css}'>{escape(t.get(entry['result'], entry['result']))}</td></tr>"
        )
        if entry.get("target") and entry["target"] != record["target"]:
            timeline.append(f"<tr><td></td><td colspan='5' class='note'>{escape(t['checked_target'])}: "
                            f"<span class='mono'>{escape(entry['target'])}</span></td></tr>")
        if entry.get("error"):
            timeline.append(f"<tr><td></td><td colspan='5' class='bad'>{escape(entry['error'])}</td></tr>")
        if entry.get("result") == "mismatch" and entry.get("hashes"):
            changed = "".join(
                f"<div class='mono'>{escape(ALGORITHMS[a])}: {escape(v)}</div>"
                for a, v in entry["hashes"].items() if v != record["hashes"].get(a)
            )
            timeline.append(f"<tr><td></td><td colspan='5'>{changed}</td></tr>")
        for key in ("added", "removed", "modified"):
            items = (entry.get("differences") or {}).get(key)
            if items:
                differences_html += (f"<p><b>{escape(t['verification'])} {entry['number']} · {escape(t[key])} "
                                     f"({len(items)})</b></p><div class='mono'>"
                                     + "<br>".join(escape(i) for i in items[:200]) + "</div>")

    env = record.get("environment") or {}
    env_rows = _rows([
        (t["tool"], f"{env.get('tool', APP_NAME)} {env.get('version', '')}"),
        (t["host"], env.get("host")), (t["user"], env.get("user")), (t["os"], env.get("os")),
        (t["admin"], t["yes"] if env.get("admin") else t["no"]),
    ])

    custody_html = ""
    if custody:
        custody_html = (
            f"<h2>{escape(t['custody'])}</h2><table><thead><tr><th>#</th><th>{escape(t['time'])}</th>"
            f"<th>{escape(t['event'])}</th><th>{escape(t['by'])}</th><th>Hash</th></tr></thead><tbody>"
            + "".join(
                f"<tr><td>{e.get('seq')}</td><td>{escape(e.get('time', ''))}</td><td>{escape(_action(e, t))}</td>"
                f"<td>{escape(e.get('examiner', ''))}</td><td class='mono'>{escape(e.get('hash', '')[:16])}…</td></tr>"
                for e in custody)
            + "</tbody></table>"
        )

    manifest_html = ""
    if include_manifest and record["kind"] == "directory":
        main_alg = "sha256" if "sha256" in record["algorithms"] else record["algorithms"][-1]
        rows = "".join(
            f"<tr><td>{escape(f['path'])}</td><td>{f['size']:,}</td><td class='mono'>"
            f"{escape(f['hashes'][main_alg]) if 'hashes' in f else escape(t['file_error'] + ': ' + f.get('error', ''))}"
            f"</td></tr>"
            for f in record["details"]["files"]
        )
        skipped = "".join(f"<tr><td>{escape(s['path'])}</td><td></td><td class='bad'>{escape(s['error'])}</td></tr>"
                          for s in record["details"]["skipped"])
        manifest_html = (f"<h2>{escape(t['manifest'])} ({escape(ALGORITHMS[main_alg])})</h2>"
                         f"<table class='manifest'><thead><tr><th>{escape(t['path'])}</th><th>Bytes</th>"
                         f"<th>{escape(ALGORITHMS[main_alg])}</th></tr></thead><tbody>{rows}{skipped}</tbody></table>")

    sealed = seal_ok(record)
    seal_value = (record.get("seal") or {}).get("value", "")
    title = f"{t['title']} · {record['case'].get('case_number') or record['label']}"

    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{_CSS}</style></head><body><main>
<header><div><div class="brand">{LOGO_SVG}<b>Forensi<span>X</span> Hash</b></div>
<h1>{escape(t['title'])}</h1><p class="sub">{escape(t['subtitle'])}</p></div>
<div class="meta">{escape(t['generated'])}<br><b>{_generated()}</b><br><br>{escape(t['record_id'])}<br>
<span class="mono">{escape(record['id'])}</span></div></header>

<div class="verdict {result}"><span class="badge">{escape(t[result])}</span><div>{escape(t[result + '_text'])}</div></div>

<h2>{escape(t['case'])}</h2><table>{case_rows}</table>
<h2>{escape(t['evidence'])}</h2><table>{_rows(evidence_rows(record, t, lang))}</table>
<h2>{escape(t['hashes'])}</h2><table>{hashes_rows}</table>
{f"<p class='note'>{escape(t['dir_hash_note'])}</p>" if record['kind'] == 'directory' else ''}
<h2>{escape(t['timeline'])}</h2>
<table><thead><tr><th></th><th>{escape(t['started'])}</th><th>{escape(t['finished'])}</th><th>{escape(t['duration'])}</th>
<th>{escape(t['by'])}</th><th>{escape(t['result'])}</th></tr></thead><tbody>{''.join(timeline)}</tbody></table>
{f"<h2>{escape(t['differences'])}</h2>{differences_html}" if differences_html else ''}
<h2>{escape(t['environment'])}</h2><table>{env_rows}</table>
{custody_html}
<h2>{escape(t['seal'])}</h2>
<p class="{'ok' if sealed else 'bad'}">{escape(t['seal_ok'] if sealed else t['seal_bad'])}</p>
<p class="mono">SHA-256: {escape(seal_value)}</p><p class="note">{escape(t['seal_note'])}</p>
<h2>{escape(t['signatures'])}</h2>
<div class="sign"><div>{escape(t['sign_examiner'])}<br>{escape(case.get('examiner', ''))}</div><div>{escape(t['sign_witness'])}</div></div>
{manifest_html}
<footer>{escape(t['footer'].format(app=APP_NAME, version=__version__))} · {escape(REPO_URL)}</footer>
</main></body></html>"""


# --- Texto, JSON, CSV y manifiestos ---------------------------------------------------

def to_text(record: dict, custody: list[dict] | None = None, lang: str = "es") -> str:
    t = texts(lang)
    lines = [f"{APP_NAME} {__version__} — {t['title']}", "=" * 72,
             f"{t['generated']}: {_generated()}", f"{t['record_id']}: {record['id']}", "",
             f"{t['result']}: {t[status(record)]}", ""]

    def section(name, rows):
        lines.extend([name.upper(), "-" * len(name)])
        width = max((len(k) for k, v in rows if v), default=0)
        lines.extend(f"{k.ljust(width)} : {v}" for k, v in rows if v not in (None, ""))
        lines.append("")

    section(t["case"], [(t[n], record["case"].get(n)) for n in
                        ("case_number", "evidence_number", "examiner", "organization", "description", "notes")])
    section(t["evidence"], evidence_rows(record, t, lang))
    section(t["hashes"], [(ALGORITHMS[a], record["hashes"][a]) for a in record["algorithms"]])
    created = record["created"]
    timeline = [(t["acquisition"], f"{created['started']} → {created['finished']} "
                                   f"({human_duration(created.get('duration'))}) · {record['case']['examiner']}")]
    for entry in record.get("verifications", []):
        timeline.append((f"{t['verification']} {entry['number']}",
                         f"{entry['started']} → {entry['finished']} · {entry.get('examiner', '')} · "
                         f"{t.get(entry['result'], entry['result'])}"))
    section(t["timeline"], timeline)
    env = record.get("environment") or {}
    section(t["environment"], [(t["tool"], f"{env.get('tool')} {env.get('version')}"), (t["host"], env.get("host")),
                               (t["user"], env.get("user")), (t["os"], env.get("os"))])
    if custody:
        section(t["custody"], [(f"#{e.get('seq')} {e.get('time')}", f"{_action(e, t)} · {e.get('examiner', '')}")
                               for e in custody])
    lines.append(f"{t['seal']}: {(record.get('seal') or {}).get('value', '')} "
                 f"({'OK' if seal_ok(record) else t['seal_bad']})")
    return "\n".join(lines) + "\n"


def to_json(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, indent=2)


def to_csv(record: dict) -> str:
    """Una fila por archivo (carpeta) o una fila con la evidencia (archivo y disco)."""

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    algorithms = record["algorithms"]
    writer.writerow(["path", "size", *(ALGORITHMS[a] for a in algorithms), "error"])
    if record["kind"] == "directory":
        for item in record["details"]["files"]:
            hashes = item.get("hashes") or {}
            writer.writerow([item["path"], item["size"], *(hashes.get(a, "") for a in algorithms), item.get("error", "")])
        for item in record["details"]["skipped"]:
            writer.writerow([item["path"], "", *("" for _ in algorithms), item["error"]])
    else:
        writer.writerow([record["target"], record["size"], *(record["hashes"][a] for a in algorithms), ""])
    return output.getvalue()


def to_manifest(record: dict, algorithm: str) -> str:
    """Formato de `md5sum`/`sha1sum`/`sha256sum` (comprobable con `-c`)."""

    if algorithm not in record["algorithms"]:
        raise ValueError(f"El registro no tiene {algorithm}.")
    if record["kind"] == "directory":
        return manifest_text(record["details"]["files"], algorithm)
    name = (record.get("source") or {}).get("name") or record["target"]
    return f"{record['hashes'][algorithm]}  {name}\n"


EXPORTS = {
    "html": ("text/html", "html"),
    "txt": ("text/plain", "txt"),
    "json": ("application/json", "json"),
    "csv": ("text/csv", "csv"),
    **{a: ("text/plain", a) for a in ALGORITHMS},
}


def export(record: dict, fmt: str, custody: list[dict] | None = None, lang: str = "es") -> str:
    if fmt == "html":
        return to_html(record, custody, lang)
    if fmt == "txt":
        return to_text(record, custody, lang)
    if fmt == "json":
        return to_json(record)
    if fmt == "csv":
        return to_csv(record)
    if fmt in ALGORITHMS:
        return to_manifest(record, fmt)
    raise ValueError(f"Formato no soportado: {fmt}")


def filename(record: dict, fmt: str) -> str:
    base = record["case"].get("evidence_number") or record["case"].get("case_number") or record["label"]
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in base)[:60].strip("_") or "evidencia"
    return f"ForensiX-Hash_{safe}_{record['id'][:8]}.{EXPORTS[fmt][1]}"
