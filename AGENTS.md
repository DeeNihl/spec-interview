# AGENTS.md

## Purpose

Build `spec-interview` as a provider-neutral conversational runtime. The authoritative scope
is `docs/START-HERE.md`. Do not turn this repository into the larger TMNT or Protocol Manager
framework.

## Invariants

- Keep provider SDK types and raw events inside `providers/`.
- Persist only normalized `ConversationEvent` records.
- Treat JSONL as authoritative; transcript and summary files are regenerated views.
- Keep the stable interview session ID distinct from provider connection IDs.
- Report capabilities truthfully. Never silently emulate an unsupported provider feature.
- The mock test suite must run without AWS, audio, browser, or model dependencies.
- Preserve interrupted response text and cancellation history.
- Never store credentials or machine-specific paths.

## Engineering conventions

- Python 3.12+, Pydantic v2, async-first lifecycle.
- Strict mypy, Ruff, and pytest are required before handoff.
- Prefer small typed models and exhaustive event translation.
- Optional integrations belong behind package extras.
- Add fixtures for provider protocol shapes; do not leak those shapes into public models.
- Update README status claims whenever validation boundaries move.

## Definition of done

Run:

```bash
ruff check .
ruff format --check .
mypy
pytest
docker build -t spec-interview:dev .
```

Then demonstrate one completed mock session, one interrupted session, and checkpoint resume.
Separate tested behavior from Mac- and AWS-dependent validation in the final report.

