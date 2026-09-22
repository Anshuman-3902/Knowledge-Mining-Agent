import os
import json
import re
import base64
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from dotenv import load_dotenv

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from openai import AzureOpenAI

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_credentials_file():
    local_file = BASE_DIR / "credentials.json"
    if local_file.exists():
        return local_file

    env_content = os.getenv("GMAIL_CREDENTIALS_JSON")
    if env_content:
        tmp_file = Path("/tmp") / "credentials.json"
        try:
            tmp_file.write_text(env_content, encoding="utf-8")
            return tmp_file
        except OSError:
            pass
    return local_file

def get_token_file():
    local_file = BASE_DIR / "token.json"
    if local_file.exists():
        return local_file

    env_content = os.getenv("GMAIL_TOKEN_JSON")
    if env_content:
        tmp_file = Path("/tmp") / "token.json"
        try:
            tmp_file.write_text(env_content, encoding="utf-8")
            return tmp_file
        except OSError:
            pass

    if os.getenv("VERCEL") or not os.access(BASE_DIR, os.W_OK):
        return Path("/tmp") / "token.json"

    return local_file

def save_token(creds):
    token_json = creds.to_json()
    token_file = get_token_file()
    try:
        token_file.write_text(token_json, encoding="utf-8")
    except OSError:
        fallback = Path("/tmp") / "token.json"
        try:
            fallback.write_text(token_json, encoding="utf-8")
        except OSError:
            pass

CREDENTIALS_FILE = get_credentials_file()
TOKEN_FILE = get_token_file()

FOUNDRY_PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
FOUNDRY_AGENT_NAME = os.getenv("FOUNDRY_AGENT_NAME", "student-ai-agent")

AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://avadhi3137beai24-0213-resource.openai.azure.com/")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATA_SOURCE_ID = os.getenv("NOTION_DATA_SOURCE_ID", "")
NOTION_VERSION = "2026-03-11"

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
CORS(app)


# -------------------------
# Gmail
# -------------------------

def gmail_service():
    creds = None
    token_file = get_token_file()

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), GMAIL_SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        save_token(creds)

    if not creds or not creds.valid:
        creds_file = get_credentials_file()
        if not creds_file.exists():
            raise FileNotFoundError(
                "credentials.json is missing from the project folder. "
                "Provide credentials.json or set GMAIL_CREDENTIALS_JSON in environment variables."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(creds_file), GMAIL_SCOPES
        )
        creds = flow.run_local_server(port=0)
        save_token(creds)

    return build("gmail", "v1", credentials=creds)


def get_header(headers, name):
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def decode_part(part):
    data = part.get("body", {}).get("data")
    if not data:
        return ""

    try:
        decoded = base64.urlsafe_b64decode(data + "===")
        return decoded.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def extract_body(payload):
    if not payload:
        return ""

    mime = payload.get("mimeType", "")

    if mime == "text/plain":
        return decode_part(payload)

    if mime == "text/html":
        return BeautifulSoup(
            decode_part(payload), "html.parser"
        ).get_text(" ", strip=True)

    for part in payload.get("parts", []):
        result = extract_body(part)
        if result:
            return result

    return ""


def get_gmail_emails(query="newer_than:7d", max_results=20):
    service = gmail_service()

    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )

    emails = []

    for message in result.get("messages", []):
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message["id"], format="full")
            .execute()
        )

        payload = msg.get("payload", {})
        headers = payload.get("headers", [])

        emails.append({
            "id": msg["id"],
            "thread_id": msg.get("threadId", ""),
            "subject": get_header(headers, "Subject"),
            "sender": get_header(headers, "From"),
            "date": get_header(headers, "Date"),
            "body": extract_body(payload),
        })

    return emails


def determine_gmail_query(question):
    q = question.lower()

    if "today" in q:
        return "newer_than:1d"
    if "yesterday" in q:
        return "newer_than:2d older_than:1d"
    if "this week" in q:
        return "newer_than:7d"
    if "this month" in q:
        return "newer_than:30d"
    if "recent" in q:
        return "newer_than:7d"
    if any(x in q for x in ["assignment", "homework", "submission"]):
        return "newer_than:30d"
    if "exam" in q:
        return "newer_than:60d"
    if "cho" in q:
        return "newer_than:60d CHO"
    if any(x in q for x in ["timetable", "schedule"]):
        return "newer_than:60d"
    if any(x in q for x in ["result", "re-evaluation"]):
        return "newer_than:60d"
    if any(x in q for x in ["lab", "laboratory"]):
        return "newer_than:30d"
    if "project" in q:
        return "newer_than:30d"
    if any(x in q for x in ["deadline", "due"]):
        return "newer_than:30d"

    return "newer_than:7d"


# -------------------------
# Foundry
# -------------------------

def foundry_client():
    if not FOUNDRY_PROJECT_ENDPOINT or not FOUNDRY_AGENT_NAME:
        raise RuntimeError(
            "Azure AI Foundry is not configured. Please set FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_AGENT_NAME in your .env file."
        )
    credential = DefaultAzureCredential()
    project = AIProjectClient(
        endpoint=FOUNDRY_PROJECT_ENDPOINT,
        credential=credential,
    )
    return project.get_openai_client(agent_name=FOUNDRY_AGENT_NAME)


def ask_foundry(prompt):
    # Option 1: Direct Azure OpenAI with API Key (Recommended for Vercel / Cloud)
    if AZURE_OPENAI_KEY and AZURE_OPENAI_ENDPOINT:
        client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_KEY,
            api_version="2024-08-01-preview",
        )
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    # Option 2: Azure AI Foundry Agent (DefaultAzureCredential fallback)
    client = foundry_client()
    conversation = client.conversations.create()

    response = client.responses.create(
        conversation=conversation.id,
        input=prompt,
    )

    output = getattr(response, "output_text", None)
    return output if output else str(response)


def email_context(emails):
    chunks = []

    for index, email in enumerate(emails, start=1):
        chunks.append(
            f"""
EMAIL {index}
Gmail ID: {email["id"]}
Subject: {email["subject"]}
From: {email["sender"]}
Date: {email["date"]}
Body:
{email["body"][:12000]}
"""
        )

    return "\n".join(chunks)


def parse_json_response(text):
    if not text:
        return None

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.I).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None

    return None


def format_structured_chat(data):
    """
    Safety net: if the Foundry agent still returns the old JSON format
    during chat, turn it into readable text before sending it to the UI.
    """
    if not isinstance(data, dict):
        return None

    items = data.get("items")
    if items is None:
        # Old single-item format.
        if "study_related" in data:
            items = [data]
        else:
            return None

    useful = []
    for item in items:
        if not item or item.get("study_related") is False:
            continue

        title = item.get("title") or item.get("category") or "Academic email"
        task = item.get("task") or item.get("important_information") or ""
        deadline = item.get("deadline") or item.get("exam_date") or ""
        priority = item.get("priority") or ""
        category = item.get("category") or ""

        parts = [f"**{title}**"]
        if category:
            parts.append(f"Category: {category}")
        if task:
            parts.append(f"What you need to do: {task}")
        if deadline:
            parts.append(f"Date/deadline: {deadline}")
        if priority:
            parts.append(f"Priority: {priority}")

        useful.append(" — ".join(parts))

    if not useful:
        return "I couldn't find any actionable academic information in the retrieved emails."

    return "Here are the relevant academic emails:\n\n" + "\n".join(
        f"{i}. {item}" for i, item in enumerate(useful, 1)
    )


def chat_with_foundry(question, emails):
    prompt = f"""
MODE: CONVERSATIONAL CHAT

You are a Student Academic Assistant.

Answer the student's question using ONLY the retrieved Gmail messages.

IMPORTANT:
- Return normal human-readable text.
- DO NOT return JSON.
- DO NOT wrap the answer in a code block.
- If there are multiple relevant emails, use a numbered list.
- Combine emails that clearly refer to the same assignment/task.
- Do not invent information.
- If a deadline is not stated, say "Deadline not stated."
- Ignore OTPs, passwords, security alerts, promotions, advertisements,
  newsletters, personal emails and unrelated messages.

For relevant academic emails, include:
- subject/title
- what it is about
- what the student needs to do
- date/deadline when available
- priority when it can be determined from the email

Student question:
{question}

Retrieved Gmail messages:
{email_context(emails)}
"""

    raw = ask_foundry(prompt)

    # The application remains robust even if an older Foundry instruction
    # causes JSON to be returned.
    structured = parse_json_response(raw)
    if structured:
        formatted = format_structured_chat(structured)
        if formatted:
            return formatted

    return raw


def analyze_emails_for_tasks(emails):
    prompt = f"""
MODE: STRUCTURED TASK EXTRACTION

You are a Student Academic Assistant.

Analyze the Gmail messages below and find ACTIONABLE academic work.

Create a task only when the student needs to do something.

Include:
- assignments
- CHOs
- project work
- lab work
- exam-related actions
- registration/submission deadlines
- important university actions

Do NOT create tasks for:
- OTPs
- passwords
- login/security alerts
- advertisements
- promotions
- newsletters
- personal email
- informational material that requires no action

If several emails clearly refer to the same assignment/task, GROUP THEM
into one item and put all relevant Gmail IDs in gmail_ids.

Never invent dates, deadlines, subjects, courses or instructions.

Return ONLY valid JSON:
{{
  "items": [
    {{
      "gmail_ids": [],
      "study_related": true,
      "create_task": true,
      "category": "",
      "course": "",
      "title": "",
      "task": "",
      "deadline": "",
      "exam_date": "",
      "exam_time": "",
      "location": "",
      "priority": "",
      "important_information": "",
      "attachment_information": ""
    }}
  ]
}}

Gmail messages:
{email_context(emails)}
"""

    raw = ask_foundry(prompt)
    parsed = parse_json_response(raw)

    if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
        return parsed

    # Support an accidental single-object response.
    if isinstance(parsed, dict) and "create_task" in parsed:
        return {"items": [parsed]}

    return {"items": []}


# -------------------------
# Notion
# -------------------------

def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def notion_configured():
    return bool(NOTION_TOKEN and NOTION_DATA_SOURCE_ID)


def rich_text_value(property_value):
    return "".join(
        item.get("plain_text", "")
        for item in property_value.get("rich_text", [])
    )


def title_value(property_value):
    return "".join(
        item.get("plain_text", "")
        for item in property_value.get("title", [])
    )


def property_value(properties, name, default=""):
    prop = properties.get(name, {})
    if prop.get("type") == "title":
        return title_value(prop)
    if prop.get("type") == "rich_text":
        return rich_text_value(prop)
    if prop.get("type") == "select":
        return (prop.get("select") or {}).get("name", default)
    if prop.get("type") == "status":
        return (prop.get("status") or {}).get("name", default)
    if prop.get("type") == "date":
        return (prop.get("date") or {}).get("start", default)
    return default


def get_notion_tasks():
    if not notion_configured():
        raise RuntimeError(
            "Notion is not configured. Check NOTION_TOKEN and NOTION_DATA_SOURCE_ID in .env."
        )

    url = f"https://api.notion.com/v1/data_sources/{NOTION_DATA_SOURCE_ID}/query"

    response = requests.post(
        url,
        headers=notion_headers(),
        json={"page_size": 100},
        timeout=20,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Notion task query failed ({response.status_code}): {response.text}"
        )

    tasks = []

    for page in response.json().get("results", []):
        props = page.get("properties", {})

        tasks.append({
            "id": page.get("id", ""),
            "url": page.get("url", ""),
            "title": property_value(props, "Task name", "Untitled task"),
            "course": property_value(props, "course", ""),
            "category": property_value(props, "category", ""),
            "priority": property_value(props, "priority", "Medium"),
            "status": property_value(props, "Status", "Not started"),
            "source_email": property_value(props, "Source Email", ""),
            "due_date": property_value(props, "Due date", ""),
        })

    tasks.sort(key=lambda task: (task["due_date"] or "9999-99-99", task["title"].lower()))
    return tasks


def notion_task_exists(email_id):
    if not notion_configured() or not email_id:
        return False

    url = f"https://api.notion.com/v1/data_sources/{NOTION_DATA_SOURCE_ID}/query"

    response = requests.post(
        url,
        headers=notion_headers(),
        json={
            "filter": {
                "property": "Source Email",
                "rich_text": {"equals": email_id},
            },
            "page_size": 1,
        },
        timeout=20,
    )

    if response.status_code != 200:
        # Fail safe: don't create a duplicate if Notion cannot be checked.
        return True

    return bool(response.json().get("results", []))


def create_notion_task(item, source_email_id):
    if not notion_configured():
        raise RuntimeError("Notion is not configured.")

    if notion_task_exists(source_email_id):
        return {"created": False, "skipped": True}

    priority = item.get("priority") or "Medium"
    if priority not in {"Low", "Medium", "High"}:
        priority = "Medium"

    properties = {
        "Task name": {
            "title": [{
                "text": {
                    "content": (item.get("title") or "Academic Task")[:200]
                }
            }]
        },
        "course": {
            "rich_text": [{
                "text": {"content": (item.get("course") or "Unknown")[:200]}
            }]
        },
        "category": {
            "rich_text": [{
                "text": {"content": (item.get("category") or "Other Academic")[:200]}
            }]
        },
        "priority": {"select": {"name": priority}},
        "Status": {"status": {"name": "Not started"}},
        "Source Email": {
            "rich_text": [{"text": {"content": source_email_id[:2000]}}]
        },
    }

    deadline = item.get("deadline") or ""
    date_match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", deadline)

    if date_match:
        year, month, day = date_match.groups()
        properties["Due date"] = {
            "date": {"start": f"{year}-{int(month):02d}-{int(day):02d}"}
        }

    body_parts = [
        item.get("task"),
        item.get("important_information"),
        item.get("location"),
        item.get("attachment_information"),
    ]
    body = "\n".join(part for part in body_parts if part)

    children = []
    if body:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": body[:1900]}
                }]
            },
        })

    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers=notion_headers(),
        json={
            "parent": {
                "type": "data_source_id",
                "data_source_id": NOTION_DATA_SOURCE_ID,
            },
            "properties": properties,
            "children": children,
        },
        timeout=20,
    )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Notion task creation failed ({response.status_code}): {response.text}"
        )

    return {"created": True, "skipped": False}


# -------------------------
# API routes
# -------------------------

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    ai_ready = bool(
        AZURE_OPENAI_KEY
        or (FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_AGENT_NAME)
    )
    return jsonify({
        "ok": True,
        "gmail": get_credentials_file().exists() or get_token_file().exists(),
        "notion": notion_configured(),
        "foundry": ai_ready,
    })


@app.post("/api/chat")
def api_chat():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()

    if not question:
        return jsonify({"ok": False, "error": "Question is required."}), 400

    try:
        query = determine_gmail_query(question)
        emails = get_gmail_emails(query, 20)
        answer = chat_with_foundry(question, emails)

        return jsonify({
            "ok": True,
            "answer": answer,
            "emails_found": len(emails),
            "query": query,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/api/emails")
def api_emails():
    try:
        emails = get_gmail_emails("newer_than:7d", 50)

        return jsonify({
            "ok": True,
            "emails": [
                {
                    "id": email["id"],
                    "subject": email["subject"],
                    "sender": email["sender"],
                    "date": email["date"],
                }
                for email in emails
            ],
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/api/tasks")
def api_tasks():
    try:
        tasks = get_notion_tasks()
        return jsonify({"ok": True, "tasks": tasks})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/api/stats")
def api_stats():
    try:
        emails = get_gmail_emails("newer_than:1d", 50)
        tasks = get_notion_tasks()

        return jsonify({
            "ok": True,
            "today_emails": len(emails),
            "important": sum(1 for task in tasks if task["priority"] == "High"),
            "assignments": sum(
                1 for task in tasks
                if "assignment" in (
                    f'{task["title"]} {task["category"]}'.lower()
                )
            ),
            "high_priority": sum(1 for task in tasks if task["priority"] == "High"),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/api/schedule")
def api_schedule():
    try:
        tasks = get_notion_tasks()

        events = [
            {
                "id": task["id"],
                "title": task["title"],
                "course": task["course"],
                "date": task["due_date"],
                "priority": task["priority"],
                "status": task["status"],
            }
            for task in tasks
            if task["due_date"]
        ]

        return jsonify({"ok": True, "events": events})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/scan")
def api_scan():
    try:
        scan_limit = 15 if os.getenv("VERCEL") else 50
        emails = get_gmail_emails("in:inbox newer_than:30d", scan_limit)
        analysis = analyze_emails_for_tasks(emails)

        created = 0
        skipped = 0
        failures = []

        for item in analysis.get("items", []):
            if not item.get("create_task"):
                continue

            gmail_ids = item.get("gmail_ids") or []
            if not gmail_ids:
                continue

            # Use the first Gmail message as the stable duplicate key.
            source_id = str(gmail_ids[0])

            try:
                result = create_notion_task(item, source_id)

                if result["skipped"]:
                    skipped += 1
                elif result["created"]:
                    created += 1
            except Exception as exc:
                failures.append(str(exc))

        return jsonify({
            "ok": True,
            "emails_scanned": len(emails),
            "tasks_created": created,
            "tasks_skipped": skipped,
            "failures": failures,
            "items": analysis.get("items", []),
        })

    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
