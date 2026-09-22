// ==========================================================================
// Student AI · Knowledge Mining Studio Frontend Controller
// ==========================================================================

const navPills = document.querySelectorAll(".nav-pill");

const views = {
    chat: document.getElementById("chatView"),
    tasks: document.getElementById("tasksView"),
    schedule: document.getElementById("scheduleView"),
    emails: document.getElementById("emailsView")
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
// Initialize
// -------------------------

checkHealth();
loadStats();
