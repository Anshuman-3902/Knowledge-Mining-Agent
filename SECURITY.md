# Security Policy

## Supported Versions

Security updates and patches are applied to the latest `main` branch.

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |

---

## Reporting a Vulnerability

The maintainers take security seriously. If you discover a vulnerability or potential security issue in **Knowledge Mining Agent**, please follow these responsible disclosure steps:

1. **Do NOT disclose vulnerabilities publicly** via open GitHub issues, pull requests, or public discussions.
2. Report the vulnerability privately to the project maintainer ([Anshuman-3902](https://github.com/Anshuman-3902)) via GitHub private vulnerability reporting or direct contact.
3. Provide details including:
   - A description of the issue.
   - Steps to reproduce the vulnerability or proof-of-concept.
   - Potential impact.

### Response Timeline
- You will receive an acknowledgment of your report within 48-72 hours.
- We will provide updates on the investigation and any planned remediation or patch.

---

## Security Best Practices for Users

- **Credentials Protection**: Never commit `credentials.json`, `token.json`, or `.env` to GitHub or any public repository.
- **Local Execution**: The OAuth flow runs on `localhost` (`port=0`), and generated tokens are stored locally on your machine.
- **API Keys**: Rotate your Notion Integration Tokens and Azure AI keys regularly.
