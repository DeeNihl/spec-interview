"""Executable boundary for a separately deployed Parlor/Gemma service."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from urllib.error import URLError
from urllib.request import urlopen

from spec_interview.conversation.models import (
    AudioChunk,
    ConversationCapabilities,
    ConversationCheckpoint,
    ConversationEvent,
    ProviderError,
    ProviderStatus,
    ResponseCompleted,
    ResponseDelta,
    ResponseInterrupted,
    SessionContext,
    SessionHandle,
    SessionSummary,
    ToolResult,
    TranscriptDelta,
    TranscriptFinalized,
)
from spec_interview.conversation.provider import ConversationProvider, ProviderUnavailableError
from spec_interview.providers.base_queue import QueueEventMixin


class LocalParlorGemmaProvider(QueueEventMixin, ConversationProvider):
    name = "parlor-gemma"
    capabilities = ConversationCapabilities(
        native_audio=True,
        native_vad=True,
        barge_in=True,
        local_execution=True,
        transcript_events=True,
    )

    def __init__(self, endpoint: str = "http://127.0.0.1:8765") -> None:
        self._init_queue()
        self.endpoint = endpoint.rstrip("/")

    @staticmethod
    def translate_event(raw: dict[str, object]) -> object:
        kind = raw.get("type")
        text = str(raw.get("text", ""))
        mapping: dict[object, object] = {
            "transcript.partial": TranscriptDelta(text=text),
            "transcript.final": TranscriptFinalized(text=text),
            "response.delta": ResponseDelta(text=text),
            "response.complete": ResponseCompleted(text=text),
            "response.interrupted": ResponseInterrupted(text=text),
            "error": ProviderError(message=str(raw.get("message", "Parlor provider error"))),
        }
        if kind not in mapping:
            raise ValueError(f"unsupported Parlor event: {kind!r}")
        return mapping[kind]

    async def status(self) -> ProviderStatus:
        def check() -> tuple[bool, str]:
            try:
                with urlopen(f"{self.endpoint}/health", timeout=1.0) as response:
                    data = json.loads(response.read())
                return True, f"Parlor service healthy: {data.get('status', 'ok')}"
            except (OSError, URLError, json.JSONDecodeError) as error:
                return False, f"Parlor service unavailable at {self.endpoint}: {error}"

        available, detail = await asyncio.to_thread(check)
        return ProviderStatus(
            name=self.name,
            available=available,
            detail=detail,
            capabilities=self.capabilities,
        )

    async def start_session(self, context: SessionContext) -> SessionHandle:
        status = await self.status()
        if not status.available:
            raise ProviderUnavailableError(status.detail)
        raise ProviderUnavailableError(
            "Parlor service is reachable, but live WebSocket transport is a Mac validation slice"
        )

    async def send_audio(self, chunk: AudioChunk) -> None:
        raise ProviderUnavailableError("live Parlor transport is not connected")

    async def send_text(self, text: str) -> None:
        raise ProviderUnavailableError("live Parlor transport is not connected")

    def events(self) -> AsyncIterator[ConversationEvent]:
        return self._event_iterator()

    async def interrupt(self) -> None:
        return None

    async def submit_tool_result(self, result: ToolResult) -> None:
        raise NotImplementedError("Parlor adapter does not support tool results")

    async def checkpoint(self, last_sequence: int) -> ConversationCheckpoint:
        if self._session_id is None:
            raise RuntimeError("provider session has not started")
        return ConversationCheckpoint(
            session_id=self._session_id,
            provider=self.name,
            last_sequence=last_sequence,
        )

    async def restore(self, checkpoint: ConversationCheckpoint) -> None:
        raise ProviderUnavailableError("live Parlor resume requires its WebSocket transport")

    async def close(self) -> SessionSummary:
        raise ProviderUnavailableError("live Parlor transport is not connected")
