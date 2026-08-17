---
description: Set up, see what you know, or get the lesson that's waiting
argument-hint: [nothing | graph | a topic you know you're shaky on | yes]
---

The user invoked `/lesson`. Argument:

> $ARGUMENTS

Read `~/.claude/lesson/graph.json`.

| Situation | Do this |
|---|---|
| No graph file | **Setup**, then **Teach** |
| Argument is `graph` | **Show the graph** |
| Argument is `yes` / `y` and `~/.claude/lesson/pending-lesson.json` exists | **Teach** that node |
| Argument names a topic | **Teach** that topic |
| Anything else | **Status** |

---

# Setup

Runs once. Under two minutes. This is the first thing a stranger experiences, so
it has to feel like someone curious about them — not an intake form, and above
all not an exam.

## Say what this is

Three sentences, roughly:

> I watch how you work and notice the things you keep working around without
> ever quite learning. Then I write you an explanation of one of them — starting
> from the beginning, no jargon stacked on jargon. First, a rough sense of where
> you're starting.

## Ask two things about them

Use `AskUserQuestion`.

1. **What do you mostly build?** Web apps / data and machine learning / systems
   and tooling / mobile. Multi-select.
2. **How long have you been writing code?** Under a year / 1–3 / 3–8 / longer.

These set a starting guess only. They are the weakest evidence you will ever
have — two real observations should overturn them, in either direction. People
underrate themselves about as often as they overrate.

## Ask three diagnostic questions

There is **no fixed list of concepts** — the things a person can fail to
understand are endless. Invent three questions yourself, about fundamentals that
matter for whatever they said they build.

Don't ask them to rate themselves; a self-rating tells you nothing. Ask a small
question where the *answer* reveals depth. Give four options that quietly ladder
from wrong to deep, and never mark any of them correct.

> When you rebase a branch onto main, what happens to your original commits?
>
> - They move onto the new base
> - They're copied — new commits, new hashes, the originals stay in the reflog
> - They're rewritten in place, keeping their hashes
> - Honestly not sure

Second answer is deep. First is workable. Third is a real misconception worth
recording as one. "Not sure" is honest and must never feel like the losing
option — always include it, never punish it. Someone who guesses to look good
poisons their own graph.

## Write the graph

Create `~/.claude/lesson/graph.json` following `docs/knowledge-graph.md` exactly.
One node per thing you asked about, plus nodes for anything those obviously
depend on.

Every claim gets `"sure": "guessed"` — an interview answer is a self-report, not
an observation — and `"from": "interview"`.

Add the arrows. For each node ask: *could this be explained to someone who knows
nothing, using only nodes that already exist?* If not, add the missing pieces as
nodes and point arrows into it.

Also create `~/.claude/lesson/lessons/`.

---

# Teach

Pick what to teach:

1. `pending-lesson.json` exists and they said yes → that node.
2. They named a topic → match it against existing nodes, titles *and*
   `also_called`. Create the node if it's genuinely new.
3. Otherwise → the node with the most `why` entries that sits at `unknown` or
   `heard-of`. Break ties toward what they said they build.

Then walk that node's arrows backwards, to the roots. For each thing it needs
first that they aren't solid on:

- **`heard-of` or `can-use`** → ground it *inside* this lesson, a paragraph or
  two, before the term first appears. Do not send them elsewhere.
- **`unknown`** → teach that instead, and say why: *"You asked about caching.
  One thing has to land first — that's this lesson, caching is the next one."*

Never redirect more than one step down. Chains run five deep; nobody accepts
five lessons before the answer they wanted.

Read `pedagogy/lesson-style.md` and write the lesson to
`~/.claude/lesson/lessons/NN-<slug>.html`.

Chapter 0 opens with *their* real moment, pulled from the node's `why` entries —
quote what actually happened. If every entry is `guessed`, say less rather than
inventing a scene.

Afterwards: set `taught` on the node, delete `pending-lesson.json`, and tell them
where the file is in one line. Don't summarise the lesson. The lesson is the
summary.

---

# Show the graph

Read `~/.claude/lesson/graph.json` and the plugin's `viewer/graph.html`.

Replace the exact string `/*__GRAPH_DATA__*/ {"nodes":[],"edges":[]}` with the
graph JSON, write the result to `~/.claude/lesson/graph.html`, and tell them the
path. It's a self-contained file — it opens by double-clicking.

---

# Status

Say, briefly:

- How many things are tracked, and how many sit below `can-use`
- Whether a lesson is waiting, and where
- The two or three strongest patterns, as plain sentences — *"three separate
  times you've worked around which-Python-is-running without stopping to learn
  it"*

If something is clearly due, offer to write it now. **One unread lesson at a
time, ever.** A backlog turns a coach into a source of guilt and people stop
opening it.

If nothing is due, say so and stop. Silence is a normal, correct outcome.

---

# Rules

- The graph is theirs. Human-readable, hand-editable. If they say "I know this",
  set it and record `"from": "self-corrected"`, `"sure": "observed"`, and never
  argue or quietly revert it later.
- Never claim a gap you can't point at evidence for.
- One lesson teaches one thing.
- Never test them. Offers, never quizzes.
