from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from spec_interview.conversation.models import SessionContext
from spec_interview.providers.mock import MockConversationProvider


@pytest.mark.asyncio
async def test_mock_streams_completed_response() -> None:
    provider = MockConversationProvider(responses={"hello": "one two"}, delay_seconds=0)
    session_id = uuid4()
    await provider.start_session(SessionContext(session_id=session_id, provider=provider.name))
    await provider.send_text("hello")
    await provider.wait_until_idle()
    await provider.close()

    events = [event async for event in provider.events()]
    types = [event.payload.type for event in events]
    assert types == [
        "session_started",
        "session_state_changed",
        "transcript_finalized",
        "session_state_changed",
        "response_started",
        "session_state_changed",
        "response_delta",
        "response_delta",
        "response_completed",
        "session_state_changed",
        "session_state_changed",
        "session_stopped",
    ]


@pytest.mark.asyncio
async def test_mock_preserves_partial_text_when_interrupted() -> None:
    provider = MockConversationProvider(
        responses={"hello": "one two three four"}, delay_seconds=0.02
    )
    session_id = uuid4()
    await provider.start_session(SessionContext(session_id=session_id, provider=provider.name))
    await provider.send_text("hello")
    await asyncio.sleep(0.025)
    await provider.interrupt()
    await provider.close()

    events = [event async for event in provider.events()]
    interrupted = [
        event.payload for event in events if event.payload.type == "response_interrupted"
    ]
    assert len(interrupted) == 1
    assert interrupted[0].text
    assert interrupted[0].text != "one two three four"
