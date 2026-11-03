// Idiomas de la interfaz: español (el texto del HTML) e inglés.
// Los textos estáticos llevan data-i18n="clave"; los que crea app.js usan t("clave").

const I18N = (() => {
  const EN = {
    "nav.new": "New hash", "nav.history": "Records", "nav.custody": "Custody", "nav.settings": "Settings",
    "new.title": "New hash",
    "new.lead": "Hash a piece of evidence, verify it with a second read and get the PDF report with the case details.",
    "wizard.select": "Evidence", "wizard.case": "Details", "wizard.hash": "Hash", "wizard.save": "Save",
    "wizard.process": "Process", "wizard.back": "Back", "wizard.next": "Next",
    "new.what": "What do you want to hash?", "new.browse": "Browse…",
    "new.case": "Evidence details", "new.algorithms": "Which hash do you want to calculate?",
    "new.output": "Where should the PDF report be saved?",
    "new.output_hint": "When it finishes, the PDF report is created there as proof. It cannot be inside the evidence, because that would modify it.",
    "new.summary": "Summary",
    "new.verify_note": "When it finishes it is verified automatically: the evidence is read a second time and the hashes must match.",
    "new.start": "Hash and verify",
    "settings.title": "Settings", "settings.lead": "Appearance, language and updates. Saved on this computer.",
    "settings.theme": "Theme", "settings.theme_hint": "The first time, the Windows theme is used.",
    "settings.light": "Light", "settings.dark": "Dark",
    "settings.language": "Language", "settings.language_hint": "Interface and reports.",
    "settings.updates": "Updates",
    "settings.updates_hint": "When the app opens it checks GitHub for a new version. Updates are signed.",
    "settings.auto": "Check automatically", "settings.check": "Check now",
    "update.install": "Update now", "update.notes": "What's new",
    "record.new_pdf": "Create another PDF…", "record.verify_output": "Save the verification PDF in",
    "kind.file": "File", "kind.file_hint": "A single file",
    "kind.directory": "Folder", "kind.directory_hint": "All its files and subfolders",
    "kind.disk": "Disk", "kind.disk_hint": "Disk, USB drive, volume or image",
    "disk.need_admin": "Reading a whole disk requires running ForensiX Hash as administrator.",
    "disk.relaunch": "Restart as administrator", "disk.choose": "Choose the whole disk or one of its volumes:",
    "disk.refresh": "Refresh", "disk.image_placeholder": "…or a disk image (.dd, .raw, .img, .iso)",
    "disk.readonly": "It is read in read-only mode, sector by sector. For real evidence use a write blocker.",
    "case.examiner": "Performed by", "case.examiner_ph": "Full name", "case.organization": "Organization / unit",
    "case.case_number": "Case number", "case.evidence_number": "Evidence number",
    "case.description": "Evidence description", "case.description_ph": "Make, model, serial number, condition…",
    "case.notes": "Notes",
    "progress.title": "Hashing", "progress.hashing": "Hashing", "progress.verifying": "Verification",
    "progress.done": "PDF report", "progress.percent": "Progress", "progress.read": "Read", "progress.speed": "Speed",
    "progress.eta": "Time left", "progress.files": "Files", "progress.cancel": "Cancel",
    "record.back": "← Records", "record.hashes": "Hashes",
    "record.compare_ph": "Paste a known hash to compare it…",
    "record.dir_note": "For a folder, each hash is the hash of its manifest: the \"hash  path\" list of all its files, sorted by path.",
    "record.export": "PDF report",
    "record.reverify": "Verify again", "record.verifier": "Verified by", "record.copy_path": "Check a copy (optional)",
    "record.copy_ph": "Same evidence at another path", "record.verify_now": "Verify now",
    "record.case": "Case details", "record.evidence": "Evidence", "record.timeline": "Timeline",
    "record.files": "Files", "record.filter": "Filter…", "record.path": "Path",
    "record.integrity": "Record integrity",
    "record.seal_hint": "The seal is the SHA-256 of the record. If someone edits the JSON (a hash, a date, a name), it no longer matches.",
    "record.delete": "Delete record",
    "history.title": "Records", "history.lead": "All the evidence hashed on this computer.",
    "history.search": "Search by case, evidence, path or person…",
    "custody.title": "Chain of custody",
    "custody.lead": "Every operation is logged and linked to the previous one by its hash: if an event is deleted or edited, the chain breaks.",
    "custody.time": "Date and time", "custody.action": "Event", "custody.evidence": "Evidence", "custody.by": "By",
    "about.title": "About ForensiX Hash",
    "about.text": "Forensic hashing tool: files, folders and disks, with automatic verification, case details, chain of custody and reports.",
    "about.legal": "Use the tool only on your own evidence or with authorization. For real evidence, connect disks through a write blocker.",
    "browser.title": "Choose", "browser.cancel": "Cancel", "browser.choose_folder": "Choose this folder",
  };

  // Textos comunes a los dos idiomas que crea app.js (se añaden a DYNAMIC).
  const EXTRA = {
    es: {
      "err.output": "Elige dónde guardar el informe PDF.", "copy": "Copiar",
      "sum.evidence": "Evidencia", "sum.algorithms": "Hash",
      "alg.md5": "Compatibilidad con herramientas antiguas", "alg.sha1": "Habitual en informes periciales",
      "alg.sha256": "Recomendado (estándar actual)", "alg.sha512": "Más largo, muy robusto",
      "alg.sha3_256": "Familia SHA-3", "alg.blake2b": "Moderno y muy rápido",
      "progress.pdf": "Creando el informe PDF…",
      "pdf.saved": "Informe PDF guardado en {0}", "pdf.failed": "El hash está guardado, pero no se pudo crear el PDF: {0}",
      "pdf.none": "Todavía no hay informes PDF.", "pdf.missing": "Ya no está en esa carpeta",
      "pdf.open": "Abrir", "pdf.folder": "Mostrar en la carpeta",
      "browser.choose_folder": "Elegir esta carpeta",
      "update.available": "Hay una versión nueva: {0}", "update.latest": "Tienes la última versión ({0}).",
      "update.checking": "Buscando actualizaciones…", "update.error": "No se pudo comprobar: {0}",
      "update.installing": "Descargando y comprobando la firma…",
      "about.reports": "Informes",
    },
    en: {
      "err.output": "Choose where to save the PDF report.", "copy": "Copy",
      "sum.evidence": "Evidence", "sum.algorithms": "Hash",
      "alg.md5": "Compatibility with older tools", "alg.sha1": "Common in forensic reports",
      "alg.sha256": "Recommended (current standard)", "alg.sha512": "Longer, very robust",
      "alg.sha3_256": "SHA-3 family", "alg.blake2b": "Modern and very fast",
      "progress.pdf": "Creating the PDF report…",
      "pdf.saved": "PDF report saved to {0}", "pdf.failed": "The hash is saved, but the PDF could not be created: {0}",
      "pdf.none": "No PDF reports yet.", "pdf.missing": "No longer in that folder",
      "pdf.open": "Open", "pdf.folder": "Show in folder",
      "browser.choose_folder": "Choose this folder",
      "update.available": "A new version is available: {0}", "update.latest": "You have the latest version ({0}).",
      "update.checking": "Checking for updates…", "update.error": "Could not check: {0}",
      "update.installing": "Downloading and checking the signature…",
      "about.reports": "Reports",
    },
  };

  // Textos que genera app.js.
  const DYNAMIC = {
    es: {
      "path.file": "Ruta del archivo", "path.directory": "Ruta de la carpeta",
      "status.verified": "VERIFICADO", "status.mismatch": "NO COINCIDE", "status.error": "ERROR", "status.pending": "SIN VERIFICAR",
      "status.tampered": "MODIFICADO",
      "verdict.verified": "La evidencia se ha leído de nuevo y da exactamente los mismos hashes.",
      "verdict.mismatch": "La evidencia ha cambiado: los hashes no coinciden con los originales.",
      "verdict.error": "No se pudo leer la evidencia para verificarla.",
      "verdict.pending": "Todavía no se ha verificado.",
      "verdict.last": "Última verificación: {0} · {1}",
      "progress.title.acquire": "Calculando hashes", "progress.title.verify": "Verificando",
      "progress.scanning": "Listando archivos…",
      "err.examiner": "Indica quién realiza el hash.", "err.target": "Elige qué quieres hashear.",
      "err.algorithms": "Elige al menos un algoritmo.", "err.verifier": "Indica quién verifica.",
      "job.cancelled": "Operación cancelada.", "job.failed": "No se pudo completar: {0}",
      "kind.file": "Archivo", "kind.directory": "Carpeta", "kind.disk": "Disco",
      "disk.whole": "Disco completo", "disk.system": "sistema", "disk.none": "No se encontraron discos.",
      "disk.loading": "Buscando discos…", "admin.on": "Administrador", "admin.off": "Sin permisos de administrador",
      "case.case_number": "Nº de caso", "case.evidence_number": "Nº de evidencia", "case.examiner": "Realizado por",
      "case.organization": "Organización", "case.description": "Descripción", "case.notes": "Notas",
      "ev.kind": "Tipo", "ev.path": "Ruta", "ev.size": "Tamaño", "ev.model": "Modelo", "ev.serial": "Nº de serie",
      "ev.bus": "Conexión", "ev.filesystem": "Sistema de archivos", "ev.sector": "Sector", "ev.created": "Creado",
      "ev.modified": "Modificado", "ev.accessed": "Último acceso", "ev.files": "Archivos", "ev.errors": "Errores de lectura",
      "ev.links": "Enlaces no seguidos", "ev.bad": "Sectores ilegibles", "ev.host": "Equipo", "ev.user": "Usuario",
      "ev.image": "Imagen de disco", "ev.volume": "Volumen", "ev.changed": "Cambió durante la lectura",
      "tl.created": "Hash calculado", "tl.verification": "Verificación {0}", "tl.automatic": "automática",
      "tl.by": "por {0}", "tl.on": "en {0}", "tl.copy": "Copia comprobada: {0}",
      "tl.added": "Añadidos", "tl.removed": "Eliminados", "tl.modified": "Modificados",
      "seal.ok": "✔ Íntegro: el registro no se ha modificado. Sello SHA-256: {0}",
      "seal.bad": "✖ MODIFICADO: el contenido no coincide con su sello.",
      "compare.match": "✔ Coincide con {0}", "compare.nomatch": "✖ No coincide con ningún hash",
      "copy.done": "Copiado", "export.saved": "Guardado en {0}", "export.downloaded": "Descargado: {0}",
      "history.empty": "Todavía no hay registros. Empieza en «Nuevo hash».", "history.none": "Sin resultados.",
      "history.verifications": "{0} verificaciones",
      "delete.confirm": "¿Eliminar este registro de la lista? La cadena de custodia conserva el evento.",
      "import.bad": "No es un informe válido.", "import.tampered": "El informe ha sido modificado (sello no válido).",
      "custody.ok": "ÍNTEGRA", "custody.ok_text": "{0} eventos enlazados correctamente.",
      "custody.broken": "ROTA", "custody.broken_text": "La cadena se rompe en el evento {0}: se ha borrado o editado.",
      "custody.empty": "Sin eventos todavía.",
      "act.created": "Hash creado", "act.verified": "Verificado", "act.exported": "Informe exportado",
      "act.imported": "Informe importado", "act.deleted": "Registro eliminado",
      "browser.choose_file": "Elige un archivo", "browser.choose_image": "Elige una imagen de disco",
      "about.version": "Versión", "about.data": "Datos", "about.repo": "Código",
      "files.more": "Mostrando {0} de {1} archivos.", "files.error": "error: {0}",
      "admin.relaunching": "Abriendo como administrador…",
    },
    en: {
      "path.file": "File path", "path.directory": "Folder path",
      "status.verified": "VERIFIED", "status.mismatch": "MISMATCH", "status.error": "ERROR", "status.pending": "NOT VERIFIED",
      "status.tampered": "MODIFIED",
      "verdict.verified": "The evidence was read again and produced exactly the same hashes.",
      "verdict.mismatch": "The evidence has changed: the hashes do not match the originals.",
      "verdict.error": "The evidence could not be read to verify it.",
      "verdict.pending": "Not verified yet.",
      "verdict.last": "Last verification: {0} · {1}",
      "progress.title.acquire": "Hashing", "progress.title.verify": "Verifying",
      "progress.scanning": "Listing files…",
      "err.examiner": "Enter who is performing the hash.", "err.target": "Choose what to hash.",
      "err.algorithms": "Choose at least one algorithm.", "err.verifier": "Enter who is verifying.",
      "job.cancelled": "Operation cancelled.", "job.failed": "Could not complete: {0}",
      "kind.file": "File", "kind.directory": "Folder", "kind.disk": "Disk",
      "disk.whole": "Whole disk", "disk.system": "system", "disk.none": "No disks found.",
      "disk.loading": "Looking for disks…", "admin.on": "Administrator", "admin.off": "Not administrator",
      "case.case_number": "Case number", "case.evidence_number": "Evidence number", "case.examiner": "Performed by",
      "case.organization": "Organization", "case.description": "Description", "case.notes": "Notes",
      "ev.kind": "Type", "ev.path": "Path", "ev.size": "Size", "ev.model": "Model", "ev.serial": "Serial number",
      "ev.bus": "Bus", "ev.filesystem": "File system", "ev.sector": "Sector", "ev.created": "Created",
      "ev.modified": "Modified", "ev.accessed": "Last accessed", "ev.files": "Files", "ev.errors": "Read errors",
      "ev.links": "Links not followed", "ev.bad": "Unreadable sectors", "ev.host": "Computer", "ev.user": "User",
      "ev.image": "Disk image", "ev.volume": "Volume", "ev.changed": "Changed while reading",
      "tl.created": "Hash calculated", "tl.verification": "Verification {0}", "tl.automatic": "automatic",
      "tl.by": "by {0}", "tl.on": "on {0}", "tl.copy": "Copy checked: {0}",
      "tl.added": "Added", "tl.removed": "Removed", "tl.modified": "Modified",
      "seal.ok": "✔ Intact: the record has not been modified. SHA-256 seal: {0}",
      "seal.bad": "✖ MODIFIED: the content does not match its seal.",
      "compare.match": "✔ Matches {0}", "compare.nomatch": "✖ Does not match any hash",
      "copy.done": "Copied", "export.saved": "Saved to {0}", "export.downloaded": "Downloaded: {0}",
      "history.empty": "No records yet. Start with \"New hash\".", "history.none": "No results.",
      "history.verifications": "{0} verifications",
      "delete.confirm": "Delete this record from the list? The chain of custody keeps the event.",
      "import.bad": "Not a valid report.", "import.tampered": "The report has been modified (invalid seal).",
      "custody.ok": "INTACT", "custody.ok_text": "{0} events correctly linked.",
      "custody.broken": "BROKEN", "custody.broken_text": "The chain breaks at event {0}: it was deleted or edited.",
      "custody.empty": "No events yet.",
      "act.created": "Hash created", "act.verified": "Verified", "act.exported": "Report exported",
      "act.imported": "Report imported", "act.deleted": "Record deleted",
      "browser.choose_file": "Choose a file", "browser.choose_image": "Choose a disk image",
      "about.version": "Version", "about.data": "Data", "about.repo": "Source code",
      "files.more": "Showing {0} of {1} files.", "files.error": "error: {0}",
      "admin.relaunching": "Opening as administrator…",
    },
  };

  const original = new Map();
  let lang = "es";
  try { lang = localStorage.getItem("forensix.lang") || (navigator.language.startsWith("es") ? "es" : "en"); } catch { /* sin almacenamiento */ }
  if (!DYNAMIC[lang]) lang = "es";

  function apply() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach(el => {
      if (!original.has(el)) original.set(el, el.textContent);
      el.textContent = lang === "en" ? (EN[el.dataset.i18n] ?? original.get(el)) : original.get(el);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
      if (!original.has(el)) original.set(el, el.placeholder);
      el.placeholder = lang === "en" ? (EN[el.dataset.i18nPlaceholder] ?? original.get(el)) : original.get(el);
    });
    document.querySelectorAll("[data-i18n-title]").forEach(el => {
      if (!original.has(el)) original.set(el, el.title);
      el.title = lang === "en" ? (EN[el.dataset.i18nTitle] ?? original.get(el)) : original.get(el);
    });
  }

  function t(key, ...args) {
    const text = EXTRA[lang][key] ?? DYNAMIC[lang][key] ?? DYNAMIC.es[key] ?? key;
    return text.replace(/\{(\d)\}/g, (_, i) => args[Number(i)] ?? "");
  }

  function setLang(next) {
    lang = next;
    try { localStorage.setItem("forensix.lang", lang); } catch { /* sin almacenamiento */ }
    apply();
    document.dispatchEvent(new CustomEvent("langchange"));
  }

  return { apply, t, setLang, get lang() { return lang; } };
})();

const t = I18N.t;
