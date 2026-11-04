// Interfaz de ForensiX Hash: asistente de nuevo hash, progreso, registros, custodia y ajustes.
// Funciona igual en el navegador (python -m web) y en la app de escritorio, donde
// window.pywebview.api añade los diálogos de Windows, la ventana y las actualizaciones.

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

const state = {
  info: null,
  kind: "file",
  step: 1,
  disks: [],
  job: null,
  record: null,
  recordData: null,
  records: [],
  update: null,
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
    throw new Error(I18N.error(detail) || `HTTP ${response.status}`);
  }
  return data;
}

const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body) });

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

const locale = () => (I18N.lang === "es" ? "es-ES" : "en-GB");

function formatSize(bytes) {
  if (bytes === null || bytes === undefined) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes, unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
  return `${value.toLocaleString(locale(), { maximumFractionDigits: unit ? 2 : 0 })} ${units[unit]}`;
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  seconds = Math.round(seconds);
  const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : m ? `${m}m ${String(s).padStart(2, "0")}s` : `${s}s`;
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(locale(), { dateStyle: "medium", timeStyle: "medium" });
}

function toast(message) {
  const box = $("#toast");
  box.textContent = message;
  box.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { box.hidden = true; }, 4200);
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
  if (!target) return;
  if (state.job) {
    show("progress");  // Hay una operación en curso: se queda en el progreso
    return;
  }
  show(target.dataset.view);
});

// --- Asistente: 1 evidencia · 2 datos · 3 hash · 4 guardar ----------------------------------

function setKind(kind) {
  state.kind = kind;
  $$(".kind").forEach(button => button.classList.toggle("active", button.dataset.kind === kind));
  $("#pathPicker").hidden = kind === "disk";
  $("#diskPicker").hidden = kind !== "disk";
  $("#imageOption").hidden = kind !== "disk";
  $("#imageHint").hidden = kind !== "disk";
  if (kind !== "disk") $("#makeImage").checked = false;
  $("#targetPath").placeholder = t(kind === "directory" ? "path.directory" : "path.file");
  if (kind === "disk") loadDisks();
}

$$(".kind").forEach(button => button.addEventListener("click", () => setKind(button.dataset.kind)));

function goToStep(step) {
  state.step = step;
  $$(".wizard-page").forEach(page => { page.hidden = Number(page.dataset.page) !== step; });
  $$("#wizardSteps li").forEach(li => {
    const n = Number(li.dataset.step);
    li.classList.toggle("current", n === step);
    li.classList.toggle("complete", n < step);
  });
  $("#backButton").style.visibility = step === 1 ? "hidden" : "visible";
  $("#nextButton").hidden = step === 4;
  $("#startButton").hidden = step !== 4;
  $("#newError").textContent = "";
  if (step === 4) renderSummary();
  const first = $(`.wizard-page[data-page="${step}"] input:not([type=radio]):not([type=checkbox])`);
  if (first && step === 2) first.focus();
}

function selectedTarget() {
  if (state.kind !== "disk") return $("#targetPath").value.trim();
  return $("input[name=disk]:checked")?.value || $("#imagePath").value.trim();
}

function selectedAlgorithms() {
  return $$("#algorithms input:checked").map(input => input.value);
}

function stepError(step) {
  if (step === 1 && !selectedTarget()) return t("err.target");
  if (step === 2 && !$("#caseForm").examiner.value.trim()) return t("err.examiner");
  if (step === 3 && !selectedAlgorithms().length) return t("err.algorithms");
  if (step === 4 && !$("#outputPath").value.trim()) return t("err.output");
  return "";
}

$("#nextButton").addEventListener("click", () => {
  const error = stepError(state.step);
  if (error) { $("#newError").textContent = error; return; }
  goToStep(state.step + 1);
});
$("#backButton").addEventListener("click", () => goToStep(Math.max(1, state.step - 1)));
$("#caseForm").addEventListener("submit", event => { event.preventDefault(); $("#nextButton").click(); });
$("#makeImage").addEventListener("change", renderSummary);

function renderSummary() {
  const data = caseData($("#caseForm"));
  const names = Object.fromEntries(state.info.algorithms.map(a => [a.id, a.name]));
  facts($("#summary"), [
    [t("sum.evidence"), `${t(`kind.${state.kind}`)} · ${selectedTarget()}`],
    [t("case.examiner"), data.examiner],
    ...[["case.case_number", data.case_number], ["case.evidence_number", data.evidence_number]]
      .filter(([, value]) => value).map(([key, value]) => [t(key), value]),
    [t("sum.algorithms"), selectedAlgorithms().map(id => names[id]).join(" · ")],
    ...($("#makeImage").checked ? [[t("sum.image"), t("sum.image_yes")]] : []),
  ]);
}

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
        disk.system ? el("span", { class: "tag system" }, t("disk.system")) : null, " ",
        disk.write_protected ? el("span", { class: "tag protected" }, t("disk.protected")) : null,
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
    input.addEventListener("change", () => { $("#imagePath").value = ""; updateLiveNotice(); }));
  updateLiveNotice();
}

// Aviso si lo elegido es el disco del sistema o uno de sus volúmenes.
function updateLiveNotice() {
  const selected = $("input[name=disk]:checked")?.value;
  $("#liveNotice").hidden = !state.disks.some(disk =>
    disk.system && (disk.path === selected || disk.volumes.some(volume => volume.path === selected)));
}

$("#refreshDisks").addEventListener("click", () => { state.disks = []; loadDisks(); });
$("#imagePath").addEventListener("input", () => {
  $$("input[name=disk]").forEach(input => { input.checked = false; });
  updateLiveNotice();
});
$("#relaunchAdmin").addEventListener("click", async () => {
  toast(t("admin.relaunching"));
  await state.desktop.relaunch_as_admin();
});

function renderAlgorithms() {
  const saved = recall("algorithms").split(",").filter(Boolean);
  $("#algorithms").replaceChildren(...state.info.algorithms.map(algorithm => el("label", { class: "algorithm" },
    el("input", {
      type: "checkbox", value: algorithm.id,
      checked: saved.length ? saved.includes(algorithm.id) : algorithm.default,
    }),
    el("span", {}, el("b", {}, algorithm.name), el("small", {}, t(`alg.${algorithm.id}`))))));
}

function caseData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

$("#startButton").addEventListener("click", async () => {
  const error = $("#newError");
  const problem = [1, 2, 3, 4].map(stepError).find(Boolean);
  if (problem) { error.textContent = problem; return; }
  const data = caseData($("#caseForm"));
  const algorithms = selectedAlgorithms();
  const output = $("#outputPath").value.trim();
  remember("examiner", data.examiner);
  remember("organization", data.organization);
  remember("algorithms", algorithms.join(","));
  remember("output", output);

  $("#startButton").disabled = true;
  try {
    const job = await post("/api/jobs", {
      kind: state.kind, target: selectedTarget(), algorithms, case: data, output, lang: I18N.lang,
      image: $("#makeImage").checked, timestamp: useTimestamp(),
    });
    startProgress(job, "acquire");
  } catch (err) {
    error.textContent = err.message;
  } finally {
    $("#startButton").disabled = false;
  }
});

function resetWizard() {
  const form = $("#caseForm");
  ["case_number", "evidence_number", "description", "notes"].forEach(name => { form[name].value = ""; });
  $("#targetPath").value = "";
  $("#imagePath").value = "";
  $("#makeImage").checked = false;
  $$("input[name=disk]").forEach(input => { input.checked = false; });
  updateLiveNotice();
  goToStep(1);
}

// --- Elegir rutas (diálogo de Windows en la app, explorador propio en la web) -------------------

async function pick(mode) {
  if (state.desktop) return state.desktop.pick(mode);
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
$("#browseOutput").addEventListener("click", async () => {
  const path = await pick("folder");
  if (path) $("#outputPath").value = path;
});
$("#browseCopy").addEventListener("click", async () => {
  const kind = state.record?.kind;
  const path = await pick(kind === "directory" ? "folder" : kind === "disk" ? "image" : "file");
  if (path) $("#verifyForm").target.value = path;
});
$("#browseVerifyOutput").addEventListener("click", async () => {
  const path = await pick("folder");
  if (path) $("#verifyForm").output.value = path;
});

function webBrowse(mode) {
  const dialog = $("#browser");
  const list = $("#browserList");
  const pathInput = $("#browserPath");
  const choose = $("#browserChoose");
  let current = "", parent = null, chosenFile = null;

  choose.textContent = t(mode === "folder" ? "browser.choose_folder" : mode === "image" ? "browser.choose_image" : "browser.choose_file");
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
    resolver?.(value);
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

// --- Progreso: cálculo · verificación · informe PDF -------------------------------------------

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
      if (job.action === "acquire") resetWizard();
      await openRecord(job.record_id);
      if (job.pdf) toast(t("pdf.saved", job.pdf));
      if (job.timestamp_error) toast(t("timestamp.failed"));
      if (job.pdf_error) toast(t("pdf.failed", I18N.error(job.pdf_error)));
    } else {
      show(job.action === "verify" && state.record ? "record" : "new");
      toast(job.state === "cancelled" ? t("job.cancelled") : t("job.failed", I18N.error(job.error)));
      if (job.state === "error") $("#newError").textContent = I18N.error(job.error);
    }
  } catch {
    setTimeout(pollJob, 1000);
  }
}

function renderProgress(progress) {
  const order = ["hashing", "verifying", "report"];
  const current = order.indexOf(progress.phase === "verifying_image" ? "verifying" : progress.phase);
  $$(".phases li").forEach(li => {
    const index = order.indexOf(li.dataset.phase);
    li.classList.toggle("current", index === current);
    li.classList.toggle("complete", current > index || progress.phase === "done");
  });
  const percent = progress.phase === "report" || progress.phase === "done" ? 100 : progress.percent;
  $("#progressBar").style.width = `${percent}%`;
  $("#statPercent").textContent = `${percent.toLocaleString(locale())} %`;
  $("#statBytes").textContent = progress.bytes_total ? `${formatSize(progress.bytes_done)} / ${formatSize(progress.bytes_total)}` : "—";
  $("#statSpeed").textContent = progress.speed ? `${formatSize(progress.speed)}/s` : "—";
  $("#statEta").textContent = progress.eta !== null ? formatDuration(progress.eta) : "—";
  $("#statFiles").textContent = progress.files_total ? `${progress.files_done} / ${progress.files_total}` : "—";
  $("#statCurrent").textContent = progress.phase === "scanning" ? t("progress.scanning")
    : progress.phase === "report" ? t("progress.pdf")
      : progress.phase === "verifying_image" ? t("progress.image") : progress.current;
}

$("#cancelButton").addEventListener("click", async () => {
  if (!state.job) return;
  $("#cancelButton").disabled = true;
  await api(`/api/jobs/${state.job.id}`, { method: "DELETE" }).catch(() => {});
});

// --- Registro -------------------------------------------------------------------------------

async function openRecord(id) {
  state.recordData = await api(`/api/records/${id}`);
  state.record = state.recordData.record;
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
    }, t("copy")))));
  $("#compareInput").value = "";
  $("#compareResult").textContent = "";
  $("#dirHashNote").hidden = record.kind !== "directory";

  renderReports(data.reports);
  $("#exportStatus").textContent = "";

  const form = $("#verifyForm");
  form.examiner.value = form.examiner.value || recall("examiner");
  form.target.value = "";
  form.notes.value = "";
  form.output.value = recall("output") || state.info.reports_folder;

  const caseFacts = ["case_number", "evidence_number", "examiner", "organization", "description", "notes"]
    .filter(name => record.case[name]).map(name => [t(`case.${name}`), record.case[name]]);
  facts($("#recordCase"), caseFacts);
  facts($("#recordEvidence"), evidenceFacts(record));

  renderTimeline(record);
  renderFiles(record);

  const seal = $("#recordSeal");
  seal.className = data.seal_ok ? "ok-text" : "bad-text";
  seal.textContent = data.seal_ok ? t("seal.ok", record.seal.value) : t("seal.bad");
  facts($("#recordTrust"), trustFacts(record, data));
}

function trustFacts(record, data) {
  const rows = [[t("sig.title"), t(`sig.${data.signature}`)]];
  if (record.signature) rows.push([t("sig.fingerprint"), record.signature.fingerprint]);
  const creator = record.environment.fingerprint;
  if (creator && creator !== record.signature?.fingerprint) rows.push([t("sig.creator"), creator]);
  const stamps = record.timestamps || [];
  stamps.forEach(stamp => rows.push([t("ts.title"),
    `${formatDate(stamp.time)} · ${stamp.tsa}${stamp.seal === record.seal.value ? "" : ` (${t("ts.old")})`}`]));
  if (!stamps.length) rows.push([t("ts.title"), t("ts.none")]);
  if (record.image) {
    rows.push([t("img.title"), `${t(`status.${record.image.result || "pending"}`)} · ${record.image.path}`]);
  }
  return rows;
}

function renderReports(reports) {
  const list = $("#reportList");
  if (!reports.length) {
    list.replaceChildren(el("li", { class: "muted" }, t("pdf.none")));
    return;
  }
  list.replaceChildren(...reports.slice().reverse().map(report => {
    const name = report.path.split(/[\\/]/).pop();
    return el("li", { class: report.exists ? "" : "missing" },
      pdfIcon(),
      el("div", {}, el("b", {}, name), el("small", { class: "mono" }, report.exists ? report.path : t("pdf.missing"))),
      report.exists ? el("div", { class: "report-actions" },
        el("button", { type: "button", class: "secondary small", onclick: () => openPath(report.path, false) }, t("pdf.open")),
        el("button", { type: "button", class: "ghost small", onclick: () => openPath(report.path, true) }, t("pdf.folder"))) : null);
  }));
}

function pdfIcon() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.innerHTML = '<path d="M6 3h8l4 4v14H6z M14 3v4h4"/><path d="M9 13h6M9 17h4"/>';
  return svg;
}

async function openPath(path, folder) {
  try {
    await post("/api/open", { path, folder });
  } catch (error) {
    toast(error.message);
  }
}

$("#newPdf").addEventListener("click", async () => {
  const folder = await pick("folder");
  if (!folder) return;
  const status = $("#exportStatus");
  status.textContent = t("progress.pdf");
  try {
    const result = await post(`/api/records/${state.record.id}/pdf`, { folder, lang: I18N.lang });
    status.textContent = t("pdf.saved", result.pdf);
    state.recordData = await api(`/api/records/${state.record.id}`);
    renderReports(state.recordData.reports);
  } catch (error) {
    status.textContent = error.message;
  }
});

function facts(container, rows) {
  container.replaceChildren(...rows.flatMap(([key, value]) => [el("dt", {}, key), el("dd", {}, String(value))]));
}

function evidenceFacts(record) {
  const source = record.source || {};
  const details = record.details || {};
  const kindLabel = record.kind === "disk"
    ? { image: t("ev.image"), volume: t("ev.volume"), ewf: "E01" }[source.kind] || t("kind.disk") : t(`kind.${record.kind}`);
  const rows = [[t("ev.kind"), kindLabel], [t("ev.size"), `${formatSize(record.size)} (${record.size.toLocaleString(locale())} bytes)`]];
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
  if ("write_protected" in source) {
    const value = source.write_protected;
    rows.push([t("ev.protected"), value === null ? t("ev.unknown") : t(value ? "ev.yes" : "ev.no")]);
  }
  if (details.ewf) {
    const match = details.ewf.match;
    rows.push([t("ev.ewf"), t(match === null ? "ev.ewf_none" : match ? "ev.ewf_ok" : "ev.ewf_bad")]);
  }
  if (details.live_system) rows.push([t("ev.live"), "⚠"]);
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
    el("td", {}, file.size.toLocaleString(locale())),
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
  const data = caseData(event.target);
  if (!data.examiner.trim()) { toast(t("err.verifier")); return; }
  remember("examiner", data.examiner);
  if (data.output) remember("output", data.output);
  try {
    const job = await post(`/api/records/${state.record.id}/verify`, {
      examiner: data.examiner, target: data.target || null, notes: data.notes, output: data.output || null,
      lang: I18N.lang, timestamp: useTimestamp(),
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
      el("div", { class: "history-side" }, el("span", { class: `pill ${status}` }, t(`status.${status}`)),
        el("div", { class: "sub" }, t(item.verifications === 1 ? "history.verification" : "history.verifications", item.verifications))));
  }));
}

$("#historySearch").addEventListener("input", renderHistory);

// Importar el informe PDF de otro equipo: lleva dentro el registro firmado.
$("#importFile").addEventListener("change", async event => {
  const file = event.target.files[0];
  event.target.value = "";
  if (!file) return;
  try {
    const result = await api("/api/import", { method: "POST", body: await file.arrayBuffer(), headers: { "Content-Type": "application/pdf" } });
    await openRecord(result.id);
    toast(t(result.already_present ? "import.present" : "import.done"));
  } catch (error) {
    toast(error.message);
  }
});

// --- Custodia ---------------------------------------------------------------------------------

async function loadCustody() {
  const data = await api("/api/custody");
  const ok = data.check.ok;
  const box = $("#custodyStatus");
  box.className = `verdict ${ok ? "verified" : "broken"}`;
  const broken = data.check.reason === "truncated" ? t("custody.truncated_text") : t("custody.broken_text", data.check.broken_at);
  box.replaceChildren(el("span", { class: "badge" }, t(ok ? "custody.ok" : "custody.broken")),
    el("p", {}, ok ? t("custody.ok_text", data.check.events) : broken));
  const body = $("#custodyBody");
  if (!data.events.length) {
    body.replaceChildren(el("tr", {}, el("td", { colspan: 6, class: "muted" }, t("custody.empty"))));
    return;
  }
  body.replaceChildren(...data.events.slice().reverse().map(event => {
    let action = t(`act.${event.action}`);
    if (event.action === "verified") action += `: ${t(`status.${event.result}`)}`;
    if (event.action === "exported") action += ` (${(event.format || "").toUpperCase()})`;
    const record = event.record_id
      ? el("a", { href: "#", onclick: e => { e.preventDefault(); openRecord(event.record_id).catch(err => toast(err.message)); } },
        event.evidence_number || event.target) : "";
    return el("tr", {},
      el("td", {}, event.seq), el("td", {}, formatDate(event.time)), el("td", {}, action),
      el("td", { class: "mono" }, record), el("td", {}, event.examiner || ""),
      el("td", { class: "mono", title: event.hash }, (event.hash || "").slice(0, 12) + "…"));
  }));
}

// --- Ajustes: tema, idioma y actualizaciones ----------------------------------------------------

const darkQuery = matchMedia("(prefers-color-scheme: dark)");

// Claro u oscuro. Hasta que se elija uno en Ajustes, se usa el de Windows.
function themeChoice() {
  const saved = recall("theme");
  return saved === "light" || saved === "dark" ? saved : "";
}

function applyTheme(choice) {
  const theme = choice || (darkQuery.matches ? "dark" : "light");
  document.documentElement.dataset.theme = theme;
  $$("[data-theme-choice]").forEach(button => button.classList.toggle("active", button.dataset.themeChoice === theme));
  state.desktop?.set_theme(theme);  // Bordes y fondo de la ventana del mismo color
}

darkQuery.addEventListener("change", () => { if (!themeChoice()) applyTheme(""); });
$$("[data-theme-choice]").forEach(button => button.addEventListener("click", () => {
  remember("theme", button.dataset.themeChoice);
  applyTheme(button.dataset.themeChoice);
}));

$$("[data-lang-choice]").forEach(button => button.addEventListener("click", () => I18N.setLang(button.dataset.langChoice)));

function renderLanguage() {
  $$("[data-lang-choice]").forEach(button => button.classList.toggle("active", button.dataset.langChoice === I18N.lang));
}

const useTimestamp = () => recall("timestamp") !== "0";
$("#useTimestamp").addEventListener("change", event => remember("timestamp", event.target.checked ? "1" : "0"));

const autoUpdate = () => recall("autoUpdate") !== "0";
$("#autoUpdate").addEventListener("change", event => remember("autoUpdate", event.target.checked ? "1" : "0"));

async function checkUpdates(manual) {
  const status = $("#updateStatus");
  if (manual) status.textContent = t("update.checking");
  try {
    state.update = await api("/api/update");
  } catch (error) {
    if (manual) status.textContent = t("update.error", error.message);
    return;
  }
  if (state.update.available) {
    $("#updateText").textContent = t("update.available", state.update.latest);
    $("#updateNotes").href = state.update.notes_url;
    $("#updateBanner").hidden = false;
    if (manual) status.textContent = t("update.available", state.update.latest);
  } else if (manual) {
    status.textContent = t("update.latest", state.update.current);
  }
}

$("#checkUpdates").addEventListener("click", () => checkUpdates(true));
$("#updateDismiss").addEventListener("click", () => { $("#updateBanner").hidden = true; });
$("#updateInstall").addEventListener("click", async () => {
  if (state.desktop && state.update?.can_install) {
    $("#updateInstall").disabled = true;
    $("#updateText").textContent = t("update.installing");
    const error = await state.desktop.install_update();
    if (error) {
      $("#updateText").textContent = I18N.error(error);
      $("#updateInstall").disabled = false;
    }
  } else {
    window.open(state.update?.notes_url || state.info.repo + "/releases/latest", "_blank", "noopener");
  }
});

function renderAbout() {
  facts($("#aboutFacts"), [
    [t("about.version"), `${state.info.app} ${state.info.version}`],
    [t("about.data"), state.info.home],
    [t("about.reports"), recall("output") || state.info.reports_folder],
    [t("sig.fingerprint"), state.info.signing.fingerprint],
    [t("about.repo"), state.info.repo],
  ]);
}

document.addEventListener("langchange", () => {
  renderLanguage();
  $("#targetPath").placeholder = t(state.kind === "directory" ? "path.directory" : "path.file");
  if (!state.info) return;
  renderAbout();
  renderAlgorithms();
  if (state.step === 4) renderSummary();
  if (state.disks.length) renderDisks();
  if (state.record && $("#view-record").classList.contains("active")) renderRecord();
  if ($("#view-history").classList.contains("active")) renderHistory();
  if ($("#view-custody").classList.contains("active")) loadCustody();
});

window.addEventListener("pywebviewready", () => {
  state.desktop = window.pywebview.api;
  state.desktop.set_theme(document.documentElement.dataset.theme);
  if (state.kind === "disk") loadDisks();
});

// --- Inicio ---------------------------------------------------------------------------------

(async function init() {
  applyTheme(themeChoice());
  I18N.apply();
  renderLanguage();
  state.info = await api("/api/info");
  renderAlgorithms();
  renderAbout();
  $("#autoUpdate").checked = autoUpdate();
  $("#useTimestamp").checked = useTimestamp();
  const form = $("#caseForm");
  form.examiner.value = recall("examiner");
  form.organization.value = recall("organization");
  $("#outputPath").value = recall("output") || state.info.reports_folder;
  setKind("file");
  goToStep(1);
  await openLink();
  if (autoUpdate()) checkUpdates(false);
})();

window.addEventListener("hashchange", () => { if (state.info) openLink(); });

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
      show("new");
      setKind(params.get("kind"));
      goToStep(1);
    } else if (params.get("view")) {
      show(params.get("view"));
    }
  } catch {
    history.replaceState(null, "", location.pathname);
  }
}
