# lesson — AI Context

A Claude Code plugin that models **the learner**, not the session.

It watches how someone works, notices what they keep working around without
ever learning, and writes them a proper lesson on one of those things — built
from the ground up, never stacking jargon on jargon.

> Rewritten from scratch on 2026-08-16. The previous design (v0.3, tag
> `v0.3-graph-era`) built a per-session knowledge graph from tool-call logs.
> It could not work: nothing in it ever created a `concept` or `hypothesis`
> node, so root-cause and misconception detection always returned nothing, and
> the shipping behaviour was an LLM reading a truncated tool log. Do not
> reintroduce per-session graphs, TF-IDF significance scoring, or `arc.jsonl`.

## The model

Three layers, kept separate:

**One knowledge graph is the entire memory.** `~/.claude/lesson/graph.json`.
Dots are things a person can understand; arrows mean "you need this first".
Every claim carries evidence, an `observed`/`guessed` tag, and provenance back
to the session it came from. Schema: `docs/knowledge-graph.md`.

**There is no fixed concept list.** Concepts are infinite; any list we shipped
would just be a list of things we thought of. The graph starts empty and grows
via the **match-first rule**: before adding a node, read the existing nodes
(titles *and* `also_called`) and reuse one if it fits. Skip that step and the
same gap becomes five one-off nodes that never accumulate into anything.

**Global and always-on.** Not per-project. There is no session start/stop
ritual, no `active-session` marker, no `.claude/lessons/` inside target repos.
All state lives in `~/.claude/lesson/`.

**Depth, not binary.** Every concept sits at `unknown` → `aware` → `working` →
`mechanistic`. A lesson moves one concept up exactly one rung. This is how the
same short concept list serves a beginner and a senior engineer.

## Why the concept list exists

So the same gap gets the same name every time. Free-form naming produces
"python virtual environments", "conda activation", and "pip inside Dockerfile"
as three separate entries with a count of one each — when it is one gap hit
three times, and no lesson ever fires.

The list **grows with a match-first rule**: before recording a gap, check the
existing list and reuse a name if one fits; only append when nothing does.
Never hand-author a large list upfront — that is the over-engineering that
killed v0.3.

## Evidence signals, weakest to strongest

1. **Errors** — a bug exposing a wrong belief. Noisy; reveals typos as often as gaps.
2. **Questions asked** — what someone asks reveals their level.
3. **Delegation** — *the important one.* What the user does not scrutinise maps
   their competence boundary. Accepting forty lines of Dockerfile without a
   follow-up is evidence they don't model containers. This signal exists only
   inside AI pair-programming transcripts and nothing else can see it.
4. **Absence** — what a competent practitioner would have done and they didn't
   (never checked class balance, never set a seed). Needs per-domain notions of
   competence; one domain first, after the rest works.

## Files

| Path | Purpose |
|---|---|
| `commands/lesson.md` | `/lesson` — onboarding interview, first lesson, or status |
| `analysis/watch.md` | Prompt the background `claude --bare -p` runs to read a transcript and update the graph |
| `hooks/on_stop.py` | Stop hook: counts turns, spawns the background analysis, raises a pending offer once |
| `viewer/graph.html` | Self-contained graph viewer; `/lesson graph` injects data at `/*__GRAPH_DATA__*/` |
| `docs/knowledge-graph.md` | The graph schema, in plain language |
| `pedagogy/lesson-style.md` | House writing style; derived from the `make-lesson` skill |
| `.claude-plugin/plugin.json` | Plugin manifest |

`~/.claude/skills/make-lesson/SKILL.md` is a **separate, standalone skill that
must stay intact.** `pedagogy/lesson-style.md` is the same pedagogy adapted for
learner-model-driven lessons. Keep them consistent; don't delete either.

## Rules

- **No per-session graph.** The session is a sensor reading; the learner model
  is the state. A session that yields no lesson still moved the model.
- **Read transcripts, not a hook log.** Claude Code already writes every
  session to `~/.claude/projects/<munged-cwd>/<id>.jsonl` with untruncated tool
  results plus user prompts. A hook that logs tool calls captures strictly less.
  (Thinking blocks are stripped to signatures — narration survives.)
- **Never touch the main conversation's context.** Extraction runs once at
  session end, out of band, never per tool call.
- **One pending unread lesson at a time.** A backlog turns a coach into guilt.
- **One lesson teaches one concept**, from the learner's depth to the next rung.
- **Never build a term on an ungrounded term.** Walk `requires` first; ground
  anything the learner isn't `working` on yet, inside the lesson.
- **The learner file belongs to the user** — human-readable, hand-editable. "I
  know this" is always accepted without argument.
- **Never claim a gap without evidence you can point to.**
- Claude Code only. Other platforms are out of scope until this works.

## How watching works

The Stop hook fires when Claude hands control back. It is deliberately dumb: it
counts turns, and after ~12 turns / 15 minutes spawns

```
claude --bare -p "<analysis/watch.md + paths>"
```

detached, in the background. **`--bare` is load-bearing** — it skips hooks, so
the analysis process doesn't fire this same hook and recurse forever.

That background process reads the transcript, updates the graph, and sometimes
writes `~/.claude/lesson/pending-lesson.json`. The next Stop hook raises it
**once** (`offered_at` guarantees never twice) as an offer, never a quiz. The
file survives until answered, because `/lesson yes` needs to know which node.

Hook output is *context for Claude*, not text shown to the user — so it
instructs Claude what to say and what to do with each answer.

## Status

Working and tested: graph schema, graph viewer (verified in a browser), Stop
hook (silent when not onboarded, survives garbage input, raises an offer exactly
once).

Written but **never run against a real transcript**: `analysis/watch.md`. This
is the risky part — the open question is whether it produces statements that are
actually *true* about a person. Validate that before building anything on top.

Never done: the plugin has not been installed into Claude Code or run end to
end. `README.md` still describes v0.3.
