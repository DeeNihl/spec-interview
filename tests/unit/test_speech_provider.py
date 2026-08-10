from __future__ import annotations

from collections.abc import Sequence

import pytest

from spec_interview.android.probe import CommandResult
from spec_interview.speech import TermuxSpeechProvider, sentence_chunks


def test_sentence_chunks_preserve_sentences_and_bound_long_text() -> None:
    assert sentence_chunks("First question?  Second answer. Last thought") == (
        "First question?",
        "Second answer.",
        "Last thought",
    )
    assert sentence_chunks("one two three four", max_chars=7) == (
        "one two",
        "three",
        "four",
    )


@pytest.mark.asyncio
async def test_termux_speech_uses_system_tts_options_and_sentence_chunks() -> None:
    commands: list[tuple[str, ...]] = []

    async def runner(command: Sequence[str]) -> CommandResult:
        commands.append(tuple(command))
        return CommandResult(returncode=0)

    speech = TermuxSpeechProvider(runner, language="en", rate=1.2, pitch=0.9)

    assert await speech.available()
    await speech.speak("First question? Second question.")

    assert commands == [
        ("termux-tts-speak", "-h"),
        (
            "termux-tts-speak",
            "-l",
            "en",
            "-p",
            "0.9",
            "-r",
            "1.2",
            "--",
            "First question?",
        ),
        (
            "termux-tts-speak",
            "-l",
            "en",
            "-p",
            "0.9",
            "-r",
            "1.2",
            "--",
            "Second question.",
        ),
    ]


@pytest.mark.asyncio
async def test_termux_speech_reports_failure_and_non_interruptible_boundary() -> None:
    async def failed(command: Sequence[str]) -> CommandResult:
        return CommandResult(returncode=1, stderr="TTS engine unavailable")

    speech = TermuxSpeechProvider(failed)
    assert not await speech.available()
    with pytest.raises(RuntimeError, match="TTS engine unavailable"):
        await speech.speak("Hello.")
    with pytest.raises(NotImplementedError, match="does not expose"):
        await speech.interrupt()
