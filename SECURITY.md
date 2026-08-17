# Security and privacy

## What this plugin touches

`lesson` reads your Claude Code session transcripts and keeps a file describing
what you appear to understand. That is a real privacy surface, so here is
exactly what happens.

**Reads:**

- `~/.claude/projects/<project>/<session>.jsonl` — the transcripts Claude Code
  already writes. These contain everything you typed, everything Claude said,
  and the full input and output of every command run.

**Writes:**

- `~/.claude/lesson/graph.json` — the knowledge graph. Statements about what you
  understand, each with the evidence behind it.
- `~/.claude/lesson/lessons/*.html` — generated lessons.
- `~/.claude/lesson/state.json`, `pending-lesson.json`, `analysis.lock` —
  bookkeeping.

**Runs:**

- `claude --bare -p …` as a detached background process, roughly once every 12
  turns. It uses your existing Claude Code login and consumes your usage. It
  runs with `--bare`, which skips hooks, so it cannot trigger itself.

**Never:**

- Makes network requests of its own
- Reads credentials, environment variables, or secret files
- Sends anything off your machine
- Modifies your code or runs your tests

## Things worth knowing

**Your transcripts contain whatever you put in them.** If you have pasted a
secret into a Claude Code session, it is in that transcript, and the background
analysis reads it. The analysis is instructed to extract only statements about
your understanding, and never to copy code, keys, or file contents into the
graph — but that is an instruction to a model, not a guarantee. Treat
`graph.json` as roughly as sensitive as your transcripts.

**The graph is a file about you.** It is plain text in your home directory and
it is yours. Open it, edit it, delete entries, delete the whole thing. Telling
the plugin "I know this" is always accepted and never quietly reverted.

**Everything is local.** Deleting `~/.claude/lesson/` removes every trace.

## Reporting a problem

Please don't open a public issue for a security bug.

Email: oussemabenameur9@gmail.com — include what you found, how to reproduce it,
and what you think the impact is. You'll get a reply within 72 hours.
