# `/lesson` — turn debugging sessions into textbook lessons

A [Claude Code](https://claude.com/claude-code) plugin that watches your real problem-solving sessions and produces grounded, textbook-quality markdown lessons from them — using *your* code, *your* errors, and *your* wrong turns as the raw material.

Instead of reading a generic "Intro to async Python" article, you get a lesson that says: *"Here is the exact line in `worker.py` where you called a coroutine without awaiting it. Here is the mental model you were missing. Here is how it shows up in the asyncio docs. Here is an exercise to fix the other three places in your code where the same mistake is lurking."*

---

## Why

LLMs are great at generating tutorials. They are not great at knowing *which* tutorial *you* needed. By the time you've been stuck on a bug for 40 minutes, you've generated enough signal to pinpoint the exact misconception — you just don't have a good way to capture it.

`/lesson` captures it. It silently records your debugging arc via Claude Code hooks, identifies the one fundamental concept that would have prevented the whole episode, researches it, and writes a lesson that's impossible to write from cold.

## What you get

A single markdown file at `.claude/lessons/output/<slug>.md` containing:

- **Narrative of what broke** — with real snippets and real error messages from your session
- **The concept, explained** — textbook-style prose with inline citations to authoritative sources (MDN, official docs, etc.)
- **Two mermaid diagrams** — one of the concept, one of the actual debug path you took (with the misconception marked)
- **Curated resources** — 3–5 links, hand-picked from what Claude fetched
- **A closing exercise grounded in your code** — not a generic problem; something you can verify against your own files

---

## Quickstart

Inside Claude Code:

```
/plugin marketplace add OussemaBenAmeur/lesson
/plugin install lesson
```

Then restart Claude Code — hooks and commands register at session start, so the first session after install is when it becomes active.

Then, in any project:

```
/lesson python asyncio event loop blocking on cpu work
```

Work normally. Hit errors. Try things. Edit files. Fix things.

When you're done:

```
/lesson-done
```

Your lesson is now at `.claude/lessons/output/<slug>.md`. Open it, read it, commit it, share it — it's just markdown.

> If you just close Claude Code without running `/lesson-done`, the Stop hook will nudge you to generate the lesson first. If you want to bail without generating anything, delete `.claude/lessons/active-session` and try again.

---

## Install

### From GitHub (recommended)

Inside Claude Code:

```
/plugin marketplace add OussemaBenAmeur/lesson
/plugin install lesson
```

Restart your Claude Code session. Hooks and commands register at session start, so the first session after install is when it becomes active.

### Local dev

Clone the repo anywhere and add it as a local marketplace:

```bash
git clone https://github.com/OussemaBenAmeur/lesson.git
```

Then in Claude Code:

```
/plugin marketplace add /absolute/path/to/lesson
/plugin install lesson
```

### Verify install

Start a new Claude Code session and type `/lesson` — you should see the command autocomplete. If it doesn't, the plugin didn't load; check `claude --debug` output.

---

## Usage

### Starting a session

```
/lesson <free-form description of what you're trying to do>
```

The description is optional but helps Claude focus the final analysis. Good descriptions name the problem, the tool, and the context: `/lesson react useEffect infinite loop when depending on an object`.

Once you run `/lesson`, the PostToolUse hook is live. Every tool call — every `Read`, `Edit`, `Bash`, `Grep`, etc. — gets logged to an append-only file. You will not see anything; it runs silently.

### Working

Just work. Solve the problem, or try to. Hit errors. Revert bad changes. Run tests. The hook captures everything it can see without polluting your context: tool name, a truncated view of the arguments, a truncated view of the result, and an error flag.

Every `LESSON_COMPRESS_EVERY` events (default 25), the plugin spawns a compression subagent that rolls the raw log into a running narrative summary. This keeps the main conversation context lean — you don't pay a huge token cost at the end.

### Finishing

```
/lesson-done
```

Claude reads the full session state, runs analysis to pick the one fundamental concept, uses `WebSearch` + `WebFetch` to pull authoritative sources on that concept, and writes the lesson.

If Claude can't find good sources, it tells you instead of writing a degraded lesson. Grounding is the whole point.

### Aborting without a lesson

```bash
rm .claude/lessons/active-session
```

The hook goes back to being a no-op for this project.

---

## How it works

```
user types /lesson
  └─> commands/lesson.md       — Claude creates session dir, writes active-session marker
       │
       ▼  (user works normally)
  PostToolUse fires on every tool call
  └─> hooks/post_tool_use.py   — appends one truncated event to arc.jsonl
                                  bumps counter; at threshold, emits a
                                  system reminder asking Claude to compress
       │
       ▼
  Claude spawns Task subagent of type `lesson-compress`
  └─> agents/lesson-compress.md — reads arc.jsonl, merges into summary.md,
                                   archives consumed events, truncates arc.jsonl
       │
       ▼  (eventually)
  user types /lesson-done OR Stop hook fires
  └─> commands/lesson-done.md   — Claude loads summary + arc, analyzes,
                                   searches the web, fills templates/lesson.md.tmpl,
                                   writes output/<slug>.md, removes marker
```

Two design rules this plugin is opinionated about:

1. **Hooks are dumb.** The PostToolUse hook is a 150-line Python script with no LLM calls. It appends, truncates, and signals. All summarization happens via a Claude subagent, because summarization is a reasoning task and reasoning tasks belong in Claude.
2. **Main context never sees the raw log.** Compression is done by a subagent that reads `arc.jsonl` and returns only a one-line "done" status. The main conversation only ever sees the compressed `summary.md` — and only when `/lesson-done` runs.

### File layout

Plugin (what this repo ships):

```
lesson-plugin/
├── .claude-plugin/plugin.json     # manifest
├── hooks/
│   ├── hooks.json                 # PostToolUse + Stop registration
│   ├── post_tool_use.py           # event logger + compression trigger
│   └── stop.py                    # session-end nudge
├── commands/
│   ├── lesson.md                  # /lesson command
│   └── lesson-done.md             # /lesson-done command
├── agents/
│   └── lesson-compress.md         # compression subagent
├── templates/
│   └── lesson.md.tmpl             # markdown scaffold with mermaid blocks
├── LICENSE
└── README.md
```

Per-project runtime state (created in your project's `.claude/lessons/`):

```
.claude/lessons/
├── active-session                 # marker file — presence = hook is tracking
├── sessions/<slug>/
│   ├── meta.json                  # goal, start time, cwd
│   ├── arc.jsonl                  # raw events since last compression
│   ├── summary.md                 # rolling compressed summary
│   ├── counter                    # events since last compression
│   └── arc.jsonl.archive.<N>      # consumed raw events
└── output/
    └── <slug>.md                  # your finished lessons
```

### Recommended `.gitignore` entries

```gitignore
.claude/lessons/active-session
.claude/lessons/sessions/
```

Keep `.claude/lessons/output/` versioned if you want the lessons themselves to live with the repo. Skip it if you consider them private notes.

---

## Configuration

All settings are optional environment variables:

| Variable | Default | What it does |
|---|---|---|
| `LESSON_COMPRESS_EVERY` | `25` | Events between compression subagent runs. Lower = more subagent invocations, cleaner context. Higher = fewer invocations, larger intermediate logs. |
| `LESSON_STOP_MIN_EVENTS` | `5` | Minimum total events for the Stop hook to nudge `/lesson-done`. Below this, the hook stays silent (avoids half-baked lessons from interrupted sessions). |

Set them in your shell, or under `env` in `.claude/settings.json`:

```json
{
  "env": {
    "LESSON_COMPRESS_EVERY": "15"
  }
}
```

---

## FAQ

**Does this send my code to random services?**
No. The only external calls are `WebSearch` and `WebFetch`, and only during `/lesson-done`. They search for the *concept*, not your code. Your code is used locally to ground the lesson.

**Does it slow down my tool calls?**
No. The PostToolUse hook is a short Python script that exits in milliseconds. It's a no-op in any project that isn't actively tracking a `/lesson` session.

**Can I run multiple lesson sessions in parallel?**
Not in the same project — the `active-session` marker is a single file. Different projects are fine.

**What if `/lesson-done` fails partway through?**
It won't leave a half-written lesson file. It reports the failure and leaves `active-session` in place so you can retry.

**How do I edit the lesson template?**
Edit `templates/lesson.md.tmpl` in the plugin directory. It's a plain markdown file with `{{PLACEHOLDER}}` tokens that `/lesson-done` fills.

**Will this work offline?**
`/lesson` and the tracking hooks work offline. `/lesson-done` requires network access for the web research step.

---

## Troubleshooting

**`/lesson` command not found after install.** The plugin loads at session start. Restart Claude Code. If still not found, run `claude --debug` and look for plugin load errors.

**Hook errors in the status line.** The hooks are designed to exit 0 on any exception so they can never block your real tool calls. If you're seeing errors, run the smoke test below to isolate.

**`/lesson-done` says there's no active session.** The `.claude/lessons/active-session` file is missing. Either you never ran `/lesson`, or it was deleted. Start a new session with `/lesson`.

**Stop hook keeps nudging me and I just want to stop.**
Delete the marker: `rm .claude/lessons/active-session`.

### Smoke-testing the hooks without Claude

```bash
cd /tmp && rm -rf lesson-test && mkdir lesson-test && cd lesson-test

# 1. Hook is a no-op when no session is active.
echo '{"cwd":"/tmp/lesson-test","tool_name":"Read","tool_input":{},"tool_response":{}}' \
  | python3 ~/.claude/plugins/lesson/hooks/post_tool_use.py
echo "expect exit 0: $?"

# 2. Simulate an active session and feed an event.
mkdir -p .claude/lessons/sessions/test
printf test > .claude/lessons/active-session
printf 0 > .claude/lessons/sessions/test/counter
: > .claude/lessons/sessions/test/arc.jsonl

echo '{"cwd":"/tmp/lesson-test","tool_name":"Bash","tool_input":{"command":"ls"},"tool_response":{"content":"a\nb"}}' \
  | python3 ~/.claude/plugins/lesson/hooks/post_tool_use.py

cat .claude/lessons/sessions/test/arc.jsonl
# → one JSON line with tool=Bash, is_error=false
```

---

## Contributing

Issues and PRs welcome. The plugin is intentionally small — prefer edits over additions.

Design principles to preserve:

- Hooks stay LLM-free and never block
- Compression is always a subagent, never the main conversation
- Lessons are grounded in real session data or they don't get written
- No half-baked fallbacks: fail loudly rather than degrade quietly

## License

MIT — see [LICENSE](LICENSE).
