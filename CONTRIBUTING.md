# Contributing to Knowledge Mining Agent

Thank you for your interest in contributing to **Knowledge Mining Agent**! We welcome contributions, bug reports, and feature proposals from the community.

---

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## How Can I Contribute?

### 1. Reporting Bugs
- Before creating a bug report, check the [open issues](https://github.com/Anshuman-3902/Knowledge-Mining-Agent/issues) to make sure it hasn't already been reported.
- Use the **Bug Report** issue template.
- Provide a clear, descriptive title.
- Include step-by-step instructions to reproduce the behavior, along with expected vs. actual outcomes and error logs.
- **Never paste sensitive information (tokens, credentials, client secrets) into public issue reports.**

### 2. Suggesting Enhancements
- Feature requests are tracked as [GitHub Issues](https://github.com/Anshuman-3902/Knowledge-Mining-Agent/issues).
- Use the **Feature Request** issue template.
- Clearly describe the problem, proposed solution, and alternative approaches considered.

### 3. Submitting Pull Requests (PRs)
1. **Fork** the repository and clone your fork locally.
2. Create a new branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
   or
   ```bash
   git checkout -b fix/your-bugfix-name
   ```
3. Set up the development environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Make your code changes cleanly.
5. Follow PEP 8 style standards and verify syntax:
   ```bash
   python -m py_compile app.py
   ```
6. Commit your changes with clear, semantic commit messages:
   ```bash
   git commit -m "feat: add support for background scheduler"
   ```
7. Push your branch to GitHub and open a Pull Request against the `main` branch.
8. Complete the PR template checklist.

---

## Coding Standards

- **Python**: Follow [PEP 8](https://peps.python.org/pep-0008/) style conventions.
- **Secrets Management**: Never commit `.env`, `credentials.json`, or `token.json`.
- **Documentation**: Update `README.md` and docstrings when introducing new features, environment variables, or endpoints.

---

## Questions and Support

Feel free to open an issue or start a discussion on GitHub if you have any questions or need guidance!
