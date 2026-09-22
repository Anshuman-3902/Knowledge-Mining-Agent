#!/usr/bin/env python3
"""
GitHub Issues Automation Script for Knowledge-Mining-Agent
Repository: Anshuman-3902/Knowledge-Mining-Agent

Usage:
  1. Using GitHub Personal Access Token (PAT):
     python scripts/create_issues.py --token YOUR_GITHUB_PAT

  2. Print GitHub CLI (gh) commands:
     python scripts/create_issues.py --print-cli
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

REPO_OWNER = "Anshuman-3902"
REPO_NAME = "Knowledge-Mining-Agent"

ISSUES = [
    {
        "title": "[Feature]: Background Scheduled Email Poller & Periodic Sync",
        "labels": ["enhancement", "backend"],
        "body": """### Summary
Implement a background scheduler (e.g., using `APScheduler` or background worker threads) to automatically poll Gmail at configurable intervals (e.g., every 30 minutes) and sync newly discovered academic deadlines into Notion without requiring manual user scans.

### Key Deliverables
- [ ] Configurable polling interval via `.env` (`POLL_INTERVAL_MINUTES=30`).
- [ ] Non-blocking background worker thread in Flask.
- [ ] Automatic deduplication using Gmail message IDs.
- [ ] UI status indicator showing last sync time and next scheduled scan.
- [ ] Desktop/browser push notification support for newly detected High-Priority tasks.

### Additional Context
Currently, task extraction only happens when the user manually triggers `/api/scan`. An automated poller provides true set-and-forget automation for students.
""",
    },
    {
        "title": "[Feature]: Semantic Search & Hybrid RAG with Vector Embeddings",
        "labels": ["enhancement", "ai-ml"],
        "body": """### Summary
Upgrade the keyword-based Gmail query routing (`determine_gmail_query`) with dense vector embeddings and a lightweight vector store (e.g. FAISS / ChromaDB / Azure AI Search) for true semantic knowledge retrieval across past academic emails.

### Key Deliverables
- [ ] Email chunking and embedding generation pipeline.
- [ ] Local vector index stored in a secure local database (e.g. SQLite-vss or ChromaDB).
- [ ] Hybrid search combining Gmail date/subject filters with cosine similarity matching.
- [ ] Source citation footnotes in AI chat answers linking directly to the specific email message ID.

### Additional Context
Students frequently search with ambiguous queries like "when is our group presentation due?" where keyword searches might miss relevant announcements.
""",
    },
    {
        "title": "[Feature]: Customizable Notion Database Schema Property Mapping",
        "labels": ["enhancement", "notion-integration"],
        "body": """### Summary
Make Notion database property names (e.g. "Task name", "Due date", "course", "category", "priority", "Status", "Source Email") configurable rather than hardcoded in `app.py`.

### Key Deliverables
- [ ] Support custom property name mappings via `notion_schema.json` configuration file or environment variables.
- [ ] Add Notion database schema verification on startup or `/api/health` check.
- [ ] Display clear warning in the web UI if expected Notion columns are missing or have mismatched types.
- [ ] Document sample Notion database templates.
""",
    },
    {
        "title": "[Enhancement]: Docker Containerization & Docker Compose Setup",
        "labels": ["devops", "enhancement"],
        "body": """### Summary
Create a production-ready, multi-stage `Dockerfile` and `docker-compose.yml` to enable running Knowledge Mining Agent in containerized environments with isolated dependencies.

### Key Deliverables
- [ ] Multi-stage `Dockerfile` based on `python:3.11-slim`.
- [ ] `docker-compose.yml` configured with volume mounts for `credentials.json`, `token.json`, and `.env`.
- [ ] Healthcheck instruction querying `/api/health`.
- [ ] Non-root container user setup for improved security.
- [ ] Documentation in `README.md` on Docker deployment.
""",
    },
    {
        "title": "[Enhancement]: Automated Unit & Mock Integration Test Suite",
        "labels": ["testing", "ci-cd"],
        "body": """### Summary
Build a comprehensive `pytest` test suite with fixtures and mock responses to test all Flask routes, email parsers, date extractors, and Notion sync logic.

### Key Deliverables
- [ ] `tests/test_email_parser.py`: Unit tests for HTML/MIME decoding, date regex parsing, and header extraction.
- [ ] `tests/test_routes.py`: Flask test client testing endpoints `/api/health`, `/api/chat`, `/api/emails`, and `/api/tasks`.
- [ ] Mock fixtures simulating Google OAuth tokens, Gmail API messages, and Azure AI Foundry responses.
- [ ] Integrate test execution into `.github/workflows/ci.yml`.
""",
    },
    {
        "title": "[Feature]: Multi-Provider Email Support (Microsoft Outlook / Microsoft Graph API)",
        "labels": ["enhancement", "integrations"],
        "body": """### Summary
Expand the Knowledge Mining Assistant beyond Gmail to support university Microsoft 365 / Outlook email accounts using the Microsoft Graph API.

### Key Deliverables
- [ ] Implement OAuth 2.0 device flow / web flow using MSAL (Microsoft Authentication Library).
- [ ] Create an abstract base class `EmailProvider` with concrete implementations for `GmailProvider` and `OutlookProvider`.
- [ ] Unified data schema for retrieved emails and message IDs.
- [ ] UI toggle to select active inbox source (Gmail, Outlook, or both).
""",
    },
    {
        "title": "[UI/UX]: Dark Mode / Light Mode Theme Toggle & Responsive Mobile Layout",
        "labels": ["ui/ux", "frontend"],
        "body": """### Summary
Enhance the frontend interface with a polished dark mode toggle, improved CSS variable theming, and responsive layout for mobile and tablet screens.

### Key Deliverables
- [ ] Theme switcher button with persistence in `localStorage`.
- [ ] Responsive grid layout for email sidebar, calendar/schedule view, and chat interface.
- [ ] Accessibility optimizations (contrast ratios, keyboard navigation, ARIA tags).
- [ ] Mobile navigation drawer.
""",
    },
    {
        "title": "[Security]: Token Encryption at Rest & Secure Key Vault Integration",
        "labels": ["security", "enhancement"],
        "body": """### Summary
Enhance security for stored OAuth tokens (`token.json`) and API keys by implementing local symmetric encryption (Fernet / AES-GCM) or integrating with native OS credential vaults (Windows Credential Manager / macOS Keychain).

### Key Deliverables
- [ ] Encrypted token cache adapter using master password or machine-specific key.
- [ ] Support reading secrets from Azure Key Vault or system environment variables.
- [ ] Automatic token expiry check and secure revocation on logout.
""",
    },
]


def create_issue_via_api(token, issue):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Knowledge-Mining-Agent-Setup",
    }
    data = json.dumps({
        "title": issue["title"],
        "body": issue["body"],
        "labels": issue["labels"],
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            print(f" [+] Created: #{res_data.get('number')} - {issue['title']}")
            print(f"     URL: {res_data.get('html_url')}")
    except urllib.error.HTTPError as err:
        err_msg = err.read().decode("utf-8")
        print(f" [!] Error creating issue '{issue['title']}': HTTP {err.code} - {err_msg}")
    except Exception as exc:
        print(f" [!] Unexpected error: {exc}")


def print_cli_commands():
    print("# Run the following GitHub CLI commands to create all issues:")
    print()
    for issue in ISSUES:
        labels_arg = ",".join(issue["labels"])
        # Escape quotes for shell
        title = issue["title"].replace('"', '\\"')
        body = issue["body"].replace('"', '\\"').replace("\n", "\\n")
        print(f'gh issue create --repo {REPO_OWNER}/{REPO_NAME} --title "{title}" --label "{labels_arg}" --body "{body}"')
        print()


def main():
    parser = argparse.ArgumentParser(description="Create initial GitHub issues for Knowledge-Mining-Agent")
    parser.add_argument("--token", help="GitHub Personal Access Token with repo scope")
    parser.add_argument("--print-cli", action="store_true", help="Print gh CLI commands instead of calling API")

    args = parser.parse_args()

    if args.print_cli:
        print_cli_commands()
        return

    if not args.token:
        print("Usage:")
        print("  1. Create via API:  python scripts/create_issues.py --token YOUR_GITHUB_PAT")
        print("  2. Print CLI cmds: python scripts/create_issues.py --print-cli")
        sys.exit(1)

    print(f"Creating {len(ISSUES)} issues on {REPO_OWNER}/{REPO_NAME}...")
    for issue in ISSUES:
        create_issue_via_api(args.token, issue)
    print("\nDone! All issues have been processed.")


if __name__ == "__main__":
    main()
