from __future__ import annotations

import pytest

from spec_interview.providers.nova import BedrockNovaSonicProvider
from spec_interview.providers.parlor import LocalParlorGemmaProvider


@pytest.mark.parametrize(
    ("raw", "expected_type"),
    [
        ({"type": "transcript.partial", "text": "hel"}, "transcript_delta"),
        ({"type": "transcript.final", "text": "hello"}, "transcript_finalized"),
        ({"type": "response.delta", "text": "hi"}, "response_delta"),
        ({"type": "response.complete", "text": "hi there"}, "response_completed"),
        ({"type": "response.interrupted", "text": "hi"}, "response_interrupted"),
    ],
)
def test_parlor_fixture_translation(raw: dict[str, object], expected_type: str) -> None:
    assert LocalParlorGemmaProvider.translate_event(raw).type == expected_type


@pytest.mark.parametrize(
    ("raw", "expected_type"),
    [
        ({"eventType": "inputTranscriptDelta", "content": "hel"}, "transcript_delta"),
        ({"eventType": "inputTranscriptComplete", "content": "hello"}, "transcript_finalized"),
        ({"eventType": "textOutputDelta", "content": "hi"}, "response_delta"),
        ({"eventType": "textOutputComplete", "content": "hi there"}, "response_completed"),
        ({"eventType": "interruption", "content": "hi"}, "response_interrupted"),
    ],
)
def test_nova_fixture_translation(raw: dict[str, object], expected_type: str) -> None:
    assert BedrockNovaSonicProvider.translate_event(raw).type == expected_type


def test_unknown_adapter_events_fail_explicitly() -> None:
    with pytest.raises(ValueError, match="unsupported Parlor"):
        LocalParlorGemmaProvider.translate_event({"type": "mystery"})
    with pytest.raises(ValueError, match="unsupported Nova"):
        BedrockNovaSonicProvider.translate_event({"type": "mystery"})
