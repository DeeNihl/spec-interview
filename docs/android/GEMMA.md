# Gemma on Android and Termux

## Current integration boundary

`gemma-local` is a streaming text provider for an OpenAI-compatible model server on the
same device. It is designed first for LiteRT-LM's loopback server and is also compatible
with servers such as llama.cpp that implement:

```text
GET  /v1/models
POST /v1/chat/completions   (stream=true, SSE response)
```

This slice includes model discovery, streamed normalized events, cancellation, partial-text
preservation, conversation history, checkpoint, and resume. It does not yet send microphone
audio to Gemma or synthesize speech.

## Why an existing Google app may not be reusable

Google AI Edge Gallery and similar Android apps keep their downloaded model files in the
app's private storage. Android normally prevents Termux and another app from reading that
storage. Having Gemma available inside the app therefore does not prove that the Python CLI
can use the same model artifact.

If the app is still installed, record its exact name and model label before downloading
anything else. We can then check whether it supports export, shared-storage selection, or an
external API. Do not root the phone or weaken app isolation for this project.

## LiteRT-LM path

LiteRT-LM 0.14 and newer documents Android `aarch64` support for its Python API and CLI,
including Termux. Its OpenAI-compatible server can be started with:

```bash
litert-lm serve --host 127.0.0.1 --port 8081
```

Install the project and run diagnostics:

```bash
python -m pip install -e '.[android]'
curl -s http://127.0.0.1:8081/v1/models

export SPEC_INTERVIEW_GEMMA_ENDPOINT=http://127.0.0.1:8081
export SPEC_INTERVIEW_GEMMA_MODEL=MODEL_ID_FROM_V1_MODELS

spec-interview doctor
spec-interview start --provider gemma-local \
  --message "Help me identify the most fragile boundary in this design."
```

Use the plain model ID returned by `/v1/models`. LiteRT-LM 0.14 has a reported regression
when backend suffixes such as `,gpu` are placed in the OpenAI request's `model` field.
Configure CPU/GPU/NPU in LiteRT-LM itself rather than adding a suffix here.

## Device acceptance checklist

1. Confirm Android version, Termux architecture, free storage, and available memory.
2. Record the exact existing Google app and model name, if present.
3. Start LiteRT-LM and verify `/v1/models` from the same Termux session.
4. Run `spec-interview doctor` and confirm `gemma-local` is available.
5. Complete a text turn and inspect the saved transcript.
6. Interrupt a long response and confirm partial text is preserved.
7. Resume the session and confirm earlier turns remain in model context.
8. Record time-to-first-token, tokens per second, memory pressure, heat, and battery use.

## Next Android slice

After text inference works, add a small native Android audio client or LiteRT-LM bridge for:

- microphone capture and 16 kHz mono audio normalization;
- Gemma 4 native audio input;
- VAD and interruption;
- streamed text back to the provider;
- Android audio focus, Bluetooth routing, and foreground-service lifecycle.

The core provider must continue to report `native_audio=false` until that path is actually
implemented and tested on the device.
