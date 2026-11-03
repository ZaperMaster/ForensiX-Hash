// Interfaz de ForensiX Hash: nuevo hash, progreso, registros, verificación y custodia.
// Funciona igual en el navegador (python -m web) y en la app de escritorio, donde
// window.pywebview.api añade los diálogos nativos de Windows y el guardado de PDF.

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

const state = {
  info: null,
  kind: "file",
  disks: [],
  job: null,
  record: null,
  records: [],
  desktop: null,   // window.pywebview.api cuando es la app de escritorio
};

// --- Utilidades --------------------------------------------------------------------------

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "X-ForensiX": "1", ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(", ") : data.detail;
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return data;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child !== null && child !== undefined && child !== false) node.append(child);
  }
  return node;
}

function formatSize(bytes) {
  if (bytes === null || bytes === undefined) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes, unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
  const locale = I18N.lang === "es" ? "es-ES" : "en-GB";
  return `${value.toLocaleString(locale, { maximumFractionDigits: unit ? 2 : 0 })} ${units[unit]}`;
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  seconds = Math.round(seconds);
  const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : m ? `${m}m ${String(s).padStart(2, "0")}s` : `${s}s`;
}

function formatDate(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  const locale = I18N.lang === "es" ? "es-ES" : "en-GB";
  return `${date.toLocaleString(locale, { dateStyle: "medium", timeStyle: "medium" })}`;
}

function toast(message) {
  const box = $("#toast");
  box.textContent = message;
  box.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { box.hidden = true; }, 3200);
}

function remember(name, value) {
  try { localStorage.setItem(`forensix.${name}`, value); } catch { /* sin almacenamiento */ }
}

function recall(name) {
  try { return localStorage.getItem(`forensix.${name}`) || ""; } catch { return ""; }
}

const KIND_ICONS = {
  file: "M6 3h8l4 4v14H6z M14 3v4h4",
  directory: "M3 6h6l2 2h10v11H3z",
  disk: "M5 5h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z M7 15h4",
};

function icon(kind) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", KIND_ICONS[kind]);
  svg.append(path);
  return svg;
}

// --- Navegación --------------------------------------------------------------------------

function show(view) {
  // El enlace de la página refleja lo que se ve, para recargar sin perder el sitio.
  const link = view === "record" && state.record ? `#record=${state.record.id}`
    : view === "progress" && state.job ? `#job=${state.job.id}` : view === "new" ? "" : `#view=${view}`;
  history.replaceState(null, "", link || location.pathname);
  $$(".view").forEach(section => section.classList.toggle("active", section.id === `view-${view}`));
  $$(".sidebar .nav").forEach(button => button.classList.toggle("active", button.dataset.view === view));
  $("#main").scrollTop = 0;
  if (view === "history") loadHistory();
  if (view === "custody") loadCustody();
  if (view === "new" && state.kind === "disk") loadDisks();
}

document.addEventListener("click", event => {
  const target = event.target.closest("[data-view]");
  if (target) {
    if (state.job && target.dataset.view !== "progress") {
      show("progress");  // Hay una operación en curso: se queda en el progreso
      return;
    }
    show(target.dataset.view);
  }
});

// --- Nuevo hash ----------------------------------------------------------------------------

function setKind(kind) {
  state.kind = kind;
  $$(".kind").forEach(button => button.classList.toggle("active", button.dataset.kind === kind));
  $("#pathPicker").hidden = kind === "disk";
  $("#diskPicker").hidden = kind !== "disk";
  $("#targetPath").placeholder = t(kind === "directory" ? "path.directory" : "path.file");
  if (kind === "disk") loadDisks();
}

$$(".kind").forEach(button => button.addEventListener("click", () => setKind(button.dataset.kind)));

async function loadDisks() {
  const list = $("#diskList");
  if (!state.disks.length) list.replaceChildren(el("p", { class: "muted" }, t("disk.loading")));
  try {
    const data = await api("/api/disks");
    state.disks = data.disks;
    const needAdmin = !data.admin && state.info?.os === "nt";
    $("#adminNotice").hidden = !needAdmin;
    $("#relaunchAdmin").hidden = !(needAdmin && state.desktop);
    renderDisks();
  } catch (error) {
    list.replaceChildren(el("p", { class: "error" }, error.message));
  }
}

function renderDisks() {
  const selected = $("input[name=disk]:checked")?.value;
  const list = $("#diskList");
  if (!state.disks.length) {
    list.replaceChildren(el("p", { class: "muted" }, t("disk.none")));
    return;
  }
  list.replaceChildren(...state.disks.map(disk => {
    const bus = (disk.bus || "").toUpperCase();
    const whole = el("label", { class: "disk-option" },
      el("input", { type: "radio", name: "disk", value: disk.path, checked: selected === disk.path }),
      icon("disk"),
      el("div", {},
        el("b", {}, disk.model || disk.path), " ",
        bus ? el("span", { class: `tag ${bus === "USB" ? "usb" : ""}` }, bus) : null, " ",
        disk.system ? el("span", { class: "tag system" }, t("disk.system")) : null,
        el("div", { class: "muted small" }, `${t("disk.whole")} · ${disk.path}${disk.serial ? " · S/N " + disk.serial : ""}`)),
      el("span", { class: "meta" }, formatSize(disk.size), el("br"), disk.partition_style || ""));
    const volumes = disk.volumes.map(volume => el("label", { class: "disk-option" },
      el("input", { type: "radio", name: "disk", value: volume.path, checked: selected === volume.path }),
      el("div", {}, el("b", {}, `${volume.letter} ${volume.label || ""}`),
        el("div", { class: "muted small" }, `${volume.filesystem} · ${volume.path}`)),
      el("span", { class: "meta" }, formatSize(volume.size))));
    return el("div", { class: "disk" }, whole, ...volumes);
  }));
  list.querySelectorAll("input[name=disk]").forEach(input =>
    input.addEventListener("change", () => { $("#imagePath").value = ""; }));
}

$("#refreshDisks").addEventListener("click", () => { state.disks = []; loadDisks(); });
$("#imagePath").addEventListener("input", () => {
  $$("input[name=disk]").forEach(input => { input.checked = false; });
});
$("#relaunchAdmin").addEventListener("click", async () => {
  toast(t("admin.relaunching"));
  await state.desktop.relaunch_as_admin();
});

function renderAlgorithms() {
  const saved = recall("algorithms").split(",").filter(Boolean);
  $("#algorithms").replaceChildren(...state.info.algorithms.map(algorithm => el("label", { class: "chip" },
    el("input", {
      type: "checkbox", value: algorithm.id,
      checked: saved.length ? saved.includes(algorithm.id) : algorithm.default,
    }),
    algorithm.name)));
}

function caseData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function selectedTarget() {
  if (state.kind !== "disk") return $("#targetPath").value.trim();
  return $("input[name=disk]:checked")?.value || $("#imagePath").value.trim();
}

$("#startButton").addEventListener("click", async () => {
  const error = $("#newError");
  error.textContent = "";
  const target = selectedTarget();
  const algorithms = $$("#algorithms input:checked").map(input => input.value);
  const form = $("#caseForm");
  const data = caseData(form);
  if (!target) { error.textContent = t("err.target"); return; }
  if (!data.examiner.trim()) { error.textContent = t("err.examiner"); form.examiner.focus(); return; }
  if (!algorithms.length) { error.textContent = t("err.algorithms"); return; }

  remember("examiner", data.examiner);
  remember("organization", data.organization);
  remember("algorithms", algorithms.join(","));

  $("#startButton").disabled = true;
  try {
    const job = await api("/api/jobs", { method: "POST", body: JSON.stringify({ kind: state.kind, target, algorithms, case: data }) });
    startProgress(job, "acquire");
  } catch (err) {
    error.textContent = err.message;
  } finally {
    $("#startButton").disabled = false;
  }
});

// --- Elegir rutas (diálogo nativo en la app, explorador propio en la web) -------------------------

async function pick(mode) {
  if (state.desktop) {
    return state.desktop.pick(mode);
  }
  return webBrowse(mode);
}

$("#browseButton").addEventListener("click", async () => {
  const path = await pick(state.kind === "directory" ? "folder" : "file");
  if (path) $("#targetPath").value = path;
});
$("#browseImage").addEventListener("click", async () => {
  const path = await pick("image");
  if (path) {
    $("#imagePath").value = path;
    $$("input[name=disk]").forEach(input => { input.checked = false; });
  }
});
$("#browseCopy").addEventListener("click", async () => {
  const kind = state.record?.kind;
  const path = await pick(kind === "directory" ? "folder" : kind === "disk" ? "image" : "file");
  if (path) $("#verifyForm").target.value = path;
});

function webBrowse(mode) {
  const dialog = $("#browser");
  const list = $("#browserList");
  const pathInput = $("#browserPath");
  const choose = $("#browserChoose");
  let current = "", parent = null, chosenFile = null;

  choose.textContent = mode === "folder" ? I18N.lang === "es" ? "Elegir esta carpeta" : "Choose this folder"
    : t(mode === "image" ? "browser.choose_image" : "browser.choose_file");
  choose.disabled = mode !== "folder";

  async function open(path) {
    try {
      const data = await api(`/api/browse?path=${encodeURIComponent(path)}`);
      current = data.path; parent = data.parent; chosenFile = null;
      pathInput.value = current;
      choose.disabled = mode !== "folder" || !current;
      list.replaceChildren(...data.entries.map(entry => {
        const item = el("li", { class: entry.dir ? "dir" : "" }, el("span", {}, entry.name),
          entry.dir ? null : el("small", {}, formatSize(entry.size)));
        item.addEventListener("click", () => {
          if (entry.dir) { open(entry.path); return; }
          if (mode === "folder") return;
          list.querySelectorAll(".selected").forEach(node => node.classList.remove("selected"));
          item.classList.add("selected");
          chosenFile = entry.path;
          choose.disabled = false;
        });
        item.addEventListener("dblclick", () => { if (!entry.dir && mode !== "folder") finish(entry.path); });
        return item;
      }));
    } catch (error) {
      toast(error.message);
    }
  }

  let resolver;
  function finish(value) {
    dialog.close();
    resolver(value);
  }

  $("#browserUp").onclick = () => open(parent ?? "");
  pathInput.onkeydown = event => { if (event.key === "Enter") { event.preventDefault(); open(pathInput.value); } };
  choose.onclick = () => finish(mode === "folder" ? current : chosenFile);
  dialog.onclose = () => resolver?.(null);

  return new Promise(resolve => {
    resolver = value => { resolver = null; resolve(value); };
    dialog.showModal();
    open(recall("lastBrowse"));
  }).then(value => {
    if (value) remember("lastBrowse", mode === "folder" ? value : value.replace(/[\\/][^\\/]*$/, ""));
    return value;
  });
}

// --- Progreso ---------------------------------------------------------------------------------

function startProgress(job, action) {
  state.job = job;
  $("#progressTitle").textContent = t(action === "verify" ? "progress.title.verify" : "progress.title.acquire");
  $("#progressTarget").textContent = job.title;
  $$(".phases li").forEach(li => li.classList.remove("current", "complete"));
  $(".phases li[data-phase=hashing]").hidden = action === "verify";
  $("#cancelButton").disabled = false;
  renderProgress(job.progress);
  show("progress");
  pollJob();
}

async function pollJob() {
  if (!state.job) return;
  try {
    const job = await api(`/api/jobs/${state.job.id}`);
    renderProgress(job.progress);
    if (job.state === "running") {
      setTimeout(pollJob, 500);
      return;
    }
    state.job = null;
    if (job.state === "done") {
      await openRecord(job.record_id);
    } else {
      show(job.action === "verify" && state.record ? "record" : "new");
      toast(job.state === "cancelled" ? t("job.cancelled") : t("job.failed", job.error));
      if (job.state === "error") $("#newError").textContent = job.error;
    }
  } catch (error) {
    setTimeout(pollJob, 1000);
  }
}

function renderProgress(progress) {
  const order = ["hashing", "verifying", "done"];
  const phase = progress.phase === "scanning" || progress.phase === "preparing" ? null : progress.phase;
  $$(".phases li").forEach(li => {
    const index = order.indexOf(li.dataset.phase);
    const current = order.indexOf(phase);
    li.classList.toggle("current", index === current);
    li.classList.toggle("complete", current > index);
  });
  $("#progressBar").style.width = `${progress.percent}%`;
  $("#statPercent").textContent = `${progress.percent.toLocaleString(I18N.lang)} %`;
  $("#statBytes").textContent = progress.bytes_total ? `${formatSize(progress.bytes_done)} / ${formatSize(progress.bytes_total)}` : "—";
  $("#statSpeed").textContent = progress.speed ? `${formatSize(progress.speed)}/s` : "—";
  $("#statEta").textContent = progress.eta !== null ? formatDuration(progress.eta) : "—";
  $("#statFiles").textContent = progress.files_total ? `${progress.files_done} / ${progress.files_total}` : "—";
  $("#statCurrent").textContent = progress.phase === "scanning" ? t("progress.scanning") : progress.current;
}

$("#cancelButton").addEventListener("click", async () => {
  if (!state.job) return;
  $("#cancelButton").disabled = true;
  await api(`/api/jobs/${state.job.id}`, { method: "DELETE" }).catch(() => {});
});

// --- Registro -------------------------------------------------------------------------------

async function openRecord(id) {
  const data = await api(`/api/records/${id}`);
  state.record = data.record;
  state.recordData = data;
  renderRecord();
  show("record");
}

function verdictBox(container, status, detail) {
  container.className = `verdict ${status}`;
  container.replaceChildren(el("span", { class: "badge" }, t(`status.${status}`)), el("div", {}, ...detail));
}

function renderRecord() {
  const record = state.record;
  const data = state.recordData;
  const last = record.verifications.at(-1);
  const status = data.summary.status;

  $("#recordTitle").textContent = record.case.evidence_number
    ? `${record.case.evidence_number} · ${record.label}` : record.label;
  $("#recordTarget").textContent = record.target;
  verdictBox($("#recordVerdict"), status, [
    el("p", {}, t(`verdict.${status}`)),
    last ? el("small", {}, t("verdict.last", formatDate(last.finished), last.examiner)) : null,
  ]);

  $("#recordSize").textContent = formatSize(record.size);
  const names = Object.fromEntries(state.info.algorithms.map(a => [a.id, a.name]));
  $("#recordHashes").replaceChildren(...record.algorithms.map(algorithm => el("div", { class: "hash", "data-alg": algorithm },
    el("b", {}, names[algorithm]),
    el("span", { class: "mono" }, record.hashes[algorithm]),
    el("button", {
      type: "button", class: "ghost small",
      onclick: () => navigator.clipboard.writeText(record.hashes[algorithm]).then(() => toast(t("copy.done"))),
    }, I18N.lang === "es" ? "Copiar" : "Copy"))));
  $("#compareInput").value = "";
  $("#compareResult").textContent = "";
  $("#dirHashNote").hidden = record.kind !== "directory";

  $("#manifestButtons").replaceChildren(...record.algorithms.map(algorithm =>
    el("button", { type: "button", class: "ghost small", "data-export": algorithm }, `.${algorithm}`)));

  const form = $("#verifyForm");
  form.examiner.value = form.examiner.value || recall("examiner");
  form.target.value = "";
  form.notes.value = "";

  const caseFacts = ["case_number", "evidence_number", "examiner", "organization", "description", "notes"]
    .filter(name => record.case[name]).map(name => [t(`case.${name}`), record.case[name]]);
  facts($("#recordCase"), caseFacts);
  facts($("#recordEvidence"), evidenceFacts(record));

  renderTimeline(record, data.custody);
  renderFiles(record);

  const seal = $("#recordSeal");
  seal.className = data.seal_ok ? "ok-text" : "bad-text";
  seal.textContent = data.seal_ok ? t("seal.ok", record.seal.value) : t("seal.bad");
}

function facts(container, rows) {
  container.replaceChildren(...rows.flatMap(([key, value]) => [el("dt", {}, key), el("dd", {}, String(value))]));
}

function evidenceFacts(record) {
  const source = record.source || {};
  const details = record.details || {};
  const kindLabel = record.kind === "disk"
    ? { image: t("ev.image"), volume: t("ev.volume") }[source.kind] || t("kind.disk") : t(`kind.${record.kind}`);
  const rows = [[t("ev.kind"), kindLabel], [t("ev.size"), `${formatSize(record.size)} (${record.size.toLocaleString(I18N.lang)} bytes)`]];
  if (source.model) rows.push([t("ev.model"), source.model]);
  if (source.serial) rows.push([t("ev.serial"), source.serial]);
  if (source.bus) rows.push([t("ev.bus"), source.bus]);
  if (source.disk) rows.push([t("kind.disk"), `${source.disk.model} · S/N ${source.disk.serial}`]);
  if (source.filesystem) rows.push([t("ev.filesystem"), source.filesystem]);
  if (details.sector_size) rows.push([t("ev.sector"), `${details.sector_size} bytes`]);
  if (source.times) {
    rows.push([t("ev.created"), formatDate(source.times.created)]);
    rows.push([t("ev.modified"), formatDate(source.times.modified)]);
    rows.push([t("ev.accessed"), formatDate(source.times.accessed)]);
  }
  if (details.totals) {
    rows.push([t("ev.files"), details.totals.files]);
    rows.push([t("ev.errors"), details.totals.errors]);
    if (details.totals.links) rows.push([t("ev.links"), details.totals.links]);
  }
  if (details.bad_sectors) rows.push([t("ev.bad"), details.bad_sectors.count]);
  if (details.changed_while_reading) rows.push([t("ev.changed"), "⚠"]);
  rows.push([t("ev.host"), `${record.environment.host} (${record.environment.user})`]);
  return rows;
}

function renderTimeline(record) {
  const items = [el("li", {},
    el("b", {}, t("tl.created")),
    el("small", {}, `${formatDate(record.created.finished)} · ${t("tl.by", record.case.examiner)} · ${formatDuration(record.created.duration)}`))];
  for (const entry of record.verifications) {
    const title = `${t("tl.verification", entry.number)}${entry.automatic ? ` (${t("tl.automatic")})` : ""} — ${t(`status.${entry.result}`)}`;
    const diff = entry.differences || {};
    items.push(el("li", { class: entry.result },
      el("b", {}, title),
      el("small", {}, `${formatDate(entry.finished)} · ${t("tl.by", entry.examiner)} · ${t("tl.on", entry.host)} · ${formatDuration(entry.duration)}`),
      entry.target !== record.target ? el("div", { class: "diff mono" }, t("tl.copy", entry.target)) : null,
      entry.error ? el("div", { class: "diff bad-text" }, entry.error) : null,
      entry.notes ? el("div", { class: "diff" }, entry.notes) : null,
      ...["added", "removed", "modified"].filter(key => diff[key]?.length).map(key =>
        el("div", { class: "diff" }, el("b", {}, `${t(`tl.${key}`)} (${diff[key].length}): `),
          el("span", { class: "mono" }, diff[key].slice(0, 20).join(", ") + (diff[key].length > 20 ? "…" : ""))))));
  }
  $("#recordTimeline").replaceChildren(...items);
}

const FILES_SHOWN = 500;

function renderFiles(record) {
  const card = $("#filesCard");
  card.hidden = record.kind !== "directory";
  if (card.hidden) return;
  const algorithm = record.algorithms.includes("sha256") ? "sha256" : record.algorithms.at(-1);
  $("#filesAlg").textContent = state.info.algorithms.find(a => a.id === algorithm).name;
  const filter = $("#fileFilter").value.trim().toLowerCase();
  const all = record.details.files.filter(file => !filter || file.path.toLowerCase().includes(filter));
  $("#filesBody").replaceChildren(...all.slice(0, FILES_SHOWN).map(file => el("tr", {},
    el("td", { class: "mono" }, file.path),
    el("td", {}, file.size.toLocaleString(I18N.lang)),
    el("td", { class: file.hashes ? "mono" : "bad-text" }, file.hashes ? file.hashes[algorithm] : t("files.error", file.error)))));
  $("#filesMore").textContent = all.length > FILES_SHOWN ? t("files.more", FILES_SHOWN, all.length) : "";
}

$("#fileFilter").addEventListener("input", () => state.record && renderFiles(state.record));

$("#compareInput").addEventListener("input", event => {
  const value = event.target.value.trim().toLowerCase().replace(/\s+/g, "");
  const result = $("#compareResult");
  $$(".hash").forEach(node => node.classList.remove("match"));
  if (!value) { result.textContent = ""; return; }
  const match = Object.entries(state.record.hashes).find(([, hash]) => hash === value);
  if (match) {
    $(`.hash[data-alg="${match[0]}"]`).classList.add("match");
    result.className = "ok-text";
    result.textContent = t("compare.match", state.info.algorithms.find(a => a.id === match[0]).name);
  } else {
    result.className = "bad-text";
    result.textContent = t("compare.nomatch");
  }
});

$("#verifyForm").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.target;
  const data = caseData(form);
  if (!data.examiner.trim()) { toast(t("err.verifier")); return; }
  remember("examiner", data.examiner);
  try {
    const job = await api(`/api/records/${state.record.id}/verify`, {
      method: "POST", body: JSON.stringify({ examiner: data.examiner, target: data.target || null, notes: data.notes }),
    });
    startProgress(job, "verify");
  } catch (error) {
    toast(error.message);
  }
});

$("#deleteRecord").addEventListener("click", async () => {
  if (!confirm(t("delete.confirm"))) return;
  await api(`/api/records/${state.record.id}`, { method: "DELETE" });
  state.record = null;
  show("history");
});

// --- Exportar ------------------------------------------------------------------------------

document.addEventListener("click", async event => {
  const button = event.target.closest("[data-export]");
  if (!button || !state.record) return;
  const format = button.dataset.export;
  const status = $("#exportStatus");
  status.textContent = "";
  try {
    if (format === "pdf") {
      await exportPdf();
      return;
    }
    const data = await api(`/api/records/${state.record.id}/export`, {
      method: "POST", body: JSON.stringify({ format, lang: I18N.lang }),
    });
    if (state.desktop) {
      const filter = { html: "HTML (*.html)", txt: "Texto (*.txt)", json: "JSON (*.json)", csv: "CSV (*.csv)" }[format]
        || `${format.toUpperCase()} (*.${format})`;
      const path = await state.desktop.save_text(data.filename, data.content, filter);
      if (path) status.textContent = t("export.saved", path);
    } else {
      const bom = format === "csv" ? "﻿" : "";
      const url = URL.createObjectURL(new Blob([bom + data.content], { type: `${data.mime};charset=utf-8` }));
      el("a", { href: url, download: data.filename }).click();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      status.textContent = t("export.downloaded", data.filename);
    }
  } catch (error) {
    status.textContent = error.message;
  }
});

async function exportPdf() {
  const id = state.record.id;
  const logPdf = () => api(`/api/records/${id}/export`, { method: "POST", body: JSON.stringify({ format: "pdf", lang: I18N.lang }) });
  if (state.desktop) {
    const base = (state.record.case.evidence_number || state.record.case.case_number || state.record.label)
      .replace(/[^\w.-]+/g, "_").slice(0, 60);
    const path = await state.desktop.save_pdf(id, I18N.lang, `ForensiX-Hash_${base}_${id.slice(0, 8)}.pdf`);
    if (path) {
      $("#exportStatus").textContent = t("export.saved", path);
      await logPdf();
    }
  } else {
    window.open(`/report/${id}?lang=${I18N.lang}&print=1`, "_blank", "noopener");
    await logPdf();
  }
}

// --- Registros ----------------------------------------------------------------------------

async function loadHistory() {
  try {
    state.records = await api("/api/records");
  } catch (error) {
    $("#historyList").replaceChildren(el("p", { class: "error" }, error.message));
    return;
  }
  renderHistory();
}

function renderHistory() {
  const query = $("#historySearch").value.trim().toLowerCase();
  const list = $("#historyList");
  if (!state.records.length) {
    list.replaceChildren(el("div", { class: "empty" }, t("history.empty")));
    return;
  }
  const items = state.records.filter(item => !query || [item.label, item.target, item.case_number, item.evidence_number, item.examiner]
    .some(value => (value || "").toLowerCase().includes(query)));
  if (!items.length) {
    list.replaceChildren(el("div", { class: "empty" }, t("history.none")));
    return;
  }
  list.replaceChildren(...items.map(item => {
    const status = item.seal_ok ? item.status : "tampered";
    const sub = [item.case_number, item.evidence_number, item.examiner, formatDate(item.created), formatSize(item.size)]
      .filter(Boolean).join(" · ");
    return el("button", { type: "button", class: "history-item", onclick: () => openRecord(item.id) },
      icon(item.kind),
      el("div", {},
        el("div", { class: "title" }, item.label),
        el("div", { class: "sub" }, sub),
        el("div", { class: "sub mono" }, `SHA-256 ${item.hashes.sha256 || Object.values(item.hashes).at(-1)}`)),
      el("div", {}, el("span", { class: `pill ${status}` }, t(`status.${status}`)),
        el("div", { class: "sub", style: "text-align:right;margin-top:6px" }, t("history.verifications", item.verifications))));
  }));
}

$("#historySearch").addEventListener("input", renderHistory);

// --- Verificar desde un informe JSON ----------------------------------------------------------------

async function importReport(file) {
  const error = $("#importError");
  error.textContent = "";
  try {
    const result = await api("/api/import", { method: "POST", body: await file.text() });
    await openRecord(result.id);
  } catch (err) {
    error.textContent = err.message || t("import.bad");
  }
}

$("#importFile").addEventListener("change", event => {
  const file = event.target.files[0];
  if (file) importReport(file);
  event.target.value = "";
});
const drop = $("#dropZone");
drop.addEventListener("dragover", event => { event.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", event => {
  event.preventDefault();
  drop.classList.remove("over");
  const file = event.dataTransfer.files[0];
  if (file) importReport(file);
});

// --- Custodia ---------------------------------------------------------------------------------

async function loadCustody() {
  const data = await api("/api/custody");
  const ok = data.check.ok;
  const box = $("#custodyStatus");
  box.className = `verdict ${ok ? "verified" : "broken"}`;
  box.replaceChildren(el("span", { class: "badge" }, t(ok ? "custody.ok" : "custody.broken")),
    el("p", {}, ok ? t("custody.ok_text", data.check.events) : t("custody.broken_text", data.check.broken_at)));
  const body = $("#custodyBody");
  if (!data.events.length) {
    body.replaceChildren(el("tr", {}, el("td", { colspan: 6, class: "muted" }, t("custody.empty"))));
    return;
  }
  body.replaceChildren(...data.events.slice().reverse().map(event => {
    let action = t(`act.${event.action}`);
    if (event.action === "verified") action += `: ${t(`status.${event.result}`)}`;
    if (event.action === "exported") action += ` (${event.format})`;
    const record = event.record_id
      ? el("a", { href: "#", onclick: e => { e.preventDefault(); openRecord(event.record_id).catch(err => toast(err.message)); } },
        event.evidence_number || event.target) : "";
    return el("tr", {},
      el("td", {}, event.seq), el("td", {}, formatDate(event.time)), el("td", {}, action),
      el("td", { class: "mono" }, record), el("td", {}, event.examiner || ""),
      el("td", { class: "mono", title: event.hash }, (event.hash || "").slice(0, 12) + "…"));
  }));
}

// --- Inicio ---------------------------------------------------------------------------------

function renderAbout() {
  facts($("#aboutFacts"), [
    [t("about.version"), `${state.info.app} ${state.info.version}`],
    [t("about.data"), state.info.home],
    [t("about.repo"), state.info.repo],
  ]);
  const pill = $("#adminPill");
  pill.hidden = state.info.os !== "nt";
  pill.classList.toggle("on", state.info.admin);
  pill.textContent = t(state.info.admin ? "admin.on" : "admin.off");
}

$("#language").addEventListener("click", () => I18N.setLang(I18N.lang === "es" ? "en" : "es"));
document.addEventListener("langchange", () => {
  $("#language").textContent = I18N.lang === "es" ? "EN" : "ES";
  $("#targetPath").placeholder = t(state.kind === "directory" ? "path.directory" : "path.file");
  if (state.info) renderAbout();
  if (state.disks.length) renderDisks();
  if (state.record && $("#view-record").classList.contains("active")) renderRecord();
  if ($("#view-history").classList.contains("active")) renderHistory();
  if ($("#view-custody").classList.contains("active")) loadCustody();
});

window.addEventListener("pywebviewready", () => {
  state.desktop = window.pywebview.api;
  if (state.kind === "disk") loadDisks();
});

(async function init() {
  I18N.apply();
  $("#language").textContent = I18N.lang === "es" ? "EN" : "ES";
  state.info = await api("/api/info");
  $("#appVersion").textContent = `v${state.info.version}`;
  renderAlgorithms();
  renderAbout();
  const form = $("#caseForm");
  form.examiner.value = recall("examiner");
  form.organization.value = recall("organization");
  setKind("file");
  await openLink();
})();

// #record=<id>, #job=<id>, #view=<vista> o #kind=<file|directory|disk>
async function openLink() {
  const params = new URLSearchParams(location.hash.slice(1));
  try {
    if (params.get("job")) {
      const job = await api(`/api/jobs/${params.get("job")}`);
      if (job.state === "running") startProgress(job, job.action);
      else if (job.record_id) await openRecord(job.record_id);
    } else if (params.get("record")) {
      await openRecord(params.get("record"));
    } else if (params.get("kind")) {
      setKind(params.get("kind"));
    } else if (params.get("view")) {
      show(params.get("view"));
    }
  } catch {
    history.replaceState(null, "", location.pathname);
  }
}
