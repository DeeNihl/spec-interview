"""Speech output provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SpeechProvider(ABC):
    """Turn completed semantic text into audible output."""

    name: str
    interruptible: bool

    @abstractmethod
    async def available(self) -> bool: ...

    @abstractmethod
    async def speak(self, text: str) -> None: ...

    @abstractmethod
    async def interrupt(self) -> None: ...
