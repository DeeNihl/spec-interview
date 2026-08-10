from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

import pytest

from spec_interview.cli import app as cli_app
from spec_interview.config import ConversationProviderFactory
from spec_interview.conversation.models import AudioChunk
from spec_interview.providers.gemma import ChatMessage, LocalGemmaProvider
from spec_interview.sessions import SessionStore
from spec_interview.speech import SpeechProvider


class ConversationTransport:
    def __init__(self) -> None:
        self.transcriptions = iter(("First idea", "Second detail"))

    async def list_models(self) -> Sequence[str]:
        return ("test-gemma",)

    async def transcribe_audio(self, model: str, audio: bytes, encoding: str, prompt: str) -> str:
        assert encoding == "wav"
        return next(self.transcriptions)

    async def stream_chat(self, model: str, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        yield f"Question about {messages[-1]['content']}?"


class RecordingSpeechProvider(SpeechProvider):
    name = "recording-speech"
    interruptible = True

    def __init__(self) -> None:
        self.spoken: list[str] = []

    async def available(self) -> bool:
        return True

    async def speak(self, text: str) -> None:
        self.spoken.append(text)

    async def interrupt(self) -> None:
        return None


@pytest.mark.asyncio
async def test_android_conversation_keeps_one_session_across_spoken_turns(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = LocalGemmaProvider("test-gemma", ConversationTransport(), audio_enabled=True)
    speech = RecordingSpeechProvider()

    async def capture(duration_seconds: int) -> AudioChunk:
        assert duration_seconds == 4
        return AudioChunk(data=b"RIFF", encoding="wav")

    monkeypatch.setattr(cli_app, "_capture_android_audio", capture)
    monkeypatch.setattr(
        ConversationProviderFactory,
        "create",
        lambda name, config: provider,
    )

    session_id = await cli_app._converse_android(
        4,
        2,
        tmp_path,
        speech,
        "Opening question?",
        False,
    )

    events = SessionStore(tmp_path).read_events(session_id)
    payload_types = [event.payload.type for event in events]
    assert payload_types.count("transcript_finalized") == 2
    assert payload_types.count("response_completed") == 2
    assert payload_types.count("checkpoint_created") == 2
    assert speech.spoken == [
        "Opening question?",
        "Question about First idea?",
        "Question about Second detail?",
    ]
