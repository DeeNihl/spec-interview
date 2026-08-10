# Cloud proof implementation report

Date: 2026-08-09

## Fully implemented and tested

- Python 3.12 package with manager, provider ABC, factory, and typed configuration.
- Strict Pydantic capability, session, checkpoint, summary, and discriminated event models.
- Deterministic async mock provider with streaming, interruption, and restore behavior.
- Canonical manager-side sequencing independent of provider placeholder sequences.
- Append-only, fsynced JSONL event history with safe truncated-tail recovery.
- Atomic checkpoint replacement, stable-ID resume, deterministic transcript, and Markdown summary.
- CLI commands for providers, devices, doctor, start, resume, transcript, and sessions.
- Rich human output and plain JSON output for non-interactive use.
- Parlor/Gemma health/configuration boundary and fixture-tested event translation.
- Nova Sonic prerequisite/configuration boundary and fixture-tested event translation.
- Local Gemma streaming transport with model discovery, interruption, history checkpointing,
  and resume through an OpenAI-compatible endpoint.
- Exact LiteRT-LM `input_audio` request boundary, native Gemma ASR-to-text normalization,
  bounded Termux:API microphone capture, Opus-to-PCM-WAV conversion, and non-mutating
  Android/app/model inventory probe.
- Dockerfile, Compose file, dev container configuration, project guidance, and validation docs.

Validation results:

```text
ruff check .                 All checks passed
ruff format --check .        37 files already formatted
mypy                         Success: no issues found in 23 source files
pytest                       39 passed
```

Two real CLI processes were run against the installed editable package. One completed and
one was interrupted. The interrupted session was then resumed under the same UUID. Its
regenerated transcript contained:

```text
You: Explain every fragile assumption in detail
Assistant [interrupted]: Let
You: Continue from the interruption and challenge the assumption
Assistant: Let us make that concrete. You said: Continue from the interruption and challenge the assumption
```

This proves that the CLI, manager, event store, checkpoint, and transcript consumers operate
without special interruption or resume paths outside the provider contract.

## Implemented but requiring Mac audio validation

- Parlor endpoint configuration and health detection.
- The provider capability declaration and explicit unavailable behavior.
- Translation of representative transcript, response, interruption, and error events.

The live WebSocket transport, browser audio window, CoreAudio/Bluetooth routing, VAD,
playback, and natural barge-in are not implemented or claimed as tested yet.

## Implemented but requiring Z Fold validation

- Loopback model discovery and streaming text against the LiteRT-LM OpenAI server.
- LiteRT-LM-compatible base64 `input_audio` requests and Gemma ASR normalization.
- Termux:API bounded mono 16 kHz Opus capture and FFmpeg mono 16 kHz PCM WAV conversion.
- Read-only device, likely app-package, microphone-command, and model-server probe.

The cloud suite proves these boundaries with fakes and HTTP protocol fixtures. The phone must
still prove the end-to-end WAV inference result, latency, memory pressure, temperature,
battery cost, and audio routing. The Z Fold validation has already confirmed Android 16,
aarch64, Termux microphone permission and capture, LiteRT-LM 0.15.0, the registered
`gemma-4-E4B-it.litertlm` model, and a healthy loopback server.

## Implemented but requiring AWS credentials and model access

- Nova model/region configuration boundary.
- Optional AWS dependency and prerequisite detection.
- Translation of representative transcript, output, interruption, and error events.
- Capability declaration for audio, VAD, barge-in, tools, renewal, and transcripts.

Live Bedrock bidirectional streaming, actual protocol-frame verification, audio transport,
and eight-minute connection renewal are not implemented or claimed as tested yet.

## Environment limitation

The Dockerfile and Compose configuration were created, but a Docker build was not run because
the cloud workspace does not have the `docker` executable installed. Local Python packaging
and CLI execution succeeded. The first Mac or GitHub Actions pass should run:

```bash
docker build -t spec-interview:dev .
docker run --rm spec-interview:dev doctor --plain
```

## Deliberately deferred

- Opus shadow architect and asynchronous intervention policy.
- Full structured interview state machine and specification domain records.
- Protocol Manager, TMNT, typed-agent, or larger-framework integration.
- Automatic repository editing or Claude Code invocation.
- Native desktop or Android GUI clients and authenticated multi-user service.
- Continuous microphone streaming, VAD, TTS playback, and full-duplex voice on Android.

## Recommended next vertical slice

Implement the Parlor WebSocket client behind `LocalParlorGemmaProvider`, using recorded
frames first and a transport interface that can be replaced in tests. Then validate the tiny
browser audio window on the Mac. That exercises the most uncertain local-audio behavior
without entangling AWS credentials or Nova renewal in the same debugging pass.
