# /lesson — Claude Code Skill

This skill is natively supported via commands in `~/.claude/plugins/lesson/commands/` and hooks in `~/.claude/plugins/lesson/hooks/`. No manual logging is needed — the PostToolUse hook writes `arc.jsonl` and silently runs `lesson compress` at the 25-event threshold, and the Stop hook emits a single passive nudge without blocking exit.

This file is provided for reference only. See `docs/architecture.md` for full details.

**Install:**
```bash
python3 scripts/install.py --platform claude-code
```
