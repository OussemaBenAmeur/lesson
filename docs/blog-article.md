# I Built `/lesson` Because AI Agents Are Quietly Killing My Ability to Learn

I'm a software engineering student. And I have a confession: most of the problems I've "solved" this year, I didn't really solve. An agent did. I pasted the error, I described the goal, and the code worked. The assignment was done, the feature shipped, the deadline met — and somewhere in the middle of that, the part where I actually learn something got skipped.

That used to be the whole point of getting stuck. You'd hit a wall, go read a docs page, form a wrong theory, try it, fail, read another page, and eventually the concept would click — and the reason it clicked was that you'd earned the understanding through every wrong turn along the way.

Agents compress all of that into a two-line fix. The wall is gone. And so is the learning that lived on the other side of it.

This isn't an anti-AI piece. I love agents. I use them constantly. The problem is that the teaching signal — the errors, the wrong assumptions, the turning point where something finally made sense — is *still there in every session*, it just evaporates the moment the session ends. Nobody is reading it. Nothing is learning from it. Including me.

So I built a plugin to fix that.

## What `/lesson` actually does

```text
/lesson react useEffect infinite loop
# work normally, get stuck, get unstuck
/lesson-done
```

That's it. The first command turns on tracking. You work with your agent like you always would — reading files, running commands, editing code, hitting errors, recovering from them. `/lesson-done` turns the whole arc into a real lesson: the concept you were actually missing, explained from first principles, using *your* errors and *your* commands as examples, with diagrams, a misconception callout, a fix explanation, and a quiz.

It doesn't invent a generic tutorial. It teaches you the thing the session was secretly about.

## The insight: a working session is better teaching material than any tutorial

A generic tutorial starts from an abstract topic and invents an explanation. The examples are canned. The errors are fake. The "common mistakes" section is a guess.

A real debugging session contains the exact opposite: the commands you actually ran, the output you actually misread, the belief you actually held, and the observation that actually changed your mind. That is textbook-grade pedagogical signal. It's just unstructured and thrown away.

The whole plugin is a pipeline for catching that signal before it disappears.

## How it captures the session without slowing anything down

The core constraint was: the capture layer cannot be smart, or it becomes a liability. If the thing listening to every tool call has to call an LLM, that's a latency and failure mode attached to every single action you take.

So the `PostToolUse` hook (`hooks/post_tool_use.py`) is deliberately dumb. It's a Python script that:

1. Checks if there's an active session (if not, exits in under a millisecond)
2. Appends a compact JSON line to `arc.jsonl`
3. Increments a counter
4. Every 25 events, nudges the main agent: "time to compress"

No LLM calls. No network. If anything goes wrong, it exits 0 silently. A crash in a hook should never interfere with your actual work.

## The hard part: picking what matters

A 45-minute debugging session generates hundreds of events. Most of them are noise — file reads for context, exploratory navigation, command retries with tiny variations. A handful of them are the turning points where the session actually moved forward.

The algorithmic compressor (`lesson/nlp/scorer.py`) scores every event with a weighted composite:

```text
score = 0.40 × TF-IDF novelty
      + 0.35 × error signal
      + 0.15 × edit signal
      + 0.10 × version signal
```

**TF-IDF novelty** catches events whose vocabulary is unusual compared to the batch — an event saying `ModuleNotFoundError: numpy` scores higher than one saying "reading file" because the error word is rarer and more information-dense. **Error signal** directly captures failures. **Edit signal** captures deliberate decisions (you edited a file, that was intentional). **Version signal** catches version mismatches and path discoveries, which are often the hidden cause of a problem.

Events above threshold 0.25 (max 12 per batch) get promoted. Everything else is archived as context and ignored. This is how the plugin keeps the main agent's context window lean — it never sees the hundreds of raw events, only the compressed structure.

## The graph: causality, not sequence

Here's the part I'm proudest of.

Every promoted event becomes a typed node in `session_graph.json`:

| Type | What it represents |
|---|---|
| `goal` | What you were trying to accomplish |
| `observation` | A factual finding — error, output, file state |
| `hypothesis` | A belief or assumption (often wrong) |
| `attempt` | A deliberate action — edit, command, fix |
| `concept` | A technical concept that became relevant |
| `resolution` | The approach that worked |

And nodes are connected by *typed* edges — not "and then." The edge types are `motivated`, `produced`, `contradicted`, `seemed_to_confirm`, `revealed`, `assumed_about`, `involves`, `enabled`, `achieves`. Each one encodes *why* one node led to another. Not that it happened after — that it happened *because*.

This matters because "and then" is what generic tutorials give you. "And because" is what actually teaches.

Once the graph exists, `lesson/graph/algorithms.py` runs **betweenness centrality** on the concept nodes. Betweenness measures how many shortest paths between other nodes pass through a given node — in other words, which concept everything else funnels through. That node gets flagged `root_cause: true`. The entire debugging arc depended on it, whether you knew it at the time or not.

That's how the lesson knows what the session was *really* about, even when you didn't.

## Silent, deterministic compression

Compression runs one way everywhere: `EventGraphBuilder` does the whole pipeline in **~50ms with zero tokens** — TF-IDF scoring, entity extraction via regex, node classification, optional semantic deduplication (sentence-transformers cosine similarity > 0.85 = same node), typed edge inference, betweenness centrality. On Claude Code the PostToolUse hook spawns `lesson compress` as a detached subprocess every 25 events so you never see it happen; outside Claude Code the same command runs from the terminal or is invoked inline at `/lesson-done` time.

Deterministic. Inspectable. Runs anywhere. Same graph on every platform — Claude Code, Cursor, Codex, Gemini, Copilot, OpenCode, OpenClaw, Droid, Trae, Antigravity. No LLM-subagent fork, no quality drift between hosts, no tokens burned on bookkeeping.

## What the generated lesson looks like

`commands/lesson-done.md` reads the graph (not the raw events — they're too noisy) and fills `templates/lesson.md.tmpl`. Every lesson has:

- The real goal and the real breakdown moment, in plain language
- A **Foundations** section built bottom-up — every prerequisite concept explained from scratch, calibrated to the depth hint you gave in `/lesson [notes]`
- The core concept in 3–6 paragraphs, with a Mermaid concept diagram
- **Why this bit you specifically** — connecting your actual wrong assumption to the concept
- A Mermaid flowchart of your real debugging path, auto-generated from the graph
- The verbatim fix — the command or code that actually worked
- A quiz with visible answers (no hidden spoilers, I hate that pattern)

For concepts that need external grounding (specific version numbers, third-party library internals, distribution-specific behavior), it uses WebSearch + WebFetch and cites real sources. For fundamentals (how an event loop works, what a closure is), it explains from general knowledge. One of the command's rules is *grounded or nothing* — if the session is too thin or the concept can't be properly supported, it refuses to write rather than producing a weak lesson.

## Growing as you grow

`~/.claude/lessons/profile.json` is a global learner profile that persists across every project and every platform:

```json
{
  "misconceptions": [
    { "concept": "asyncio event loop — coroutine scheduling",
      "count": 2, "last_seen": "2026-04-18" }
  ],
  "learned_concepts": [...],
  "aggregate_tokens": { "total_estimated": 187000 }
}
```

Every time you finish a lesson, your wrong mental models get logged. When the same misconception shows up in a new session — maybe in a totally different project — the next lesson opens with a callout: *"You've encountered this pattern before. Here's why it keeps appearing."*

That's the feature I wanted most. An agent never remembers that you made this same mistake three months ago. The profile does.

Then `/lesson-map` goes further: it reads every lesson you've ever generated and builds an HTML concept graph across them. Concepts that co-occurred in the same session become linked nodes. Suddenly you can see that the asyncio lesson from March and the Linux kernel lesson from April are connected through a shared node about *scheduling* — something you'd never have spotted reading them one at a time.

## You stay in control

The `[notes]` on `/lesson` are the customization knob. `/lesson react stale closure I know hooks basics, focus on the bug pattern` tells the generator to skip the intro and go deep. `/lesson linux driver mismatch explain from first principles` goes the other way. `/regenerate make the foundations deeper and the quiz harder` rewrites the last lesson with new direction.

The plugin adapts to where you are, not where someone assumed you'd be.

## Why any of this matters

If you're a student right now, you've probably noticed the same thing I have: agents are so good that they make the struggle optional. And the struggle is where learning lived.

I don't want to go back to pre-agent development. That's not the argument. The argument is that the teaching signal in every debugging session is still there — agents didn't delete it, they just made it easier to ignore. A plugin that captures it, structures it as a causal graph, and turns it into a grounded lesson with your own errors as examples is, at minimum, a way to not let every session leave me exactly as dumb as I started it.

You're not supposed to hand learning off to the agent. But you can let the agent help you build the textbook version of what you just survived.

That's what `/lesson` is trying to be.

---

*Plugin source: [github.com/OussemaBenAmeur/lesson](https://github.com/OussemaBenAmeur/lesson). MIT-licensed. Installs on 10 AI coding platforms via one script. Runs locally, no data leaves your machine.*
