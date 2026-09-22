# Knowledge Mining Agent — GitHub Issues Catalog

This catalog documents the curated initial roadmap issues for the repository [Knowledge-Mining-Agent](https://github.com/Anshuman-3902/Knowledge-Mining-Agent).

You can create these issues manually on GitHub, or automatically execute the script:
```powershell
python scripts/create_issues.py --token YOUR_GITHUB_PERSONAL_ACCESS_TOKEN
```
*(Or run `gh issue create` using the GitHub CLI).*

---

### Issue #1: `[Feature]: Background Scheduled Email Poller & Periodic Sync`
- **Labels**: `enhancement`, `backend`
- **Summary**: Implement a background scheduler (e.g. `APScheduler` or Celery worker) to poll Gmail automatically at user-defined intervals (e.g., every 30 minutes) instead of requiring manual scans.
- **Key Deliverables**:
  - Configurable polling interval via `.env` (`POLL_INTERVAL_MINUTES=30`).
  - Automatic task extraction and Notion sync.
  - Desktop / browser notification hook when new high-priority tasks or deadlines are detected.

---

### Issue #2: `[Feature]: Semantic Search & Hybrid RAG with Vector Embeddings`
- **Labels**: `enhancement`, `ai-ml`, `knowledge-retrieval`
- **Summary**: Upgrade the keyword-based Gmail query routing with a local or hosted vector database (such as FAISS, ChromaDB, or Azure AI Search) to support true semantic knowledge retrieval across academic emails.
- **Key Deliverables**:
  - Incremental chunking and vector embedding generation for email bodies and attachments.
  - Hybrid retrieval combining keyword matching (`q=newer_than...`) with dense vector cosine similarity.
  - Citation attribution with exact email subject/date references.

---

### Issue #3: `[Feature]: Customizable Notion Database Schema Property Mapping`
- **Labels**: `enhancement`, `notion-integration`
- **Summary**: Allow users to configure Notion property names (such as "Task name", "Due date", "Course", "Priority") via a JSON mapping file or environment settings rather than hardcoded column headers.
- **Key Deliverables**:
  - `config/notion_schema.json` mapping template.
  - Schema discovery endpoint verifying that user's Notion database contains required columns.
  - Clear error reporting in UI if Notion database properties do not match.

---

### Issue #4: `[Enhancement]: Docker Containerization & Docker Compose Setup`
- **Labels**: `devops`, `enhancement`
- **Summary**: Provide a multi-stage `Dockerfile` and `docker-compose.yml` configuration for single-command deployment.
- **Key Deliverables**:
  - Production-ready `Dockerfile` based on `python:3.11-slim`.
  - `docker-compose.yml` with persistent volume mount for `credentials.json` and `token.json`.
  - Non-root user execution in container for security best practices.

---

### Issue #5: `[Enhancement]: Automated Unit & Mock Integration Test Suite`
- **Labels**: `testing`, `ci-cd`
- **Summary**: Introduce a `pytest` test suite with `pytest-mock` to test Flask endpoints, email parsing, JSON extraction, and Notion client interactions with simulated API responses.
- **Key Deliverables**:
  - `tests/test_email_parser.py`: Unit tests for HTML/MIME decoding, date regex matching, and payload parsing.
  - `tests/test_routes.py`: Endpoint tests for `/api/health`, `/api/chat`, `/api/emails`, and `/api/scan`.
  - Mock fixtures for Google OAuth and Azure AI Foundry responses.

---

### Issue #6: `[Feature]: Multi-Provider Email Support (Microsoft Outlook / Microsoft Graph API)`
- **Labels**: `enhancement`, `integrations`
- **Summary**: Expand knowledge mining beyond Gmail to support university Microsoft 365 / Outlook accounts via Microsoft Graph API.
- **Key Deliverables**:
  - Outlook OAuth flow using MSAL (Microsoft Authentication Library).
  - Provider abstraction interface (`EmailProvider`) supporting both Gmail and Outlook.
  - Unified email model for analysis and extraction.

---

### Issue #7: `[UI/UX]: Dark Mode / Light Mode Theme Toggle & Responsive Mobile UI`
- **Labels**: `ui/ux`, `frontend`
- **Summary**: Add a modern dark/light mode toggle with CSS variables and optimize the layout for mobile and tablet screens.
- **Key Deliverables**:
  - Theme toggle switch with `localStorage` persistence.
  - Responsive flexbox/grid layout adjustments for screen widths below 768px.
  - Improved accessibility (ARIA labels, contrast ratios).

---

### Issue #8: `[Security]: Token Encryption at Rest & Secure Key Vault Integration`
- **Labels**: `security`, `enhancement`
- **Summary**: Encrypt cached OAuth tokens (`token.json`) on disk using `cryptography.fernet` or integrate with OS credential stores (Windows Credential Manager, macOS Keychain) and Azure Key Vault.
- **Key Deliverables**:
  - Secure storage adapter for local OAuth credentials.
  - Optional support for reading Notion/Foundry secrets from Azure Key Vault or environment secret manager.
