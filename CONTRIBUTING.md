# Contributing to `lesson`

Thanks for taking the time to help. This doc is deliberately short: everything you need to make a good-faith contribution, nothing more.

## Dev setup

```bash
git clone https://github.com/OussemaBenAmeur/lesson.git
cd lesson
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The `dev` extra pulls in `pytest`, `pytest-cov`, and `hypothesis`. Semantic-dedup work also needs `pip install -e ".[nlp]"` (heavier — `sentence-transformers`).

## Running the suite

```bash
pytest                          # fast path
pytest --cov=lesson             # with coverage
pytest tests/unit               # unit only
pytest tests/integration        # end-to-end
```

The suite must stay green on Python 3.10, 3.11, and 3.12. CI enforces this matrix on every push and pull request.

## What good changes look like

- **Bug fix:** reproduce in a failing test first, then fix.
- **New feature:** open an issue to align on scope before you code — feature creep is the biggest threat to this project's clarity.
- **Docs:** keep them truthful against the shipped code. If behavior changed, the doc changes in the same PR.
- **Refactors:** welcome, but keep them surgical. Don't renumber node IDs in the schema, don't break `arc.jsonl`/`session_graph.json` compatibility, don't turn deterministic code into LLM calls.

## Non-negotiables

1. Hook scripts (`hooks/post_tool_use.py`, `hooks/stop.py`) must **never crash** — they exit 0 on any exception. They also must never block the user's main conversation or call an LLM.
2. `EventGraphBuilder` stays deterministic — no randomness, no API calls.
3. Node IDs in `session_graph.json` are stable forever. You may only append new ones.
4. `scripts/render_pdf.py` must never fail the build — it always exits 0.

## Release process

A release is a version bump in three files plus a CHANGELOG entry:

1. Bump `version` in `pyproject.toml`
2. Bump `__version__` in `lesson/__init__.py`
3. Bump `version` in `.claude-plugin/plugin.json`
4. Add a `## [X.Y.Z] — YYYY-MM-DD` section to `CHANGELOG.md` following Keep a Changelog
5. Tag the commit (`git tag -a vX.Y.Z -m "..."`) and push

## Code of conduct

Be kind. Assume good faith. Critique code, not people. If something is confusing, it's a doc bug, not a you bug.
