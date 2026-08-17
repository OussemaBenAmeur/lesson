# Lesson writing spec

The house style for every lesson this plugin produces. Derived from the
`make-lesson` skill (`~/.claude/skills/make-lesson/SKILL.md`), which remains a
standalone command for writing a lesson on a topic you name. This file is the
same pedagogy, adapted for lessons that come from a learner model instead of a
typed-in topic.

**The one difference that matters:** `make-lesson` is told a topic. Here, the
concept comes from the learner model and Chapter 0's scenario comes from the
learner's real evidence. Everything below the opening is identical.

---

## Output

A single self-contained HTML file at `~/.claude/lesson/lessons/NN-<concept-slug>.html`.
All CSS and JS inline. It must work when double-clicked, offline. No CDN
dependencies for functionality.

Use the visual language specified in `make-lesson`: `Newsreader` serif body at
17px/1.85 (the serif is non-negotiable — it signals essay, not documentation),
`Inter` for UI and labels, `JetBrains Mono` for code. Cream ground `#fffef9`,
ink `#1a1917`, accent `#d4622a`. Fixed left sidebar with JS chapter navigation,
one `<article class="chapter">` visible at a time.

---

## Structure

### Chapter 0 — Why You Actually Need This

The most important section, and the only one that is personal.

Open with **the learner's own moment**, taken from their evidence:

> Three weeks ago you ran `pip install numpy`, watched it succeed, ran your
> script, and got `ModuleNotFoundError: No module named 'numpy'`. You fixed it
> by switching to `pip3`. It worked, and you moved on.
>
> It'll happen again. Here's the thing you actually needed to know.

Do not fabricate the moment. Use what the evidence records. If the evidence is
thin, say what you know and no more — a vague-but-true opening beats an
invented-but-vivid one.

Then raise **2–4 numbered questions** the lesson will answer. These are the
reading contract; resolve them in order and reference back when you do.

Never open with a definition, a generic importance claim, or an interview
framing.

### Chapters 1–N — The concept

Narrative, not a list of definitions. For each step:

1. What happens (the story)
2. The mechanism behind it (the explanation)
3. A real name, number, or path that grounds it
4. A way to observe it — a command in a `<div class="note">`, or a live
   `<div class="demo">`

### Final chapter — Mental model transfer

Not a summary. Name what the reader now *sees* that they couldn't before:

> The next time an import fails right after a successful install, I hope you
> don't see a broken package. I hope you see a specific question: which
> interpreter ran, and which one did pip write to? Those are two different
> programs, and now you know how to ask each of them.

Then 5–7 numbered **Key Things to Remember**, each standing alone out of
context, and a short **What to Study Next** — drawn from the concepts that list
this one in their `requires`, since those are literally what it unlocks.

---

## Depth targeting

The learner model records a depth per concept. Teach from where they are to the
next rung, and no further:

| Current | Target | What the lesson does |
|---|---|---|
| `unknown` | `aware` | Establish that the thing exists and name it |
| `aware` | `working` | Make them able to use it and predict the ordinary outcome |
| `working` | `mechanistic` | Explain *why*, and what breaks at the edges |

**Depth controls how far *up* the lesson goes. It never licenses skipping the
ground.** A `working → mechanistic` lesson goes further, but it still defines
its terms — it does not get to assume vocabulary because the reader is further
along. Our reader is someone who cannot learn from an explanation that assumes
things; that is true of them at every depth, and it does not stop being true
because they've reached `working`.

Concretely: a lesson may be *shorter* at higher depths because there's less new
ground to lay, but there is no rung at which an undefined term becomes
acceptable.

---

## Non-negotiables

**Every abbreviation expanded on first use.** `DNS (Domain Name System)`, then
`DNS` thereafter. Every lesson is read independently.

**No floating abstractions.** Every abstract idea grounded in something real —
a file on disk, a running process, a command you can type. Not "a resolver
handles the query" but "a resolver is a server, a real machine; when you set
8.8.8.8 you're sending your questions to a specific box in a Google datacenter."

**No term before its prerequisite.** This is the rule the learner asked for
above all others: never build a complex term on another complex term. Walk the
concept's `requires` chain first — anything the learner isn't `working` on yet
gets grounded inside this lesson before it's used.

**Real names and numbers.** "Over 1,500 root server instances" not "many
servers."

**Use "you" throughout.** The reader is the protagonist.

**Show up as a co-discoverer.** Sparingly, at moments of genuine surprise: "I
always assumed the shell handled shebang lines. It doesn't — the kernel does."

**Model amazement without announcing it.** Never "Interestingly," "Fun fact,"
or "Notably." Drop the surprising thing cold and keep moving.

---

## Anti-patterns

- Opening with a definition
- "This is fundamental to modern software"
- Motivating with interviews
- Unexpanded abbreviations
- Announcing the spicy bits
- Ending with a bullet summary instead of a mental model transfer
- Teaching two concepts because both looked relevant — one lesson, one concept
