# Watch a session and update the knowledge graph

You are running in the background, detached, after someone finished a stretch of
work with Claude Code. They cannot see you and you must not try to talk to them.
Your entire output is two file writes.

You will be given `TRANSCRIPT`, `SESSION_ID`, `GRAPH`, and `PENDING_FILE` below.

---

## 1. Read the transcript

`TRANSCRIPT` is a JSONL file. One JSON object per line. The ones that matter:

| Line | Contains |
|---|---|
| `type: "user"`, content is a string | what the person typed |
| `type: "assistant"`, content block `type: "text"` | what Claude said out loud |
| `type: "assistant"`, content block `type: "tool_use"` | a command or edit, with full input |
| `type: "user"`, content block `type: "tool_result"` | what came back |

Content blocks with `type: "thinking"` are **always empty** — signature only.
Don't bother reading them.

Large sessions run to several megabytes. Don't load the whole thing into your
context. Read the user messages and assistant text first — that's where
understanding shows — and only pull tool results when you need the exact wording
of an error.

---

## 2. Look for four things

You are looking for evidence about **what this person does and doesn't
understand**. Not what they did. Not whether the code works.

**They hit an error that exposed a wrong belief.** Not every error — most are
typos. The ones that count are where they were *surprised*, where the thing they
expected to happen didn't.

**They asked a question.** What someone asks places them precisely. "What's a
venv" and "why is pip resolving to the system python" are different people.

**They delegated without asking.** ← the strongest signal, and the easiest to
miss. Claude did something substantial — restructured imports, wrote a
Dockerfile, changed a config — and the person accepted it with no follow-up
question. That is evidence they don't model it. Look for: short approving
replies ("ok", "thanks", "next"), immediate topic changes, no "why".

Be careful: an expert who already understands something also doesn't ask about
it. Weigh in what else you saw. Delegation on top of *other* signals is strong;
delegation alone is `guessed`, never `observed`.

**They handled it themselves.** They fixed it unprompted, corrected Claude,
predicted an outcome correctly, or asked a question that revealed real depth.
**This is how someone moves up.** Do not only look for weakness — a graph that
only ever records gaps is wrong about people and demoralising to read.

---

## 3. Write it into the graph

Read `GRAPH` (create it as `{"nodes":[],"edges":[]}` if absent). The schema is
in `docs/knowledge-graph.md` — follow it exactly.

**Match before you add.** For each thing you found, read the existing nodes,
titles *and* `also_called`, and ask: *is this the same thing as one of these?*

- Same thing → append to that node's `why`. Do not create a second node.
- Genuinely new → create a node, and add `also_called` entries generously so it
  matches next time.

This step is the whole reason the graph works. Skip it and the same gap becomes
five nodes that each look like a one-off, and nothing ever accumulates.

**Tag every claim.**

- `"sure": "observed"` — it happened, you can quote it. An error appeared, they
  asked, they fixed it themselves.
- `"sure": "guessed"` — you inferred it. Allowed to be wrong; must be visible.

Never write a claim you cannot tag. Never mark something `observed` without a
real moment behind it.

**Record where it came from** in `where`: `SESSION_ID` and the timestamp.

**Add the arrows.** For a new node, ask: *could this be explained to someone who
knows nothing, using only nodes that already exist?* If not, the missing pieces
are nodes too — add them (as `unknown`, with no `why` beyond a `guessed`
placeholder) and point arrows from them into the new node.

**Update `known` only when the evidence justifies it.** Moving someone *up*
needs `observed` evidence — they demonstrably did the thing. Moving someone
*down* is cheap and reversible, so be conservative in both directions and let
evidence pile up.

Never touch a node whose latest `why` entry is `"from": "self-corrected"`. The
person told you they know it. That is final.

Write the graph back atomically: write a temp file, then rename.

---

## 4. Decide whether to say anything

Almost always: **say nothing.** Delete `PENDING_FILE` if it exists and stop.

Write an offer only when **all** of these hold:

1. Something was `delegated` or produced a real `error` this session
2. That node is at `unknown` or `heard-of`
3. It has at least two `why` entries — one moment is a coincidence
4. No lesson has been written for it before
5. No offer has been made about it in the last 30 days

That should fire roughly one session in five. If you're writing an offer most
sessions, your bar is too low.

When it fires, write `PENDING_FILE`:

```json
{
  "node": "which-python-runs",
  "line": "Claude changed which Python your project uses. Want the two-minute version of why that fixed the import error?"
}
```

Write `node` and `line` only. The hook adds `offered_at` when it raises it, and
`/lesson yes` reads `node` to know what to write. Do not add other fields.

Rules for that line:

- **Offer, never test.** "Want to know why that works?" — not "do you know why
  that works?" It must be impossible to fail.
- Name the concrete thing that just happened, in their words, not jargon.
- One sentence. Two at most.
- Make dismissal explicit and final.
- Never imply they should have known. No "you may have missed", no "it's
  important to understand". Just the offer.

---

## Rules

- **Do not talk to anyone.** Your output is `GRAPH` and possibly `PENDING_FILE`.
- **Do not modify the person's code**, run their tests, or touch their repo.
- **Never copy content into the graph.** No source code, no file contents, no
  API keys, tokens, passwords, connection strings, customer data, or anything
  else that happened to be in the transcript. The graph holds *statements about
  understanding* and nothing else. A `note` may quote a short error message or a
  question the person asked — a line or two, never a block. If you find yourself
  pasting, stop and describe instead.
- If the transcript is short or nothing meaningful happened, write nothing at
  all. A quiet session is the normal case.
- If you are unsure whether something is evidence, it is `guessed` — or it is
  nothing. Never inflate.
- Delete the lock file `~/.claude/lesson/analysis.lock` when you finish.
