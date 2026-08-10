"""Lifecycle owner that normalizes, sequences, and persists provider events."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from spec_interview.conversation.models import (
    AudioChunk,
    CheckpointCreated,
    ConversationEvent,
    EventPayload,
    EventSource,
    SessionContext,
    SessionHandle,
    SessionSummary,
)
from spec_interview.conversation.provider import ConversationProvider
from spec_interview.sessions.store import SessionStore


class ConversationManager:
    """Own one stable interview session across provider connections."""

    def __init__(
        self,
        provider: ConversationProvider,
        store: SessionStore,
        session_id: UUID | None = None,
    ) -> None:
        self.provider = provider
        self.store = store
        self.session_id = session_id or uuid4()
        existing = self.store.read_events(self.session_id)
        self._sequence = existing[-1].sequence if existing else 0
        self._consumer_task: asyncio.Task[None] | None = None
        self._event_changed = asyncio.Condition()
        self._closed = False

    @property
    def last_sequence(self) -> int:
        return self._sequence

    async def start(self, metadata: dict[str, str] | None = None) -> SessionHandle:
        self._start_consumer()
        return await self.provider.start_session(
            SessionContext(
                session_id=self.session_id,
                provider=self.provider.name,
                metadata=metadata or {},
            )
        )

    async def resume(self) -> None:
        checkpoint = self.store.read_checkpoint(self.session_id)
        if checkpoint.provider != self.provider.name:
            raise ValueError(
                f"checkpoint requires provider {checkpoint.provider!r}, got {self.provider.name!r}"
            )
        self._start_consumer()
        await self.provider.restore(checkpoint)

    def _start_consumer(self) -> None:
        if self._consumer_task is not None:
            raise RuntimeError("event consumer already started")
        self._consumer_task = asyncio.create_task(self._consume_events())

    async def _consume_events(self) -> None:
        async for event in self.provider.events():
            await self._record(event.payload, event.source, event.timestamp)

    async def _record(
        self,
        payload: EventPayload,
        source: EventSource,
        timestamp: datetime | None = None,
    ) -> ConversationEvent:
        self._sequence += 1
        event = ConversationEvent(
            session_id=self.session_id,
            sequence=self._sequence,
            timestamp=timestamp or datetime.now(UTC),
            source=source,
            payload=payload,
        )
        self.store.append(event)
        async with self._event_changed:
            self._event_changed.notify_all()
        return event

    async def send_text(self, text: str) -> None:
        await self.provider.send_text(text)

    async def send_audio(self, chunk: AudioChunk) -> None:
        await self.provider.send_audio(chunk)

    async def interrupt(self) -> None:
        await self.provider.interrupt()

    async def wait_for_response(
        self, after_sequence: int, wait_seconds: float = 10.0
    ) -> ConversationEvent:
        terminal_types = {"response_completed", "response_interrupted", "provider_error"}

        async def find() -> ConversationEvent | None:
            return next(
                (
                    event
                    for event in self.store.read_events(self.session_id)
                    if event.sequence > after_sequence and event.payload.type in terminal_types
                ),
                None,
            )

        async with asyncio.timeout(wait_seconds):
            while True:
                event = await find()
                if event is not None:
                    return event
                async with self._event_changed:
                    await self._event_changed.wait()

    async def create_checkpoint(self) -> None:
        checkpoint = await self.provider.checkpoint(self._sequence)
        self.store.write_checkpoint(checkpoint)
        await self._record(
            CheckpointCreated(last_sequence=checkpoint.last_sequence),
            EventSource.MANAGER,
        )

    async def close(self) -> SessionSummary:
        if self._closed:
            raise RuntimeError("manager already closed")
        provider_summary = await self.provider.close()
        if self._consumer_task:
            await self._consumer_task
        self._closed = True
        self.store.write_views(self.session_id)
        events = self.store.read_events(self.session_id)
        return provider_summary.model_copy(
            update={
                "event_count": len(events),
                "transcript_lines": len(self.store.transcript_lines(events)),
            }
        )

    async def cancel(self) -> None:
        """Best-effort orderly shutdown used by CLI cancellation handling."""
        if not self._closed:
            await self.create_checkpoint()
            await self.close()
