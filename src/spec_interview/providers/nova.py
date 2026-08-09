"""Protocol boundary for Bedrock Nova Sonic bidirectional streaming."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import AsyncIterator

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


class BedrockNovaSonicProvider(QueueEventMixin, ConversationProvider):
    name = "nova-sonic"
    capabilities = ConversationCapabilities(
        native_audio=True,
        native_vad=True,
        barge_in=True,
        async_tools=True,
        session_renewal=True,
        transcript_events=True,
    )

    def __init__(
        self, region: str | None = None, model_id: str = "amazon.nova-2-sonic-v1:0"
    ) -> None:
        self._init_queue()
        self.region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        self.model_id = model_id

    @staticmethod
    def translate_event(raw: dict[str, object]) -> object:
        kind = raw.get("type") or raw.get("eventType")
        text = str(raw.get("text") or raw.get("content") or "")
        mapping: dict[object, object] = {
            "inputTranscriptDelta": TranscriptDelta(text=text),
            "inputTranscriptComplete": TranscriptFinalized(text=text),
            "textOutputDelta": ResponseDelta(text=text),
            "textOutputComplete": ResponseCompleted(text=text),
            "interruption": ResponseInterrupted(text=text, reason="nova_interruption"),
            "error": ProviderError(message=str(raw.get("message", "Nova Sonic error"))),
        }
        if kind not in mapping:
            raise ValueError(f"unsupported Nova Sonic event: {kind!r}")
        return mapping[kind]

    async def status(self) -> ProviderStatus:
        sdk = importlib.util.find_spec("boto3") is not None
        has_credentials_hint = bool(
            os.getenv("AWS_PROFILE")
            or os.getenv("AWS_ACCESS_KEY_ID")
            or os.getenv("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
        )
        available = sdk and bool(self.region) and has_credentials_hint
        missing = []
        if not sdk:
            missing.append("install the aws extra")
        if not self.region:
            missing.append("set AWS_REGION")
        if not has_credentials_hint:
            missing.append("configure AWS credentials/profile")
        detail = "Nova Sonic prerequisites detected" if available else "; ".join(missing)
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
            "Nova prerequisites detected, but live bidirectional transport requires "
            "AWS acceptance validation"
        )

    async def send_audio(self, chunk: AudioChunk) -> None:
        raise ProviderUnavailableError("live Nova Sonic transport is not connected")

    async def send_text(self, text: str) -> None:
        raise ProviderUnavailableError("live Nova Sonic transport is not connected")

    def events(self) -> AsyncIterator[ConversationEvent]:
        return self._event_iterator()

    async def interrupt(self) -> None:
        return None

    async def submit_tool_result(self, result: ToolResult) -> None:
        raise ProviderUnavailableError("live Nova Sonic transport is not connected")

    async def checkpoint(self, last_sequence: int) -> ConversationCheckpoint:
        if self._session_id is None:
            raise RuntimeError("provider session has not started")
        return ConversationCheckpoint(
            session_id=self._session_id,
            provider=self.name,
            last_sequence=last_sequence,
            provider_state={"region": self.region, "model_id": self.model_id},
        )

    async def restore(self, checkpoint: ConversationCheckpoint) -> None:
        raise ProviderUnavailableError("live Nova renewal/resume requires AWS validation")

    async def close(self) -> SessionSummary:
        raise ProviderUnavailableError("live Nova Sonic transport is not connected")
