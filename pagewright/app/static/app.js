"use strict";
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const files = [];
let mode = "manual";
let provider = "anthropic";
let polling = null;
let lastResult = null; // {id, result} — to re-localize the result view on language change

/* ───────── toast ───────── */
function toast(msg, kind = "ok") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<span class="ti">${kind === "ok" ? "✓" : "!"}</span><span></span>`;
  el.querySelector("span:last-child").textContent = msg;
  $("#toastHost").appendChild(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 260); }, 2600);
}

/* ───────── settings ───────── */
async function loadSettings() {
  const s = await (await fetch("/api/settings")).json();
  provider = s.llm || "anthropic";
  setProvider(provider, false);
  $("#model").value = s.model || "";
  $("#baseUrl").value = s.base_url || "";
  $("#apiKey").value = s.api_key_set ? s.api_key : "";
  $("#targetLang").value = s.target_lang ?? "zh-CN";
  $("#theme").value = s.theme || "editorial";
  refreshHealth();
}
function setProvider(p, fromClick = true) {
  provider = p;
  $$(".prov-card").forEach((c) => c.classList.toggle("active", c.dataset.prov === p));
  $("#baseUrlRow").classList.toggle("hidden", p !== "openai");
  if (fromClick) $("#apiKey").focus();
}
async function saveSettings() {
  const payload = {
    llm: provider, model: $("#model").value.trim(), base_url: $("#baseUrl").value.trim(),
    target_lang: $("#targetLang").value, theme: $("#theme").value,
  };
  const k = $("#apiKey").value.trim();
  if (k && !k.startsWith("•")) payload.api_key = k;
  await fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload) });
  closeModal();
  toast(t("t.saved"));
  refreshHealth();
}
async function refreshHealth() {
  const h = await (await fetch("/api/health")).json();
  const pill = $("#statusPill"), txt = $("#statusText");
  pill.classList.remove("ok", "warn");
  let key;
  if (!h.renderer) { pill.classList.add("warn"); key = "status.norender"; }
  else if (!h.configured) { pill.classList.add("warn"); key = "status.unset"; }
  else { pill.classList.add("ok"); key = "status.ready"; }
  txt.dataset.i18n = key; txt.textContent = t(key);
}

/* ───────── modal ───────── */
function openModal() { $("#settings").classList.remove("hidden"); }
function closeModal() { $("#settings").classList.add("hidden"); }

/* ───────── segmented control ───────── */
$$(".seg-btn").forEach((b) => b.onclick = () => {
  $$(".seg-btn").forEach((x) => x.classList.remove("active"));
  b.classList.add("active");
  mode = b.dataset.mode;
  $(".seg-ind").classList.toggle("right", mode === "url");
  $("#pane-manual").classList.toggle("hidden", mode !== "manual");
  $("#pane-url").classList.toggle("hidden", mode !== "url");
});

/* ───────── description counter ───────── */
$("#desc").addEventListener("input", (e) => {
  $("#descCount").textContent = [...e.target.value].length + t("count.suffix");
});

/* ───────── files ───────── */
function addFiles(list) {
  for (const f of list) if (f.type.startsWith("image/")) files.push({ file: f, url: URL.createObjectURL(f) });
  renderThumbs();
}
function renderThumbs() {
  const c = $("#thumbs"); c.innerHTML = "";
  files.forEach((f, i) => {
    const d = document.createElement("div");
    d.className = "t";
    d.innerHTML = `<img alt=""><button class="x" data-i="${i}" title="">×</button>`;
    d.querySelector("img").src = f.url;
    c.appendChild(d);
  });
  $$("#thumbs .x").forEach((b) => b.onclick = () => { files.splice(+b.dataset.i, 1); renderThumbs(); });
}
const drop = $("#drop");
drop.onclick = () => $("#fileInput").click();
drop.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("#fileInput").click(); } };
$("#fileInput").onchange = (e) => addFiles(e.target.files);
["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("drag"); }));
["dragleave", "dragend"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("drag")));
drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("drag"); addFiles(e.dataTransfer.files); });

/* ───────── canvas state ───────── */
function showState(name) {
  $("#stateEmpty").classList.toggle("hidden", name !== "empty");
  $("#stateProgress").classList.toggle("hidden", name !== "progress");
  $("#stateResult").classList.toggle("hidden", name !== "result");
}

/* ───────── generate ───────── */
$("#genBtn").onclick = async () => {
  if (mode === "manual" && files.length === 0 && !$("#desc").value.trim())
    return toast(t("t.needInput"), "err");
  if (mode === "url" && !$("#url").value.trim()) return toast(t("t.needUrl"), "err");

  const fd = new FormData();
  fd.append("mode", mode);
  fd.append("description", $("#desc").value);
  fd.append("url", $("#url").value);
  fd.append("target_lang", $("#targetLang").value);
  fd.append("theme", $("#theme").value);
  for (const f of files) fd.append("files", f.file, f.file.name);

  $("#genBtn").disabled = true;
  $("#progTitle").textContent = t("prog.title");
  $("#progressList").innerHTML = "";
  showState("progress");

  let job;
  try { job = await (await fetch("/api/generate", { method: "POST", body: fd })).json(); }
  catch (e) { return fail(t("t.reqfail") + e); }
  poll(job.job_id);
};

function stepLabel(key) { return t("p." + key) !== "p." + key ? t("p." + key) : key; }

function renderTimeline(messages, finished) {
  const steps = messages.filter((m) => m !== "queued" && !m.startsWith("error:"));
  const ul = $("#progressList"); ul.innerHTML = "";
  steps.forEach((m, i) => {
    const li = document.createElement("li");
    const isLast = i === steps.length - 1;
    li.className = (finished || !isLast) ? "done" : "active";
    li.innerHTML = `<span class="node"></span>`;
    li.appendChild(document.createTextNode(stepLabel(m)));
    ul.appendChild(li);
  });
}

function poll(id) {
  clearInterval(polling);
  polling = setInterval(async () => {
    let j;
    try { j = await (await fetch(`/api/jobs/${id}`)).json(); } catch { return; }
    const done = j.status === "done", err = j.status === "error";
    renderTimeline(j.progress || [], done || err);
    if (done) { clearInterval(polling); $("#progTitle").textContent = t("prog.done"); showResult(id, j.result); }
    else if (err) { clearInterval(polling); fail(j.error); }
  }, 650);
}

function fail(msg) {
  clearInterval(polling);
  $("#genBtn").disabled = false;
  showState("empty");
  toast(t("t.failed") + (msg || ""), "err");
}

function dlIcon() {
  return `<svg viewBox="0 0 24 24"><path d="M12 4v11m0 0l-4-4m4 4l4-4M5 19h14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

function showResult(id, r) {
  lastResult = { id, result: r };
  $("#genBtn").disabled = false;
  const base = `/api/jobs/${id}/file`;
  $("#resultDim").textContent = r.size ? `${t("prog.done")} · ${r.size[0]}×${r.size[1]}` : t("prog.done");

  const dl = $("#downloads"); dl.innerHTML = "";
  const full = document.createElement("a");
  full.href = `${base}/full.png`; full.download = "detail_full.png"; full.className = "btn solid";
  full.innerHTML = dlIcon(); full.appendChild(document.createTextNode(t("dl.full")));
  dl.appendChild(full);
  if (r.spec) {
    const a = document.createElement("a");
    a.href = `${base}/${r.spec}`; a.download = "product_spec.json"; a.className = "btn";
    a.innerHTML = `<svg viewBox="0 0 24 24"><path d="M8 4h8l4 4v12H4V4h4z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
    a.appendChild(document.createTextNode(t("dl.spec")));
    dl.appendChild(a);
  }

  $("#preview").innerHTML = "";
  const img = document.createElement("img");
  img.src = `${base}/full.png?t=${Date.now()}`; img.alt = "detail page";
  $("#preview").appendChild(img);

  const strip = $("#panelStrip"); strip.innerHTML = "";
  (r.panels || []).forEach((p) => {
    const a = document.createElement("a");
    a.href = `${base}/${p}`; a.download = p; a.title = t("dl.panel");
    const im = document.createElement("img"); im.src = `${base}/${p}?t=${Date.now()}`; im.alt = p;
    a.appendChild(im); strip.appendChild(a);
  });
  showState("result");
}

/* ───────── library / history ───────── */
async function openLibrary() {
  $("#library").classList.remove("hidden");
  await refreshLibrary();
}
function closeLibrary() { $("#library").classList.add("hidden"); }

async function refreshLibrary() {
  const body = $("#libBody");
  let data;
  try { data = await (await fetch("/api/library")).json(); } catch { return; }
  const groups = data.groups || [];
  if (!groups.length) { body.innerHTML = `<div class="lib-empty">${t("lib.empty")}</div>`; return; }
  body.innerHTML = "";
  for (const g of groups) {
    const sec = document.createElement("div");
    sec.className = "lib-group";
    const title = g.entries[0]?.title_secondary && LANG === "zh-CN" ? g.entries[0].title_secondary : g.title;
    sec.innerHTML = `<div class="lib-group-h"><span class="lib-proj">${escapeHtml(title)}</span>
      <span class="lib-count">${g.entries.length} ${t("lib.versions")}</span></div>`;
    const grid = document.createElement("div"); grid.className = "lib-grid";
    g.entries.forEach((m) => grid.appendChild(libCard(m)));
    sec.appendChild(grid); body.appendChild(sec);
  }
}

function libCard(m) {
  const base = `/api/library/${m.id}/file`;
  const card = document.createElement("div"); card.className = "lib-card";
  const thumb = m.files?.thumb ? `${base}/${m.files.thumb}` : `${base}/full.png`;
  const date = (m.created_at || "").slice(0, 16).replace("T", " ");
  card.innerHTML = `
    <div class="lib-thumb"><img loading="lazy" src="${thumb}" alt=""><span class="lib-ver">v${m.version}</span></div>
    <div class="lib-meta"><span class="lib-date">${date}</span>
      <span class="lib-badges">${m.theme ? `<i>${m.theme}</i>` : ""}${m.target_lang ? `<i>${m.target_lang}</i>` : ""}</span></div>
    <div class="lib-actions"></div>`;
  card.querySelector(".lib-thumb").onclick = () => lightbox(`${base}/full.png`);
  const acts = card.querySelector(".lib-actions");
  acts.appendChild(libBtn(t("lib.view"), () => lightbox(`${base}/full.png`)));
  const dl = document.createElement("a");
  dl.className = "lib-btn"; dl.href = `${base}/full.png`; dl.download = `${m.project}_v${m.version}.png`;
  dl.textContent = t("lib.download"); acts.appendChild(dl);
  acts.appendChild(libBtn(t("lib.regen"), () => regen(m.id)));
  acts.appendChild(libBtn(t("lib.delete"), () => delEntry(m.id), "danger"));
  return card;
}
function libBtn(label, fn, cls = "") {
  const b = document.createElement("button"); b.className = "lib-btn " + cls; b.textContent = label; b.onclick = fn; return b;
}
async function regen(id) {
  await fetch(`/api/library/${id}/regenerate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  toast(t("lib.regenDone")); refreshLibrary();
}
async function delEntry(id) {
  if (!confirm(t("lib.confirmDel"))) return;
  await fetch(`/api/library/${id}`, { method: "DELETE" });
  toast(t("lib.deleted")); refreshLibrary();
}
function lightbox(src) {
  $("#lightboxImg").src = src; $("#lightbox").classList.remove("hidden");
}
function escapeHtml(s) { const d = document.createElement("div"); d.textContent = s || ""; return d.innerHTML; }

/* ───────── wire UI ───────── */
$("#historyBtn").onclick = openLibrary;
$$("[data-lib-close]").forEach((el) => el.onclick = closeLibrary);
$$("[data-lb-close]").forEach((el) => el.onclick = () => $("#lightbox").classList.add("hidden"));
$("#settingsBtn").onclick = openModal;
$("#statusPill").onclick = openModal;
$$("[data-close]").forEach((el) => el.onclick = closeModal);
$("#saveSettings").onclick = saveSettings;
$$(".prov-card").forEach((c) => c.onclick = () => setProvider(c.dataset.prov));
$("#toggleKey").onclick = () => { const i = $("#apiKey"); i.type = i.type === "password" ? "text" : "password"; };
$("#langBtn").onclick = toggleLang;
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!$("#lightbox").classList.contains("hidden")) $("#lightbox").classList.add("hidden");
  else if (!$("#library").classList.contains("hidden")) closeLibrary();
  else closeModal();
});
document.addEventListener("langchange", () => {  // re-localize dynamic bits
  refreshHealth();
  if (lastResult && !$("#stateResult").classList.contains("hidden")) showResult(lastResult.id, lastResult.result);
});
if (location.hash === "#settings") openModal();
if (location.hash === "#library") openLibrary();

applyI18n();
loadSettings();
