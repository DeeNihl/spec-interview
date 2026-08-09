from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator, Sequence

import httpx
import pytest

from spec_interview.conversation.manager import ConversationManager
from spec_interview.conversation.models import AudioChunk
from spec_interview.providers.gemma import (
    ChatMessage,
    LocalGemmaProvider,
    OpenAICompatibleGemmaTransport,
)
from spec_interview.sessions import SessionStore


class FakeGemmaTransport:
    def __init__(
        self,
        chunks: Sequence[str] = ("Which ", "boundary?"),
        *,
        delay_seconds: float = 0,
        models: Sequence[str] = ("gemma4-e4b",),
    ) -> None:
        self.chunks = chunks
        self.delay_seconds = delay_seconds
        self.models = models
        self.requests: list[tuple[str, list[ChatMessage]]] = []
        self.audio_requests: list[tuple[str, bytes, str, str]] = []
        self.transcript = "The protocol boundary is unclear."
        self.transcription_delay_seconds = 0.0
        self.chunk_emitted = asyncio.Event()

    async def list_models(self) -> Sequence[str]:
        return self.models

    async def stream_chat(self, model: str, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        self.requests.append((model, list(messages)))
        for chunk in self.chunks:
            await asyncio.sleep(self.delay_seconds)
            yield chunk
            self.chunk_emitted.set()

    async def transcribe_audio(self, model: str, audio: bytes, encoding: str, prompt: str) -> str:
        self.audio_requests.append((model, audio, encoding, prompt))
        await asyncio.sleep(self.transcription_delay_seconds)
        return self.transcript


@pytest.mark.asyncio
async def test_gemma_provider_streams_and_checkpoints_history(tmp_path) -> None:
    transport = FakeGemmaTransport()
    store = SessionStore(tmp_path)
    manager = ConversationManager(LocalGemmaProvider("gemma4-e4b", transport), store)

    await manager.start()
    before = manager.last_sequence
    await manager.send_text("Walk me through the components.")
    terminal = await manager.wait_for_response(before)
    await manager.create_checkpoint()
    await manager.close()

    assert terminal.payload.type == "response_completed"
    assert terminal.payload.text == "Which boundary?"
    assert transport.requests[0][0] == "gemma4-e4b"
    assert transport.requests[0][1][-1] == {
        "role": "user",
        "content": "Walk me through the components.",
    }
    assert "Assistant: Which boundary?" in store.render_transcript(manager.session_id)
    checkpoint = store.read_checkpoint(manager.session_id)
    assert "Which boundary?" in str(checkpoint.provider_state["history_json"])


@pytest.mark.asyncio
async def test_gemma_provider_interrupt_preserves_partial_text(tmp_path) -> None:
    transport = FakeGemmaTransport(("This ", "response ", "keeps going"), delay_seconds=0.02)
    store = SessionStore(tmp_path)
    manager = ConversationManager(LocalGemmaProvider("gemma4-e4b", transport), store)

    await manager.start()
    before = manager.last_sequence
    await manager.send_text("Challenge the assumption.")
    await asyncio.wait_for(transport.chunk_emitted.wait(), timeout=1.0)
    await manager.interrupt()
    terminal = await manager.wait_for_response(before)
    await manager.close()

    assert terminal.payload.type == "response_interrupted"
    assert terminal.payload.text == "This "
    assert "Assistant [interrupted]: This" in store.render_transcript(manager.session_id)


@pytest.mark.asyncio
async def test_gemma_provider_restore_reuses_conversation_history(tmp_path) -> None:
    first_transport = FakeGemmaTransport(("First answer",))
    store = SessionStore(tmp_path)
    first = ConversationManager(LocalGemmaProvider("gemma4-e4b", first_transport), store)
    await first.start()
    before = first.last_sequence
    await first.send_text("First question")
    await first.wait_for_response(before)
    await first.create_checkpoint()
    await first.close()

    second_transport = FakeGemmaTransport(("Second answer",))
    second = ConversationManager(
        LocalGemmaProvider("gemma4-e4b", second_transport),
        store,
        session_id=first.session_id,
    )
    await second.resume()
    before = second.last_sequence
    await second.send_text("Second question")
    await second.wait_for_response(before)
    await second.close()

    messages = second_transport.requests[0][1]
    assert [message["content"] for message in messages[-3:]] == [
        "First question",
        "First answer",
        "Second question",
    ]


@pytest.mark.asyncio
async def test_gemma_audio_transcribes_then_uses_normalized_text_turn(tmp_path) -> None:
    transport = FakeGemmaTransport(("What ", "fails first?"))
    provider = LocalGemmaProvider("gemma4-e4b", transport, audio_enabled=True)
    store = SessionStore(tmp_path)
    manager = ConversationManager(provider, store)

    await manager.start()
    before = manager.last_sequence
    await manager.send_audio(AudioChunk(data=b"opus-data", encoding="opus"))
    terminal = await manager.wait_for_response(before)
    await manager.close()

    assert terminal.payload.type == "response_completed"
    assert terminal.payload.text == "What fails first?"
    assert transport.audio_requests[0][1:3] == (b"opus-data", "opus")
    assert transport.requests[0][1][-1]["content"] == transport.transcript
    transcript = store.render_transcript(manager.session_id)
    assert f"You: {transport.transcript}" in transcript
    assert "Assistant: What fails first?" in transcript
    event_types = [event.payload.type for event in store.read_events(manager.session_id)]
    assert event_types.index("audio_input_started") < event_types.index("audio_input_stopped")
    assert event_types.index("audio_input_stopped") < event_types.index("transcript_finalized")
    assert event_types.index("transcript_finalized") < event_types.index("response_started")


@pytest.mark.asyncio
async def test_gemma_audio_buffers_chunks_and_rejects_mixed_encodings(tmp_path) -> None:
    transport = FakeGemmaTransport(("answer",))
    manager = ConversationManager(
        LocalGemmaProvider("gemma4-e4b", transport, audio_enabled=True),
        SessionStore(tmp_path),
    )
    await manager.start()
    await manager.send_audio(AudioChunk(data=b"one", encoding="opus", is_final=False))
    with pytest.raises(ValueError, match="same encoding"):
        await manager.send_audio(AudioChunk(data=b"two", encoding="wav"))
    await manager.send_audio(AudioChunk(data=b"two", encoding="opus"))
    await manager.wait_for_response(0)
    await manager.close()

    assert transport.audio_requests[0][1] == b"onetwo"


@pytest.mark.asyncio
async def test_gemma_audio_interruption_during_transcription_is_terminal(tmp_path) -> None:
    transport = FakeGemmaTransport()
    transport.transcription_delay_seconds = 1.0
    manager = ConversationManager(
        LocalGemmaProvider("gemma4-e4b", transport, audio_enabled=True),
        SessionStore(tmp_path),
    )
    await manager.start()
    before = manager.last_sequence
    await manager.send_audio(AudioChunk(data=b"audio", encoding="opus"))
    await asyncio.sleep(0)
    await manager.interrupt()
    terminal = await manager.wait_for_response(before)
    await manager.close()

    assert terminal.payload.type == "response_interrupted"
    assert terminal.payload.reason == "audio_input_cancelled"


@pytest.mark.asyncio
async def test_gemma_audio_requires_explicit_enablement_and_expected_shape(tmp_path) -> None:
    provider = LocalGemmaProvider("gemma4-e4b", FakeGemmaTransport())
    manager = ConversationManager(provider, SessionStore(tmp_path))
    await manager.start()
    assert not provider.capabilities.native_audio
    with pytest.raises(NotImplementedError, match="AUDIO_ENABLED"):
        await manager.send_audio(AudioChunk(data=b"audio", encoding="opus"))
    await manager.close()


@pytest.mark.asyncio
async def test_gemma_empty_audio_transcript_becomes_normalized_provider_error(tmp_path) -> None:
    transport = FakeGemmaTransport()
    transport.transcript = ""
    provider = LocalGemmaProvider("gemma4-e4b", transport, audio_enabled=True)
    manager = ConversationManager(provider, SessionStore(tmp_path))
    await manager.start()
    before = manager.last_sequence
    await manager.send_audio(AudioChunk(data=b"audio", encoding="opus"))
    terminal = await manager.wait_for_response(before)
    await manager.close()

    assert provider.capabilities.native_audio
    assert terminal.payload.type == "provider_error"
    assert "empty audio transcription" in terminal.payload.message


@pytest.mark.asyncio
async def test_gemma_status_reports_missing_registered_model() -> None:
    provider = LocalGemmaProvider("gemma4-e4b", FakeGemmaTransport(models=("another-model",)))

    status = await provider.status()

    assert not status.available
    assert "another-model" in status.detail


def test_openai_sse_decoder_extracts_text_and_done() -> None:
    assert (
        OpenAICompatibleGemmaTransport.decode_sse_data(
            '{"choices":[{"delta":{"content":"hello"}}]}'
        )
        == "hello"
    )
    assert OpenAICompatibleGemmaTransport.decode_sse_data("[DONE]") is None


@pytest.mark.asyncio
async def test_openai_transport_discovers_model_and_streams_sse() -> None:
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "gemma4-e4b"}]})
        assert request.url.path == "/v1/chat/completions"
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            text=(
                'data: {"choices":[{"delta":{"content":"hello "}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"phone"}}]}\n\n'
                "data: [DONE]\n\n"
            ),
            headers={"content-type": "text/event-stream"},
        )

    transport = OpenAICompatibleGemmaTransport(http_transport=httpx.MockTransport(handler))

    assert await transport.list_models() == ["gemma4-e4b"]
    chunks = [
        chunk
        async for chunk in transport.stream_chat(
            "gemma4-e4b", [{"role": "user", "content": "hello"}]
        )
    ]
    assert chunks == ["hello ", "phone"]

    transcript = await transport.transcribe_audio(
        "gemma4-e4b", b"audio-bytes", "opus", "Transcribe only."
    )
    assert transcript == "hello phone"
    audio_content = captured[1]["messages"][0]["content"]  # type: ignore[index]
    assert audio_content == [
        {
            "type": "input_audio",
            "input_audio": {
                "data": base64.b64encode(b"audio-bytes").decode("ascii"),
                "format": "opus",
            },
        },
        {"type": "text", "text": "Transcribe only."},
    ]
