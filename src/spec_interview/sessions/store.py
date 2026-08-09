"""Append-only session persistence and deterministic derived views."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from uuid import UUID

from pydantic import TypeAdapter

from spec_interview.conversation.models import (
    ConversationCheckpoint,
    ConversationEvent,
    ResponseCompleted,
    ResponseInterrupted,
    TranscriptFinalized,
)

_EVENT_ADAPTER = TypeAdapter(ConversationEvent)


class SessionStore:
    """Filesystem store with JSONL as the source of truth."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def session_dir(self, session_id: UUID) -> Path:
        return self.root / str(session_id)

    def events_path(self, session_id: UUID) -> Path:
        return self.session_dir(session_id) / "events.jsonl"

    def checkpoint_path(self, session_id: UUID) -> Path:
        return self.session_dir(session_id) / "checkpoint.json"

    def append(self, event: ConversationEvent) -> None:
        directory = self.session_dir(event.session_id)
        directory.mkdir(parents=True, exist_ok=True)
        with self.events_path(event.session_id).open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def read_events(self, session_id: UUID) -> list[ConversationEvent]:
        path = self.events_path(session_id)
        if not path.exists():
            return []
        events: list[ConversationEvent] = []
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                events.append(_EVENT_ADAPTER.validate_json(line))
            except ValueError:
                if index == len(lines) - 1:
                    break
                raise
        return events

    def write_checkpoint(self, checkpoint: ConversationCheckpoint) -> None:
        directory = self.session_dir(checkpoint.session_id)
        directory.mkdir(parents=True, exist_ok=True)
        destination = self.checkpoint_path(checkpoint.session_id)
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(checkpoint.model_dump_json(indent=2), encoding="utf-8")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        temporary.replace(destination)

    def read_checkpoint(self, session_id: UUID) -> ConversationCheckpoint:
        return ConversationCheckpoint.model_validate_json(
            self.checkpoint_path(session_id).read_text(encoding="utf-8")
        )

    def list_sessions(self) -> list[UUID]:
        if not self.root.exists():
            return []
        sessions: list[UUID] = []
        for path in self.root.iterdir():
            if path.is_dir():
                try:
                    sessions.append(UUID(path.name))
                except ValueError:
                    continue
        return sorted(
            sessions, key=lambda value: self.session_dir(value).stat().st_mtime, reverse=True
        )

    @staticmethod
    def transcript_lines(events: Iterable[ConversationEvent]) -> list[str]:
        lines: list[str] = []
        for event in events:
            payload = event.payload
            if isinstance(payload, TranscriptFinalized):
                label = "You" if payload.role == "user" else "Assistant"
                lines.append(f"{label}: {payload.text}")
            elif isinstance(payload, ResponseCompleted):
                lines.append(f"Assistant: {payload.text}")
            elif isinstance(payload, ResponseInterrupted):
                lines.append(f"Assistant [interrupted]: {payload.text}")
        return lines

    def render_transcript(self, session_id: UUID) -> str:
        return "\n".join(self.transcript_lines(self.read_events(session_id))) + "\n"

    def render_summary(self, session_id: UUID) -> str:
        events = self.read_events(session_id)
        provider = "unknown"
        interrupted = 0
        completed = 0
        for event in events:
            if event.payload.type == "session_started":
                provider = event.payload.provider
            elif isinstance(event.payload, ResponseInterrupted):
                interrupted += 1
            elif isinstance(event.payload, ResponseCompleted):
                completed += 1
        transcript = self.transcript_lines(events)
        body = "\n".join(f"> {line}" for line in transcript) or "> No transcript recorded."
        return (
            f"# Spec Interview Session {session_id}\n\n"
            f"- Provider: `{provider}`\n"
            f"- Events: {len(events)}\n"
            f"- Completed responses: {completed}\n"
            f"- Interrupted responses: {interrupted}\n\n"
            f"## Transcript\n\n{body}\n"
        )

    def write_views(self, session_id: UUID) -> tuple[Path, Path]:
        directory = self.session_dir(session_id)
        directory.mkdir(parents=True, exist_ok=True)
        transcript = directory / "transcript.txt"
        summary = directory / "summary.md"
        transcript.write_text(self.render_transcript(session_id), encoding="utf-8")
        summary.write_text(self.render_summary(session_id), encoding="utf-8")
        return transcript, summary
