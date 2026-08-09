"""Shared queue mechanics for provider adapters."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

from spec_interview.conversation.models import ConversationEvent, EventPayload, EventSource


class QueueEventMixin:
    _queue: asyncio.Queue[ConversationEvent | None]
    _session_id: UUID | None

    def _init_queue(self) -> None:
        self._queue = asyncio.Queue()
        self._session_id = None

    async def _emit(
        self, payload: EventPayload, source: EventSource = EventSource.PROVIDER
    ) -> None:
        if self._session_id is None:
            raise RuntimeError("provider session has not started")
        await self._queue.put(
            ConversationEvent(
                session_id=self._session_id,
                sequence=0,
                timestamp=datetime.now(UTC),
                source=source,
                payload=payload,
            )
        )

    async def _finish_events(self) -> None:
        await self._queue.put(None)

    async def _event_iterator(self) -> AsyncIterator[ConversationEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            yield event
