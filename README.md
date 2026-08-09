# spec-interview

`spec-interview` is a provider-neutral Python runtime and CLI for sustained technical
interviews. This proof demonstrates that one manager, event store, checkpoint format, and
CLI can outlive provider connections and preserve both completed and interrupted responses.

The mock provider is fully executable and tested. The Parlor/Gemma and Amazon Nova Sonic
providers currently define honest, fixture-tested adapter boundaries; their live transports
still require Mac audio and AWS acceptance slices respectively.

## Quick start

Python 3.12 or newer is required.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

spec-interview providers list
spec-interview doctor
spec-interview start --provider mock --message "Describe the system boundary."
```

By default session records are written beneath `.spec-interview/sessions`. Override that
location with `--data-dir` or `SPEC_INTERVIEW_DATA_DIR`.

## Contract proof

Run a completed session:

```bash
spec-interview start \
  --provider mock \
  --message "The runtime is a service and the CLI is a participant." \
  --data-dir ./proof-sessions \
  --plain
```

Run an interrupted session:

```bash
spec-interview start \
  --provider mock \
  --message "Explain the deliberately fragile assumption in detail." \
  --interrupt-after 0.015 \
  --data-dir ./proof-sessions \
  --plain
```

Resume either session using the UUID returned by `start`:

```bash
spec-interview resume SESSION_ID \
  --message "Now challenge that assumption." \
  --data-dir ./proof-sessions

spec-interview transcript SESSION_ID --data-dir ./proof-sessions
```

Each session directory contains:

- `events.jsonl`: append-only normalized source of truth;
- `checkpoint.json`: atomically replaced recovery state;
- `transcript.txt`: deterministic derived view;
- `summary.md`: basic human-reviewable session summary.

## Commands

```text
spec-interview providers list [--plain]
spec-interview devices list
spec-interview doctor [--plain]
spec-interview start --provider {mock,parlor-gemma,nova-sonic}
spec-interview resume SESSION_ID
spec-interview transcript SESSION_ID
spec-interview sessions list [--plain]
```

`start` for `parlor-gemma` and `nova-sonic` fails with an actionable message until their
live transport slices are implemented and validated. `doctor` is safe and does not start a
session.

## Development

```bash
ruff check .
ruff format --check .
mypy
pytest
docker build -t spec-interview:dev .
```

The default test suite does not require AWS credentials, a browser, audio hardware, local
models, or optional provider dependencies.

## Provider extras

```bash
pip install -e '.[aws]'    # boto3 prerequisite detection for Nova Sonic
pip install -e '.[audio]'  # sounddevice-backed device listing
```

For the current validation boundary and remaining work, see
[`docs/validation/ACCEPTANCE.md`](docs/validation/ACCEPTANCE.md). The authoritative product
brief is [`docs/START-HERE.md`](docs/START-HERE.md).

## Status

Fully implemented and tested in the cloud proof:

- strict public models and discriminated normalized events;
- manager sequencing and provider-neutral lifecycle;
- deterministic streaming mock provider;
- mid-response interruption with partial output preservation;
- append-only JSONL, truncated-tail recovery, checkpoint/resume, transcript, and summary;
- CLI plus plain JSON output;
- fixture-level Parlor and Nova event translation;
- provider diagnostics and explicit unavailable states.

Not yet claimed:

- live Parlor/Gemma WebSocket and browser audio;
- microphone, playback, Bluetooth routing, VAD, and barge-in on macOS;
- live Bedrock bidirectional streaming or Nova session renewal;
- interview policy, Opus architect, or automatic repository edits.

