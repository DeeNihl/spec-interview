from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from spec_interview.conversation.models import (
    ConversationEvent,
    EventSource,
    ResponseInterrupted,
    TranscriptFinalized,
)
from spec_interview.sessions import SessionStore


def test_store_ignores_truncated_final_line(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session_id = uuid4()
    event = ConversationEvent(
        session_id=session_id,
        sequence=1,
        timestamp=datetime.now(UTC),
        source=EventSource.USER,
        payload=TranscriptFinalized(text="hello"),
    )
    store.append(event)
    with store.events_path(session_id).open("a", encoding="utf-8") as handle:
        handle.write('{"incomplete":')
    assert store.read_events(session_id) == [event]


def test_transcript_preserves_interrupted_assistant_text(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session_id = uuid4()
    for sequence, payload in enumerate(
        [TranscriptFinalized(text="hello"), ResponseInterrupted(text="partial answer")], start=1
    ):
        store.append(
            ConversationEvent(
                session_id=session_id,
                sequence=sequence,
                source=EventSource.PROVIDER,
                payload=payload,
            )
        )
    assert store.render_transcript(session_id) == (
        "You: hello\nAssistant [interrupted]: partial answer\n"
    )


def test_summary_is_deterministic(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session_id = uuid4()
    store.append(
        ConversationEvent(
            session_id=session_id,
            sequence=1,
            source=EventSource.USER,
            payload=TranscriptFinalized(text="a boundary"),
        )
    )
    assert store.render_summary(session_id) == store.render_summary(session_id)
