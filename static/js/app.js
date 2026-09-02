/* PDF Studio — Modern SPA with Icons & Glassmorphism */
"use strict";

const API = "";
let TOOLS = [];
let CATEGORIES = [];

// Tool icons by category
const CATEGORY_ICONS = {
  files: "📂", pages: "📄", edit: "✏️", convert: "🔄",
  scan: "📊", security: "🔒", misc: "🔧"
};

// Individual tool icons
const TOOL_ICONS = {
  merge: "🔗", alternate_mix: "🔀", organize: "📋", split_pages: "✂️",
  split_bookmarks: "📑", split_half: "↔️", split_size: "📦",
  split_text: "📝", extract_pages: "📤", delete_pages: "🗑️",
  rotate: "🔄", crop: "✂️", resize: "📐", flip: "🔃",
  nup: "🔲", grayscale: "⬛", remove_annotations: "🧹",
  editor: "🎨", create_forms: "📝",
  pdf_to_text: "📄", pdf_to_jpg: "🖼️", pdf_to_png: "🖼️",
  pdf_to_word: "📘", pdf_to_excel: "📊", pdf_to_ppt: "📽️",
  jpg_to_pdf: "📷", html_to_pdf: "🌐", word_to_pdf: "📄",
  extract_images: "🖼️",
  compress: "📦", deskew: "📐", ocr: "🔍",
  protect: "🔐", unlock: "🔓", watermark: "💧",
  flatten: "🧹", bates: "🔢", metadata: "📋",
  page_numbers: "#️⃣", header_footer: "📌", rename: "✏️",
  repair: "🔧", create_bookmarks: "🔖"
};

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function formatBytes(b) {
  if (!b) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return b.toFixed(b >= 100 ? 0 : 1) + " " + u[i];
}

function buildRanges(idxList) {
  const out = [];
  let start = idxList[0], prev = idxList[0];
  for (let i = 1; i <= idxList.length; i++) {
    const cur = idxList[i];
    if (i < idxList.length && cur === prev + 1) { prev = cur; continue; }
    out.push(start === prev ? String(start + 1) : `${start + 1}-${prev + 1}`);
    start = cur; prev = cur;
  }
  return out.join(",");
}

/* ==================== Router ==================== */
function route() {
  const h = location.hash || "#/";
  if (h === "#/" || h === "#") return renderHome();
  const m = h.match(/^#\/tool\/([\w]+)$/);
  if (m) {
    const t = TOOLS.find(x => x.id === m[1]);
    return t ? (t.editor ? renderEditor(t) : renderToolPage(t)) : renderHome();
  }
  renderHome();
}

/* ==================== Home ==================== */
function renderHome() {
  const app = $("#app");
  app.innerHTML = "";

  // Hero
  const hero = el("div", "hero");
  hero.innerHTML = `
    <h1>All the PDF tools. Offline. Free.</h1>
    <p>A simple, fast PDF toolkit — everything runs locally on your computer.</p>
    <span class="badge">🔒 100% local · no uploads · no account · unlimited</span>
  `;
  app.appendChild(hero);

  // Stats bar
  const statsBar = el("div", "stats-bar");
  const toolCount = TOOLS.length;
  const catCount = CATEGORIES.length;
  statsBar.innerHTML = `
    <div class="stat"><div class="stat-num">${toolCount}</div><div class="stat-label">Tools</div></div>
    <div class="stat"><div class="stat-num">${catCount}</div><div class="stat-label">Categories</div></div>
    <div class="stat"><div class="stat-num">0</div><div class="stat-label">Cloud APIs</div></div>
    <div class="stat"><div class="stat-num">100%</div><div class="stat-label">Offline</div></div>
  `;
  app.appendChild(statsBar);

  // Categories with tools
  for (const cat of CATEGORIES) {
    const tools = TOOLS.filter(t => t.category === cat.id);
    if (!tools.length) continue;
    const sec = el("div", "category");

    const header = el("div", "category-header");
    header.innerHTML = `
      <div class="category-icon">${CATEGORY_ICONS[cat.id] || "📁"}</div>
      <div>
        <h2>${cat.name}</h2>
        <div class="sub">${cat.desc}</div>
      </div>
    `;
    sec.appendChild(header);

    const grid = el("div", "grid");
    for (const t of tools) {
      const card = el("div", "card");
      const icon = TOOL_ICONS[t.id] || "🔧";
      const tagText = t.multi ? "Multi-file" : (t.editor ? "Canvas editor" : (t.params.length === 0 ? "No options" : `${t.params.length} options`));
      card.innerHTML = `
        <div class="card-header">
          <h3>${icon} ${t.name}</h3>
          <span class="arrow">→</span>
        </div>
        <p>${t.desc}</p>
        <span class="tag">${tagText}</span>
      `;
      card.addEventListener("click", () => (location.hash = `#/tool/${t.id}`));
      grid.appendChild(card);
    }
    sec.appendChild(grid);
    app.appendChild(sec);
  }
}

/* ==================== Tool Page ==================== */
let _files = [];
let _polling = false;
let _preview = null;

function renderToolPage(tool) {
  _files = [];
  const app = $("#app");
  app.innerHTML = "";
  app.className = "tool-page";

  const back = el("a", "back-link", "← All tools");
  back.href = "#/";
  app.appendChild(back);

  const icon = TOOL_ICONS[tool.id] || "🔧";
  const head = el("div", "tool-head");
  head.innerHTML = `<h1>${icon} ${tool.name}</h1><p>${tool.desc}</p>`;
  app.appendChild(head);

  // File upload panel
  const dropPanel = el("div", "panel");
  dropPanel.appendChild(el("h2", null, tool.multi ? "📁 Files (order matters)" : "📁 File"));
  const dz = el("div", "dropzone");
  dz.innerHTML = `<div class="icon">📤</div><b>Click to choose</b> or drag & drop ${tool.multi ? "files" : "a file"} here`;
  dropPanel.appendChild(dz);
  const fileList = el("div", "file-list");
  dropPanel.appendChild(fileList);
  app.appendChild(dropPanel);

  // Preview panel
  const previewWrap = el("div", "panel preview-panel");
  previewWrap.style.display = "none";
  app.appendChild(previewWrap);

  // Options panel
  const optPanel = el("div", "panel");
  optPanel.appendChild(el("h2", null, "⚙️ Options"));
  const params = el("div", "params");
  const state = {};
  let pagesInput = null;
  for (const p of tool.params) {
    state[p.name] = p.default;
    const wrap = el("div", "param");
    if (p.type === "checkbox") {
      wrap.classList.add("full");
      const label = el("label", "check-row");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!p.default;
      cb.addEventListener("change", () => (state[p.name] = cb.checked));
      label.appendChild(cb);
      label.appendChild(document.createTextNode(p.label));
      wrap.appendChild(label);
    } else if (p.type === "select") {
      wrap.appendChild(el("label", null, p.label));
      const s = document.createElement("select");
      for (const [val, lab] of p.options) {
        const o = document.createElement("option");
        o.value = val; o.textContent = lab;
        if (String(val) === String(p.default)) o.selected = true;
        s.appendChild(o);
      }
      s.addEventListener("change", () => (state[p.name] = s.value));
      wrap.appendChild(s);
    } else {
      wrap.appendChild(el("label", null, p.label));
      const inp = document.createElement("input");
      inp.type = p.type === "number" ? "number" : "text";
      inp.value = p.default;
      inp.placeholder = p.placeholder || "";
      if (p.type === "number") {
        inp.min = p.min; inp.max = p.max; inp.step = p.step;
      }
      inp.addEventListener("input", () => (state[p.name] = inp.value));
      if (p.name === "pages") pagesInput = inp;
      wrap.appendChild(inp);
      if (p.type === "text" && p.placeholder) wrap.classList.add("full");
    }
    params.appendChild(wrap);
  }
  optPanel.appendChild(params);

  // Actions
  const actions = el("div", "actions");
  const applyBtn = el("button", "btn", "⚡ Apply");
  applyBtn.disabled = true;
  actions.appendChild(applyBtn);
  const progress = el("div", "progress-wrap");
  const bar = el("div", "progress-bar");
  const fill = el("div", "fill");
  bar.appendChild(fill);
  const ptext = el("div", "progress-text", "Upload a file to start.");
  progress.appendChild(bar); progress.appendChild(ptext);
  actions.appendChild(progress);
  optPanel.appendChild(actions);
  const msg = el("div");
  optPanel.appendChild(msg);
  app.appendChild(optPanel);

  // File input setup
  const input = document.createElement("input");
  input.type = "file"; input.multiple = tool.multi;
  input.accept = acceptFor(tool.accept);
  input.addEventListener("change", () => addFiles(input.files, tool, fileList));
  dz.addEventListener("click", () => input.click());
  dz.addEventListener("dragover", e => { e.preventDefault(); dz.classList.add("dragover"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
  dz.addEventListener("drop", e => {
    e.preventDefault(); dz.classList.remove("dragover");
    addFiles(e.dataTransfer.files, tool, fileList);
  });

  function addFiles(list, tool, container) {
    for (const f of list) {
      const ext = f.name.split(".").pop().toLowerCase();
      if (!extOk(ext, tool.accept)) {
        showError(msg, `"${f.name}" has an unsupported type for this tool.`);
        continue;
      }
      _files.push(f);
    }
    renderFileList(container);
    applyBtn.disabled = !_files.length;
    ptext.textContent = _files.length ? `${_files.length} file(s) ready.` : "Upload a file to start.";
    maybeLoadPreview(tool, msg);
  }

  function renderFileList(container) {
    container.innerHTML = "";
    _files.forEach((f, i) => {
      const row = el("div", "file-row");
      row.innerHTML = `
        <span class="icon">📄</span>
        <span class="name">${esc(f.name)}</span>
        <span class="size">${formatBytes(f.size)}</span>
      `;
      if (tool.multi) {
        const up = el("button", "", "↑");
        up.title = "Move up";
        up.addEventListener("click", () => {
          if (i > 0) { [_files[i - 1], _files[i]] = [_files[i], _files[i - 1]]; renderFileList(container); }
        });
        const down = el("button", "", "↓");
        down.title = "Move down";
        down.addEventListener("click", () => {
          if (i < _files.length - 1) { [_files[i + 1], _files[i]] = [_files[i], _files[i + 1]]; renderFileList(container); }
        });
        row.appendChild(up); row.appendChild(down);
      }
      const del = el("button", "del", "✕");
      del.title = "Remove";
      del.addEventListener("click", () => { _files.splice(i, 1); renderFileList(container); applyBtn.disabled = !_files.length; maybeLoadPreview(tool, msg); });
      row.appendChild(del);
      container.appendChild(row);
    });
  }

  function maybeLoadPreview(tool, msg) {
    const pdf = _files.find(f => /\.pdf$/i.test(f.name));
    const wants = tool.accept.split(",").includes("pdf");
    previewWrap.innerHTML = "";
    if (!wants || !pdf) { previewWrap.style.display = "none"; _preview = null; return; }
    previewWrap.style.display = "";
    const head = el("div", "preview-head");
    head.appendChild(el("div", "preview-title", "📄 Pages — click to select"));
    head.appendChild(el("div", "preview-tools", ""));
    const hint = el("div", "preview-hint", "Rendering…");
    previewWrap.appendChild(head);
    previewWrap.appendChild(hint);
    loadPreview(pdf, msg);
  }

  async function loadPreview(file, msg) {
    try {
      const jobId = await renderPreview(file);
      let timedOut = true;
      for (let i = 0; i < 120; i++) {
        const res = await fetch(`${API}/api/preview/${jobId}`);
        if (res.status === 404) { await sleep(500); continue; }
        const data = await res.json();
        if (data.status === "done") {
          const pages = [];
          for (const r of data.results) {
            const m = r.name.match(/^preview_(\d+)_(\d+)x(\d+)\.png$/);
            if (m) pages.push({ index: +m[1], w: +m[2], h: +m[3], url: r.url });
          }
          pages.sort((a, b) => a.index - b.index);
          _preview = { pages, selected: new Set() };
          renderThumbs(pagesInput, state);
          timedOut = false;
          return;
        }
        if (data.status === "error") throw new Error(data.error || "Preview failed");
        await sleep(500);
      }
      if (timedOut) throw new Error("Preview timed out.");
    } catch (err) {
      const hint = previewWrap.querySelector(".preview-hint");
      if (hint) hint.textContent = "Preview unavailable: " + (err.message || String(err));
    }
  }

  function renderThumbs(pagesInput, state) {
    const head = previewWrap.querySelector(".preview-head .preview-tools");
    if (head) {
      const all = el("button", "btn ghost", "Select all");
      all.style.fontSize = "12px"; all.style.padding = "6px 12px";
      all.addEventListener("click", () => { _preview.selected = new Set(_preview.pages.map(p => p.index)); syncPages(pagesInput, state); });
      const none = el("button", "btn ghost", "Clear");
      none.style.fontSize = "12px"; none.style.padding = "6px 12px";
      none.addEventListener("click", () => { _preview.selected = new Set(); syncPages(pagesInput, state); });
      head.innerHTML = ""; head.appendChild(all); head.appendChild(none);
    }
    const grid = el("div", "preview-thumbs");
    const hint = previewWrap.querySelector(".preview-hint");
    for (const p of _preview.pages) {
      const t = el("div", "thumb");
      t.dataset.index = p.index;
      const img = document.createElement("img");
      img.src = p.url; img.loading = "lazy"; img.alt = `Page ${p.index + 1}`;
      t.appendChild(img);
      t.appendChild(el("span", "pnum", String(p.index + 1)));
      t.appendChild(el("span", "pcheck", "✓"));
      t.addEventListener("click", () => {
        if (_preview.selected.has(p.index)) _preview.selected.delete(p.index);
        else _preview.selected.add(p.index);
        grid.querySelectorAll(".thumb").forEach(th => th.classList.toggle("selected", _preview.selected.has(+th.dataset.index)));
        syncPages(pagesInput, state);
      });
      grid.appendChild(t);
    }
    if (hint) hint.textContent = `Click pages to select. Leave blank = all pages.`;
    previewWrap.appendChild(grid);
  }

  function syncPages(pagesInput, state) {
    const sorted = [..._preview.selected].sort((a, b) => a - b);
    const text = sorted.length ? buildRanges(sorted) : "";
    state.pages = text;
    if (pagesInput) pagesInput.value = text;
  }

  applyBtn.addEventListener("click", async () => {
    msg.innerHTML = ""; applyBtn.disabled = true; fill.style.width = "0%";
    ptext.textContent = "Uploading…";
    const options = {};
    for (const [k, v] of Object.entries(state)) options[k] = v;
    try {
      const jobId = await uploadTool(tool.id, _files, options);
      await pollJob(jobId, fill, ptext, msg, applyBtn);
    } catch (err) {
      showError(msg, err.message || String(err));
      applyBtn.disabled = false;
    }
  });
}

function extOk(ext, accept) {
  const map = {
    "pdf": ["pdf"], "image": ["jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff", "webp"],
    "html": ["html", "htm"],
    "office": ["docx", "doc", "xlsx", "xls", "pptx", "ppt", "odt", "ods", "odp"],
    "pdf,image": ["pdf", "jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff", "webp"],
  };
  return (map[accept] || ["pdf"]).includes(ext);
}
function acceptFor(accept) {
  const map = {
    "pdf": ".pdf", "image": ".jpg,.jpeg,.png,.gif,.bmp,.tif,.tiff,.webp",
    "html": ".html,.htm",
    "office": ".docx,.doc,.xlsx,.xls,.pptx,.ppt,.odt,.ods,.odp",
    "pdf,image": ".pdf,.jpg,.jpeg,.png,.gif,.bmp,.tif,.tiff,.webp",
  };
  return map[accept] || ".pdf";
}

function showError(msgBox, text) {
  msgBox.innerHTML = "";
  msgBox.appendChild(Object.assign(el("div", "error-box"), { textContent: text }));
}

async function uploadTool(id, files, options) {
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  fd.append("options", JSON.stringify(options || {}));
  const res = await fetch(`${API}/api/tools/${id}`, { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data.job_id;
}

async function pollJob(jobId, fill, ptext, msgBox, applyBtn) {
  if (_polling) return;
  _polling = true;
  try {
    while (true) {
      const res = await fetch(`${API}/api/jobs/${jobId}`);
      const data = await res.json();
      fill.style.width = (data.progress || 0) + "%";
      ptext.textContent = data.message || data.status;
      if (data.status === "done") { showSuccess(msgBox, data, ptext); return; }
      if (data.status === "error") {
        showError(msgBox, data.error || "Processing failed");
        if (applyBtn) applyBtn.disabled = false;
        return;
      }
      await sleep(700);
    }
  } finally { _polling = false; }
}

function showSuccess(msgBox, data, ptext) {
  msgBox.innerHTML = "";
  const box = el("div", "success-box");
  box.innerHTML = `<b>✅ Done!</b>`;
  for (const r of data.results) {
    const a = el("a", "btn green", "⬇ Download " + r.name);
    a.href = r.url;
    a.style.cssText = "display:inline-block;text-decoration:none;font-size:13px;padding:8px 16px;";
    box.appendChild(a);
  }
  msgBox.appendChild(box);
  if (ptext) ptext.textContent = "Finished.";
  const pdfResult = (data.results || []).find(r => /\.pdf$/i.test(r.name));
  if (pdfResult) loadOutputPreview(data.id, pdfResult, msgBox);
}

async function loadOutputPreview(jobId, result, msgBox) {
  try {
    const box = el("div", "preview-panel");
    const head = el("div", "preview-head");
    head.appendChild(el("div", "preview-title", `📄 Output preview — ${esc(result.name)}`));
    head.appendChild(el("div", "preview-tools", ""));
    const hint = el("div", "preview-hint", "Rendering output preview…");
    box.appendChild(head); box.appendChild(hint);
    msgBox.appendChild(box);
    const res = await fetch(`${API}/api/preview/result/${jobId}`, { method: "POST", headers: { "Accept": "application/json" } });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { hint.textContent = "Preview unavailable"; return; }
    let done = false;
    for (let i = 0; i < 120 && !done; i++) {
      const r = await fetch(`${API}/api/preview/${data.job_id}`);
      if (r.status === 404) { await sleep(600); continue; }
      const d = await r.json();
      if (d.status === "done") {
        const pages = [];
        for (const pr of d.results) {
          const m = pr.name.match(/^preview_(\d+)_(\d+)x(\d+)\.png$/);
          if (m) pages.push({ index: +m[1], w: +m[2], h: +m[3], url: pr.url });
        }
        pages.sort((a, b) => a.index - b.index);
        hint.remove();
        const grid = el("div", "preview-thumbs");
        for (const p of pages) {
          const t = el("div", "thumb");
          const img = document.createElement("img");
          img.src = p.url; img.loading = "lazy"; img.alt = `Page ${p.index + 1}`;
          t.appendChild(img);
          t.appendChild(el("span", "pnum", String(p.index + 1)));
          grid.appendChild(t);
        }
        box.appendChild(grid); done = true;
      } else if (d.status === "error") { hint.textContent = "Preview unavailable"; done = true; }
      else await sleep(600);
    }
  } catch (err) { /* silent */ }
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

/* ==================== Editor ==================== */
let ED = null;

function renderEditor(tool) {
  ED = { tool, pdfFile: null, pages: [], current: 0, items: {}, scale: 0, activeTool: "rect", color: "#6366f1", width: 3, drawing: null, img: null };
  const app = $("#app");
  app.innerHTML = ""; app.className = "tool-page";
  const back = el("a", "back-link", "← All tools"); back.href = "#/"; app.appendChild(back);
  const head = el("div", "tool-head");
  head.innerHTML = `<h1>🎨 ${tool.name}</h1><p>${tool.desc}</p>`;
  app.appendChild(head);
  const upPanel = el("div", "panel");
  const dz = el("div", "dropzone");
  dz.innerHTML = `<div class="icon">📤</div><b>Click to choose</b> or drag & drop a PDF to start editing`;
  upPanel.appendChild(dz); app.appendChild(upPanel);
  const input = document.createElement("input");
  input.type = "file"; input.accept = ".pdf";
  input.addEventListener("change", () => startEdit(input.files[0]));
  dz.addEventListener("click", () => input.click());
  dz.addEventListener("dragover", e => { e.preventDefault(); dz.classList.add("dragover"); });
  dz.addEventListener("drop", e => { e.preventDefault(); dz.classList.remove("dragover"); startEdit(e.dataTransfer.files[0]); });
  const msg = el("div"); app.appendChild(msg);
  async function startEdit(file) {
    if (!file) return;
    ED.pdfFile = file;
    dz.innerHTML = `<b>${esc(file.name)}</b> — rendering preview…`;
    try { const jobId = await renderPreview(file); await waitForPreview(jobId, msg); }
    catch (err) { showError(msg, err.message || String(err)); }
  }
}

async function renderPreview(file) {
  const fd = new FormData(); fd.append("file", file); fd.append("dpi", "100");
  const res = await fetch(`${API}/api/editor/render`, { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Render failed");
  return data.job_id;
}

async function waitForPreview(jobId, msg) {
  let data;
  while (true) {
    const res = await fetch(`${API}/api/preview/${jobId}`);
    data = await res.json();
    if (data.status === "done") break;
    if (data.status === "error") throw new Error(data.error || "Render failed");
    await sleep(700);
  }
  const pages = [];
  for (const r of data.results) {
    const m = r.name.match(/^preview_(\d+)_(\d+)x(\d+)\.png$/);
    const img = new Image(); img.src = r.url;
    await new Promise((res2, rej2) => { img.onload = res2; img.onerror = rej2; });
    pages.push({ index: m ? +m[1] : pages.length, w: m ? +m[2] : 1, h: m ? +m[3] : 1, img });
  }
  ED.pages = pages; ED.current = 0; ED.items = {};
  renderEditorCanvas(msg);
}

function renderEditorCanvas(msg) {
  const app = $("#app"); app.querySelector(".panel").remove();
  if (msg) msg.innerHTML = "";
  const panel = el("div", "panel");
  const toolbar = el("div", "editor-toolbar");
  const tools = [["select","Select"],["text","Text"],["rect","Rectangle"],["ellipse","Circle"],["line","Line"],["ink","Draw"],["highlight","Highlight"],["image","Image"]];
  for (const [id, label] of tools) {
    const b = el("button", "tool-btn", label); b.dataset.tool = id;
    if (id === ED.activeTool) b.classList.add("active");
    b.addEventListener("click", () => setTool(id, toolbar));
    toolbar.appendChild(b);
  }
  toolbar.appendChild(el("span", null, " 🎨 Color: "));
  const colorInput = document.createElement("input"); colorInput.type = "color"; colorInput.value = ED.color;
  colorInput.addEventListener("input", () => (ED.color = colorInput.value));
  toolbar.appendChild(colorInput);
  toolbar.appendChild(el("span", null, " 📏 Width: "));
  const widthInput = document.createElement("input"); widthInput.type = "number"; widthInput.min = "1"; widthInput.max = "30"; widthInput.value = ED.width;
  widthInput.addEventListener("change", () => (ED.width = +widthInput.value || 3));
  toolbar.appendChild(widthInput);
  const undoBtn = el("button", "tool-btn", "↩ Undo");
  undoBtn.addEventListener("click", () => { if (ED.items[ED.current]?.length) ED.items[ED.current].pop(); redraw(); });
  const clearBtn = el("button", "tool-btn", "🗑 Clear");
  clearBtn.addEventListener("click", () => { ED.items[ED.current] = []; redraw(); });
  const applyBtn = el("button", "btn", "⚡ Apply & Download");
  toolbar.appendChild(undoBtn); toolbar.appendChild(clearBtn); toolbar.appendChild(applyBtn);
  panel.appendChild(toolbar);

  const layout = el("div", "editor-layout");
  const pagesNav = el("div", "editor-pages");
  ED.pages.forEach((p, i) => {
    const img = p.img.cloneNode(); img.classList.toggle("active", i === ED.current);
    img.addEventListener("click", () => { ED.current = i; markActive(pagesNav, i); redraw(); });
    pagesNav.appendChild(img);
  });
  layout.appendChild(pagesNav);
  const canvasWrap = el("div", "editor-canvas-wrap");
  const canvas = document.createElement("canvas");
  const wrap = el("div", "hint", "🎯 Pick a tool and draw. Select to move, double-click to delete.");
  canvasWrap.appendChild(canvas); canvasWrap.appendChild(wrap);
  layout.appendChild(canvasWrap); panel.appendChild(layout);
  app.insertBefore(panel, app.querySelector(".error-box, .success-box"));

  const page = ED.pages[ED.current];
  ED.scale = page.img.naturalWidth / page.w;
  canvas.width = page.img.naturalWidth; canvas.height = page.img.naturalHeight;
  ED.canvas = canvas; ED.page = page;
  bindCanvas(canvas); redraw();

  applyBtn.addEventListener("click", async () => {
    applyBtn.disabled = true;
    try {
      const jobId = await submitEditor();
      const progressPanel = el("div", "panel");
      const bar = el("div", "progress-bar"); const fill = el("div", "fill"); bar.appendChild(fill);
      const ptext = el("div", "progress-text", "Applying…");
      progressPanel.appendChild(bar); progressPanel.appendChild(ptext);
      app.appendChild(progressPanel);
      await pollJob(jobId, fill, ptext, msg, applyBtn);
    } catch (err) { showError(msg, err.message || String(err)); applyBtn.disabled = false; }
  });
}

function setTool(id, toolbar) {
  ED.activeTool = id;
  toolbar.querySelectorAll(".tool-btn").forEach(b => b.classList.toggle("active", b.dataset.tool === id));
  if (id === "text") showTextPrompt();
}
function markActive(nav, idx) { nav.querySelectorAll("img").forEach((img, i) => img.classList.toggle("active", i === idx)); }
function bindCanvas(canvas) {
  canvas.addEventListener("mousedown", onDown); canvas.addEventListener("mousemove", onMove);
  canvas.addEventListener("mouseup", onUp); canvas.addEventListener("mouseleave", onUp);
  canvas.addEventListener("dblclick", onDblClick);
}
function canvasPos(e) {
  const rect = ED.canvas.getBoundingClientRect();
  return { x: (e.clientX - rect.left) * (ED.canvas.width / rect.width), y: (e.clientY - rect.top) * (ED.canvas.height / rect.height) };
}
function onDown(e) {
  const p = canvasPos(e); const t = ED.activeTool;
  if (t === "text") { showTextPromptAt(p); return; }
  if (t === "image") { pickImageAt(p); return; }
  if (t === "select") { const idx = hitTest(p); if (idx >= 0) { ED.dragging = { idx, start: p, orig: { ...ED.items[ED.current][idx] } }; ED.canvas.style.cursor = "move"; } return; }
  ED.drawing = { tool: t, start: p, current: p, points: [p] };
}
function onMove(e) {
  if (!ED.drawing) { if (ED.dragging) { const p = canvasPos(e); const it = ED.items[ED.current][ED.dragging.idx]; const dx = p.x - ED.dragging.start.x; const dy = p.y - ED.dragInfo.start.y; moveItem(it, ED.dragInfo.orig, dx, dy); redraw(); } return; }
  const p = canvasPos(e); ED.drawing.current = p; if (ED.drawing.tool === "ink") ED.drawing.points.push(p); redraw();
}
function onUp() {
  if (ED.drawing) {
    const d = ED.drawing;
    if (d.tool === "rect" || d.tool === "ellipse" || d.tool === "highlight") {
      const x = Math.min(d.start.x, d.current.x), y = Math.min(d.start.y, d.current.y);
      ED.items[ED.current].push({ type: d.tool, x, y, w: Math.abs(d.current.x - d.start.x), h: Math.abs(d.current.y - d.start.y), color: ED.color, width: ED.width });
    } else if (d.tool === "line") {
      ED.items[ED.current].push({ type: "line", x1: d.start.x, y1: d.start.y, x2: d.current.x, y2: d.current.y, color: ED.color, width: ED.width });
    } else if (d.tool === "ink") {
      if (d.points.length >= 2) ED.items[ED.current].push({ type: "ink", points: d.points.slice(), color: ED.color, width: ED.width });
    }
    ED.drawing = null; redraw();
  }
  if (ED.dragInfo) { ED.dragInfo = null; ED.canvas.style.cursor = ED.activeTool === "select" ? "default" : "crosshair"; }
}
function onDblClick(e) {
  if (ED.activeTool !== "select") return;
  const p = canvasPos(e); const idx = hitTest(p);
  if (idx >= 0) { ED.items[ED.current].splice(idx, 1); redraw(); }
}
function hitTest(p) {
  const items = ED.items[ED.current] || [];
  for (let i = items.length - 1; i >= 0; i--) { const it = items[i]; const b = itemBounds(it); if (p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h) return i; }
  return -1;
}
function itemBounds(it) {
  if (it.type === "line") { const x = Math.min(it.x1, it.x2), y = Math.min(it.y1, it.y2); return { x, y, w: Math.abs(it.x2 - it.x1), h: Math.abs(it.y2 - it.y1) }; }
  if (it.type === "ink") { const xs = it.points.map(p => p.x), ys = it.points.map(p => p.y); const x = Math.min(...xs), y = Math.min(...ys); return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y }; }
  if (it.type === "text") { return { x: it.x, y: it.y, w: (it.text?.length || 1) * it.size * ED.scale, h: it.size * ED.scale * 1.2 }; }
  return { x: it.x, y: it.y, w: it.w || 0, h: it.h || 0 };
}
function moveItem(it, orig, dx, dy) {
  if (it.type === "line") { it.x1 = orig.x1 + dx; it.y1 = orig.y1 + dy; it.x2 = orig.x2 + dx; it.y2 = orig.y2 + dy; }
  else if (it.type === "ink") { it.points = orig.points.map(([x, y]) => [x + dx, y + dy]); }
  else { it.x = orig.x + dx; it.y = orig.y + dy; }
}
function showTextPromptAt(p) {
  const x = p.x, y = p.y;
  const panel = ED.canvas.closest(".panel");
  const inp = document.createElement("input");
  inp.type = "text"; inp.placeholder = "Text… (Enter to add)";
  inp.style.cssText = `position:absolute;left:${ED.canvas.offsetLeft + x}px;top:${ED.canvas.offsetTop + y}px;z-index:30;padding:8px 12px;font-size:14px;border:1px solid var(--primary);border-radius:var(--radius-md);background:var(--bg-card);color:var(--text);`;
  panel.appendChild(inp); inp.focus();
  inp.addEventListener("keydown", ev => {
    if (ev.key === "Enter") { const text = inp.value.trim(); if (text) { ED.items[ED.current].push({ type: "text", x, y, size: 14, text, color: ED.color, font: "helv" }); redraw(); } inp.remove(); }
    else if (ev.key === "Escape") inp.remove();
  });
}
function pickImageAt(p) {
  const input = document.createElement("input"); input.type = "file"; input.accept = "image/*";
  input.addEventListener("change", () => {
    const f = input.files[0]; if (!f) return;
    const url = URL.createObjectURL(f); const img = new Image();
    img.onload = () => { const wPt = 100; const w = wPt * ED.scale; const h = (img.height / img.width) * w; ED.items[ED.current].push({ type: "image", x: p.x, y: p.y, w, h, src: url, img }); redraw(); };
    img.src = url;
  });
  input.click();
}
function showTextPrompt() {}
function redraw() {
  if (!ED.canvas) return;
  const ctx = ED.canvas.getContext("2d");
  ctx.clearRect(0, 0, ED.canvas.width, ED.canvas.height);
  const page = ED.page;
  const fit = Math.min(ED.canvas.width / page.img.naturalWidth, ED.canvas.height / page.img.naturalHeight);
  const dw = page.img.naturalWidth * fit, dh = page.img.naturalHeight * fit;
  ctx.drawImage(page.img, (ED.canvas.width - dw) / 2, (ED.canvas.height - dh) / 2, dw, dh);
  for (const it of ED.items[ED.current] || []) drawItem(ctx, it);
  if (ED.drawing) drawLive(ctx, ED.drawing);
}
function hexToRgba(hex, a) {
  const m = (hex || "#000000").replace("#", "");
  const r = parseInt(m.slice(0, 2) || "00", 16), g = parseInt(m.slice(2, 4) || "00", 16), b = parseInt(m.slice(4, 6) || "00", 16);
  return `rgba(${r},${g},${b},${a})`;
}
function drawItem(ctx, it) {
  ctx.save(); ctx.strokeStyle = hexToRgba(it.color, 1); ctx.fillStyle = hexToRgba(it.color, 1); ctx.lineWidth = it.width || 1;
  if (it.type === "rect") ctx.strokeRect(it.x, it.y, it.w, it.h);
  else if (it.type === "ellipse") { ctx.beginPath(); ctx.ellipse(it.x + it.w / 2, it.y + it.h / 2, it.w / 2, it.h / 2, 0, 0, Math.PI * 2); ctx.stroke(); }
  else if (it.type === "highlight") { ctx.fillStyle = "rgba(255,230,0,.45)"; ctx.fillRect(it.x, it.y, it.w, it.h); }
  else if (it.type === "line") { ctx.beginPath(); ctx.moveTo(it.x1, it.y1); ctx.lineTo(it.x2, it.y2); ctx.stroke(); }
  else if (it.type === "ink") { ctx.beginPath(); it.points.forEach((p, i) => i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)); ctx.stroke(); }
  else if (it.type === "text") { ctx.font = `${it.size * ED.scale}px sans-serif`; ctx.fillText(it.text || "", it.x, it.y + it.size * ED.scale); }
  else if (it.type === "image" && it.img) ctx.drawImage(it.img, it.x, it.y, it.w, it.h);
  ctx.restore();
}
function drawLive(ctx, d) {
  if (d.tool === "rect" || d.tool === "highlight") {
    ctx.save(); const x = Math.min(d.start.x, d.current.x), y = Math.min(d.start.y, d.current.y);
    if (d.tool === "highlight") { ctx.fillStyle = "rgba(255,230,0,.45)"; ctx.fillRect(x, y, Math.abs(d.current.x - d.start.x), Math.abs(d.current.y - d.start.y)); }
    else { ctx.strokeStyle = hexToRgba(ED.color, 1); ctx.strokeRect(x, y, Math.abs(d.current.x - d.start.x), Math.abs(d.current.y - d.start.y)); }
    ctx.restore();
  } else if (d.tool === "ellipse") { ctx.save(); ctx.strokeStyle = hexToRgba(ED.color, 1); ctx.beginPath(); ctx.ellipse((d.start.x + d.current.x) / 2, (d.start.y + d.current.y) / 2, Math.abs(d.current.x - d.start.x) / 2, Math.abs(d.current.y - d.start.y) / 2, 0, 0, Math.PI * 2); ctx.stroke(); ctx.restore(); }
  else if (d.tool === "line") { ctx.save(); ctx.strokeStyle = hexToRgba(ED.color, 1); ctx.beginPath(); ctx.moveTo(d.start.x, d.start.y); ctx.lineTo(d.current.x, d.current.y); ctx.stroke(); ctx.restore(); }
  else if (d.tool === "ink") { ctx.save(); ctx.strokeStyle = hexToRgba(ED.color, 1); ctx.beginPath(); d.points.forEach((p, i) => i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)); ctx.stroke(); ctx.restore(); }
}
function toPoints(item) {
  const s = ED.scale;
  const out = { ...item, x: item.x / s, y: item.y / s, w: item.w / s, h: item.h / s };
  if (item.type === "line") { out.x1 = item.x1 / s; out.y1 = item.y1 / s; out.x2 = item.x2 / s; out.y2 = item.y2 / s; }
  if (item.type === "ink") out.points = item.points.map(([x, y]) => [x / s, y / s]);
  if (item.type === "text") out.size = item.size;
  delete out.img; delete out.src; return out;
}
async function submitEditor() {
  const overlay = [];
  for (const p of ED.pages) { const items = (ED.items[p.index] || []).map(toPoints); if (items.length) overlay.push({ page: p.index, items }); }
  if (!overlay.length) throw new Error("Add some elements first (text, shapes, drawings…).");
  const fd = new FormData();
  fd.append("files", ED.pdfFile);
  fd.append("overlay", new File([JSON.stringify(overlay)], "overlay.json", { type: "application/json" }));
  fd.append("options", "{}");
  const res = await fetch(`${API}/api/tools/editor`, { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Apply failed");
  return data.job_id;
}

/* ==================== Init ==================== */
async function init() {
  try {
    const res = await fetch(`${API}/api/tools`);
    const data = await res.json();
    TOOLS = data.tools;
    CATEGORIES = data.categories;
  } catch (e) {
    $("#app").innerHTML = '<div class="error-box">⚠️ Could not reach the local server. Make sure Python + FastAPI is running.</div>';
    return;
  }
  window.addEventListener("hashchange", route);
  route();
}

init();
