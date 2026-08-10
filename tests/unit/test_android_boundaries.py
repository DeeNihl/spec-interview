from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest

from spec_interview.android.probe import AndroidProbe, CommandResult
from spec_interview.audio.termux import FFmpegAudioTranscoder, TermuxMicrophoneRecorder
from spec_interview.providers.gemma import ChatMessage


class ProbeTransport:
    async def list_models(self) -> Sequence[str]:
        return ("gemma-4-E4B-it",)

    async def stream_chat(self, model: str, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        if False:
            yield ""

    async def transcribe_audio(self, model: str, audio: bytes, encoding: str, prompt: str) -> str:
        return "transcript"


class FailedProbeTransport(ProbeTransport):
    async def list_models(self) -> Sequence[str]:
        raise OSError("connection refused")


@pytest.mark.asyncio
async def test_android_probe_collects_apps_device_and_models_without_mutation() -> None:
    commands: list[tuple[str, ...]] = []

    async def runner(command: Sequence[str]) -> CommandResult:
        key = tuple(command)
        commands.append(key)
        outputs = {
            ("uname", "-m"): "aarch64",
            ("getprop", "ro.build.version.release"): "16",
            ("getprop", "ro.product.model"): "SM-F966U",
            ("pm", "list", "packages"): (
                "package:com.google.android.apps.aiedge\n"
                "package:com.termux.api\npackage:irrelevant.app"
            ),
            ("termux-microphone-record", "-h"): "Usage",
        }
        return CommandResult(returncode=0, stdout=outputs[key])

    report = await AndroidProbe(ProbeTransport(), runner).inspect()

    assert report.architecture == "aarch64"
    assert report.android_version == "16"
    assert report.device == "SM-F966U"
    assert report.registered_models == ["gemma-4-E4B-it"]
    assert report.matching_packages == ["com.google.android.apps.aiedge", "com.termux.api"]
    assert all(command[0] not in {"pkg", "apt", "pip"} for command in commands)


@pytest.mark.asyncio
async def test_android_probe_keeps_device_evidence_when_model_server_is_down() -> None:
    async def runner(command: Sequence[str]) -> CommandResult:
        return CommandResult(returncode=0, stdout="aarch64")

    report = await AndroidProbe(FailedProbeTransport(), runner).inspect()

    server = next(check for check in report.checks if check.name == "gemma-server")
    assert not server.available
    assert "connection refused" in server.detail
    assert report.architecture == "aarch64"


@pytest.mark.asyncio
async def test_termux_recorder_uses_bounded_mono_16khz_opus(tmp_path: Path) -> None:
    commands: list[tuple[str, ...]] = []
    target = tmp_path / "utterance.opus"

    async def runner(command: Sequence[str]) -> CommandResult:
        commands.append(tuple(command))
        target.write_bytes(b"recorded-opus")
        return CommandResult(returncode=0, stdout="recording")

    async def no_sleep(seconds: float) -> None:
        return None

    audio = await TermuxMicrophoneRecorder(runner, no_sleep).record(target, 3)

    assert audio == b"recorded-opus"
    assert commands == [
        (
            "termux-microphone-record",
            "-f",
            str(target),
            "-l",
            "3",
            "-e",
            "opus",
            "-r",
            "16000",
            "-c",
            "1",
        )
    ]


@pytest.mark.asyncio
async def test_termux_recorder_surfaces_command_and_file_failures(tmp_path: Path) -> None:
    async def failed(command: Sequence[str]) -> CommandResult:
        return CommandResult(returncode=1, stderr="permission denied")

    async def no_sleep(seconds: float) -> None:
        return None

    recorder = TermuxMicrophoneRecorder(failed, no_sleep)
    with pytest.raises(RuntimeError, match="permission denied"):
        await recorder.record(tmp_path / "missing.opus", 1)

    with pytest.raises(ValueError, match="between 1 and 30"):
        await recorder.record(tmp_path / "too-long.opus", 31)

    async def starts_without_file(command: Sequence[str]) -> CommandResult:
        return CommandResult(returncode=0, stdout="recording")

    with pytest.raises(RuntimeError, match="did not produce"):
        await TermuxMicrophoneRecorder(starts_without_file, no_sleep).record(
            tmp_path / "never-created.opus", 1
        )


@pytest.mark.asyncio
async def test_ffmpeg_transcoder_produces_mono_16khz_pcm_wav(tmp_path: Path) -> None:
    source = tmp_path / "utterance.opus"
    target = tmp_path / "utterance.wav"
    source.write_bytes(b"opus")
    commands: list[tuple[str, ...]] = []

    async def runner(command: Sequence[str]) -> CommandResult:
        commands.append(tuple(command))
        target.write_bytes(b"RIFF-wav")
        return CommandResult(returncode=0)

    audio = await FFmpegAudioTranscoder(runner).opus_to_wav(source, target)

    assert audio == b"RIFF-wav"
    assert commands == [
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
    ]


@pytest.mark.asyncio
async def test_ffmpeg_transcoder_surfaces_conversion_failure(tmp_path: Path) -> None:
    async def failed(command: Sequence[str]) -> CommandResult:
        return CommandResult(returncode=127, stderr="ffmpeg not found")

    with pytest.raises(RuntimeError, match="ffmpeg not found"):
        await FFmpegAudioTranscoder(failed).opus_to_wav(
            tmp_path / "utterance.opus", tmp_path / "utterance.wav"
        )
