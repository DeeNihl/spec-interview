"""Conversation provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from spec_interview.conversation.models import (
    AudioChunk,
    ConversationCapabilities,
    ConversationCheckpoint,
    ConversationEvent,
    ProviderStatus,
    SessionContext,
    SessionHandle,
    SessionSummary,
    ToolResult,
)


class ConversationProvider(ABC):
    """Provider-neutral lifecycle for a duplex conversation implementation."""

    name: str
    capabilities: ConversationCapabilities

    @abstractmethod
    async def start_session(self, context: SessionContext) -> SessionHandle: ...

    @abstractmethod
    async def send_audio(self, chunk: AudioChunk) -> None: ...

    @abstractmethod
    async def send_text(self, text: str) -> None: ...

    @abstractmethod
    def events(self) -> AsyncIterator[ConversationEvent]: ...

    @abstractmethod
    async def interrupt(self) -> None: ...

    @abstractmethod
    async def submit_tool_result(self, result: ToolResult) -> None: ...

    @abstractmethod
    async def checkpoint(self, last_sequence: int) -> ConversationCheckpoint: ...

    @abstractmethod
    async def restore(self, checkpoint: ConversationCheckpoint) -> None: ...

    @abstractmethod
    async def close(self) -> SessionSummary: ...

    @abstractmethod
    async def status(self) -> ProviderStatus: ...


class ProviderUnavailableError(RuntimeError):
    """Raised when an optional provider cannot run in the current environment."""
