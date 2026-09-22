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

# Allow HTTP for local OAuth callback
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

BASE_DIR = Path(__file__).resolve().parent
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
GMAIL_SCOPES_ADD = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]

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

def get_tokens_dir():
    if os.getenv("VERCEL") or not os.access(BASE_DIR, os.W_OK):
        tokens_dir = Path("/tmp") / "tokens"
    else:
        tokens_dir = BASE_DIR / "tokens"
    tokens_dir.mkdir(parents=True, exist_ok=True)
    return tokens_dir

def get_accounts_file():
    if os.getenv("VERCEL") or not os.access(BASE_DIR, os.W_OK):
        return Path("/tmp") / "accounts.json"
    return BASE_DIR / "accounts.json"

def resolve_token_path(token_str):
    if not token_str:
        return None
    p = Path(token_str)
    if p.is_absolute() and p.exists():
        return p
    local_p = BASE_DIR / token_str
    if local_p.exists():
        return local_p
    tmp_p = Path("/tmp") / token_str
    if tmp_p.exists():
        return tmp_p
    return local_p

def save_accounts(data):
    accounts_file = get_accounts_file()
    try:
        accounts_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"Error saving accounts: {e}")

def load_accounts():
    accounts_file = get_accounts_file()
    if accounts_file.exists():
        try:
            data = json.loads(accounts_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "accounts" in data:
                return data
        except Exception as e:
            print(f"Error reading accounts.json: {e}")

    # Seamless migration: if token.json exists, migrate it to tokens/account_1.json
    legacy_token = BASE_DIR / "token.json"
    if not legacy_token.exists() and os.getenv("GMAIL_TOKEN_JSON"):
        tmp_token = Path("/tmp") / "token.json"
        try:
            tmp_token.write_text(os.getenv("GMAIL_TOKEN_JSON"), encoding="utf-8")
            legacy_token = tmp_token
        except OSError:
            pass

    if legacy_token.exists():
        try:
            # Read email directly from token JSON if available (avoids scope issues)
            token_data = json.loads(legacy_token.read_text(encoding="utf-8"))
            # Gmail token JSON from google-auth includes no email directly,
            # but we can try getProfile with only gmail.readonly scope (no refresh needed if valid)
            email = token_data.get("email", "")
            if not email:
                try:
                    creds_tmp = Credentials.from_authorized_user_file(str(legacy_token), ["https://www.googleapis.com/auth/gmail.readonly"])
                    srv = build("gmail", "v1", credentials=creds_tmp)
                    profile = srv.users().getProfile(userId="me").execute()
                    email = profile.get("emailAddress") or ""
                except Exception:
                    pass
            if not email:
                email = "Primary Account"

            creds = Credentials.from_authorized_user_file(str(legacy_token), GMAIL_SCOPES)
            tokens_dir = get_tokens_dir()
            migrated_file = tokens_dir / "account_1.json"
            migrated_file.write_text(creds.to_json(), encoding="utf-8")

            rel_token = str(migrated_file.relative_to(BASE_DIR)).replace("\\", "/") if BASE_DIR in migrated_file.parents else str(migrated_file)
            data = {
                "active_account": email,
                "accounts": [
                    {
                        "email": email,
                        "token": rel_token,
                        "active": True
                    }
                ]
            }
            save_accounts(data)
            return data
        except Exception as exc:
            print(f"Migration error for legacy token: {exc}")

    return {"active_account": "", "accounts": []}

def get_active_account():
    data = load_accounts()
    active = data.get("active_account", "")
    if active == "all":
        return "all"
    for acc in data.get("accounts", []):
        if acc.get("active"):
            return acc.get("email")
    if data.get("accounts"):
        return data["accounts"][0].get("email")
    return ""

def set_active_account(email):
    data = load_accounts()
    data["active_account"] = email
    for acc in data.get("accounts", []):
        acc["active"] = (acc.get("email") == email) or (email == "all")
    save_accounts(data)
    return data

def get_creds_for_account(email=None):
    data = load_accounts()
    accounts = data.get("accounts", [])
    if not accounts:
        # Fallback to single token.json if present
        legacy = BASE_DIR / "token.json"
        if legacy.exists():
            return Credentials.from_authorized_user_file(str(legacy), GMAIL_SCOPES), legacy
        return None, None

    target = None
    if email and email != "all":
        for a in accounts:
            if a.get("email", "").lower() == email.lower():
                target = a
                break

    if not target:
        active_email = data.get("active_account")
        for a in accounts:
            if a.get("email") == active_email:
                target = a
                break
        if not target and accounts:
            target = accounts[0]

    if not target:
        return None, None

    token_file = resolve_token_path(target.get("token"))
    if not token_file or not token_file.exists():
        return None, None

    creds = Credentials.from_authorized_user_file(str(token_file), GMAIL_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return creds, token_file

def gmail_service_for_account(email=None):
    creds, _ = get_creds_for_account(email)
    if not creds or not creds.valid:
        raise RuntimeError(f"Valid Gmail credentials not found for account '{email or 'active'}'. Please authenticate via '+ Add another email'.")
    return build("gmail", "v1", credentials=creds)

def gmail_service():
    return gmail_service_for_account()

_pending_flow = {}   # stores in-progress OAuth flow

OAUTH_REDIRECT_URI = "http://localhost:5000/api/accounts/callback"

def generate_auth_url():
    """Step 1: Create flow, return the Google OAuth URL for the user to visit."""
    creds_file = get_credentials_file()
    if not creds_file.exists():
        raise FileNotFoundError(
            "credentials.json is missing from the project folder. "
            "Provide credentials.json or set GMAIL_CREDENTIALS_JSON in environment variables."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(creds_file), GMAIL_SCOPES_ADD,
        redirect_uri=OAUTH_REDIRECT_URI,
    )
    auth_url, state = flow.authorization_url(
        prompt="select_account",
        access_type="offline",
        include_granted_scopes="true",
    )
    _pending_flow["flow"] = flow
    _pending_flow["state"] = state
    return auth_url

def save_account_from_code(code, state=None):
    """Step 2: Exchange the auth code for credentials and save the account."""
    flow = _pending_flow.get("flow")
    if not flow:
        creds_file = get_credentials_file()
        flow = InstalledAppFlow.from_client_secrets_file(
            str(creds_file), GMAIL_SCOPES_ADD,
            redirect_uri=OAUTH_REDIRECT_URI,
            state=state
        )

    flow.fetch_token(code=code)
    creds = flow.credentials
    _pending_flow.clear()

    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    email = (profile.get("emailAddress") or "").strip()
    if not email:
        raise ValueError("Could not retrieve email address from the authenticated Google account.")

    tokens_dir = get_tokens_dir()
    data = load_accounts()
    accounts = data.get("accounts", [])

    existing = next((a for a in accounts if a.get("email", "").lower() == email.lower()), None)
    if existing:
        token_path = resolve_token_path(existing.get("token"))
        if token_path:
            token_path.write_text(creds.to_json(), encoding="utf-8")
    else:
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", email.lower())
        token_file = tokens_dir / f"{safe_name}.json"
        token_file.write_text(creds.to_json(), encoding="utf-8")
        rel_token = str(token_file.relative_to(BASE_DIR)).replace("\\", "/") if BASE_DIR in token_file.parents else str(token_file)
        accounts.append({
            "email": email,
            "token": rel_token,
            "active": True
        })

    data["active_account"] = email
    for a in accounts:
        a["active"] = (a.get("email", "").lower() == email.lower())
    data["accounts"] = accounts
    save_accounts(data)

    return email, data

def remove_account(email):
    data = load_accounts()
    accounts = data.get("accounts", [])
    remaining = []
    removed_token = None
    for a in accounts:
        if a.get("email", "").lower() == email.lower():
            removed_token = resolve_token_path(a.get("token"))
        else:
            remaining.append(a)

    if removed_token and removed_token.exists():
        try:
            removed_token.unlink()
        except OSError:
            pass

    data["accounts"] = remaining
    if data.get("active_account", "").lower() == email.lower():
        data["active_account"] = remaining[0]["email"] if remaining else ""
        if remaining:
            remaining[0]["active"] = True

    save_accounts(data)
    return data

CREDENTIALS_FILE = get_credentials_file()

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


def get_gmail_emails(query="newer_than:7d", max_results=20, account_email=None):
    data = load_accounts()
    accounts = data.get("accounts", [])

    target_email = account_email or data.get("active_account") or ""

    if target_email == "all" and accounts:
        emails = []
        per_account = max(5, max_results // len(accounts))
        for acc in accounts:
            acc_email = acc.get("email")
            try:
                srv = gmail_service_for_account(acc_email)
                res = (
                    srv.users()
                    .messages()
                    .list(userId="me", q=query, maxResults=per_account)
                    .execute()
                )
                for message in res.get("messages", []):
                    msg = (
                        srv.users()
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
                        "account": acc_email,
                    })
            except Exception as exc:
                print(f"Error reading emails for account {acc_email}: {exc}")

        # Deduplicate
        seen = set()
        deduped = []
        for em in emails:
            if em["id"] not in seen:
                seen.add(em["id"])
                deduped.append(em)
        return deduped[:max_results]

    # Specific or active account
    actual_email = None
    if target_email and target_email != "all":
        actual_email = target_email
    elif accounts:
        actual_email = accounts[0].get("email")

    srv = gmail_service_for_account(actual_email)
    result = (
        srv.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )

    emails = []
    for message in result.get("messages", []):
        msg = (
            srv.users()
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
            "account": actual_email or "Primary",
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
        account_line = f"Account: {email['account']}\n" if email.get("account") else ""
        chunks.append(
            f"""
EMAIL {index}
{account_line}Gmail ID: {email["id"]}
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

CRITICAL TITLE FORMAT:
- "title" MUST be a clear, high-signal SUMMARIZED TITLE that tells the student WHAT the email is about at a glance.
- Put the Course, Subject, or Topic FIRST, followed by the specific announcement or action.
- Format: "<Course/Topic>: <Brief announcement or required action>"
- Examples:
  * "ACM Winter School: Apply by Oct 5"
  * "Full Stack SDP: Course Handout (CHO) Released"
  * "BE Civil Sem 2: Re-Appear Evaluation Result"
  * "BE Civil AIML: Re-Evaluation Circular"
  * "CSE Sem 7: Revised Class Timetable"
  * "Calculus: Assignment 3 Submission Deadline"
- Do NOT start with generic action verbs alone (e.g., avoid "Read Course Handout", "Apply for ACM", "Check result").
- Keep "title" under 60 characters so it fits neatly in tables and dashboards without truncation.

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
      "summary": "",
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


_notion_properties_cache = None

def get_notion_db_properties():
    global _notion_properties_cache
    if _notion_properties_cache is not None:
        return _notion_properties_cache
    if not notion_configured():
        return set()
    try:
        url = f"https://api.notion.com/v1/data_sources/{NOTION_DATA_SOURCE_ID}/query"
        response = requests.post(
            url,
            headers=notion_headers(),
            json={"page_size": 1},
            timeout=10,
        )
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                _notion_properties_cache = set(results[0].get("properties", {}).keys())
                return _notion_properties_cache
    except Exception:
        pass
    return set()


def create_notion_task(item, source_email_id, source_account=None):
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

    # If Notion database contains a 'Source Account' property, include it
    db_props = get_notion_db_properties()
    if source_account and "Source Account" in db_props:
        properties["Source Account"] = {
            "rich_text": [{"text": {"content": source_account[:200]}}]
        }

    deadline = item.get("deadline") or ""
    date_match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", deadline)

    if date_match:
        year, month, day = date_match.groups()
        properties["Due date"] = {
            "date": {"start": f"{year}-{int(month):02d}-{int(day):02d}"}
        }

    children = []
    
    # 1. Summary Block
    summary_text = (item.get("summary") or item.get("task") or "").strip()
    if summary_text:
        children.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "📌"},
                "rich_text": [{
                    "type": "text",
                    "text": {"content": f"Summary: {summary_text[:1800]}"}
                }]
            }
        })

    # 2. Action Required / Details Block
    details = []
    if item.get("task") and item.get("task") != summary_text:
        details.append(f"• Action: {item.get('task')}")
    if item.get("important_information"):
        details.append(f"• Key Info: {item.get('important_information')}")
    if item.get("location"):
        details.append(f"• Portal / Link: {item.get('location')}")
    if item.get("attachment_information"):
        details.append(f"• Attachments: {item.get('attachment_information')}")
    if source_account:
        details.append(f"• Account: {source_account}")

    if details:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": "\n".join(details)[:1900]}
                }]
            }
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


@app.get("/api/accounts")
def api_get_accounts():
    try:
        data = load_accounts()
        return jsonify({
            "ok": True,
            "accounts": [
                {
                    "email": acc["email"],
                    "active": acc.get("active", False),
                }
                for acc in data.get("accounts", [])
            ],
            "active_account": data.get("active_account", ""),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/accounts/select")
def api_select_account():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip()
    if not email:
        return jsonify({"ok": False, "error": "Email is required."}), 400

    try:
        data = set_active_account(email)
        return jsonify({
            "ok": True,
            "active_account": data.get("active_account", ""),
            "accounts": [
                {"email": a["email"], "active": a.get("active", False)}
                for a in data.get("accounts", [])
            ],
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/accounts/auth-url")
def api_accounts_auth_url():
    """Step 1 – generate the Google OAuth URL and return it to the frontend."""
    try:
        auth_url = generate_auth_url()
        return jsonify({"ok": True, "auth_url": auth_url})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/api/accounts/callback")
def api_accounts_callback():
    """Step 2 – Google redirects here with ?code=... after the user approves."""
    error = request.args.get("error")
    if error:
        return f"""
        <html><body style="font-family:sans-serif;text-align:center;padding:60px">
        <h2 style="color:#c0392b">❌ Authentication failed</h2>
        <p>{error}</p>
        <p>You can close this tab.</p>
        <script>window.close();</script>
        </body></html>
        """, 400

    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return "Missing authorisation code.", 400

    try:
        email, data = save_account_from_code(code, state=state)
        return f"""
        <html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#f5f7fb">
        <div style="max-width:420px;margin:auto;background:#fff;border-radius:18px;padding:48px;box-shadow:0 18px 50px rgba(29,35,58,.08)">
        <div style="font-size:48px;margin-bottom:16px">&#10004;</div>
        <h2 style="color:#172033;margin:0 0 10px">{email}</h2>
        <p style="color:#7c8497;font-size:14px">Successfully connected to Student AI.</p>
        <p style="color:#7c8497;font-size:13px">You can close this tab and go back to the dashboard.</p>
        <script>
            // Notify the opener tab and close
            if (window.opener) {{
                window.opener.postMessage({{type:'GMAIL_ACCOUNT_ADDED',email:'{email}'}}, '*');
            }}
            setTimeout(() => window.close(), 1800);
        </script>
        </div>
        </body></html>
        """
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return f"""
        <html><body style="font-family:sans-serif;text-align:center;padding:60px">
        <h2 style="color:#c0392b">Error saving account</h2>
        <pre style="text-align:left;max-width:600px;margin:20px auto;background:#f0f0f0;padding:15px;border-radius:8px;font-size:12px">{exc}</pre>
        <p>You can close this tab and try again.</p>
        </body></html>
        """, 500


@app.post("/api/accounts/remove")
def api_remove_account():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip()
    if not email:
        return jsonify({"ok": False, "error": "Email is required."}), 400

    try:
        data = remove_account(email)
        return jsonify({
            "ok": True,
            "active_account": data.get("active_account", ""),
            "accounts": [
                {"email": a["email"], "active": a.get("active", False)}
                for a in data.get("accounts", [])
            ],
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/api/health")
def health():
    ai_ready = bool(
        AZURE_OPENAI_KEY
        or (FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_AGENT_NAME)
    )
    acc_data = load_accounts()
    accounts_list = acc_data.get("accounts", [])
    gmail_ready = (
        bool(accounts_list)
        or get_credentials_file().exists()
        or (BASE_DIR / "token.json").exists()
    )

    return jsonify({
        "ok": True,
        "gmail": gmail_ready,
        "notion": notion_configured(),
        "foundry": ai_ready,
        "accounts_count": len(accounts_list),
        "active_account": acc_data.get("active_account", ""),
    })


@app.post("/api/chat")
def api_chat():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    account = (data.get("account") or "").strip() or None

    if not question:
        return jsonify({"ok": False, "error": "Question is required."}), 400

    try:
        query = determine_gmail_query(question)
        emails = get_gmail_emails(query, 20, account_email=account)
        answer = chat_with_foundry(question, emails)

        return jsonify({
            "ok": True,
            "answer": answer,
            "emails_found": len(emails),
            "query": query,
            "account": account or get_active_account(),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/api/emails")
def api_emails():
    try:
        account = request.args.get("account", "").strip() or None
        emails = get_gmail_emails("newer_than:7d", 50, account_email=account)

        return jsonify({
            "ok": True,
            "account": account or get_active_account(),
            "emails": [
                {
                    "id": email["id"],
                    "subject": email["subject"],
                    "sender": email["sender"],
                    "date": email["date"],
                    "account": email.get("account", ""),
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
        account = request.args.get("account", "").strip() or None
        emails = get_gmail_emails("newer_than:1d", 50, account_email=account)
        tasks = get_notion_tasks()

        return jsonify({
            "ok": True,
            "account": account or get_active_account(),
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
        data = request.get_json(silent=True) or {}
        account = (data.get("account") or "").strip() or None

        scan_limit = 15 if os.getenv("VERCEL") else 50
        emails = get_gmail_emails("in:inbox newer_than:30d", scan_limit, account_email=account)
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

            # Find matching email to get the source account
            matching_email = next((em for em in emails if em["id"] == source_id), None)
            source_acc = matching_email.get("account") if matching_email else (account or get_active_account())

            try:
                result = create_notion_task(item, source_id, source_account=source_acc)

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
            "account": account or get_active_account(),
        })

    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

