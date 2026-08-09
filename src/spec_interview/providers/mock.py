"""Deterministic provider used to prove the public contract."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import suppress
from uuid import uuid4

from spec_interview.conversation.models import (
    AudioChunk,
    ConversationCapabilities,
    ConversationCheckpoint,
    ConversationEvent,
    ConversationState,
    ProviderStatus,
    ResponseCompleted,
    ResponseDelta,
    ResponseInterrupted,
    ResponseStarted,
    SessionContext,
    SessionHandle,
    SessionResumed,
    SessionStarted,
    SessionStateChanged,
    SessionStopped,
    SessionSummary,
    ToolResult,
    TranscriptFinalized,
)
from spec_interview.conversation.provider import ConversationProvider
from spec_interview.providers.base_queue import QueueEventMixin


class MockConversationProvider(QueueEventMixin, ConversationProvider):
    name = "mock"
    capabilities = ConversationCapabilities(
        barge_in=True,
        local_execution=True,
        text_injection=True,
        transcript_events=True,
    )

    def __init__(
        self,
        responses: Mapping[str, str] | None = None,
        delay_seconds: float = 0.01,
    ) -> None:
        self._init_queue()
        self._responses = dict(responses or {})
        self._delay = delay_seconds
        self._response_task: asyncio.Task[None] | None = None
        self._current_text = ""
        self._turn_count = 0
        self._state = ConversationState.IDLE

    async def start_session(self, context: SessionContext) -> SessionHandle:
        self._session_id = context.session_id
        provider_session_id = f"mock-{uuid4()}"
        await self._emit(
            SessionStarted(provider=self.name, provider_session_id=provider_session_id)
        )
        await self._change_state(ConversationState.LISTENING)
        return SessionHandle(
            session_id=context.session_id,
            provider_session_id=provider_session_id,
        )

    async def send_audio(self, chunk: AudioChunk) -> None:
        raise NotImplementedError("mock provider accepts text, not audio")

    async def send_text(self, text: str) -> None:
        if self._response_task and not self._response_task.done():
            raise RuntimeError("a response is already in progress")
        self._turn_count += 1
        await self._emit(TranscriptFinalized(text=text, role="user"))
        await self._change_state(ConversationState.PROCESSING)
        response = self._responses.get(
            text,
            f"Let us make that concrete. You said: {text}",
        )
        self._response_task = asyncio.create_task(self._stream_response(response))

    async def _stream_response(self, response: str) -> None:
        self._current_text = ""
        await self._emit(ResponseStarted())
        await self._change_state(ConversationState.SPEAKING)
        try:
            words = response.split()
            for index, word in enumerate(words):
                chunk = word if index == 0 else f" {word}"
                await asyncio.sleep(self._delay)
                self._current_text += chunk
                await self._emit(ResponseDelta(text=chunk))
            await self._emit(ResponseCompleted(text=self._current_text))
            await self._change_state(ConversationState.LISTENING)
        except asyncio.CancelledError:
            await self._emit(ResponseInterrupted(text=self._current_text))
            await self._change_state(ConversationState.INTERRUPTED)
            await self._change_state(ConversationState.LISTENING)
            raise

    async def _change_state(self, state: ConversationState) -> None:
        previous = self._state
        self._state = state
        await self._emit(SessionStateChanged(previous=previous, current=state))

    def events(self) -> AsyncIterator[ConversationEvent]:
        return self._event_iterator()

    async def interrupt(self) -> None:
        if self._response_task and not self._response_task.done():
            self._response_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._response_task

    async def wait_until_idle(self) -> None:
        if self._response_task:
            with suppress(asyncio.CancelledError):
                await self._response_task

    async def submit_tool_result(self, result: ToolResult) -> None:
        raise NotImplementedError("mock provider does not support tools")

    async def checkpoint(self, last_sequence: int) -> ConversationCheckpoint:
        if self._session_id is None:
            raise RuntimeError("provider session has not started")
        return ConversationCheckpoint(
            session_id=self._session_id,
            provider=self.name,
            last_sequence=last_sequence,
            provider_state={"turn_count": self._turn_count, "state": self._state.value},
        )

    async def restore(self, checkpoint: ConversationCheckpoint) -> None:
        self._session_id = checkpoint.session_id
        turn_count = checkpoint.provider_state.get("turn_count", 0)
        if not isinstance(turn_count, (str, int, float)):
            raise ValueError("invalid mock turn_count in checkpoint")
        self._turn_count = int(turn_count)
        self._state = ConversationState.LISTENING
        await self._emit(SessionResumed(from_sequence=checkpoint.last_sequence))
        await self._change_state(ConversationState.LISTENING)

    async def close(self) -> SessionSummary:
        await self.interrupt()
        if self._session_id is None:
            raise RuntimeError("provider session has not started")
        await self._change_state(ConversationState.STOPPED)
        await self._emit(SessionStopped())
        await self._finish_events()
        return SessionSummary(
            session_id=self._session_id,
            provider=self.name,
            event_count=0,
            final_state=ConversationState.STOPPED,
            transcript_lines=self._turn_count,
        )

    async def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            available=True,
            detail="Deterministic in-process contract provider",
            capabilities=self.capabilities,
        )
