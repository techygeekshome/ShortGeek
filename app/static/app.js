// TGH Shorts Studio -- frontend. Plain JS on purpose: no build step, so the
// app stays as easy to tinker with as the mockup it was built from.

const state = {
  sourceTab: "guide",
  selectedGuideId: null,
  selectedUrl: null,
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
  state.selectedGuideId = null;
  state.selectedUrl = null;
  $("#topicInput").value = "";
  $("#pasteInput").value = "";
  $("#rssUrl").value = "";
  $("#rssList").innerHTML = "";
  $("#guideSearch").value = "";
  $$("#guideList .guide-item").forEach((el) => el.classList.remove("selected"));
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

// ------------------------------------------------------------------ source

function switchSourceTab(tab) {
  state.sourceTab = tab;
  $$("#sourceTabs .tab").forEach((el) => el.classList.toggle("active", el.dataset.src === tab));
  $$(".src-pane").forEach((el) => el.classList.toggle("hidden", el.dataset.pane !== tab));
}

function initSourceTabs() {
  $$("#sourceTabs .tab").forEach((el) => el.addEventListener("click", () => switchSourceTab(el.dataset.src)));
}

async function loadGuides(query = "") {
  const list = $("#guideList");
  list.innerHTML = '<div class="hint">Loading…</div>';
  try {
    const data = await jsonFetch(`/api/guides?search=${encodeURIComponent(query)}&per_page=20`);
    if (!data.items.length) {
      list.innerHTML = '<div class="hint">No guides found.</div>';
      return;
    }
    list.innerHTML = "";
    data.items.forEach((g) => {
      const row = document.createElement("div");
      row.className = "guide-item";
      row.innerHTML = `<div class="g-title">${escapeHtml(g.title)}</div><div class="g-meta">Guide</div>`;
      row.addEventListener("click", () => {
        state.selectedGuideId = g.id;
        $$("#guideList .guide-item").forEach((el) => el.classList.remove("selected"));
        row.classList.add("selected");
      });
      list.appendChild(row);
    });
  } catch (e) {
    list.innerHTML = `<div class="hint">Couldn't load guides: ${escapeHtml(e.message)}</div>`;
  }
}

async function fetchRss() {
  const url = $("#rssUrl").value.trim();
  const list = $("#rssList");
  if (!url) return;
  list.innerHTML = '<div class="hint">Fetching…</div>';
  try {
    const data = await jsonFetch("/api/rss/list", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feed_url: url }),
    });
    if (data.items && data.items.length) {
      list.innerHTML = "";
      data.items.forEach((it) => {
        const row = document.createElement("div");
        row.className = "guide-item";
        row.innerHTML = `<div class="g-title">${escapeHtml(it.title)}</div><div class="g-meta">Feed item</div>`;
        row.addEventListener("click", () => {
          state.selectedUrl = it.link;
          $$("#rssList .guide-item").forEach((el) => el.classList.remove("selected"));
          row.classList.add("selected");
        });
        list.appendChild(row);
      });
      return;
    }
    throw new Error("empty feed");
  } catch (e) {
    // Not a feed (or empty) -- treat the input as a direct page URL.
    list.innerHTML = "";
    const row = document.createElement("div");
    row.className = "guide-item selected";
    row.innerHTML = `<div class="g-title">Use this page directly</div><div class="g-meta">${escapeHtml(url)}</div>`;
    list.appendChild(row);
    state.selectedUrl = url;
  }
}

// ------------------------------------------------------------------ script

function beatTag(beat) {
  // Screenshot cards were dropped from the render (illegible at 9:16 phone
  // size) -- every beat now renders as a code card or a bold text callout,
  // regardless of whether the source step had an image.
  if (beat.is_code) return "💻 Code / command";
  return "📝 Text callout";
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
    const codeNote = b.is_code
      ? `<div class="hint" style="margin:4px 0 0;">On screen: <code>${escapeHtml((b.code_display || "").slice(0, 70))}${(b.code_display || "").length > 70 ? "…" : ""}</code></div>`
      : "";
    row.innerHTML = `<span class="beat-tag">${beatTag(b)}</span><textarea data-idx="${i}" rows="2">${escapeHtml(b.text)}</textarea>${codeNote}`;
    beatsList.appendChild(row);
  });
  $("#durationPill").textContent = `≈ ${Math.round(script.estimated_seconds || estimateSeconds(script))} sec`;
  $("#llmPill").style.display = script.used_llm ? "inline-block" : "none";
  $("#scriptEmpty").classList.add("hidden");
  $("#scriptEditor").classList.remove("hidden");
  $("#generateBtn").disabled = false;
}

function estimateSeconds(script) {
  const words = [script.hook, ...script.beats.map((b) => b.text), script.cta].join(" ").split(/\s+/).filter(Boolean).length;
  return words / 2.5;
}

// Generic on purpose -- mirrors app/scripting/writer.py's _CTA_POOL. The
// Topic Prompt / Guide / RSS sources all get theirs from the backend
// already; the Paste Script tab is built entirely client-side, so it needs
// its own pick. Seeded off the pasted text so the same paste always lands
// on the same line rather than reshuffling every time you re-draft it.
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
    if (state.sourceTab === "paste") {
      const raw = $("#pasteInput").value.trim();
      if (!raw) throw new Error("Paste some script text first.");
      let lines = raw.split(/\n+/).map((l) => l.trim()).filter(Boolean);
      if (lines.length < 2) {
        // No line breaks in what was pasted (a single paragraph of prose,
        // sentences separated by periods rather than actual newlines).
        // The old behaviour here used the one and only "line" as both the
        // hook AND the entire beat text -- the whole script ended up
        // spoken twice, once with no card (as the hook) and once inside
        // one giant card (as beat 1). Split on sentence boundaries instead,
        // same as the Topic Prompt tab does, so a pasted paragraph turns
        // into a real hook + separate beats like it should.
        lines = (raw.match(/[^.!?]+[.!?]+(?:\s+|$)/g) || [raw]).map((s) => s.trim()).filter(Boolean);
      }
      const script = {
        hook: lines[0] || raw.slice(0, 80),
        beats: lines.length > 1 ? lines.slice(1).map((t) => ({ text: t, image_url: null, is_code: false })) : [{ text: "Here's what you need to know.", image_url: null, is_code: false }],
        cta: pickCta(raw),
        source_title: lines[0] || "Pasted script",
        used_llm: false,
      };
      script.estimated_seconds = estimateSeconds(script);
      renderScriptEditor(script);
      return;
    }

    let body;
    if (state.sourceTab === "guide") {
      if (!state.selectedGuideId) throw new Error("Pick a guide from the list first.");
      body = { source_type: "guide", guide_id: state.selectedGuideId };
    } else if (state.sourceTab === "rss_url") {
      if (!state.selectedUrl) throw new Error("Fetch a feed/URL and pick an item first.");
      body = { source_type: "url", url: state.selectedUrl };
    } else if (state.sourceTab === "topic") {
      const topic = $("#topicInput").value.trim();
      if (!topic) throw new Error("Type a topic first.");
      body = { source_type: "topic", topic };
    }
    const script = await jsonFetch("/api/script/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
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
        '<div class="hint" style="margin-top:2px;">No clips yet — add one from the 🎬 Backgrounds page in the sidebar (open the folder or upload directly).</div>';
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
      grid.innerHTML = '<div class="hint">No clips yet — open the folder or upload one above.</div>';
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
    $("#aboutVersion").textContent = `Version ${data.version}`;
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
  $("#set_site_url").value = cfg.site_url || "";
  $("#set_brand_handle").value = cfg.brand_handle || "";
  $("#set_logo_letters").value = cfg.logo_letters || "";
  $("#set_edge_voice").value = cfg.edge_voice || "";
  $("#set_elevenlabs_voice_id").value = cfg.elevenlabs_voice_id || "";
  $("#set_llm_provider").value = cfg.llm_provider || "none";
  $("#set_brand_style_notes").value = cfg.brand_style_notes || "";
  $("#brandName").textContent = "Shorts Studio";
  $("#brandSub").textContent = cfg.brand_handle || "";
  $("#brandMark").textContent = cfg.logo_letters || "TGH";
  // Secret fields intentionally left blank -- see saveSettings().
}

async function saveSettings() {
  const patch = {
    site_url: $("#set_site_url").value.trim(),
    brand_handle: $("#set_brand_handle").value.trim(),
    logo_letters: $("#set_logo_letters").value.trim(),
    edge_voice: $("#set_edge_voice").value.trim(),
    elevenlabs_voice_id: $("#set_elevenlabs_voice_id").value.trim(),
    llm_provider: $("#set_llm_provider").value,
    brand_style_notes: $("#set_brand_style_notes").value,
  };
  const ev = $("#set_elevenlabs_api_key").value.trim();
  const lk = $("#set_llm_api_key").value.trim();
  if (ev) patch.elevenlabs_api_key = ev;
  if (lk) patch.llm_api_key = lk;

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

let guideSearchTimer = null;

function init() {
  initNav();
  initSourceTabs();
  initStylePickers();
  initClearButton();

  $("#guideSearch").addEventListener("input", (e) => {
    clearTimeout(guideSearchTimer);
    guideSearchTimer = setTimeout(() => loadGuides(e.target.value.trim()), 350);
  });
  $("#rssFetchBtn").addEventListener("click", fetchRss);
  $("#draftBtn").addEventListener("click", draftScript);
  $("#generateBtn").addEventListener("click", generateShort);
  $("#saveSettingsBtn").addEventListener("click", saveSettings);
  $("#openClipsFolderBtn").addEventListener("click", openClipsFolder);
  $("#clipUploadInput").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) uploadClip(file);
    e.target.value = "";
  });

  loadGuides();
  loadSettings();
  loadLibrary();
  loadCustomBackgrounds();
  pollQueue();
  setInterval(pollQueue, 2000);
}

document.addEventListener("DOMContentLoaded", init);
