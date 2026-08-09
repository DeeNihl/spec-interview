"""Streaming Gemma provider for a local OpenAI-compatible model server."""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import suppress
from typing import Protocol
from uuid import uuid4

import httpx

from spec_interview.conversation.models import (
    AudioChunk,
    AudioInputStarted,
    AudioInputStopped,
    ConversationCapabilities,
    ConversationCheckpoint,
    ConversationEvent,
    ConversationState,
    ProviderError,
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
from spec_interview.conversation.provider import ConversationProvider, ProviderUnavailableError
from spec_interview.providers.base_queue import QueueEventMixin

ChatMessage = dict[str, str]


class GemmaTransport(Protocol):
    """Small transport seam implemented by LiteRT-LM's OpenAI-compatible server."""

    async def list_models(self) -> Sequence[str]: ...

    def stream_chat(self, model: str, messages: Sequence[ChatMessage]) -> AsyncIterator[str]: ...

    async def transcribe_audio(
        self,
        model: str,
        audio: bytes,
        encoding: str,
        prompt: str,
    ) -> str: ...


class OpenAICompatibleGemmaTransport:
    """HTTP/SSE client compatible with LiteRT-LM and llama.cpp servers."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:8081",
        *,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        http_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.http_transport = http_transport

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def list_models(self) -> Sequence[str]:
        async with httpx.AsyncClient(
            timeout=5.0, transport=self.http_transport, trust_env=False
        ) as client:
            response = await client.get(f"{self.endpoint}/v1/models", headers=self._headers())
            response.raise_for_status()
        payload = response.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(data, list):
            raise ValueError("model server returned an invalid /v1/models payload")
        return [
            str(item["id"])
            for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]

    @staticmethod
    def decode_sse_data(data: str) -> str | None:
        """Extract one text delta from an OpenAI-compatible SSE data value."""
        if data == "[DONE]":
            return None
        payload = json.loads(data)
        if not isinstance(payload, dict):
            return None
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return None
        choice = choices[0]
        delta = choice.get("delta")
        if isinstance(delta, dict) and isinstance(delta.get("content"), str):
            return str(delta["content"])
        message = choice.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return str(message["content"])
        return None

    async def stream_chat(self, model: str, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        request = {"model": model, "messages": list(messages), "stream": True}
        async for text in self._stream_request(request):
            yield text

    @staticmethod
    def build_audio_request(
        model: str,
        audio: bytes,
        encoding: str,
        prompt: str,
    ) -> dict[str, object]:
        """Build the input_audio shape accepted by LiteRT-LM's OpenAI handler."""
        return {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": base64.b64encode(audio).decode("ascii"),
                                "format": encoding,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "stream": True,
        }

    async def transcribe_audio(
        self,
        model: str,
        audio: bytes,
        encoding: str,
        prompt: str,
    ) -> str:
        chunks = [
            text
            async for text in self._stream_request(
                self.build_audio_request(model, audio, encoding, prompt)
            )
        ]
        return "".join(chunks).strip()

    async def _stream_request(self, request: dict[str, object]) -> AsyncIterator[str]:
        timeout = httpx.Timeout(self.timeout_seconds, connect=10.0)
        async with httpx.AsyncClient(
            timeout=timeout, transport=self.http_transport, trust_env=False
        ) as client:
            async with client.stream(
                "POST",
                f"{self.endpoint}/v1/chat/completions",
                headers=self._headers(),
                json=request,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    text = self.decode_sse_data(data)
                    if text:
                        yield text


class LocalGemmaProvider(QueueEventMixin, ConversationProvider):
    """Local text conversation provider backed by Gemma through loopback HTTP."""

    name = "gemma-local"

    def __init__(
        self,
        model: str,
        transport: GemmaTransport,
        *,
        audio_enabled: bool = False,
        transcription_prompt: str = (
            "Transcribe this speech in its original language. Output only the transcription, "
            "with no commentary or formatting."
        ),
        system_prompt: str = (
            "You are a grounded technical peer conducting a specification interview. "
            "Ask one focused question at a time, challenge fragile assumptions, and make "
            "decisions, constraints, alternatives, and open questions explicit."
        ),
    ) -> None:
        self._init_queue()
        self.model = model
        self.transport = transport
        self.audio_enabled = audio_enabled
        self.transcription_prompt = transcription_prompt
        self.system_prompt = system_prompt
        self.capabilities = ConversationCapabilities(
            native_audio=audio_enabled,
            barge_in=True,
            local_execution=True,
            text_injection=True,
            transcript_events=True,
        )
        self._history: list[ChatMessage] = [{"role": "system", "content": system_prompt}]
        self._response_task: asyncio.Task[None] | None = None
        self._current_text = ""
        self._turn_count = 0
        self._state = ConversationState.IDLE
        self._audio_parts: list[bytes] = []
        self._audio_encoding: str | None = None

    async def status(self) -> ProviderStatus:
        try:
            models = list(await self.transport.list_models())
        except (OSError, ValueError, httpx.HTTPError) as error:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"Gemma server unavailable: {error}",
                capabilities=self.capabilities,
            )
        if self.model not in models:
            available = ", ".join(models) if models else "none"
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"Gemma model {self.model!r} is not registered; available: {available}",
                capabilities=self.capabilities,
            )
        return ProviderStatus(
            name=self.name,
            available=True,
            detail=(
                f"Gemma model {self.model!r} available through local server"
                + ("; native audio request boundary enabled" if self.audio_enabled else "")
            ),
            capabilities=self.capabilities,
        )

    async def start_session(self, context: SessionContext) -> SessionHandle:
        status = await self.status()
        if not status.available:
            raise ProviderUnavailableError(status.detail)
        self._session_id = context.session_id
        provider_session_id = f"gemma-{uuid4()}"
        await self._emit(
            SessionStarted(provider=self.name, provider_session_id=provider_session_id)
        )
        await self._change_state(ConversationState.LISTENING)
        return SessionHandle(
            session_id=context.session_id,
            provider_session_id=provider_session_id,
        )

    async def send_audio(self, chunk: AudioChunk) -> None:
        if not self.audio_enabled:
            raise NotImplementedError(
                "gemma-local audio is disabled; set SPEC_INTERVIEW_GEMMA_AUDIO_ENABLED=true"
            )
        if chunk.sample_rate_hz != 16_000 or chunk.channels != 1:
            raise ValueError("Gemma audio must be mono at 16 kHz")
        if self._response_task and not self._response_task.done():
            raise RuntimeError("a response is already in progress")
        if self._audio_encoding is None:
            self._audio_encoding = chunk.encoding
            await self._emit(AudioInputStarted())
        elif self._audio_encoding != chunk.encoding:
            raise ValueError("all chunks in one audio utterance must use the same encoding")
        self._audio_parts.append(chunk.data)
        if not chunk.is_final:
            return
        audio = b"".join(self._audio_parts)
        encoding = self._audio_encoding
        if encoding is None:
            raise RuntimeError("audio encoding was not initialized")
        self._audio_parts = []
        self._audio_encoding = None
        await self._emit(AudioInputStopped())
        await self._change_state(ConversationState.PROCESSING)
        self._response_task = asyncio.create_task(self._transcribe_and_respond(audio, encoding))

    async def send_text(self, text: str) -> None:
        if self._response_task and not self._response_task.done():
            raise RuntimeError("a response is already in progress")
        self._turn_count += 1
        self._history.append({"role": "user", "content": text})
        await self._emit(TranscriptFinalized(text=text, role="user"))
        await self._change_state(ConversationState.PROCESSING)
        self._response_task = asyncio.create_task(self._stream_response())

    async def _stream_response(self) -> None:
        self._current_text = ""
        await self._emit(ResponseStarted())
        await self._change_state(ConversationState.SPEAKING)
        try:
            async for text in self.transport.stream_chat(self.model, self._history):
                self._current_text += text
                await self._emit(ResponseDelta(text=text))
            self._history.append({"role": "assistant", "content": self._current_text})
            await self._emit(ResponseCompleted(text=self._current_text))
            await self._change_state(ConversationState.LISTENING)
        except asyncio.CancelledError:
            if self._current_text:
                self._history.append({"role": "assistant", "content": self._current_text})
            await self._emit(ResponseInterrupted(text=self._current_text))
            await self._change_state(ConversationState.INTERRUPTED)
            await self._change_state(ConversationState.LISTENING)
            raise
        except (OSError, ValueError, httpx.HTTPError) as error:
            await self._emit(ProviderError(message=f"Gemma generation failed: {error}"))
            await self._change_state(ConversationState.LISTENING)

    async def _transcribe_and_respond(self, audio: bytes, encoding: str) -> None:
        try:
            transcript = await self.transport.transcribe_audio(
                self.model,
                audio,
                encoding,
                self.transcription_prompt,
            )
            if not transcript:
                raise ValueError("Gemma returned an empty audio transcription")
        except asyncio.CancelledError:
            await self._emit(ResponseInterrupted(text="", reason="audio_input_cancelled"))
            await self._change_state(ConversationState.INTERRUPTED)
            await self._change_state(ConversationState.LISTENING)
            raise
        except (OSError, ValueError, httpx.HTTPError) as error:
            await self._emit(ProviderError(message=f"Gemma transcription failed: {error}"))
            await self._change_state(ConversationState.LISTENING)
            return

        self._turn_count += 1
        self._history.append({"role": "user", "content": transcript})
        await self._emit(TranscriptFinalized(text=transcript, role="user"))
        await self._stream_response()

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

    async def submit_tool_result(self, result: ToolResult) -> None:
        raise NotImplementedError("gemma-local tool results are not implemented")

    async def checkpoint(self, last_sequence: int) -> ConversationCheckpoint:
        if self._session_id is None:
            raise RuntimeError("provider session has not started")
        return ConversationCheckpoint(
            session_id=self._session_id,
            provider=self.name,
            last_sequence=last_sequence,
            provider_state={
                "turn_count": self._turn_count,
                "history_json": json.dumps(self._history, separators=(",", ":")),
            },
        )

    async def restore(self, checkpoint: ConversationCheckpoint) -> None:
        history_json = checkpoint.provider_state.get("history_json", "[]")
        if not isinstance(history_json, str):
            raise ValueError("invalid Gemma history in checkpoint")
        history = json.loads(history_json)
        if not isinstance(history, list) or not all(
            isinstance(item, dict)
            and isinstance(item.get("role"), str)
            and isinstance(item.get("content"), str)
            for item in history
        ):
            raise ValueError("invalid Gemma history in checkpoint")
        self._history = [
            {"role": str(item["role"]), "content": str(item["content"])} for item in history
        ]
        turn_count = checkpoint.provider_state.get("turn_count", 0)
        if not isinstance(turn_count, (str, int, float)):
            raise ValueError("invalid Gemma turn count in checkpoint")
        self._turn_count = int(turn_count)
        self._session_id = checkpoint.session_id
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
