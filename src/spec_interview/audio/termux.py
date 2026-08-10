"""Bounded utterance capture through the official Termux:API command."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from spec_interview.android.probe import CommandResult, CommandRunner, run_command


class TermuxMicrophoneRecorder:
    """Record one mono 16 kHz Opus utterance without shell interpolation."""

    def __init__(
        self,
        runner: CommandRunner = run_command,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.runner = runner
        self.sleeper = sleeper

    async def record(self, target: Path, duration_seconds: int) -> bytes:
        if not 1 <= duration_seconds <= 30:
            raise ValueError("recording duration must be between 1 and 30 seconds")
        result = await self.runner(
            (
                "termux-microphone-record",
                "-f",
                str(target),
                "-l",
                str(duration_seconds),
                "-e",
                "opus",
                "-r",
                "16000",
                "-c",
                "1",
            )
        )
        self._require_started(result)
        await self.sleeper(duration_seconds + 0.5)
        for _ in range(20):
            audio = await asyncio.to_thread(self._read_if_ready, target)
            if audio is not None:
                return audio
            await self.sleeper(0.1)
        raise RuntimeError(f"microphone recording did not produce {target}")

    @staticmethod
    def _require_started(result: CommandResult) -> None:
        if result.returncode != 0:
            detail = result.stderr or result.stdout or "unknown Termux:API failure"
            raise RuntimeError(f"could not start microphone recording: {detail}")

    @staticmethod
    def _read_if_ready(target: Path) -> bytes | None:
        if target.is_file() and target.stat().st_size > 0:
            return target.read_bytes()
        return None


class FFmpegAudioTranscoder:
    """Convert Termux's Opus output to the PCM WAV expected by LiteRT-LM."""

    def __init__(self, runner: CommandRunner = run_command) -> None:
        self.runner = runner

    async def opus_to_wav(self, source: Path, target: Path) -> bytes:
        result = await self.runner(
            (
                "ffmpeg",
                "-nostdin",
                "-y",
                "-i",
                str(source),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(target),
            )
        )
        if result.returncode != 0:
            detail = result.stderr or result.stdout or "unknown FFmpeg failure"
            raise RuntimeError(f"could not convert microphone audio to WAV: {detail}")
        audio = await asyncio.to_thread(TermuxMicrophoneRecorder._read_if_ready, target)
        if audio is None:
            raise RuntimeError(f"FFmpeg did not produce {target}")
        return audio
