// ShortGeek -- frontend. Plain JS on purpose: no build step, so the
// app stays as easy to tinker with as the mockup it was built from.

const state = {
  currentScript: null,
  voiceEngine: "edge",
  captionStyle: "bold_highlight",
  backgroundStyle: "content_pan",
  seenDoneJobs: new Set(),
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

async function jsonFetch(url, opts) {
  const resp = await fetch(url, opts);
  if (!resp.ok) {
    let detail = resp.statusText;
    try { detail = (await resp.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return resp.json();
}

// ---------------------------------------------------------------- nav/views

function switchView(view) {
  $$(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.view === view));
  $$(".view").forEach((el) => el.classList.toggle("active", el.id === `view-${view}`));
  if (view === "library") loadLibrary();
  if (view === "backgrounds") loadClipsManage();
  if (view === "about") loadAbout();
}

// Clears the script draft and source inputs back to a blank slate. "New
// Short" previously only switched to the New Short view -- if you were
// already sitting on that view (the normal case right after a render),
// clicking it did nothing visible at all, since there was no view change
// to make. It now always resets the form, whether or not the view itself
// changes.
function resetNewShortForm() {
  state.currentScript = null;
  $("#pasteInput").value = "";
  $("#hookField").value = "";
  $("#ctaField").value = "";
  $("#beatsList").innerHTML = "";
  $("#scriptEditor").classList.add("hidden");
  $("#scriptEmpty").classList.remove("hidden");
  $("#generateBtn").disabled = true;
  $("#draftBtn").disabled = false;
  $("#draftBtn").textContent = "✏️ Draft script";
}

function initNav() {
  $$(".nav-item").forEach((el) =>
    el.addEventListener("click", () => {
      if (el.dataset.view === "new") resetNewShortForm();
      switchView(el.dataset.view);
    })
  );
}

// Explicit "start the next one" action for batch creation -- draft, generate,
// hit Clear, draft the next script while the last one is still rendering in
// the queue (the queue panel itself is untouched by this, on purpose).
function initClearButton() {
  $("#clearFormBtn").addEventListener("click", () => {
    resetNewShortForm();
    const pill = $("#clearedPill");
    pill.style.display = "inline-block";
    setTimeout(() => (pill.style.display = "none"), 1500);
  });
}

// ------------------------------------------------------------------ script

function beatTag(beat) {
  if (beat.is_code) return "💻 Code / command";
  if (beat.image_url) return "🖼️ Text + screenshot";
  return "📝 Text callout";
}

// Uploads a screenshot for one beat and stores the returned local reference
// on that beat -- never a URL, never sent anywhere except to this app's own
// local server. Re-renders just that row's thumbnail once it's back.
async function attachBeatImage(idx, file) {
  const row = $(`#beatsList .beat-row[data-idx="${idx}"]`);
  const shotArea = row.querySelector(".beat-shot");
  shotArea.innerHTML = '<div class="hint">Uploading…</div>';
  try {
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch("/api/beat-image/upload", { method: "POST", body: form });
    if (!resp.ok) {
      let detail = resp.statusText;
      try { detail = (await resp.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    const data = await resp.json();
    state.currentScript.beats[idx].image_url = data.image_ref;
    renderBeatShot(idx, data.preview_url);
    row.querySelector(".beat-tag").textContent = beatTag(state.currentScript.beats[idx]);
  } catch (e) {
    shotArea.innerHTML = `<div class="hint">Couldn't attach that image: ${escapeHtml(e.message)}</div>`;
  }
}

function removeBeatImage(idx) {
  state.currentScript.beats[idx].image_url = null;
  renderBeatShot(idx, null);
  const row = $(`#beatsList .beat-row[data-idx="${idx}"]`);
  row.querySelector(".beat-tag").textContent = beatTag(state.currentScript.beats[idx]);
}

function renderBeatShot(idx, previewUrl) {
  const shotArea = $(`#beatsList .beat-row[data-idx="${idx}"] .beat-shot`);
  if (!shotArea) return;
  if (previewUrl) {
    shotArea.innerHTML = `
      <img src="${previewUrl}" alt="Attached screenshot" class="beat-shot-thumb" />
      <a href="#" class="beat-shot-remove" data-idx="${idx}">Remove screenshot</a>`;
  } else {
    shotArea.innerHTML = `
      <label class="btn-ghost beat-shot-attach">
        📎 Attach a small screenshot
        <input type="file" accept="image/png,image/jpeg,image/webp" data-idx="${idx}" style="display:none;">
      </label>`;
  }
}

function renderScriptEditor(script) {
  state.currentScript = script;
  $("#hookField").value = script.hook;
  $("#ctaField").value = script.cta;
  const beatsList = $("#beatsList");
  beatsList.innerHTML = "";
  script.beats.forEach((b, i) => {
    const row = document.createElement("div");
    row.className = "beat-row";
    row.dataset.idx = i;
    const codeNote = b.is_code
      ? `<div class="hint" style="margin:4px 0 0;">On screen: <code>${escapeHtml((b.code_display || "").slice(0, 70))}${(b.code_display || "").length > 70 ? "…" : ""}</code></div>`
      : "";
    row.innerHTML = `<span class="beat-tag">${beatTag(b)}</span><textarea data-idx="${i}" rows="2">${escapeHtml(b.text)}</textarea>${codeNote}<div class="beat-shot"></div>`;
    beatsList.appendChild(row);
    if (!b.is_code) renderBeatShot(i, b.image_url ? `/api/beat-image/${String(b.image_url).replace("beatimg://", "")}` : null);
  });
  $("#durationPill").textContent = `≈ ${Math.round(script.estimated_seconds || estimateSeconds(script))} sec`;
  $("#scriptEmpty").classList.add("hidden");
  $("#scriptEditor").classList.remove("hidden");
  $("#generateBtn").disabled = false;
}

function estimateSeconds(script) {
  const words = [script.hook, ...script.beats.map((b) => b.text), script.cta].join(" ").split(/\s+/).filter(Boolean).length;
  return words / 2.5;
}

// Generic on purpose -- no brand handle, no "full guide linked in bio" claim
// that might not be true for every script. Seeded off the pasted text so the
// same paste always lands on the same line rather than reshuffling every
// time you re-draft it.
const CTA_POOL = ["Follow for more.", "Follow for more like this.", "Follow along for more."];

function pickCta(seedText) {
  let hash = 0;
  for (let i = 0; i < seedText.length; i++) {
    hash = (hash * 31 + seedText.charCodeAt(i)) >>> 0;
  }
  return CTA_POOL[hash % CTA_POOL.length];
}

function collectScriptFromEditor() {
  const hook = $("#hookField").value.trim();
  const cta = $("#ctaField").value.trim();
  const beats = $$("#beatsList textarea").map((ta, i) => ({
    text: ta.value.trim(),
    image_url: state.currentScript.beats[i]?.image_url || null,
    is_code: !!state.currentScript.beats[i]?.is_code,
    code_display: state.currentScript.beats[i]?.code_display || null,
  }));
  return { hook, beats, cta, source_title: state.currentScript.source_title || hook };
}

async function draftScript() {
  const btn = $("#draftBtn");
  btn.disabled = true;
  btn.textContent = "Drafting…";
  try {
    const raw = $("#pasteInput").value.trim();
    if (!raw) throw new Error("Write or paste a script first.");
    let lines = raw.split(/\n+/).map((l) => l.trim()).filter(Boolean);
    if (lines.length < 2) {
      // No line breaks in what was pasted (a single paragraph of prose,
      // sentences separated by periods rather than actual newlines). Split
      // on sentence boundaries instead, so a pasted paragraph turns into a
      // real hook + separate beats like it should, rather than the whole
      // thing getting spoken twice (once as the hook, once as one giant beat).
      lines = (raw.match(/[^.!?]+[.!?]+(?:\s+|$)/g) || [raw]).map((s) => s.trim()).filter(Boolean);
    }
    const script = {
      hook: lines[0] || raw.slice(0, 80),
      beats: lines.length > 1 ? lines.slice(1).map((t) => ({ text: t, image_url: null, is_code: false })) : [{ text: "Here's what you need to know.", image_url: null, is_code: false }],
      cta: pickCta(raw),
      source_title: lines[0] || "Pasted script",
    };
    script.estimated_seconds = estimateSeconds(script);
    renderScriptEditor(script);
  } catch (e) {
    showGenError(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "✏️ Draft script";
  }
}

// -------------------------------------------------------------- voice/style

function initStylePickers() {
  $("#voiceEngine").addEventListener("change", (e) => (state.voiceEngine = e.target.value));
  $$("#capTabs .cap-swatch").forEach((el) =>
    el.addEventListener("click", () => {
      $$("#capTabs .cap-swatch").forEach((x) => x.classList.remove("selected"));
      el.classList.add("selected");
      state.captionStyle = el.dataset.val;
    })
  );
  // Delegated (not per-element) so swatches added later by
  // loadCustomBackgrounds() are clickable without re-binding anything.
  // Bound on BOTH containers -- built-ins live in #bgSwatches, your own
  // clips get injected into the separate #customBgSwatches -- and the
  // "clear selected" sweep spans both, so picking one always deselects
  // the other.
  const onSwatchClick = (e) => {
    const el = e.target.closest(".swatch");
    if (!el) return;
    $$("#bgSwatches .swatch, #customBgSwatches .swatch").forEach((x) => x.classList.remove("selected"));
    el.classList.add("selected");
    state.backgroundStyle = el.dataset.val;
  };
  $("#bgSwatches").addEventListener("click", onSwatchClick);
  $("#customBgSwatches").addEventListener("click", onSwatchClick);
}

async function loadCustomBackgrounds() {
  try {
    const data = await jsonFetch("/api/backgrounds/custom");
    const wrap = $("#customBgSwatches");
    if (!data.items.length) {
      wrap.innerHTML =
        '<div class="hint" style="margin-top:2px;">No clips yet - add one from the 🎬 Backgrounds page in the sidebar (open the folder or upload directly).</div>';
      return;
    }
    let html = "";
    data.items.forEach((name) => {
      const label = name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ");
      const thumbUrl = `/api/backgrounds/custom/thumb/${encodeURIComponent(name)}`;
      html += `<div class="swatch" data-val="custom:${escapeHtml(name)}">
        <div class="swatch-thumb" style="background-image:url('${thumbUrl}');background-size:cover;background-position:center;"></div>
        <div class="swatch-label">${escapeHtml(label)}</div>
      </div>`;
    });
    html += `<div class="swatch" data-val="custom_random">
      <div class="swatch-thumb t-random">🎲</div>
      <div class="swatch-label">Random of mine</div>
    </div>`;
    wrap.innerHTML = html;
  } catch (e) {
    // optional feature -- fail silently
  }
}

// ------------------------------------------------------- backgrounds (manage)

async function loadClipsManage() {
  const grid = $("#clipsManageGrid");
  try {
    const data = await jsonFetch("/api/backgrounds/custom");
    if (!data.items.length) {
      grid.innerHTML = '<div class="hint">No clips yet - open the folder or upload one above.</div>';
      return;
    }
    grid.innerHTML = "";
    data.items.forEach((name) => {
      const label = name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ");
      const thumbUrl = `/api/backgrounds/custom/thumb/${encodeURIComponent(name)}`;
      const card = document.createElement("div");
      card.className = "library-card";
      card.innerHTML = `
        <div style="aspect-ratio:9/16;background:#000 url('${thumbUrl}') center/cover;"></div>
        <div class="lc-body">
          <div class="lc-title">${escapeHtml(label)}</div>
          <a href="#" data-name="${escapeHtml(name)}" class="clip-delete-link">Delete</a>
        </div>`;
      card.querySelector(".clip-delete-link").addEventListener("click", async (e) => {
        e.preventDefault();
        if (!confirm(`Delete "${name}"? This can't be undone.`)) return;
        try {
          await jsonFetch(`/api/backgrounds/custom/${encodeURIComponent(name)}`, { method: "DELETE" });
          loadClipsManage();
          loadCustomBackgrounds();
        } catch (err) {
          alert(`Couldn't delete: ${err.message}`);
        }
      });
      grid.appendChild(card);
    });
  } catch (e) {
    grid.innerHTML = `<div class="hint">Couldn't load clips: ${escapeHtml(e.message)}</div>`;
  }
}

async function openClipsFolder() {
  try {
    await jsonFetch("/api/backgrounds/custom/open-folder", { method: "POST" });
  } catch (e) {
    alert(`Couldn't open the folder: ${e.message}`);
  }
}

async function uploadClip(file) {
  const status = $("#uploadStatus");
  if (!file.name.toLowerCase().endsWith(".mp4")) {
    status.textContent = "Only .mp4 files are supported.";
    return;
  }
  status.textContent = `Uploading ${file.name}…`;
  try {
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch("/api/backgrounds/custom/upload", { method: "POST", body: form });
    if (!resp.ok) {
      let detail = resp.statusText;
      try { detail = (await resp.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    status.textContent = "Uploaded ✓";
    loadClipsManage();
    loadCustomBackgrounds();
  } catch (e) {
    status.textContent = `Upload failed: ${e.message}`;
  }
}

// ------------------------------------------------------------------- about

async function loadAbout() {
  try {
    const data = await jsonFetch("/api/about");
    $("#aboutVersion").textContent = data.version;
    APP_VERSION = data.version;
    $("#verline").textContent = "v" + data.version;
    if (data.licence) $("#aboutLicence").textContent = data.licence;
    const list = $("#changelogList");
    list.innerHTML = "";
    data.changelog.forEach((entry) => {
      const block = document.createElement("div");
      block.style.marginBottom = "14px";
      const notes = entry.notes.map((n) => `<li style="margin-bottom:4px;">${escapeHtml(n)}</li>`).join("");
      block.innerHTML = `<div style="font-size:12px;font-weight:700;color:var(--accent);margin-bottom:4px;">v${escapeHtml(entry.version)}</div><ul style="margin:0;padding-left:18px;font-size:12.5px;color:var(--text);line-height:1.4;">${notes}</ul>`;
      list.appendChild(block);
    });
  } catch (e) {
    $("#changelogList").innerHTML = `<div class="hint">Couldn't load version info: ${escapeHtml(e.message)}</div>`;
  }
}

// ------------------------------------------------------------------ render

function showGenError(msg) {
  const el = $("#genError");
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 6000);
}

async function generateShort() {
  if (!state.currentScript) return;
  const btn = $("#generateBtn");
  btn.disabled = true;
  try {
    const script = collectScriptFromEditor();
    await jsonFetch("/api/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        script,
        voice_engine: state.voiceEngine,
        caption_style: state.captionStyle,
        background_style: state.backgroundStyle,
      }),
    });
    pollQueue();
    // The queue panel lives top-right; if the user scrolled down to reach
    // this button, jump back up so the new render's progress is visible
    // without them having to go find it.
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (e) {
    showGenError(e.message);
  } finally {
    btn.disabled = false;
  }
}

// -------------------------------------------------------------------- queue

async function pollQueue() {
  try {
    const data = await jsonFetch("/api/jobs");
    $("#queueCount").textContent = data.items.length;
    const list = $("#queueList");
    if (!data.items.length) {
      list.innerHTML = '<div class="hint">Nothing queued yet.</div>';
      return;
    }
    list.innerHTML = "";
    data.items.forEach((j) => {
      const pct = Math.round((j.progress || 0) * 100);
      const statusClass = j.status === "done" ? "done" : j.status === "error" ? "error" : "";
      const statusText = j.status === "running" ? `Rendering ${pct}%` : j.status === "done" ? "Done ✓" : j.status === "error" ? "Failed" : "Queued";
      const row = document.createElement("div");
      row.className = "queue-item";
      row.innerHTML = `
        <div class="qi-top"><div class="qi-title">${escapeHtml(j.title)}</div><div class="qi-status ${statusClass}">${statusText}</div></div>
        <div class="bar"><div class="bar-fill ${statusClass}" style="width:${j.status === "done" ? 100 : pct}%;"></div></div>
        ${j.message ? `<div class="qi-msg">${escapeHtml(j.message)}</div>` : ""}
      `;
      list.appendChild(row);

      if (j.status === "done" && !state.seenDoneJobs.has(j.id)) {
        state.seenDoneJobs.add(j.id);
        loadLibrary();
      }
    });
  } catch (e) {
    // silent -- queue polling shouldn't spam the UI with errors
  }
}

// ----------------------------------------------------------------- library

async function loadLibrary() {
  const grid = $("#libraryGrid");
  try {
    const data = await jsonFetch("/api/library");
    if (!data.items.length) {
      grid.innerHTML = '<div class="hint">Nothing rendered yet.</div>';
      return;
    }
    grid.innerHTML = "";
    data.items.forEach((item) => {
      const card = document.createElement("div");
      card.className = "library-card";
      const fileUrl = `/api/library/file/${encodeURIComponent(item.filename)}`;
      const date = new Date(item.created_at * 1000).toLocaleString();
      card.innerHTML = `
        <video controls preload="metadata" src="${fileUrl}"></video>
        <div class="lc-body">
          <div class="lc-title">${escapeHtml(item.title)}</div>
          <div class="lc-meta">${date} · ${Math.round(item.duration || 0)}s · ${escapeHtml(item.voice_engine || "")}</div>
          <a href="${fileUrl}" download>Download ↓</a>
        </div>`;
      grid.appendChild(card);
    });
  } catch (e) {
    grid.innerHTML = `<div class="hint">Couldn't load library: ${escapeHtml(e.message)}</div>`;
  }
}

// ---------------------------------------------------------------- settings

async function loadSettings() {
  const cfg = await jsonFetch("/api/settings");
  $("#set_brand_handle").value = cfg.brand_handle || "";
  $("#set_logo_letters").value = cfg.logo_letters || "";
  $("#set_edge_voice").value = cfg.edge_voice || "";
  $("#set_elevenlabs_voice_id").value = cfg.elevenlabs_voice_id || "";
  // The sidebar shows the APP's identity, not the user's. Their brand goes on the
  // end card of the videos, which is set under Settings and previewed there.
  // Secret fields intentionally left blank -- see saveSettings().
}

async function saveSettings() {
  const patch = {
    brand_handle: $("#set_brand_handle").value.trim(),
    logo_letters: $("#set_logo_letters").value.trim(),
    edge_voice: $("#set_edge_voice").value.trim(),
    elevenlabs_voice_id: $("#set_elevenlabs_voice_id").value.trim(),
  };
  const ev = $("#set_elevenlabs_api_key").value.trim();
  if (ev) patch.elevenlabs_api_key = ev;

  await jsonFetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  $("#settingsSaved").style.display = "inline-block";
  setTimeout(() => ($("#settingsSaved").style.display = "none"), 2000);
  loadSettings();
}

// --------------------------------------------------------------------- util

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

function init() {
  initNav();
  initStylePickers();
  initClearButton();

  $("#draftBtn").addEventListener("click", draftScript);
  $("#generateBtn").addEventListener("click", generateShort);
  $("#saveSettingsBtn").addEventListener("click", saveSettings);
  $("#openClipsFolderBtn").addEventListener("click", openClipsFolder);
  $("#clipUploadInput").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) uploadClip(file);
    e.target.value = "";
  });

  // Delegated so it works for rows the editor injects after this runs once.
  $("#beatsList").addEventListener("change", (e) => {
    if (e.target.matches('input[type="file"][data-idx]')) {
      const file = e.target.files[0];
      const idx = parseInt(e.target.dataset.idx, 10);
      if (file) attachBeatImage(idx, file);
    }
  });
  $("#beatsList").addEventListener("click", (e) => {
    const link = e.target.closest(".beat-shot-remove");
    if (link) {
      e.preventDefault();
      removeBeatImage(parseInt(link.dataset.idx, 10));
    }
  });

  initChrome();

  loadSettings();
  loadLibrary();
  loadCustomBackgrounds();
  pollQueue();
  setInterval(pollQueue, 2000);
}

document.addEventListener("DOMContentLoaded", init);


// -------------------------------------------------- chrome: updates, help, brand

var APP_VERSION = "0.0.0";
const REPO = "techygeekshome/ShortGeek";

function openVeil(el) { el.classList.add("on"); }
function closeVeils() { document.querySelectorAll(".veil").forEach((v) => v.classList.remove("on")); }

function cmpVer(a, b) {
  const pa = String(a).replace(/^v/, "").split(".").map((n) => parseInt(n, 10) || 0);
  const pb = String(b).replace(/^v/, "").split(".").map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const x = pa[i] || 0, y = pb[i] || 0;
    if (x !== y) return x > y ? 1 : -1;
  }
  return 0;
}

async function checkUpdates(quiet) {
  const btn = $("#btnUpdate");
  const label = btn.textContent;
  btn.disabled = true; btn.textContent = "Checking...";
  try {
    const r = await fetch("https://api.github.com/repos/" + REPO + "/releases/latest",
                          { headers: { Accept: "application/vnd.github+json" } });
    if (!r.ok) throw new Error("GitHub returned " + r.status);
    const d = await r.json();
    const latest = String(d.tag_name || "").replace(/^v/, "");
    const cell = $("#aboutLatest");
    if (cell) cell.textContent = latest || "unknown";
    const status = $("#aboutStatus");
    if (latest && cmpVer(latest, APP_VERSION) > 0) {
      if (status) {
        status.innerHTML = '<span class="badge new">Update available</span> Version ' +
          escapeHtml(latest) + ' is out. <a href="' + escapeHtml(d.html_url) +
          '" target="_blank" rel="noopener">See what changed</a>.';
      }
      switchView("about");
    } else if (!quiet && status) {
      status.innerHTML = '<span class="badge ok">Up to date</span> You are running the latest version.';
    }
  } catch (e) {
    const cell = $("#aboutLatest");
    if (cell) cell.textContent = "check failed";
    const status = $("#aboutStatus");
    if (!quiet && status) {
      status.innerHTML = '<span class="badge off">Could not check</span> No answer from GitHub. Try again later.';
    }
  } finally {
    btn.disabled = false; btn.textContent = label;
  }
}

async function maybeFirstRun() {
  try {
    const cfg = await jsonFetch("/api/settings");
    if (!cfg.brand_configured) openVeil($("#brandVeil"));
  } catch (e) { /* if settings can't be read, don't block the app */ }
}

async function saveFirstRun(skip) {
  const patch = { brand_configured: true };
  if (!skip) {
    const name = $("#fr_brand_name").value.trim();
    const handle = $("#fr_brand_handle").value.trim();
    const letters = $("#fr_logo_letters").value.trim();
    if (name) patch.brand_name = name;
    if (handle) patch.brand_handle = handle;
    if (letters) patch.logo_letters = letters.toUpperCase();
  }
  try {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
  } catch (e) { /* saving the brand should never stop the app opening */ }
  closeVeils();
  loadSettings();
}

function initChrome() {
  $("#btnUpdate").addEventListener("click", () => checkUpdates(false));
  $("#btnSupport").addEventListener("click", () => openVeil($("#supportVeil")));

  document.querySelectorAll(".veil").forEach((v) => {
    v.addEventListener("click", (e) => { if (e.target === v && v.id !== "brandVeil") closeVeils(); });
  });
  document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", closeVeils));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#brandVeil").classList.contains("on")) closeVeils();
  });
  document.querySelectorAll("[data-open]").forEach((b) => {
    b.addEventListener("click", () => window.open(b.dataset.open, "_blank", "noopener"));
  });

  $("#frSave").addEventListener("click", () => saveFirstRun(false));
  $("#frSkip").addEventListener("click", (e) => { e.preventDefault(); saveFirstRun(true); });

  loadAbout();
  maybeFirstRun();
}
