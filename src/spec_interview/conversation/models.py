"""Public provider-neutral data models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConversationState(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    PAUSED = "paused"
    STOPPED = "stopped"


class EventSource(StrEnum):
    MANAGER = "manager"
    PROVIDER = "provider"
    USER = "user"
    SYSTEM = "system"


class ConversationCapabilities(StrictModel):
    native_audio: bool = False
    native_vad: bool = False
    barge_in: bool = False
    async_tools: bool = False
    session_renewal: bool = False
    local_execution: bool = False
    text_injection: bool = False
    transcript_events: bool = False


class SessionContext(StrictModel):
    session_id: UUID
    provider: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, str] = Field(default_factory=dict)


class SessionHandle(StrictModel):
    session_id: UUID
    provider_session_id: str


class AudioChunk(StrictModel):
    data: bytes
    sample_rate_hz: int = 16_000
    channels: int = 1
    encoding: Literal["pcm_s16le", "wav", "opus", "aac", "amr_wb", "amr_nb"] = "pcm_s16le"
    is_final: bool = True


class ToolResult(StrictModel):
    tool_call_id: str
    content: str
    is_error: bool = False


class ConversationCheckpoint(StrictModel):
    session_id: UUID
    provider: str
    last_sequence: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider_state: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class SessionSummary(StrictModel):
    session_id: UUID
    provider: str
    event_count: int
    final_state: ConversationState
    transcript_lines: int = 0


class SessionStarted(StrictModel):
    type: Literal["session_started"] = "session_started"
    provider: str
    provider_session_id: str


class SessionStateChanged(StrictModel):
    type: Literal["session_state_changed"] = "session_state_changed"
    previous: ConversationState
    current: ConversationState


class AudioInputStarted(StrictModel):
    type: Literal["audio_input_started"] = "audio_input_started"


class AudioInputStopped(StrictModel):
    type: Literal["audio_input_stopped"] = "audio_input_stopped"


class TranscriptDelta(StrictModel):
    type: Literal["transcript_delta"] = "transcript_delta"
    text: str
    role: Literal["user", "assistant"] = "user"


class TranscriptFinalized(StrictModel):
    type: Literal["transcript_finalized"] = "transcript_finalized"
    text: str
    role: Literal["user", "assistant"] = "user"


class ResponseStarted(StrictModel):
    type: Literal["response_started"] = "response_started"


class ResponseDelta(StrictModel):
    type: Literal["response_delta"] = "response_delta"
    text: str


class ResponseInterrupted(StrictModel):
    type: Literal["response_interrupted"] = "response_interrupted"
    text: str
    reason: str = "user_barge_in"


class ResponseCompleted(StrictModel):
    type: Literal["response_completed"] = "response_completed"
    text: str


class ProviderWarning(StrictModel):
    type: Literal["provider_warning"] = "provider_warning"
    message: str
    code: str | None = None


class ProviderError(StrictModel):
    type: Literal["provider_error"] = "provider_error"
    message: str
    code: str | None = None
    retryable: bool = False


class CheckpointCreated(StrictModel):
    type: Literal["checkpoint_created"] = "checkpoint_created"
    last_sequence: int


class SessionResumed(StrictModel):
    type: Literal["session_resumed"] = "session_resumed"
    from_sequence: int


class SessionStopped(StrictModel):
    type: Literal["session_stopped"] = "session_stopped"
    reason: str = "completed"


EventPayload = Annotated[
    SessionStarted
    | SessionStateChanged
    | AudioInputStarted
    | AudioInputStopped
    | TranscriptDelta
    | TranscriptFinalized
    | ResponseStarted
    | ResponseDelta
    | ResponseInterrupted
    | ResponseCompleted
    | ProviderWarning
    | ProviderError
    | CheckpointCreated
    | SessionResumed
    | SessionStopped,
    Field(discriminator="type"),
]


class ConversationEvent(StrictModel):
    session_id: UUID
    sequence: int = Field(ge=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: EventSource
    payload: EventPayload


class ProviderStatus(StrictModel):
    name: str
    available: bool
    detail: str
    capabilities: ConversationCapabilities
