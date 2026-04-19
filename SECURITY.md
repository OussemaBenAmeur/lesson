# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.3.x   | Yes       |
| < 0.3   | No        |

## What This Project Handles

`lesson-ai` reads tool events from your AI coding session and writes files to your local filesystem (`.claude/lessons/` inside your project). It makes no network requests of its own, stores no credentials, and does not communicate with any external service.

## Potential Risk Areas

- **Hook execution** — `hooks/post_tool_use.py` runs as a subprocess on every tool call inside Claude Code. It writes to `arc.jsonl` and spawns `lesson compress`. It never reads environment variables, credentials, or secrets.
- **Session data** — `arc.jsonl` and `session_graph.json` may contain fragments of your code, file paths, and error messages. They live in your project directory and are never uploaded anywhere.
- **PDF rendering** — `scripts/render_pdf.py` invokes local tools (e.g. `weasyprint`, `mermaid-js`) if available. No external URLs are fetched.

## Reporting a Vulnerability

If you find a security issue, please **do not open a public GitHub issue**.

Email: oussemabenameur9@gmail.com

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact

You will receive a response within 72 hours. If the issue is confirmed, a fix will be released as a patch version and credited to you (unless you prefer to stay anonymous).
