// ==========================================================================
// Student AI · Knowledge Mining Studio Frontend Controller
// ==========================================================================

const navPills = document.querySelectorAll(".nav-pill");

const views = {
    chat: document.getElementById("chatView"),
    tasks: document.getElementById("tasksView"),
    schedule: document.getElementById("scheduleView"),
    emails: document.getElementById("emailsView"),
    documents: document.getElementById("documentsView")
};

function showView(name) {
    Object.entries(views).forEach(([key, element]) => {
        if (element) {
            element.classList.toggle("active-view", key === name);
        }
    });
    navPills.forEach(button => {
        button.classList.toggle("active", button.dataset.view === name);
    });

    if (name === "tasks") loadTasks();
    if (name === "schedule") loadSchedule();
    if (name === "emails") loadEmails();
    if (name === "documents") loadDocuments();
}

navPills.forEach(button => {
    button.addEventListener("click", () => showView(button.dataset.view));
});


// -------------------------
// Chat & Composer
// -------------------------

const questionInput = document.getElementById("questionInput");
const chatForm = document.getElementById("chatForm");
const chatMessages = document.getElementById("chatMessages");
const chatStatus = document.getElementById("chatStatus");

// Auto-adjust textarea height
if (questionInput) {
    questionInput.addEventListener("input", function() {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 180) + "px";
    });

    // Enter to submit, Shift+Enter for newline
    questionInput.addEventListener("keydown", function(e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event("submit", {cancelable: true}));
        }
    });
}

function addMessage(text, role = "assistant") {
    const item = document.createElement("div");
    item.className = `message ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = role === "assistant" ? "✦" : "You";

    const content = document.createElement("div");
    content.className = "message-content";

    const sender = document.createElement("div");
    sender.className = "message-sender";
    sender.textContent = role === "assistant" ? "Student AI Studio" : "You";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;

    content.appendChild(sender);
    content.appendChild(bubble);
    item.appendChild(avatar);
    item.appendChild(content);

    chatMessages.appendChild(item);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function askAI(question) {
    addMessage(question, "user");
    chatStatus.textContent = "Searching your college Gmail and consulting Foundry AI…";

    const askBtn = document.getElementById("askBtn");
    if (askBtn) askBtn.disabled = true;

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({question})
        });

        const data = await response.json();
        if (!data.ok) throw new Error(data.error || "Request failed.");

        addMessage(data.answer, "assistant");
        chatStatus.textContent = `✓ Checked ${data.emails_found} relevant emails · Foundry AI active`;
    } catch (error) {
        addMessage(`I couldn't complete that request: ${error.message}`, "assistant");
        chatStatus.textContent = "Request failed. Please try again.";
    } finally {
        if (askBtn) askBtn.disabled = false;
        if (questionInput) {
            questionInput.style.height = "auto";
        }
    }
}

if (chatForm) {
    chatForm.addEventListener("submit", async event => {
        event.preventDefault();
        const question = questionInput.value.trim();
        if (!question) return;
        questionInput.value = "";
        await askAI(question);
    });
}

// Suggestion Chips
document.querySelectorAll(".chip-btn").forEach(button => {
    button.addEventListener("click", () => {
        const q = button.dataset.question;
        if (q) askAI(q);
    });
});

// Clear Chat
const clearChatBtn = document.getElementById("clearChatBtn");
if (clearChatBtn) {
    clearChatBtn.addEventListener("click", () => {
        chatMessages.innerHTML = `
            <div class="message assistant">
                <div class="message-avatar">✦</div>
                <div class="message-content">
                    <div class="message-sender">Student AI Studio</div>
                    <div class="bubble">Chat cleared. Ask me anything about your college emails, assignments, or deadlines!</div>
                </div>
            </div>
        `;
        chatStatus.textContent = "";
    });
}


// -------------------------
// Notion Tasks
// -------------------------

async function loadTasks() {
    const list = document.getElementById("taskList");
    list.innerHTML = '<div class="panel-loading">Loading tasks from Notion...</div>';

    try {
        const response = await fetch("/api/tasks");
        const data = await response.json();
        if (!data.ok) throw new Error(data.error);

        if (!data.tasks || !data.tasks.length) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">✓</div>
                    <h3>No tasks found in Notion</h3>
                    <p>Click "Scan New Emails" above to mine your college inbox and extract tasks automatically.</p>
                </div>`;
            return;
        }

        list.innerHTML = data.tasks.map(task => `
            <div class="task-row">
                <div class="task-main">
                    <div class="task-title">${escapeHtml(task.title)}</div>
                    <div class="task-meta">
                        ${escapeHtml(task.course || task.category || "Academic")}
                        ${task.due_date ? ` · Due ${escapeHtml(formatDate(task.due_date))}` : ""}
                    </div>
                </div>
                <div class="task-right">
                    <span class="priority ${String(task.priority).toLowerCase()}">${escapeHtml(task.priority || "Medium")}</span>
                    <span class="task-status">${escapeHtml(task.status || "Not started")}</span>
                </div>
            </div>
        `).join("");
    } catch (error) {
        list.innerHTML = `<div class="panel-loading">Could not load Notion tasks: ${escapeHtml(error.message)}</div>`;
    }
}


// -------------------------
// Academic Schedule
// -------------------------

async function loadSchedule() {
    const list = document.getElementById("scheduleList");
    list.innerHTML = '<div class="panel-loading">Loading schedule...</div>';

    try {
        const response = await fetch("/api/schedule");
        const data = await response.json();
        if (!data.ok) throw new Error(data.error);

        if (!data.events || !data.events.length) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">▣</div>
                    <h3>No dated academic items yet</h3>
                    <p>Tasks with due dates will appear here automatically.</p>
                </div>`;
            return;
        }

        list.innerHTML = data.events.map(event => `
            <div class="schedule-row">
                <div class="date-box">${escapeHtml(formatDate(event.date))}</div>
                <div class="task-main">
                    <div class="task-title">${escapeHtml(event.title)}</div>
                    <div class="task-meta">${escapeHtml(event.course || "Academic")} · Priority: ${escapeHtml(event.priority)}</div>
                </div>
            </div>
        `).join("");
    } catch (error) {
        list.innerHTML = `<div class="panel-loading">Could not load schedule: ${escapeHtml(error.message)}</div>`;
    }
}


// -------------------------
// Gmail Emails
// -------------------------

async function loadEmails() {
    const list = document.getElementById("emailList");
    list.innerHTML = '<div class="panel-loading">Loading recent emails from Gmail...</div>';

    try {
        const response = await fetch("/api/emails");
        const data = await response.json();
        if (!data.ok) throw new Error(data.error);

        if (!data.emails || !data.emails.length) {
            list.innerHTML = '<div class="panel-loading">No recent emails found in inbox.</div>';
            return;
        }

        list.innerHTML = data.emails.map(email => `
            <div class="email-row">
                <div class="email-subject">${escapeHtml(email.subject || "(No subject)")}</div>
                <div class="email-meta">${escapeHtml(email.sender || "")} · ${escapeHtml(email.date || "")}</div>
            </div>
        `).join("");
    } catch (error) {
        list.innerHTML = `<div class="panel-loading">Could not load emails: ${escapeHtml(error.message)}</div>`;
    }
}

const refreshEmailsBtn = document.getElementById("refreshEmails");
if (refreshEmailsBtn) {
    refreshEmailsBtn.addEventListener("click", loadEmails);
}


// -------------------------
// Stats Metric Ribbon
// -------------------------

async function loadStats() {
    try {
        const response = await fetch("/api/stats");
        const data = await response.json();
        if (!data.ok) throw new Error(data.error);

        document.getElementById("emailsCount").textContent = data.today_emails ?? 0;
        document.getElementById("importantCount").textContent = data.important ?? 0;
        document.getElementById("assignmentCount").textContent = data.assignments ?? 0;
        document.getElementById("highCount").textContent = data.high_priority ?? 0;
    } catch (error) {
        console.error("Failed to load stats:", error);
        document.getElementById("emailsCount").textContent = "—";
        document.getElementById("importantCount").textContent = "—";
        document.getElementById("assignmentCount").textContent = "—";
        document.getElementById("highCount").textContent = "—";
    }
}


// -------------------------
// System Health Check
// -------------------------

async function checkHealth() {
    try {
        const response = await fetch("/api/health");
        const data = await response.json();

        if (data.ok && data.gmail && data.notion && data.foundry) {
            document.getElementById("systemStatus").textContent = "All systems ready";
        } else {
            document.getElementById("systemStatus").textContent = "Config needed";
        }
    } catch (_) {
        document.getElementById("systemStatus").textContent = "Backend offline";
    }
}


// -------------------------
// Gmail Scan & Sync
// -------------------------

async function scanGmail() {
    const scanButtons = [
        document.getElementById("scanBtn"),
        document.getElementById("scanBtn2"),
        document.getElementById("bannerScanBtn")
    ].filter(Boolean);

    scanButtons.forEach(btn => {
        btn.disabled = true;
        btn.dataset.originalText = btn.textContent;
        btn.textContent = "Scanning…";
    });

    showToast("Scanning Gmail with Foundry AI and updating Notion tasks…");

    try {
        const response = await fetch("/api/scan", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({})
        });

        const data = await response.json();
        if (!data.ok) throw new Error(data.error);

        if (data.failures && data.failures.length) {
            showToast(`Scan completed with ${data.failures.length} warning(s).`);
            console.warn(data.failures);
        } else {
            showToast(`✓ Scan complete: ${data.tasks_created} new task(s) created in Notion!`);
        }

        await Promise.all([loadTasks(), loadStats(), loadSchedule()]);
    } catch (error) {
        showToast(`Scan failed: ${error.message}`);
    } finally {
        scanButtons.forEach(btn => {
            btn.disabled = false;
            if (btn.dataset.originalText) {
                btn.textContent = btn.dataset.originalText;
            }
        });
    }
}

const scanBtn1 = document.getElementById("scanBtn");
const scanBtn2 = document.getElementById("scanBtn2");
const bannerScanBtn = document.getElementById("bannerScanBtn");

if (scanBtn1) scanBtn1.addEventListener("click", scanGmail);
if (scanBtn2) scanBtn2.addEventListener("click", scanGmail);
if (bannerScanBtn) bannerScanBtn.addEventListener("click", scanGmail);


// -------------------------
// Utilities
// -------------------------

function formatDate(value) {
    if (!value) return "";
    const date = new Date(value + (value.length === 10 ? "T00:00:00" : ""));
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString(undefined, {
        day: "2-digit",
        month: "short",
        year: "numeric"
    });
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function showToast(message) {
    const toast = document.getElementById("toast");
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 4200);
}


// -------------------------
// Document Intelligence Studio
// -------------------------

const dropZone = document.getElementById("dropZone");
const docFileInput = document.getElementById("docFileInput");
const uploadTriggerBtn = document.getElementById("uploadTriggerBtn");
const uploadStatus = document.getElementById("uploadStatus");

const documentList = document.getElementById("documentList");
const docCountBadge = document.getElementById("docCountBadge");

const docViewerEmpty = document.getElementById("docViewerEmpty");
const docViewerActive = document.getElementById("docViewerActive");

const activeDocTitle = document.getElementById("activeDocTitle");
const activeDocMeta = document.getElementById("activeDocMeta");
const activeDocOverview = document.getElementById("activeDocOverview");
const activeDocKeyPoints = document.getElementById("activeDocKeyPoints");
const activeDocDeadlines = document.getElementById("activeDocDeadlines");
const activeDocActionItems = document.getElementById("activeDocActionItems");
const activeDocActionsWrap = document.getElementById("activeDocActionsWrap");
const deleteActiveDocBtn = document.getElementById("deleteActiveDocBtn");

const docChatMessages = document.getElementById("docChatMessages");
const docChatForm = document.getElementById("docChatForm");
const docQuestionInput = document.getElementById("docQuestionInput");
const docAskBtn = document.getElementById("docAskBtn");
const docChatStatus = document.getElementById("docChatStatus");

let currentActiveDoc = null;
let documentsRegistry = [];

// Drag and drop setup
if (dropZone && docFileInput) {
    if (uploadTriggerBtn) {
        uploadTriggerBtn.addEventListener("click", () => docFileInput.click());
    }

    dropZone.addEventListener("click", () => docFileInput.click());

    ["dragenter", "dragover"].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add("dragover");
        });
    });

    ["dragleave", "drop"].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove("dragover");
        });
    });

    dropZone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
            handleDocumentUpload(files[0]);
        }
    });

    docFileInput.addEventListener("change", () => {
        if (docFileInput.files && docFileInput.files.length > 0) {
            handleDocumentUpload(docFileInput.files[0]);
            docFileInput.value = ""; // Reset
        }
    });
}

async function handleDocumentUpload(file) {
    const validExtensions = [".pdf", ".docx", ".doc", ".txt", ".md"];
    const ext = "." + file.name.split(".").pop().toLowerCase();

    if (!validExtensions.includes(ext)) {
        if (uploadStatus) {
            uploadStatus.className = "upload-status error";
            uploadStatus.textContent = `Unsupported file type: ${ext}. Please upload a PDF, Word, or Text document.`;
        }
        showToast("Unsupported file type");
        return;
    }

    if (uploadStatus) {
        uploadStatus.className = "upload-status loading";
        uploadStatus.innerHTML = `<span>⏳ Uploading <strong>${escapeHtml(file.name)}</strong> and generating AI executive summary...</span>`;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/api/documents/upload", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "Failed to upload and analyze document");
        }

        if (uploadStatus) {
            uploadStatus.className = "upload-status success";
            uploadStatus.textContent = `✓ Document successfully analyzed!`;
            setTimeout(() => { uploadStatus.textContent = ""; }, 5000);
        }

        showToast(`Document "${file.name}" scanned and summarized!`);
        await loadDocuments(data.document ? data.document.id : null);
    } catch (err) {
        console.error("Upload error:", err);
        if (uploadStatus) {
            uploadStatus.className = "upload-status error";
            uploadStatus.textContent = `Upload failed: ${err.message}`;
        }
        showToast(`Upload failed: ${err.message}`);
    }
}

async function loadDocuments(selectDocId = null) {
    if (!documentList) return;

    try {
        const response = await fetch("/api/documents");
        const data = await response.json();

        if (!response.ok || !data.success) {
            documentList.innerHTML = `<div class="empty-state"><p>Could not load documents: ${data.error || "Unknown error"}</p></div>`;
            return;
        }

        documentsRegistry = data.documents || [];

        if (docCountBadge) {
            docCountBadge.textContent = `${documentsRegistry.length} file${documentsRegistry.length === 1 ? "" : "s"}`;
        }

        if (documentsRegistry.length === 0) {
            documentList.innerHTML = `<div class="panel-loading" style="padding:32px 10px;text-align:center">No documents uploaded yet. Drop a PDF or Word doc above!</div>`;
            currentActiveDoc = null;
            if (docViewerActive) docViewerActive.style.display = "none";
            if (docViewerEmpty) docViewerEmpty.style.display = "block";
            return;
        }

        // Render library list
        documentList.innerHTML = documentsRegistry.map(doc => {
            const extIcon = doc.file_type === "pdf" ? "📕" : doc.file_type === "docx" ? "📘" : "📄";
            const isActive = currentActiveDoc && currentActiveDoc.id === doc.id;
            return `
                <div class="doc-item ${isActive ? "active" : ""}" data-doc-id="${escapeHtml(doc.id)}">
                    <div class="doc-item-icon">${extIcon}</div>
                    <div class="doc-item-body">
                        <div class="doc-item-title" title="${escapeHtml(doc.filename)}">${escapeHtml(doc.filename)}</div>
                        <div class="doc-item-meta">
                            <span>${escapeHtml(doc.file_type.toUpperCase())}</span>
                            <span>•</span>
                            <span>${escapeHtml(doc.file_size)}</span>
                        </div>
                    </div>
                </div>
            `;
        }).join("");

        // Attach item click handlers
        documentList.querySelectorAll(".doc-item").forEach(item => {
            item.addEventListener("click", () => {
                selectDocument(item.dataset.docId);
            });
        });

        // Determine which document to select
        let targetId = selectDocId;
        if (!targetId && currentActiveDoc) {
            const exists = documentsRegistry.some(d => d.id === currentActiveDoc.id);
            if (exists) targetId = currentActiveDoc.id;
        }
        if (!targetId && documentsRegistry.length > 0) {
            targetId = documentsRegistry[0].id;
        }

        if (targetId) {
            await selectDocument(targetId);
        }
    } catch (err) {
        console.error("Load documents error:", err);
        documentList.innerHTML = `<div class="empty-state"><p>Error fetching documents.</p></div>`;
    }
}

async function selectDocument(docId) {
    try {
        const response = await fetch(`/api/documents/${docId}`);
        const data = await response.json();

        if (!response.ok || !data.success || !data.document) {
            showToast("Failed to load document details");
            return;
        }

        currentActiveDoc = data.document;

        // Highlight in list
        if (documentList) {
            documentList.querySelectorAll(".doc-item").forEach(el => {
                el.classList.toggle("active", el.dataset.docId === docId);
            });
        }

        // Show viewer content
        if (docViewerEmpty) docViewerEmpty.style.display = "none";
        if (docViewerActive) docViewerActive.style.display = "block";

        // Fill meta bar
        if (activeDocTitle) activeDocTitle.textContent = currentActiveDoc.filename;
        if (activeDocMeta) {
            const dateStr = formatDate(currentActiveDoc.uploaded_at);
            activeDocMeta.textContent = `${currentActiveDoc.file_type.toUpperCase()} · ${currentActiveDoc.file_size} · Uploaded ${dateStr}`;
        }

        // Fill summary
        const summary = currentActiveDoc.summary || {};
        if (activeDocOverview) {
            activeDocOverview.textContent = summary.overview || "No executive summary available for this document.";
        }

        // Key Points
        if (activeDocKeyPoints) {
            const points = Array.isArray(summary.key_points) ? summary.key_points : [];
            activeDocKeyPoints.innerHTML = points.length > 0
                ? points.map(pt => `<li>${escapeHtml(pt)}</li>`).join("")
                : `<li>No key points identified.</li>`;
        }

        // Deadlines & Dates
        if (activeDocDeadlines) {
            const deadlines = Array.isArray(summary.deadlines) ? summary.deadlines : [];
            activeDocDeadlines.innerHTML = deadlines.length > 0
                ? deadlines.map(dl => `<li>${escapeHtml(dl)}</li>`).join("")
                : `<li>No specific dates or deadlines found.</li>`;
        }

        // Action Items
        if (activeDocActionItems && activeDocActionsWrap) {
            const actions = Array.isArray(summary.action_items) ? summary.action_items : [];
            if (actions.length > 0) {
                activeDocActionsWrap.style.display = "block";
                activeDocActionItems.innerHTML = actions.map(act => `<li>${escapeHtml(act)}</li>`).join("");
            } else {
                activeDocActionsWrap.style.display = "none";
            }
        }

        // Reset document chat thread
        if (docChatMessages) {
            docChatMessages.innerHTML = `
                <div class="message assistant">
                    <div class="message-avatar">✦</div>
                    <div class="message-content">
                        <div class="message-sender">Document Assistant</div>
                        <div class="bubble">I've thoroughly analyzed <strong>${escapeHtml(currentActiveDoc.filename)}</strong>. Ask me any question about its contents, rules, grading, or deadlines!</div>
                    </div>
                </div>
            `;
        }
    } catch (err) {
        console.error("Select document error:", err);
        showToast("Error loading document");
    }
}

// Grounded Document Chat
if (docChatForm) {
    docChatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!currentActiveDoc) {
            showToast("Please select or upload a document first.");
            return;
        }

        const question = docQuestionInput ? docQuestionInput.value.trim() : "";
        if (!question) return;

        // Append user message
        const userMsg = document.createElement("div");
        userMsg.className = "message user";
        userMsg.innerHTML = `
            <div class="message-avatar">You</div>
            <div class="message-content">
                <div class="message-sender">You</div>
                <div class="bubble">${escapeHtml(question)}</div>
            </div>
        `;
        docChatMessages.appendChild(userMsg);
        docChatMessages.scrollTop = docChatMessages.scrollHeight;

        if (docQuestionInput) docQuestionInput.value = "";
        if (docChatStatus) docChatStatus.textContent = "Grounding answer in document text with Foundry AI…";
        if (docAskBtn) docAskBtn.disabled = true;

        try {
            const response = await fetch(`/api/documents/${currentActiveDoc.id}/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || "Failed to get answer");
            }

            const botMsg = document.createElement("div");
            botMsg.className = "message assistant";
            botMsg.innerHTML = `
                <div class="message-avatar">✦</div>
                <div class="message-content">
                    <div class="message-sender">Document Assistant</div>
                    <div class="bubble">${escapeHtml(data.answer)}</div>
                </div>
            `;
            docChatMessages.appendChild(botMsg);
            docChatMessages.scrollTop = docChatMessages.scrollHeight;
        } catch (err) {
            console.error("Doc chat error:", err);
            const errDiv = document.createElement("div");
            errDiv.className = "message assistant";
            errDiv.innerHTML = `
                <div class="message-avatar">!</div>
                <div class="message-content">
                    <div class="message-sender">Document Assistant</div>
                    <div class="bubble" style="color:#ef4444">Error: ${escapeHtml(err.message)}</div>
                </div>
            `;
            docChatMessages.appendChild(errDiv);
        } finally {
            if (docChatStatus) docChatStatus.textContent = "";
            if (docAskBtn) docAskBtn.disabled = false;
        }
    });
}

// Delete Active Document
if (deleteActiveDocBtn) {
    deleteActiveDocBtn.addEventListener("click", async () => {
        if (!currentActiveDoc) return;

        const ok = confirm(`Are you sure you want to delete "${currentActiveDoc.filename}" from your Document Studio?`);
        if (!ok) return;

        try {
            const response = await fetch(`/api/documents/${currentActiveDoc.id}`, {
                method: "DELETE"
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || "Failed to delete document");
            }

            showToast(`Document "${currentActiveDoc.filename}" deleted.`);
            currentActiveDoc = null;
            await loadDocuments();
        } catch (err) {
            console.error("Delete document error:", err);
            showToast(`Could not delete document: ${err.message}`);
        }
    });
}


// -------------------------
// Theme (Light / Dark Mode)
// -------------------------

const themeToggleBtn = document.getElementById("themeToggleBtn");

function getStoredTheme() {
    return localStorage.getItem("student_ai_theme") || "light";
}

function applyTheme(theme) {
    if (theme === "dark") {
        document.documentElement.setAttribute("data-theme", "dark");
    } else {
        document.documentElement.removeAttribute("data-theme");
    }
    localStorage.setItem("student_ai_theme", theme);
}

// Initial theme apply
applyTheme(getStoredTheme());

if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
        const next = current === "dark" ? "light" : "dark";
        applyTheme(next);
        showToast(next === "dark" ? "🌙 Dark mode enabled" : "☀️ Light mode enabled");
    });
}


// -------------------------
// Initialize
// -------------------------

checkHealth();
loadStats();
loadDocuments();
