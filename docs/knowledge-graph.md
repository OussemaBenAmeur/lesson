# Your knowledge graph

One file, stored at `~/.claude/lesson/graph.json`. It is the whole memory of
this plugin. There is nothing else.

It starts **empty**. There is no built-in list of concepts, because the things a
person can fail to understand are endless and any list we wrote would just be a
list of things we happened to think of.

---

## What's in it

**Dots** (nodes) — things you can understand. One dot per thing.

**Arrows** (edges) — "you need this one first."

That's all. A dot and an arrow.

---

## A dot

```json
{
  "id": "which-python-runs",
  "title": "Which Python your computer actually runs",
  "also_called": ["venv", "conda env", "site-packages", "pip installed to the wrong place"],
  "known": "can-use",
  "why": [
    { "date": "2026-03-04", "from": "error", "sure": "observed",
      "note": "import failed right after pip install said it worked",
      "where": { "session": "0f2a…", "at": "2026-03-04T11:22:09Z" } },
    { "date": "2026-04-19", "from": "delegated", "sure": "guessed",
      "note": "accepted a fix for this without asking what it did",
      "where": { "session": "9c41…", "at": "2026-04-19T16:03:51Z" } }
  ],
  "taught": null,
  "first_seen": "2026-03-04",
  "last_seen": "2026-04-19"
}
```

**`known`** — how well you understand it. Four steps:

| Value | Means |
|---|---|
| `unknown` | No idea it exists |
| `heard-of` | You'd recognise the word |
| `can-use` | You can make it work and guess right about what happens |
| `knows-why` | You understand why it behaves that way, and what breaks it |

**`why`** — the reasons it thinks that. Never write a `known` value without at
least one entry here. If you can't point to why, you don't know it.

`from` is where the reason came from:

| `from` | Means |
|---|---|
| `interview` | You said so at setup. Weakest — two real observations beat it. |
| `error` | Something broke in a way that showed the gap |
| `asked` | You asked a question that showed your level |
| `delegated` | You let Claude do it and didn't ask what it did |
| `handled` | You did it yourself, correctly, unprompted — this is how you go *up* |
| `self-corrected` | You told it "I know this." Always believed, never argued with. |

**`sure`** — did it *see* this, or *guess* it? Two values only:

| `sure` | Means |
|---|---|
| `observed` | It happened. An error appeared, you asked a question, you fixed it yourself. Quotable. |
| `guessed` | Inferred from context. Reasonable, possibly wrong. |

Every claim carries one. The rule is simple: **never write a claim you can't
tag.** A `guessed` claim is allowed to be wrong — that's what the tag is for —
but it must be visible as a guess so you can throw it out.

Nothing is ever `observed` unless there is a real moment behind it.

**`where`** — which session, and when. So any claim can be traced back to the
exact moment it came from. If the graph says something about you that seems
wrong, this is how you check.

**`also_called`** — other ways people say the same thing. This is what stops
"venv problem" and "conda problem" becoming two separate dots.

**`taught`** — the date and filename of the lesson, once one has been written.

---

## An arrow

```json
{ "from": "what-a-file-is", "to": "which-python-runs", "needed_first": true }
```

Read it as: *you need "what a file is" before "which Python runs" will make
sense.*

Arrows are how the plugin keeps its promise never to explain something using
words you don't have yet. Before writing a lesson it follows the arrows
backwards and checks you have the ground to stand on.

---

## How it grows

Every time the plugin notices something, it does this:

1. **Look at the graph first.** Is this the same thing as a dot that already
   exists? Check titles *and* `also_called`.
2. **If yes** — add to that dot's `why` list. Do not make a new dot.
3. **If no** — make a new dot, and add arrows to whatever it needs first.

Step 1 is the important one. Skip it and you get twenty dots that are all the
same gap wearing different words, none of them with enough evidence to act on.

When you make a new dot, ask: *could I explain this to someone who knows
nothing, using only dots that already exist?* If not, the missing pieces are
themselves dots, and they go in first.

A dot with no arrows pointing into it is claiming to be a starting point —
something you can explain to anyone from scratch. Very few things are. Be
suspicious of an empty one.

---

## What it's for

**The plugin reads it** to decide what to teach next: something you're weak on,
where you already have the ground it stands on.

**You read it.** It's your file, in your home directory, in plain text. Open it,
edit it, delete things. If it says you don't understand something and you do,
change it — that gets recorded as `self-corrected` and it's never argued with.

`/lesson graph` draws it as a picture you can click around.
