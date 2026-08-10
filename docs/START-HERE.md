# spec-interview

## Project Brief and Implementation Handoff

**Status:** Approved for prototype implementation  
**Canonical repository:** `spec-interview`  
**Python package:** `spec_interview`  
**CLI command:** `spec-interview`

> A provider-neutral conversational system for eliciting, challenging, and documenting technical specifications.

## 1. Start Here

Build `spec-interview` as a standalone Python library and CLI. Its first job is to prove that substantially different conversational-audio systems can operate behind one stable manager/provider contract while sharing the same event model, persistence, checkpointing, and command-line experience.

This is an implementation project, not another architecture exercise. The prototype should produce working code, automated tests, reproducible setup, and honest evidence about what was and was not validated.

The initial slice does **not** need the larger agent framework, Protocol Manager, TMNT, Claude Code automation, or an autonomous repository editor. Those are possible consumers after the standalone seam has proved itself.

## 2. Product Intent

`spec-interview` conducts a sustained technical interview that helps a person turn an emerging design into a reviewable specification. The system should behave like a technically capable peer: curious, grounded, willing to challenge assumptions, and able to distinguish confirmed decisions from unresolved questions.

The longer-term experience is a 30–120 minute, interruptible spoken design session that can:

- clarify the problem, beneficiaries, and success conditions;
- elicit components, boundaries, data flows, and dependencies;
- identify assumptions, constraints, risks, and fragile areas;
- compare alternatives and make trade-offs explicit;
- consult a deeper architect model asynchronously;
- survive provider renewals, disconnections, and process restarts;
- generate a structured, human-reviewable specification record.

The first prototype is narrower. It answers one architectural question:

> Can two genuinely different conversational implementations behave as interchangeable providers through one usable Python manager and CLI?

## 3. Decisions Already Made

These are closed decisions for the prototype unless implementation evidence shows that one is infeasible.

| Decision | Rationale |
|---|---|
| Standalone Python project | Proves the boundary before coupling it to the larger framework. |
| Manager, factory, and provider ABC | Supports explicit lifecycle ownership and interchangeable implementations. |
| Async-first core | Duplex audio, events, cancellation, tools, and renewal are inherently concurrent. |
| Capability negotiation | Providers must expose real differences instead of pretending to be identical. |
| Normalized typed events | Session state and consumers must not depend on Parlor-, Gemma-, or AWS-specific payloads. |
| JSONL event history plus checkpoints | Keeps an auditable timeline while allowing fast recovery. |
| CLI as the first control surface | Provides a small, testable operating interface before committing to a larger UI. |
| Compact browser audio window | Reuses browser microphone, playback, VAD, and barge-in behavior without a full desktop shell. |
| Direct Nova integration first | Establishes the native protocol boundary; Strands may later sit behind the provider. |
| Repository output is review-only | The prototype may inspect context and propose Markdown, but does not edit another repository automatically. |
| Platform-neutral core | Do not hardcode macOS, CoreAudio, `localhost`, or a co-located microphone and runtime. |
| Android is a local client | The Z Fold runs LiteRT-LM, bounded Termux microphone capture, and Android system TTS locally; continuous VAD and barge-in remain later slices. |

## 4. Architectural Boundary

The prototype has four primary responsibilities:

1. **Conversation runtime** — provider selection, lifecycle, duplex event flow, interruption, and session state.
2. **Provider adapters** — local Parlor/Gemma, Bedrock Nova Sonic, and deterministic mock behavior.
3. **Persistence** — append-only normalized events, checkpoints, transcripts, and basic session summaries.
4. **CLI** — start, observe, interrupt, resume, diagnose, and review sessions.

The future interviewer and architect roles should remain conceptually separate from audio transport:

```text
ConversationManager
    -> ConversationProvider

InterviewManager                 # later vertical slice
    -> InterviewPolicy
    -> ArchitectProvider

ArtifactManager                  # later vertical slice
    -> ArtifactProvider
```

The distinction matters:

- `ConversationProvider` owns audio/session mechanics.
- `InterviewPolicy` decides what to ask and when to probe.
- `ArchitectProvider` performs deeper technical review.
- `ArtifactProvider` renders confirmed state into proposed artifacts.
- The CLI coordinates these parts without becoming their implementation.

## 5. Provider Model

### 5.1 Public provider contract

The exact signatures may evolve, but the public contract should support this lifecycle:

```python
class ConversationProvider(ABC):
    capabilities: ConversationCapabilities

    async def start_session(self, context: SessionContext) -> SessionHandle: ...
    async def send_audio(self, chunk: AudioChunk) -> None: ...
    async def events(self) -> AsyncIterator[ConversationEvent]: ...
    async def interrupt(self) -> None: ...
    async def submit_tool_result(self, result: ToolResult) -> None: ...
    async def checkpoint(self) -> ConversationCheckpoint: ...
    async def restore(self, checkpoint: ConversationCheckpoint) -> None: ...
    async def close(self) -> SessionSummary: ...
```

Public models should use strict typing, preferably Pydantic v2. Provider SDK objects and provider-specific events must not leak through the public interfaces.

### 5.2 Capabilities

At minimum, providers should truthfully report:

```text
native_audio
native_vad
barge_in
async_tools
session_renewal
local_execution
text_injection
transcript_events
```

The manager normalizes external behavior but does not erase meaningful provider differences. Unsupported operations should fail explicitly or use a documented fallback.

### 5.3 Initial providers

#### `MockConversationProvider`

This is a fully functional, deterministic provider and the primary contract proof. It must support:

- session startup and orderly shutdown;
- scripted transcript and response streaming;
- interruption of an in-progress response;
- preservation of interrupted output in event history;
- deterministic event ordering;
- checkpoint and resume;
- configurable timing without slow tests;
- CLI demonstrations and integration tests.

#### `LocalParlorGemmaProvider`

Wrap or adapt Parlor's existing conversational pipeline rather than copying it wholesale. Preserve attribution and licensing. Parlor's useful browser-side behaviors include microphone capture, Silero VAD, WebSocket audio transport, playback, and barge-in.

If live model or audio dependencies are unavailable in the cloud environment, still implement and test:

- configuration and dependency detection;
- launch and health-check behavior;
- lifecycle and cancellation;
- the executable service boundary;
- translation of recorded/simulated Parlor events;
- clear local launch instructions;
- a compact Chrome app-mode audio window path.

Do not claim live audio validation unless it actually occurred.

#### `BedrockNovaSonicProvider`

Implement Amazon Bedrock Nova Sonic bidirectional streaming behind the same contract. Keep AWS event shapes inside the adapter. Translate them into normalized events and design explicitly for connection renewal and continuity.

If credentials, model access, region support, or audio hardware are unavailable, implement and test through the protocol boundary using recorded or simulated AWS event streams. Live validation remains a named acceptance step, not a reason to omit the adapter.

Strands must not be a mandatory dependency in the initial proof. It may later become an alternate internal implementation behind this provider.

## 6. Normalized Event Model

Every event should contain at least:

```python
class ConversationEvent(BaseModel):
    session_id: UUID
    sequence: int
    timestamp: datetime
    source: EventSource
    payload: EventPayload
```

Initial payload types should include:

```text
SessionStarted
SessionStateChanged
AudioInputStarted
AudioInputStopped
TranscriptDelta
TranscriptFinalized
ResponseStarted
ResponseDelta
ResponseInterrupted
ResponseCompleted
ProviderWarning
ProviderError
CheckpointCreated
SessionResumed
SessionStopped
```

Reserve or add later when the interview vertical slice begins:

```text
ArchitectConsultationRequested
ArchitectInterventionReady
DecisionRecorded
ConstraintRecorded
AssumptionRecorded
QuestionOpened
QuestionResolved
ArtifactProposed
```

Events are the durable seam. Ordering, cancellation, interruption semantics, and replay must be tested independently of any live audio system.

## 7. Persistence and Recovery

Use append-only JSONL as the authoritative event history for the prototype. A session directory should also contain a compact checkpoint and generated views such as a transcript and Markdown summary.

Required behavior:

- monotonic event sequence within a session;
- atomic or recoverable checkpoint writes;
- safe handling of a truncated final JSONL line;
- no loss of completed or interrupted transcript content;
- resume without replaying side effects;
- provider renewal represented in the event stream;
- deterministic regeneration of transcript and summary views.

Do not confuse provider session identity with `spec-interview` session identity. A single interview may span multiple provider connections.

## 8. CLI

The first CLI should provide at least:

```bash
spec-interview providers list
spec-interview devices list
spec-interview doctor
spec-interview start --provider mock
spec-interview start --provider parlor-gemma
spec-interview start --provider nova-sonic
spec-interview resume <session-id>
spec-interview transcript <session-id>
spec-interview sessions list
```

The live terminal view should show:

- selected provider and capabilities;
- stable interview session ID;
- listening, processing, speaking, interrupted, paused, or stopped state;
- recent finalized transcript lines;
- event count and last checkpoint;
- actionable provider health or configuration errors.

The CLI must remain usable in a non-interactive/test environment. Rich output should have a plain-output mode.

## 9. Suggested Package Layout

```text
spec-interview/
|-- src/spec_interview/
|   |-- conversation/       # manager, contracts, capabilities, events
|   |-- providers/          # mock, Parlor/Gemma, Nova Sonic
|   |-- sessions/           # event store, checkpoint, replay, views
|   |-- cli/                # commands and terminal presentation
|   `-- config/             # typed configuration and factory
|-- tests/
|   |-- unit/
|   |-- integration/
|   `-- fixtures/           # recorded/simulated provider events
|-- docs/
|   |-- design/
|   `-- validation/
|-- Dockerfile
|-- compose.yaml
|-- .devcontainer/
|-- pyproject.toml
|-- README.md
`-- AGENTS.md
```

Optional provider dependencies should be installable as extras. The mock-provider test suite must not require AWS, local models, a browser, or audio hardware.

## 10. Interview Behavior Direction

The initial contract proof does not need a full interview policy, but its domain model should leave room for these structured records:

```text
Problem
Beneficiary
SuccessCondition
Component
Boundary
Dependency
Evidence
Decision
Constraint
Assumption
Risk
Alternative
OpenQuestion
NextStep
```

The later policy should move conversationally through:

1. framing the problem and desired outcome;
2. exploring components, boundaries, and flows;
3. evaluating fragility, alternatives, and trade-offs;
4. reality-testing load, failure, evolution, and MVP scope;
5. confirming decisions and unresolved questions;
6. producing a concise specification and next-step proposal.

It should sound like a technical peer, not a questionnaire reader. The script is a repertoire of probes, not a mandatory linear sequence.

## 11. Prototype Scope

### Must implement now

- Python 3.12+ package and reproducible development setup;
- `ConversationManager`, provider ABC, factory, and typed configuration;
- typed capabilities and normalized event union;
- deterministic mock provider;
- JSONL event store, checkpoint, resume, transcript, and summary;
- usable CLI and plain-output mode;
- Parlor/Gemma adapter boundary and fixtures;
- Nova Sonic adapter boundary and fixtures;
- reliable cancellation and shutdown;
- Ruff, type checking, Pytest, and relevant integration tests;
- Dockerfile, development container configuration, README, AGENTS, and validation guides.

### Implement only if the environment supports honest validation

- live Parlor/Gemma conversation;
- real microphone, playback, Bluetooth routing, and barge-in;
- live Nova Sonic streaming through Bedrock;
- connection renewal against a real Nova session.

### Deliberately deferred

- Opus shadow architect and asynchronous intervention policy;
- full structured interview state machine;
- Protocol Manager, TMNT, or larger-framework integration;
- typed-agent packaging;
- automatic repository edits or Claude Code invocation;
- native desktop or Android applications;
- public multi-user service, identity, authorization, or internet exposure;
- a native Android GUI or unattended foreground-service lifecycle.

## 12. Implementation Sequence

1. Read this brief and the two supporting design PDFs.
2. Record a concise implementation plan; continue directly into implementation.
3. Build the provider-neutral models, manager, and deterministic mock provider.
4. Add JSONL persistence, replay, checkpoints, transcript views, and resume.
5. Build the CLI and demonstrate interrupt/resume through the mock provider.
6. Add the Parlor/Gemma adapter boundary, fixtures, health checks, and documentation.
7. Add the Nova Sonic adapter boundary, fixtures, renewal design, and documentation.
8. Add Docker and development-container support.
9. Run formatting, linting, type checking, tests, and safe smoke tests.
10. Correct the documentation to describe only what genuinely works.

Do not stop after planning or scaffolding. Complete as many vertical slices as the environment allows.

## 13. Acceptance Criteria

The cloud proof succeeds when:

- the same manager, CLI, event store, and event consumers operate unchanged when the provider configuration changes;
- a scripted mock session can start, stream, be interrupted, stop, resume, and finish;
- interrupted response content remains visible and correctly typed;
- normalized event order is deterministic and validated;
- a completed transcript and Markdown summary can be regenerated from stored events;
- the process handles cancellation without hanging or corrupting the session;
- Parlor and Nova adapters translate representative fixtures without leaking provider types;
- tests run without AWS credentials, local models, audio devices, or optional provider packages;
- Docker and local Python setup paths are documented and tested where possible;
- documentation clearly separates tested behavior from hardware- or credential-dependent validation.

The later Mac acceptance test succeeds when:

- a 15-minute spoken session works with real input and output;
- natural barge-in interrupts playback and records both sides accurately;
- an audio-device disconnect does not lose the interview record;
- checkpoint and resume work across a process restart;
- the same user workflow can be exercised with Parlor/Gemma and Nova Sonic;
- observed latency, transcript quality, interruption behavior, stability, and cost can be compared.

## 14. Required Final Implementation Report

Codex should finish with evidence grouped as:

1. fully implemented and tested;
2. implemented but requiring Mac audio validation;
3. implemented but requiring AWS credentials/model access;
4. deliberately deferred;
5. exact commands for the remaining Mac and AWS acceptance tests;
6. known limitations and recommended next vertical slice.

Include the actual commands and summarized results for tests, lint, type checking, Docker build, and the two simulated CLI demonstrations. Do not describe unrun checks as passing.

## 15. Supporting Design Documents

These documents retain the deeper rationale and roadmap. Their older `idea_architect` filenames predate the final project name; they describe the same project now canonically named `spec-interview`.

1. `idea_architect_parlor_recommendations_roadmap.pdf`  
   Product direction, Parlor-based interaction shell, sequencing, roadmap, release gates, and validation metrics.

2. `idea_architect_standalone_library_design.pdf`  
   Detailed standalone manager/provider design, contracts, normalized events, CLI, checkpoint semantics, test strategy, and future integration shapes.

If the brief and a supporting PDF appear to differ, follow this brief for name, current scope, Android priority, and implementation authority. Use the PDFs for deeper design rationale.

## 16. Immediate Instruction to Codex

> Build a working proof of concept for `spec-interview` from this brief and the supporting PDFs. This is an implementation task. Do not stop after writing a plan or scaffolding. Make reasonable decisions where details are missing, preserve the provider-neutral boundary, run every safe validation available, and report honestly what genuinely works.
