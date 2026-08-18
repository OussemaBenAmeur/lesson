# lesson

**Notices what you didn't understand while you work, then explains it properly.**

You use Claude Code. It fixes things. Some of those fixes you understood, and
some you nodded at and moved on from. `lesson` watches for the second kind.

> ⚠️ **Unreleased.** The design is complete; it has not been run end to end.
> See [Status](#status) before installing.

---

## The idea

When Claude writes forty lines of Dockerfile and you accept them without a
single follow-up question, that is evidence about you. Not proof — an expert
also doesn't ask — but evidence.

**What you don't scrutinise maps the edge of what you understand.** That signal
exists inside AI pair-programming transcripts and essentially nowhere else,
which is the reason this plugin can exist at all.

`lesson` reads for it, remembers across sessions, and when the same gap shows up
more than once, offers to explain that one thing from the beginning.

---

## How it works

**It watches.** When Claude finishes a turn, a small script counts. Every so
often — roughly a dozen turns, at least fifteen minutes apart — it starts a
separate Claude in the background to read that session's transcript. It runs
detached and silent. Your conversation is never touched.

Four signals, weakest to strongest:

| Signal | What it means |
|---|---|
| An error that surprised you | what you expected didn't happen |
| A question you asked | what you ask places you exactly |
| **Something you let Claude do without asking about it** | **the edge of your model — and nothing else can see it** |
| Something you handled yourself | this is how you move *up* |

**It remembers.** One file: `~/.claude/lesson/graph.json`. Dots are things you
can understand. Arrows mean *you need this one first*.

```json
{
  "id": "container-networking",
  "title": "How containers reach each other on a network",
  "also_called": ["localhost in docker", "service name", "compose networking"],
  "known": "unknown",
  "why": [
    { "date": "2026-08-04", "from": "delegated", "sure": "guessed",
      "note": "accepted a compose rewrite changing localhost to a service name, no follow-up" },
    { "date": "2026-08-19", "from": "error", "sure": "observed",
      "note": "spent 20 minutes on a container that couldn't be reached" }
  ]
}
```

Every claim records whether it **observed** that or **guessed** it, and which
session it came from. Nothing is asserted without evidence you can trace.

It's your file — plain text, in your home directory. Edit it. Delete things.
Tell it it's wrong; that is recorded as `self-corrected` and never argued with.

**It offers.** About one session in five, when a gap has appeared more than once:

```
Claude changed which Python your project uses. Want the two-minute version
of why that fixed the import error?
```

An offer, never a quiz. There is no wrong answer. "No" means it never asks again.

**It explains.** One lesson, one concept, as a self-contained HTML page. Before
writing it, the plugin walks the arrows backwards — anything you need first that
you don't have yet gets grounded *inside* the lesson, before the word is used.

That last rule is the whole point: **never build a complex term on another
complex term.**

---

## Install

```
/plugin marketplace add OussemaBenAmeur/lesson
/plugin install lesson@lesson
```

Then run `/lesson` once. Setup is a short conversation — under two minutes — and
nothing runs in the background until you've been through it.

To remove it: `/plugin uninstall lesson`, then delete `~/.claude/lesson/`.

---

## Commands

| Command | Does |
|---|---|
| `/lesson` | First time: setup, then your first lesson. After: what's waiting. |
| `/lesson graph` | Draw what you know as a picture you can click around |
| `/lesson <topic>` | Explain something you already know you're shaky on |
| `/lesson yes` | Accept the lesson currently being offered |

---

## What it costs

The background analysis is a real Claude process reading a real transcript, so
it is not free. It runs at most once per ~12 turns and no more often than every
15 minutes, and a quiet session writes nothing at all.

Budget and model are not yet configurable. Fixing that is a prerequisite for
release.

---

## Privacy

Everything stays on your machine. The plugin makes no network requests of its
own beyond the Claude Code process it spawns.

The graph holds **statements about understanding, and nothing else** — never
source code, file contents, credentials, or customer data. A note may quote a
short error message or a question you asked. If the extraction ever finds itself
copying, it is instructed to stop and describe instead.

---

## What it will not do

- **Test you.** Ever. Offers only.
- **Interrupt you mid-task.** Only when Claude hands control back.
- **Pile up.** One unread lesson at a time, maximum. A backlog turns a coach
  into a source of guilt.
- **Claim a gap it can't point at.** Every statement carries its evidence.

---

## Status

**Works, verified:** graph schema, graph viewer, the Stop hook — silent when not
onboarded, survives malformed input, raises an offer exactly once.

**Written, never run against a real transcript:** the extraction
(`analysis/watch.md`). This is the part that decides whether the whole idea
works. The open question is not whether it produces output — it is whether that
output is *true about a person*.

**Not started:** end-to-end install, evaluation of extraction accuracy, cost
controls.

Until the extraction is measured, treat everything here as a design, not a tool.

---

## Requirements

Claude Code, and Python 3 for the hook. No packages, no API key, no build step.

Other platforms are out of scope until this one is good.

## License

MIT
