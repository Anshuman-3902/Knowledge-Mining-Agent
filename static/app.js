const navItems = document.querySelectorAll(".nav-item");

const views = {
    chat: document.getElementById("chatView"),
    tasks: document.getElementById("tasksView"),
    schedule: document.getElementById("scheduleView"),
    emails: document.getElementById("emailsView")
};

const titles = {
    chat: "Good evening 👋",
    tasks: "Your academic tasks",
    schedule: "Your academic schedule",
    emails: "Your recent emails"
};

function showView(name) {
    Object.entries(views).forEach(([key, element]) => {
        element.classList.toggle("active-view", key === name);
    });

    navItems.forEach(button => {
        button.classList.toggle("active", button.dataset.view === name);
    });

    document.getElementById("pageTitle").textContent = titles[name];

    if (name === "tasks") loadTasks();
    if (name === "schedule") loadSchedule();
    if (name === "emails") loadEmails();
}

navItems.forEach(button => {
    button.addEventListener("click", () => showView(button.dataset.view));
});


function addMessage(text, role = "assistant") {
    const container = document.getElementById("chatMessages");
    const item = document.createElement("div");
    item.className = `message ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "assistant" ? "✦" : "A";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;

    item.appendChild(avatar);
    item.appendChild(bubble);
    container.appendChild(item);
    container.scrollTop = container.scrollHeight;
}


async function askAI(question) {
    addMessage(question, "user");

    const status = document.getElementById("chatStatus");
    status.textContent = "Searching Gmail and asking Foundry AI...";

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({question})
        });

        const data = await response.json();

        if (!data.ok) throw new Error(data.error || "Request failed.");

        addMessage(data.answer, "assistant");
        status.textContent = `${data.emails_found} email(s) checked.`;
    } catch (error) {
        addMessage(`I couldn't complete that request: ${error.message}`, "assistant");
        status.textContent = "Request failed.";
    }
}


document.getElementById("chatForm").addEventListener("submit", async event => {
    event.preventDefault();

    const input = document.getElementById("questionInput");
    const question = input.value.trim();

    if (!question) return;

    input.value = "";
    await askAI(question);
});


document.querySelectorAll(".suggestions button").forEach(button => {
    button.addEventListener("click", () => askAI(button.dataset.question));
});


async function loadTasks() {
    const list = document.getElementById("taskList");
    list.innerHTML = '<div class="loading">Loading Notion tasks...</div>';

    try {
        const response = await fetch("/api/tasks");
        const data = await response.json();

        if (!data.ok) throw new Error(data.error);

        if (!data.tasks.length) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">✓</div>
                    <h3>No tasks found</h3>
                    <p>Click “Scan new emails” to find actionable academic work and add it to Notion.</p>
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
        list.innerHTML = `<div class="loading">Could not load Notion tasks: ${escapeHtml(error.message)}</div>`;
    }
}


async function loadSchedule() {
    const list = document.getElementById("scheduleList");
    list.innerHTML = '<div class="loading">Loading schedule...</div>';

    try {
        const response = await fetch("/api/schedule");
        const data = await response.json();

        if (!data.ok) throw new Error(data.error);

        if (!data.events.length) {
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
                <div>
                    <div class="task-title">${escapeHtml(event.title)}</div>
                    <div class="task-meta">${escapeHtml(event.course || "Academic")} · ${escapeHtml(event.priority)}</div>
                </div>
            </div>
        `).join("");
    } catch (error) {
        list.innerHTML = `<div class="loading">Could not load schedule: ${escapeHtml(error.message)}</div>`;
    }
}


async function loadEmails() {
    const list = document.getElementById("emailList");
    list.innerHTML = '<div class="loading">Loading recent emails...</div>';

    try {
        const response = await fetch("/api/emails");
        const data = await response.json();

        if (!data.ok) throw new Error(data.error);

        if (!data.emails.length) {
            list.innerHTML = '<div class="loading">No recent emails found.</div>';
            return;
        }

        list.innerHTML = data.emails.map(email => `
            <div class="email-row">
                <div class="email-subject">${escapeHtml(email.subject || "(No subject)")}</div>
                <div class="email-meta">${escapeHtml(email.sender || "")} · ${escapeHtml(email.date || "")}</div>
            </div>
        `).join("");
    } catch (error) {
        list.innerHTML = `<div class="loading">Could not load emails: ${escapeHtml(error.message)}</div>`;
    }
}

document.getElementById("refreshEmails").addEventListener("click", loadEmails);


async function loadStats() {
    try {
        const response = await fetch("/api/stats");
        const data = await response.json();

        if (!data.ok) throw new Error(data.error);

        document.getElementById("emailsCount").textContent = data.today_emails;
        document.getElementById("importantCount").textContent = data.important;
        document.getElementById("assignmentCount").textContent = data.assignments;
        document.getElementById("highCount").textContent = data.high_priority;
    } catch (error) {
        console.error(error);
        document.getElementById("emailsCount").textContent = "—";
        document.getElementById("importantCount").textContent = "—";
        document.getElementById("assignmentCount").textContent = "—";
        document.getElementById("highCount").textContent = "—";
    }
}


async function checkHealth() {
    try {
        const response = await fetch("/api/health");
        const data = await response.json();

        if (data.ok && data.gmail && data.notion && data.foundry) {
            document.getElementById("connectionText").textContent = "Gmail connected";
            document.getElementById("systemStatus").textContent = "All systems ready";
        } else {
            document.getElementById("connectionText").textContent = "Check configuration";
            document.getElementById("systemStatus").textContent = "Configuration needed";
        }
    } catch (_) {
        document.getElementById("connectionText").textContent = "Backend offline";
        document.getElementById("systemStatus").textContent = "Backend offline";
    }
}


async function scanGmail() {
    const buttons = [
        document.getElementById("scanBtn"),
        document.getElementById("scanBtn2")
    ];

    buttons.forEach(button => {
        button.disabled = true;
        button.textContent = "Scanning...";
    });

    showToast("Scanning Gmail and creating Notion tasks...");

    try {
        const response = await fetch("/api/scan", {method: "POST"});
        const data = await response.json();

        if (!data.ok) throw new Error(data.error);

        if (data.failures && data.failures.length) {
            showToast(`Scan completed with ${data.failures.length} issue(s).`);
            console.error(data.failures);
        } else {
            showToast(`${data.tasks_created} task(s) created · ${data.tasks_skipped} duplicate(s) skipped.`);
        }

        await Promise.all([loadTasks(), loadStats(), loadSchedule()]);
    } catch (error) {
        showToast(`Scan failed: ${error.message}`);
    } finally {
        buttons[0].disabled = false;
        buttons[0].textContent = "↻ Scan Gmail";
        buttons[1].disabled = false;
        buttons[1].textContent = "Scan new emails";
    }
}

document.getElementById("scanBtn").addEventListener("click", scanGmail);
document.getElementById("scanBtn2").addEventListener("click", scanGmail);


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
    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 4500);
}


checkHealth();
loadStats();
