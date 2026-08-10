"""Android system text-to-speech through the official Termux:API command."""

from __future__ import annotations

import re
import textwrap

from spec_interview.android.probe import CommandResult, CommandRunner, run_command
from spec_interview.speech.provider import SpeechProvider

_SENTENCE = re.compile(r".+?(?:[.!?]+(?=\s|$)|$)")


def sentence_chunks(text: str, max_chars: int = 500) -> tuple[str, ...]:
    """Split model output into bounded, speakable sentence chunks."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    normalized = " ".join(text.split())
    chunks: list[str] = []
    for match in _SENTENCE.finditer(normalized):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        chunks.extend(
            textwrap.wrap(
                sentence,
                width=max_chars,
                break_long_words=False,
                break_on_hyphens=False,
            )
            or [sentence]
        )
    return tuple(chunks)


class TermuxSpeechProvider(SpeechProvider):
    """Speak sentence chunks with Android's configured system TTS engine."""

    name = "android-system-tts"
    interruptible = False

    def __init__(
        self,
        runner: CommandRunner = run_command,
        *,
        language: str | None = None,
        rate: float | None = None,
        pitch: float | None = None,
        max_chunk_chars: int = 500,
    ) -> None:
        if rate is not None and rate <= 0:
            raise ValueError("speech rate must be positive")
        if pitch is not None and pitch <= 0:
            raise ValueError("speech pitch must be positive")
        self.runner = runner
        self.language = language
        self.rate = rate
        self.pitch = pitch
        self.max_chunk_chars = max_chunk_chars

    async def available(self) -> bool:
        result = await self.runner(("termux-tts-speak", "-h"))
        return result.returncode == 0

    async def speak(self, text: str) -> None:
        for chunk in sentence_chunks(text, self.max_chunk_chars):
            result = await self.runner(self._command(chunk))
            self._require_spoken(result)

    async def interrupt(self) -> None:
        raise NotImplementedError(
            "Termux:API system TTS does not expose a reliable playback stop command"
        )

    def _command(self, text: str) -> tuple[str, ...]:
        command = ["termux-tts-speak"]
        if self.language:
            command.extend(("-l", self.language))
        if self.pitch is not None:
            command.extend(("-p", str(self.pitch)))
        if self.rate is not None:
            command.extend(("-r", str(self.rate)))
        command.extend(("--", text))
        return tuple(command)

    @staticmethod
    def _require_spoken(result: CommandResult) -> None:
        if result.returncode != 0:
            detail = result.stderr or result.stdout or "unknown Termux:API TTS failure"
            raise RuntimeError(f"could not speak Android TTS output: {detail}")
