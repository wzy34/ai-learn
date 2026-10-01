"""Tests for the retrieval service's three-state aggregation (design D6)."""

from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.core.exceptions import SearchNoResultsError
from app.llm.quiz_agent import AgentUnavailableError, AgentRunResult
from app.llm.quiz_tools import RetrievedSource, ToolCallRecord
from app.services.retrieval_service import (
    RetrievalOutcome,
    RetrievalService,
    get_retrieval_service,
)


def _record(tool: str, status: str, category: str = "", failed_urls=()) -> ToolCallRecord:
    sources = (RetrievedSource(title="t", url="https://example.com"),) if status == "ok" else ()
    return ToolCallRecord(
        tool=tool,
        status=status,
        category=category,
        query="q",
        sources=sources,
        failed_urls=failed_urls,
    )


def _patch_agent(monkeypatch, result: AgentRunResult | Exception):
    fake = type("A", (), {})()
    if isinstance(result, Exception):
        fake.generate = AsyncMock(side_effect=result)
    else:
        fake.generate = AsyncMock(return_value=result)
    monkeypatch.setattr("app.services.retrieval_service.get_quiz_agent", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def _configured_key(monkeypatch):
    """Local .env has no TAVILY_API_KEY; the guard tests override this."""
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-key")


@pytest.mark.asyncio
async def test_usable_material_yields_ok(monkeypatch):
    records = [_record("tavily_search", "ok"), _record("tavily_extract", "ok")]
    sources = [RetrievedSource(title="t", url="https://example.com")]
    _patch_agent(monkeypatch, AgentRunResult(response_text="{}", records=records, sources=sources))

    result = await RetrievalService().run(user_input="x")

    assert result.outcome == RetrievalOutcome.OK
    assert result.response_text == "{}"
    assert result.sources == sources


@pytest.mark.asyncio
async def test_all_empty_search_raises_no_results(monkeypatch):
    _patch_agent(monkeypatch, AgentRunResult(
        response_text="{}",
        records=[_record("tavily_search", "empty")],
    ))

    with pytest.raises(SearchNoResultsError) as exc_info:
        await RetrievalService().run(user_input="生造词")

    assert "换个说法" in exc_info.value.detail


@pytest.mark.asyncio
async def test_extract_only_empty_points_at_the_link(monkeypatch):
    _patch_agent(monkeypatch, AgentRunResult(
        response_text="{}",
        records=[_record("tavily_extract", "empty", failed_urls=("https://dead.com",))],
    ))

    with pytest.raises(SearchNoResultsError) as exc_info:
        await RetrievalService().run(user_input="https://dead.com")

    assert "链接" in exc_info.value.detail


@pytest.mark.asyncio
async def test_all_failed_calls_degrade(monkeypatch):
    _patch_agent(monkeypatch, AgentRunResult(
        response_text="{}",
        records=[_record("tavily_search", "error", category="timeout")],
    ))

    result = await RetrievalService().run(user_input="x")

    assert result.outcome == RetrievalOutcome.UNAVAILABLE


@pytest.mark.asyncio
async def test_mixed_empty_and_error_degrades(monkeypatch):
    _patch_agent(monkeypatch, AgentRunResult(
        response_text="{}",
        records=[_record("tavily_search", "empty"), _record("tavily_extract", "error", category="server")],
    ))

    result = await RetrievalService().run(user_input="x")

    assert result.outcome == RetrievalOutcome.UNAVAILABLE


@pytest.mark.asyncio
async def test_no_tool_calls_degrades(monkeypatch):
    _patch_agent(monkeypatch, AgentRunResult(response_text="{}", records=[]))

    result = await RetrievalService().run(user_input="x")

    assert result.outcome == RetrievalOutcome.UNAVAILABLE


@pytest.mark.asyncio
async def test_agent_unavailable_degrades(monkeypatch):
    _patch_agent(monkeypatch, AgentUnavailableError("timeout"))

    result = await RetrievalService().run(user_input="x")

    assert result.outcome == RetrievalOutcome.UNAVAILABLE


@pytest.mark.asyncio
async def test_disabled_search_skips_the_agent(monkeypatch):
    fake = _patch_agent(monkeypatch, AgentRunResult(response_text="{}", records=[]))
    monkeypatch.setattr(settings, "SEARCH_ENABLED", False)

    result = await RetrievalService().run(user_input="x")

    assert result.outcome == RetrievalOutcome.UNAVAILABLE
    fake.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_api_key_skips_the_agent(monkeypatch):
    fake = _patch_agent(monkeypatch, AgentRunResult(response_text="{}", records=[]))
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")

    result = await RetrievalService().run(user_input="x")

    assert result.outcome == RetrievalOutcome.UNAVAILABLE
    fake.generate.assert_not_awaited()


def test_singleton_is_shared():
    assert get_retrieval_service() is get_retrieval_service()
