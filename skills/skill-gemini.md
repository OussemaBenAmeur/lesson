<!--
platform: gemini
data_root: .claude/lessons
cmd_prefix: /
-->

# /lesson — Gemini CLI Skill

You are equipped with a learning session tracker. When the user invokes `/lesson`, `/lesson-done`, `/regenerate`, `/lesson resume`, `/lesson-profile`, `/lesson-index`, or `/lesson-map`, follow the shared workflow below.

If hooks are active, this file is informational; the hook captures events automatically.

**Gemini note:** Gemini supports a `BeforeTool` hook — `scripts/install.py --platform gemini` registers `hooks/post_tool_use.py` as that hook so event logging is automatic in this shell. Compression at the 25-event threshold is run as a detached subprocess (`lesson compress`) — never via an LLM subagent.

---
