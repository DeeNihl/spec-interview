from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

from spec_interview.conversation.manager import ConversationManager
from spec_interview.providers.mock import MockConversationProvider
from spec_interview.sessions import SessionStore


@pytest.mark.asyncio
async def test_manager_sequences_persists_checkpoints_and_resumes(tmp_path) -> None:
    store = SessionStore(tmp_path)
    first_provider = MockConversationProvider(
        responses={"first": "a deliberately longer response"}, delay_seconds=0.02
    )
    first = ConversationManager(first_provider, store)
    await first.start()
    before = first.last_sequence
    await first.send_text("first")
    await asyncio.sleep(0.025)
    await first.interrupt()
    terminal = await first.wait_for_response(before)
    assert terminal.payload.type == "response_interrupted"
    await first.create_checkpoint()
    session_id = first.session_id
    await first.close()

    second_provider = MockConversationProvider(responses={"second": "complete"}, delay_seconds=0)
    second = ConversationManager(second_provider, store, session_id=session_id)
    await second.resume()
    before = second.last_sequence
    await second.send_text("second")
    terminal = await second.wait_for_response(before)
    assert terminal.payload.type == "response_completed"
    await second.create_checkpoint()
    await second.close()

    events = store.read_events(session_id)
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert sum(event.payload.type == "session_resumed" for event in events) == 1
    transcript = store.render_transcript(session_id)
    assert "Assistant [interrupted]" in transcript
    assert "Assistant: complete" in transcript
    assert store.checkpoint_path(session_id).exists()
    assert (store.session_dir(session_id) / "summary.md").exists()


@pytest.mark.asyncio
async def test_resume_rejects_wrong_provider(tmp_path) -> None:
    store = SessionStore(tmp_path)
    provider = MockConversationProvider(delay_seconds=0)
    manager = ConversationManager(provider, store)
    await manager.start()
    await manager.create_checkpoint()
    await manager.close()
    checkpoint_path = store.checkpoint_path(manager.session_id)
    contents = checkpoint_path.read_text(encoding="utf-8").replace('"mock"', '"nova-sonic"')
    checkpoint_path.write_text(contents, encoding="utf-8")

    resumed = ConversationManager(MockConversationProvider(), store, manager.session_id)
    with pytest.raises(ValueError, match="requires provider"):
        await resumed.resume()


def test_session_ids_are_valid_uuid(tmp_path) -> None:
    store = SessionStore(tmp_path)
    manager = ConversationManager(MockConversationProvider(), store)
    assert UUID(str(manager.session_id)) == manager.session_id
