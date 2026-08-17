# lesson

**Notices what you don't understand while you work, then explains it properly.**

You use Claude Code. It fixes things. Some of those fixes you understood, and
some you nodded at and moved on from. `lesson` watches for the second kind.

It keeps one file — a knowledge graph of what you understand — and it fills in
as you work. When the same gap shows up more than once, it offers to explain
that one thing, starting from the beginning, never using a word it hasn't
defined.

> ⚠️ **Rewritten from scratch, August 2026.** Everything before `v0.3-graph-era`
> was a different design and does not work. This version has not been released
> and is not finished — see [Status](#status).

---

## How it works

**It watches.** When Claude finishes and hands control back, a small script
counts. Every so often it starts a separate Claude in the background to read
what happened in that session. You never see it, and it never touches your
conversation.

It looks for four things:

| Signal | What it means |
|---|---|
| An error that surprised you | what you expected didn't happen |
| A question you asked | what you ask places you exactly |
| Something you let Claude do without asking about it | the strongest signal, and the one nothing else can see |
| Something you handled yourself | this is how you move *up* |

**It remembers.** One file, `~/.claude/lesson/graph.json`. Dots are things you
can understand, arrows mean *you need this one first*. Every claim records why
it thinks so, whether it **observed** that or **guessed** it, and which session
it came from. It's your file — plain text, edit it, delete things, tell it it's
wrong.

**It offers.** About one session in five, when a gap has shown up more than
once:

```
Claude changed which Python your project uses. Want the two-minute version
of why that fixed the import error?
```

An offer, never a quiz. There is no wrong answer, and "no" means it never asks
again.

**It explains.** One lesson, one concept, as a self-contained HTML page. Before
writing it, it walks the arrows backwards — anything you need first that you
don't have yet gets explained inside the lesson, before the word is used.

That last rule is the whole point: **never build a complex term on another
complex term.**

---

## Commands

| Command | Does |
|---|---|
| `/lesson` | First time: a short setup conversation, then your first lesson. After: what's waiting. |
| `/lesson graph` | Draw what you know as a picture you can click around |
| `/lesson <topic>` | Explain something you already know you're shaky on |

---

## What it doesn't do

- **Test you.** Ever. Offers only.
- **Interrupt you mid-task.** Only when Claude hands control back.
- **Pile up.** One unread lesson at a time, maximum.
- **Send anything anywhere.** No network requests of its own.
- **Claim things it can't back up.** Every statement carries its evidence.

---

## Status

Not finished, not released.

**Working:** the graph format, the graph viewer, the watching hook.

**Written but never run for real:** reading a transcript and turning it into
statements about a person. This is the part that decides whether the whole idea
works, and it hasn't been validated yet.

**Not started:** installing and running the thing end to end.

---

## Requirements

Claude Code. Nothing else — no Python packages, no API key, no install step
beyond adding the plugin. Other platforms are out of scope until this one is
good.

## License

MIT
