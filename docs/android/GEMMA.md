# Gemma on Android and Termux

## What this branch implements

`gemma-local` uses LiteRT-LM's OpenAI-compatible loopback server for streamed text and
native audio input. The audio path is intentionally two-stage:

1. Termux:API records one bounded mono 16 kHz Opus utterance.
2. Gemma transcribes it through LiteRT-LM's `input_audio` request shape.
3. The transcript enters the ordinary text-turn path.
4. The interview response streams through normalized events.

This preserves a real user transcript and reuses the same interruption, JSONL, checkpoint,
resume, and transcript consumers as every other provider. It is not yet continuous duplex
audio. Gemma 4 accepts mono 16 kHz audio clips up to 30 seconds, so the CLI enforces the same
upper bound. See Google's [Gemma audio guidance](https://ai.google.dev/gemma/docs/capabilities/audio)
and [LiteRT-LM Android API](https://developers.google.com/edge/litert-lm/android).

## First: identify what is already on the phone

From Termux, clone the repository's `feature-android` branch and install the project. Then run
the read-only probe before downloading another model:

```bash
git clone --branch feature-android https://github.com/DeeNihl/spec-interview.git
cd spec-interview
python -m pip install -e .
spec-interview android probe --plain | tee android-probe.json
```

The report contains the Android/device identity, architecture, likely AI Edge or Termux:API
package IDs, microphone command availability, and model IDs returned by `/v1/models`. Android
does not allow Termux to inspect another app's private model files, so a package match proves
only that the app is installed—not that its model can be reused.

Google identifies AI Edge Gallery as its Android sample app, but its app-private downloads are
not a supported cross-app model registry. Do not root the phone or weaken app isolation.

## Termux prerequisites

Microphone capture uses the official `termux-microphone-record` command. It requires both the
Termux:API Android companion app and its Termux package, plus microphone permission:

```bash
pkg install termux-api
termux-microphone-record -h
```

The command boundary uses only documented flags: file, duration, Opus encoder, 16 kHz sample
rate, and one channel. See the official
[Termux:API microphone script](https://github.com/termux/termux-api-package/blob/master/scripts/termux-microphone-record.in).

## LiteRT-LM registry and server

Install the Android extra, import an audio-capable Gemma model into LiteRT-LM's registry, and
start the loopback-only server. Do not guess the client model name; use the ID returned by the
registry endpoint.

```bash
python -m pip install -e '.[android]'
litert-lm serve --host 127.0.0.1 --port 8081
```

In a second Termux session:

```bash
curl -s http://127.0.0.1:8081/v1/models

export SPEC_INTERVIEW_GEMMA_ENDPOINT=http://127.0.0.1:8081
export SPEC_INTERVIEW_GEMMA_MODEL=MODEL_ID_FROM_V1_MODELS
export SPEC_INTERVIEW_GEMMA_AUDIO_ENABLED=true

spec-interview doctor
spec-interview start --provider gemma-local \
  --message "Help me identify the most fragile boundary in this design."
spec-interview android record-test --seconds 8
```

LiteRT-LM documents `litert-lm serve`, its model registry, and `/v1/models` in the
[OpenAI-compatible server guide](https://developers.google.com/edge/litert-lm/cli/openai_server).
Its current server source explicitly translates OpenAI `input_audio` parts into LiteRT native
audio blobs; the repository tests pin our serializer to that boundary.

## Device acceptance

Record these results before calling the integration complete:

1. Exact `android-probe.json` app package and model ID output.
2. `doctor` reports `gemma-local` available with native audio enabled.
3. One text turn completes and persists its transcript.
4. One 8-second microphone turn produces an accurate `You:` transcript and response.
5. An audio turn interrupted during ASR produces `response_interrupted` and remains resumable.
6. A long text response interrupted mid-stream preserves its partial assistant text.
7. Resume uses the same interview UUID and includes earlier turns in model context.
8. Time to first token, transcription latency, tokens/second, peak memory, heat, and battery.
9. Internal microphone and intended Bluetooth headset routing tested separately.

## Honest boundary

The cloud suite proves serialization, event order, cancellation, persistence, and command
construction without Android, a microphone, or a model. The phone must still prove Android
permissions, actual Opus decode, model/audio-backend compatibility, and routing. Continuous
capture, VAD, TTS playback, Bluetooth controls, foreground-service lifecycle, and full duplex
conversation are later slices.
