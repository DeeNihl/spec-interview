# Acceptance and validation

## Cloud proof

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy
pytest
```

Run two independent sessions and resume the interrupted one:

```bash
proof_dir="$(mktemp -d)"
spec-interview start --provider mock --message "Map the stable boundary" \
  --data-dir "$proof_dir" --plain
spec-interview start --provider mock --message "Explain every fragile assumption" \
  --interrupt-after 0.015 --data-dir "$proof_dir" --plain
spec-interview resume SESSION_ID --message "Continue from the interruption" \
  --data-dir "$proof_dir" --plain
spec-interview transcript SESSION_ID --data-dir "$proof_dir"
```

Expected evidence:

- every session has monotonic sequences beginning at one;
- interrupted text appears as `Assistant [interrupted]`;
- the resumed session keeps the same UUID;
- a `session_resumed` event follows the earlier checkpoint;
- `transcript.txt` and `summary.md` can be deleted and deterministically regenerated.

## Android Gemma boundary — implemented, hardware acceptance pending

The suite verifies the LiteRT-LM `input_audio` payload, SSE response translation, 16 kHz mono
Termux command boundary, ASR-to-normalized-text handoff, audio interruption, model discovery,
package inventory, and failure reporting. Follow [`../android/GEMMA.md`](../android/GEMMA.md)
to validate the actual model, microphone permission, capture codec, latency, heat, and routing
on the Z Fold. Continuous audio, VAD, playback, and Bluetooth behavior are not claimed.

## Mac audio acceptance — not yet validated

After the Parlor transport slice exists:

1. Install the project and Parlor dependencies on macOS.
2. Start the Parlor backend and confirm `spec-interview doctor` reports it healthy.
3. Launch the compact Chrome app-mode audio window.
4. Run a 15-minute spoken session using the intended Bluetooth device.
5. Interrupt playback naturally at least three times.
6. Disconnect and reconnect the audio device once.
7. Stop the process, resume from its checkpoint, and inspect the transcript.
8. Record latency, transcript quality, partial-output preservation, and routing failures.

## AWS/Nova acceptance — not yet validated

Do not paste credentials into chat or commit them. Use an AWS profile or normal workload
identity, enable Nova Sonic model access in a supported region, install `.[aws]`, and run
`spec-interview doctor` before attempting live transport.

The live slice must validate:

- bidirectional audio streaming;
- AWS event translation against actual protocol frames;
- interruption semantics;
- provider connection renewal while preserving the interview session ID;
- checkpoint continuity across process restart;
- latency and cost collection.
