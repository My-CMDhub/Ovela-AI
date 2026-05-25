"""
Tests for ADKOrchestrator — Google ADK multi-agent graph routing.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.anyio
async def test_orchestrator_initializes_with_three_agents():
    """Manager + BookingWorker + InfoWorker are registered in graph."""
    from services.adk.graph import ADKOrchestrator
    orc = ADKOrchestrator()
    assert orc.manager.name == "OvelaManager"
    assert orc.booking_worker.name == "BookingWorker"
    assert orc.info_worker.name == "InfoWorker"


@pytest.mark.anyio
async def test_orchestrator_creates_session_per_caller():
    """Each unique call_sid gets an isolated ADK session."""
    from services.adk.graph import ADKOrchestrator
    orc = ADKOrchestrator()

    session_a = await orc.get_or_create_session(user_id="call_sid_aaa")
    session_b = await orc.get_or_create_session(user_id="call_sid_bbb")

    assert session_a.id != session_b.id


@pytest.mark.anyio
async def test_orchestrator_reuses_existing_session():
    """Same call_sid returns the same session (state is preserved)."""
    from services.adk.graph import ADKOrchestrator
    orc = ADKOrchestrator()

    session_a1 = await orc.get_or_create_session(user_id="call_sid_abc")
    session_a2 = await orc.get_or_create_session(user_id="call_sid_abc")

    assert session_a1.id == session_a2.id


@pytest.mark.anyio
async def test_orchestrator_query_returns_string_response():
    """query() returns a non-empty string (mocked LLM response)."""
    from services.adk.graph import ADKOrchestrator

    orc = ADKOrchestrator()

    # Patch runner.run_async to yield a mocked final response event
    mock_event = MagicMock()
    mock_event.is_final_response.return_value = True
    mock_event.content = MagicMock()
    mock_event.content.parts = [MagicMock(text="Checking availability for tomorrow.")]

    async def fake_run_async(**kwargs):
        yield mock_event

    with patch.object(orc.runner, "run_async", side_effect=fake_run_async):
        result = await orc.query(
            user_id="call_sid_test",
            session_id="sess_test",
            text="I want to book a queen room for tomorrow",
        )

    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.anyio
async def test_orchestrator_agents_use_static_instruction_for_caching():
    """Agents must use static_instruction for prompt caching to reduce token overhead."""
    from services.adk.graph import ADKOrchestrator
    orc = ADKOrchestrator()

    assert orc.manager.static_instruction is not None
    assert orc.booking_worker.static_instruction is not None
    assert orc.info_worker.static_instruction is not None
