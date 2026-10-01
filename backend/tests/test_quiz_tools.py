"""Tests for the thin langchain-tavily tool wrappers (design D4)."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.tools import ToolException

from app.core.config import settings
from app.llm.quiz_tools import (
    GroundedTavilyExtract,
    GroundedTavilySearch,
    create_grounded_tools,
)

SEARCH_SUCCESS = {
    "query": "harness engineering",
    "results": [
        {"title": "Harness Engineering - example.com", "url": "https://example.com/he", "content": "snippet"},
        {"title": "", "url": "https://example.org/no-title", "content": "snippet"},
    ],
    "response_time": 0.4,
}


def _make_search_tool(monkeypatch) -> GroundedTavilySearch:
    tool = GroundedTavilySearch(
        max_results=6,
        topic="general",
        tavily_api_key="test-key",
    )
    wrapper = Mock()
    wrapper.raw_results = Mock(return_value=SEARCH_SUCCESS)
    wrapper.raw_results_async = AsyncMock(return_value=SEARCH_SUCCESS)
    monkeypatch.setattr(tool, "api_wrapper", wrapper)
    return tool


def _make_extract_tool(monkeypatch, results=None, failed=None) -> GroundedTavilyExtract:
    tool = GroundedTavilyExtract(extract_depth="basic", tavily_api_key="test-key")
    payload = {
        "results": results if results is not None else [{"url": "https://example.com/he", "raw_content": "page"}],
        "failed_results": failed or [],
        "response_time": 0.2,
    }
    wrapper = Mock()
    wrapper.raw_results = Mock(return_value=payload)
    wrapper.raw_results_async = AsyncMock(return_value=payload)
    monkeypatch.setattr(tool, "apiwrapper", wrapper)
    return tool


def test_search_success_records_ok_and_sources(monkeypatch):
    tool = _make_search_tool(monkeypatch)

    result = tool.invoke({"query": "harness engineering"})

    assert result is SEARCH_SUCCESS
    assert len(tool.call_log) == 1
    record = tool.call_log[0]
    assert record.status == "ok"
    assert record.sources[0].title == "Harness Engineering - example.com"
    # Empty title falls back to the URL.
    assert record.sources[1].title == "https://example.org/no-title"


@pytest.mark.asyncio
async def test_search_success_async(monkeypatch):
    tool = _make_search_tool(monkeypatch)

    await tool.ainvoke({"query": "harness engineering", "search_depth": "advanced"})

    assert tool.call_log[0].status == "ok"
    tool.api_wrapper.raw_results_async.assert_awaited_once()


def test_search_zero_results_recorded_as_empty_and_reraised(monkeypatch):
    tool = _make_search_tool(monkeypatch)
    tool.api_wrapper.raw_results = Mock(side_effect=ToolException("No search results found for 'zzz'."))

    # handle_tool_error=True turns the ToolException into the message the
    # agent sees instead of raising out of invoke().
    result = tool.invoke({"query": "zzz"})

    assert isinstance(result, str) and "No search results found" in result
    assert tool.call_log[0].status == "empty"
    assert tool.call_log[0].query == "zzz"


def test_search_provider_timeout_is_normalised(monkeypatch):
    tool = _make_search_tool(monkeypatch)
    # The real wrapper raises; the upstream tool catches it into {"error": e}.
    tool.api_wrapper.raw_results = Mock(side_effect=asyncio.TimeoutError("timed out"))

    result = tool.invoke({"query": "harness engineering"})

    assert result == {"tavily_error": "timeout"}
    assert tool.call_log[0].status == "error"
    assert tool.call_log[0].category == "timeout"


def test_search_auth_error_is_classified(monkeypatch):
    tool = _make_search_tool(monkeypatch)
    tool.api_wrapper.raw_results = Mock(side_effect=Exception("401 Unauthorized: invalid api key"))

    result = tool.invoke({"query": "harness engineering"})

    assert result == {"tavily_error": "auth"}
    assert tool.call_log[0].category == "auth"


def test_extract_success_records_urls_and_failures(monkeypatch):
    tool = _make_extract_tool(
        monkeypatch,
        results=[{"url": "https://a.com", "raw_content": "x"}],
        failed=[{"url": "https://b.com"}],
    )

    result = tool.invoke({"urls": ["https://a.com", "https://b.com"]})

    assert len(tool.call_log) == 1
    record = tool.call_log[0]
    assert record.status == "ok"
    assert record.sources[0].url == "https://a.com"
    assert record.failed_urls == ("https://b.com",)


def test_extract_all_failed_recorded_as_empty_and_reraised(monkeypatch):
    tool = _make_extract_tool(monkeypatch, results=[], failed=[{"url": "https://dead.com"}])

    result = tool.invoke({"urls": ["https://dead.com"]})

    assert isinstance(result, str) and "No extracted results found" in result
    assert tool.call_log[0].status == "empty"
    assert tool.call_log[0].failed_urls == ("https://dead.com",)


def test_extract_provider_error_is_normalised(monkeypatch):
    tool = _make_extract_tool(monkeypatch)
    tool.apiwrapper.raw_results = Mock(side_effect=ConnectionError("connection refused"))

    result = tool.invoke({"urls": ["https://a.com"]})

    assert result == {"tavily_error": "network"}
    assert tool.call_log[0].category == "network"


def test_create_grounded_tools_applies_settings(monkeypatch):
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "key-from-settings")
    monkeypatch.setattr(settings, "TAVILY_MAX_RESULTS", 6)

    search, extract = create_grounded_tools()

    assert search.max_results == 6
    assert search.topic == "general"
    assert search.search_depth == "basic"
    assert search.include_answer is False
    assert search.include_raw_content is False
    assert extract.extract_depth == "basic"


def test_official_tool_argument_surface_matches_docs():
    """Task 3.2 — the invocation-time argument surface the agent can fill."""

    from langchain_tavily.tavily_extract import TavilyExtractInput
    from langchain_tavily.tavily_search import TavilySearchInput

    search_fields = set(TavilySearchInput.model_fields.keys())
    assert {"query", "search_depth", "time_range", "include_domains", "exclude_domains", "topic"} <= search_fields

    extract_fields = set(TavilyExtractInput.model_fields.keys())
    assert {"urls", "extract_depth", "query"} <= extract_fields
