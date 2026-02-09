/**
 * patchAgent — WebSocket Chat Client
 *
 * Connects to /ws/chat, sends user messages, and renders streaming
 * agent responses (thinking, tool status, markdown text, figures).
 */

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const WS_PATH = "/ws/chat";

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------

const chatMessages  = document.getElementById("chatMessages");
const inputForm     = document.getElementById("inputForm");
const userInput     = document.getElementById("userInput");
const sendBtn       = document.getElementById("sendBtn");
const statusBar     = document.getElementById("statusBar");
const statusText    = document.getElementById("statusText");
const statusDot     = document.getElementById("statusDot");
const sampleList    = document.getElementById("sampleList");
const fileInput     = document.getElementById("fileInput");
const uploadArea    = document.getElementById("uploadArea");
const uploadStatus  = document.getElementById("uploadStatus");
const themeToggle   = document.getElementById("themeToggle");
const sidebarToggle = document.getElementById("sidebarToggle");
const sidebar       = document.getElementById("sidebar");

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let ws = null;
let sessionId = null;
let activeFileId = null;
let currentAssistantEl = null; // the <div.message-body> we're streaming into
let currentTextBuffer = "";
let thinkingEl = null;
let toolContainer = null;
let isConnected = false;

// ---------------------------------------------------------------------------
// Markdown setup
// ---------------------------------------------------------------------------

marked.setOptions({
    highlight: function (code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            return hljs.highlight(code, { language: lang }).value;
        }
        return hljs.highlightAuto(code).value;
    },
    breaks: true,
    gfm: true,
});

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------

function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}${WS_PATH}`;
    ws = new WebSocket(url);

    ws.onopen = () => {
        console.log("[ws] connected");
    };

    ws.onmessage = (evt) => {
        let msg;
        try { msg = JSON.parse(evt.data); } catch { return; }
        handleServerMessage(msg);
    };

    ws.onerror = (err) => {
        console.error("[ws] error", err);
        setStatus("error", "Connection error");
    };

    ws.onclose = () => {
        console.log("[ws] closed");
        isConnected = false;
        statusDot.className = "status-dot error";
        setStatus("show", "Disconnected — refresh to reconnect");
        sendBtn.disabled = true;
    };
}

function sendMessage(text) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const payload = { text };
    if (activeFileId) payload.file_id = activeFileId;
    ws.send(JSON.stringify(payload));
}

// ---------------------------------------------------------------------------
// Handle incoming messages
// ---------------------------------------------------------------------------

function handleServerMessage(msg) {
    switch (msg.type) {
        case "connected":
            sessionId = msg.session_id;
            isConnected = true;
            statusDot.className = "status-dot connected";
            statusDot.title = "Connected";
            sendBtn.disabled = false;
            setStatus("hide");
            break;

        case "status":
            setStatus("show", msg.text);
            break;

        case "thinking":
            ensureAssistantMessage();
            appendThinking(msg.text);
            break;

        case "tool_start":
            ensureAssistantMessage();
            addToolPill(msg.name, "running");
            setStatus("show", `Running ${msg.name}…`);
            break;

        case "tool_complete":
            updateToolPill(msg.name, "done");
            setStatus("hide");
            break;

        case "text_delta":
            ensureAssistantMessage();
            closeThinking();
            currentTextBuffer += msg.text;
            renderMarkdown();
            scrollToBottom();
            break;

        case "figure":
            ensureAssistantMessage();
            appendFigure(msg.data, msg.figure_number);
            scrollToBottom();
            break;

        case "error":
            ensureAssistantMessage();
            appendError(msg.text);
            finalizeAssistant();
            break;

        case "done":
            finalizeAssistant();
            break;
    }
}

// ---------------------------------------------------------------------------
// Message rendering
// ---------------------------------------------------------------------------

function addUserMessage(text) {
    const welcome = chatMessages.querySelector(".welcome-message");
    if (welcome) welcome.remove();

    const div = document.createElement("div");
    div.className = "message user";
    div.innerHTML = `
        <div class="message-avatar">🧑</div>
        <div class="message-body">${escapeHtml(text)}</div>
    `;
    chatMessages.appendChild(div);
    scrollToBottom();
}

function ensureAssistantMessage() {
    if (currentAssistantEl) return;

    const div = document.createElement("div");
    div.className = "message assistant";
    div.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-body"></div>
    `;
    chatMessages.appendChild(div);
    currentAssistantEl = div.querySelector(".message-body");
    currentTextBuffer = "";
    thinkingEl = null;
    toolContainer = null;
}

function appendThinking(text) {
    if (!thinkingEl) {
        const details = document.createElement("details");
        details.className = "thinking-block";
        details.innerHTML = `<summary>💭 Thinking…</summary><span class="thinking-text"></span>`;
        details.open = false;
        currentAssistantEl.appendChild(details);
        thinkingEl = details.querySelector(".thinking-text");
    }
    thinkingEl.textContent += text;
}

function closeThinking() {
    if (thinkingEl) {
        const details = thinkingEl.closest("details");
        if (details) details.open = false;
        thinkingEl = null;
    }
}

function addToolPill(name, state) {
    if (!toolContainer) {
        toolContainer = document.createElement("div");
        toolContainer.className = "tool-pills";
        currentAssistantEl.appendChild(toolContainer);
    }
    const pill = document.createElement("span");
    pill.className = `tool-pill ${state}`;
    pill.dataset.tool = name;
    pill.innerHTML = state === "running"
        ? `<span class="spinner"></span> ${name}`
        : `✓ ${name}`;
    toolContainer.appendChild(pill);
}

function updateToolPill(name, state) {
    if (!toolContainer) return;
    const pill = toolContainer.querySelector(`[data-tool="${name}"]`);
    if (pill) {
        pill.className = `tool-pill ${state}`;
        pill.innerHTML = `✓ ${name}`;
    }
}

function renderMarkdown() {
    if (!currentAssistantEl) return;
    // Preserve thinking blocks and tool pills that are already there
    let existingBlocks = "";
    const thinking = currentAssistantEl.querySelector(".thinking-block");
    const tools = currentAssistantEl.querySelector(".tool-pills");
    const figures = currentAssistantEl.querySelectorAll(".figure-container");

    // Build content div for markdown
    let mdDiv = currentAssistantEl.querySelector(".md-content");
    if (!mdDiv) {
        mdDiv = document.createElement("div");
        mdDiv.className = "md-content";
        currentAssistantEl.appendChild(mdDiv);
    }
    mdDiv.innerHTML = marked.parse(currentTextBuffer);

    // Highlight any code blocks
    mdDiv.querySelectorAll("pre code").forEach((block) => {
        hljs.highlightElement(block);
    });
}

function appendFigure(base64Data, figNum) {
    const container = document.createElement("div");
    container.className = "figure-container";
    const img = document.createElement("img");
    img.src = `data:image/png;base64,${base64Data}`;
    img.alt = `Figure ${figNum}`;
    img.title = `Figure ${figNum} — click to enlarge`;
    img.addEventListener("click", () => openLightbox(img.src));
    container.appendChild(img);
    currentAssistantEl.appendChild(container);
}

function appendError(text) {
    const errDiv = document.createElement("div");
    errDiv.className = "tool-pill";
    errDiv.style.borderColor = "var(--error)";
    errDiv.style.color = "var(--error)";
    errDiv.textContent = `⚠ ${text}`;
    if (currentAssistantEl) {
        currentAssistantEl.appendChild(errDiv);
    }
}

function finalizeAssistant() {
    currentAssistantEl = null;
    currentTextBuffer = "";
    thinkingEl = null;
    toolContainer = null;
    sendBtn.disabled = false;
    userInput.disabled = false;
    userInput.focus();
    setStatus("hide");
}

// ---------------------------------------------------------------------------
// Lightbox
// ---------------------------------------------------------------------------

function openLightbox(src) {
    const lb = document.createElement("div");
    lb.className = "lightbox";
    lb.innerHTML = `<img src="${src}" alt="Figure">`;
    lb.addEventListener("click", () => lb.remove());
    document.body.appendChild(lb);
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------

function setStatus(mode, text) {
    if (mode === "hide") {
        statusBar.hidden = true;
    } else {
        statusBar.hidden = false;
        statusText.textContent = text || "";
    }
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
}

// Auto-resize textarea
function autoResize() {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 150) + "px";
}

// ---------------------------------------------------------------------------
// Sample files
// ---------------------------------------------------------------------------

async function loadSamples() {
    try {
        const res = await fetch("/api/samples");
        const data = await res.json();
        if (!data.samples || data.samples.length === 0) {
            sampleList.innerHTML = `<p class="muted">No sample files found.<br>Upload your own!</p>`;
            return;
        }
        sampleList.innerHTML = "";
        for (const s of data.samples) {
            const item = document.createElement("div");
            item.className = "sample-item";
            item.innerHTML = `<span>📄 ${s.name}</span><span class="size">${s.size_kb} KB</span>`;
            item.addEventListener("click", () => selectSample(s.name, item));
            sampleList.appendChild(item);
        }
    } catch (err) {
        sampleList.innerHTML = `<p class="muted">Could not load samples.</p>`;
    }
}

async function selectSample(name, el) {
    // Deselect others
    document.querySelectorAll(".sample-item").forEach(i => i.classList.remove("active"));
    el.classList.add("active");

    try {
        const res = await fetch("/api/load-sample", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, session_id: sessionId }),
        });
        const data = await res.json();
        if (data.error) {
            uploadStatus.textContent = `Error: ${data.error}`;
            return;
        }
        activeFileId = data.file_id;
        uploadStatus.textContent = `Loaded ${name}`;
    } catch (err) {
        uploadStatus.textContent = "Failed to load sample";
    }
}

// ---------------------------------------------------------------------------
// File upload
// ---------------------------------------------------------------------------

fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    await uploadFile(file);
});

// Drag-and-drop
uploadArea.addEventListener("dragover", (e) => { e.preventDefault(); uploadArea.style.borderColor = "var(--accent)"; });
uploadArea.addEventListener("dragleave", () => { uploadArea.style.borderColor = ""; });
uploadArea.addEventListener("drop", async (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = "";
    const file = e.dataTransfer.files[0];
    if (file) await uploadFile(file);
});

async function uploadFile(file) {
    uploadStatus.textContent = `Uploading ${file.name}…`;
    const form = new FormData();
    form.append("file", file);
    if (sessionId) form.append("session_id", sessionId);

    try {
        const res = await fetch("/upload", { method: "POST", body: form });
        const data = await res.json();
        if (data.error) {
            uploadStatus.textContent = `Error: ${data.error}`;
            return;
        }
        activeFileId = data.file_id;
        if (data.session_id) sessionId = data.session_id;
        uploadStatus.textContent = `✓ ${file.name} ready`;
    } catch (err) {
        uploadStatus.textContent = "Upload failed";
    }
}

// ---------------------------------------------------------------------------
// Theme toggle
// ---------------------------------------------------------------------------

function initTheme() {
    const saved = localStorage.getItem("patchagent-theme");
    if (saved) {
        document.documentElement.dataset.theme = saved;
    }
    updateThemeIcon();
}

function toggleTheme() {
    const current = document.documentElement.dataset.theme;
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("patchagent-theme", next);
    updateThemeIcon();
}

function updateThemeIcon() {
    themeToggle.textContent = document.documentElement.dataset.theme === "dark" ? "🌙" : "☀️";
}

themeToggle.addEventListener("click", toggleTheme);

// ---------------------------------------------------------------------------
// Sidebar toggle (mobile)
// ---------------------------------------------------------------------------

sidebarToggle.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
});

// ---------------------------------------------------------------------------
// Suggestion chips
// ---------------------------------------------------------------------------

document.querySelectorAll(".suggestion-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
        const prompt = chip.dataset.prompt;
        userInput.value = prompt;
        autoResize();
        inputForm.dispatchEvent(new Event("submit"));
    });
});

// ---------------------------------------------------------------------------
// Form submission
// ---------------------------------------------------------------------------

inputForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = userInput.value.trim();
    if (!text || !isConnected) return;

    addUserMessage(text);
    sendMessage(text);
    userInput.value = "";
    autoResize();
    sendBtn.disabled = true;
    userInput.disabled = true;
    setStatus("show", "Agent is thinking…");
});

// Allow Shift+Enter for newlines, Enter to send
userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        inputForm.dispatchEvent(new Event("submit"));
    }
});

userInput.addEventListener("input", () => {
    autoResize();
    sendBtn.disabled = !userInput.value.trim() || !isConnected;
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

initTheme();
loadSamples();
connect();
