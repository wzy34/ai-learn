"""Tests for the grounded quiz agent loop (design D1)."""

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import ToolException
from langgraph.errors import GraphRecursionError

from app.core.config import settings
from app.llm.quiz_agent import AgentUnavailableError, QuizAgent
from app.llm.quiz_tools import GroundedTavilyExtract, GroundedTavilySearch

FINAL_JSON = json.dumps({
    "title": "Harness Engineering",
    "summary": "s",
    "questions": [{
        "id": "q1",
        "type": "single",
        "stem": "s?",
        "options": [{"key": "A", "text": "a"}, {"key": "B", "text": "b"}],
        "answer": ["A"],
        "explanation": "e",
        "knowledge_point": "k",
        "difficulty": "easy",
    }],
})


def _search_tool(monkeypatch, raw_results) -> GroundedTavilySearch:
    tool = GroundedTavilySearch(max_results=6, tavily_api_key="test-key")
    wrapper = type("W", (), {})()
    wrapper.raw_results = raw_results
    wrapper.raw_results_async = raw_results
    monkeypatch.setattr(tool, "api_wrapper", wrapper)
    return tool


def _extract_tool(monkeypatch, raw_results) -> GroundedTavilyExtract:
    tool = GroundedTavilyExtract(extract_depth="basic", tavily_api_key="test-key")
    wrapper = type("W", (), {})()
    wrapper.raw_results = raw_results
    wrapper.raw_results_async = raw_results
    monkeypatch.setattr(tool, "apiwrapper", wrapper)
    return tool


class FakeAgent:
    """Scripted stand-in for the compiled langgraph agent.

    Script items: "search"/"extract" invoke the corresponding tool (the way
    the real agent's tool round would), "sleep" stalls past the timeout,
    "raise_recursion" simulates the recursion-limit breach, and callables
    run verbatim.
    """

    def __init__(self, script, tools):
        self.script = list(script)
        self.tools = tools

    async def ainvoke(self, state, config=None):
        for step in self.script:
            if step == "raise_recursion":
                raise GraphRecursionError("recursion limit reached")
            if step == "sleep":
                await asyncio.sleep(0.5)
            elif step == "search":
                self.tools[0].invoke({"query": "Harness Engineering"})
            elif step == "extract":
                self.tools[1].invoke({"urls": ["https://example.com/he"]})
            elif callable(step):
                step()
        return {"messages": [AIMessage(content=FINAL_JSON)]}


def _patch_agent(monkeypatch, script, search_raw_results=None, extract_raw_results=None):
    """Patch create_agent + the tool factory inside the quiz_agent module."""

    def fake_create_agent(model, tools, system_prompt=None):
        return FakeAgent(script, tools)

    def search_default(**kwargs):
        return {
            "query": kwargs.get("query", ""),
            "results": [
                {"title": "Harness Engineering guide", "url": "https://example.com/he", "content": "c"}
            ],
        }

    def extract_default(**kwargs):
        return {
            "results": [{"url": "https://example.com/he", "raw_content": "page"}],
            "failed_results": [],
        }

    def fake_tools():
        return (
            _search_tool(monkeypatch, search_raw_results or search_default),
            _extract_tool(monkeypatch, extract_raw_results or extract_default),
        )

    monkeypatch.setattr("app.llm.quiz_agent.create_agent", fake_create_agent)
    monkeypatch.setattr("app.llm.quiz_agent.create_grounded_tools", fake_tools)


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key_for_testing")
    return QuizAgent()


def test_quiz_prompt_v3_carries_tool_and_grounding_guidance():
    from app.prompts.quiz_prompt import (
        QUIZ_AGENT_SYSTEM_PROMPT,
        QUIZ_SYSTEM_PROMPT_DEGRADED,
    )

    for token in (
        "tavily_search",
        "tavily_extract",
        "search_depth",
        "advanced",
        "time_range",
        "include_domains",
        "https://",
        "同名概念",
        "以资料为准",
    ):
        assert token in QUIZ_AGENT_SYSTEM_PROMPT, f"missing guidance: {token}"

    # The degraded pure-model prompt keeps the conservative notice.
    assert "未经联网核实" in QUIZ_SYSTEM_PROMPT_DEGRADED
    assert "不要编造" in QUIZ_SYSTEM_PROMPT_DEGRADED or "避免编造" in QUIZ_SYSTEM_PROMPT_DEGRADED


@pytest.mark.asyncio
async def test_agent_search_then_answer(agent, monkeypatch):
    captured = {}

    def fake_create_agent(model, tools, system_prompt=None):
        captured["system_prompt"] = system_prompt
        return FakeAgent(["search"], tools)

    _patch_agent(monkeypatch, ["search"])
    monkeypatch.setattr("app.llm.quiz_agent.create_agent", fake_create_agent)

    result = await agent.generate("Harness Engineering 是什么", question_count=5)

    assert "Harness Engineering" in result.response_text
    assert len(result.records) == 1
    assert result.records[0].status == "ok"
    assert result.records[0].query == "Harness Engineering"
    assert result.sources[0].url == "https://example.com/he"
    assert "学习教练" in captured["system_prompt"]


@pytest.mark.asyncio
async def test_agent_extract_then_answer_merges_sources(agent, monkeypatch):
    _patch_agent(monkeypatch, ["search", "extract"])

    result = await agent.generate("https://example.com/he 讲了什么")

    assert [record.status for record in result.records] == ["ok", "ok"]
    assert len(result.sources) == 1  # same URL deduped across search + extract


@pytest.mark.asyncio
async def test_agent_can_skip_retrieval(agent, monkeypatch):
    _patch_agent(monkeypatch, [])

    result = await agent.generate("什么是递归")

    assert result.records == []
    assert result.sources == []
    assert json.loads(result.response_text)["title"] == "Harness Engineering"


@pytest.mark.asyncio
async def test_agent_with_failing_tool_still_answers(agent, monkeypatch):
    def failing(**kwargs):
        raise ConnectionError("connection refused")

    _patch_agent(monkeypatch, ["search"], search_raw_results=failing)

    result = await agent.generate("Harness Engineering")

    assert result.records[0].status == "error"
    assert result.records[0].category == "network"
    assert json.loads(result.response_text)["title"] == "Harness Engineering"


@pytest.mark.asyncio
async def test_agent_with_zero_results_still_answers(agent, monkeypatch):
    def no_results(**kwargs):
        raise ToolException("No search results found for 'zzz'.")

    _patch_agent(monkeypatch, ["search"], search_raw_results=no_results)

    result = await agent.generate("生造词")

    assert result.records[0].status == "empty"
    assert json.loads(result.response_text)["title"] == "Harness Engineering"


@pytest.mark.asyncio
async def test_agent_recursion_limit_raises_unavailable(agent, monkeypatch):
    _patch_agent(monkeypatch, ["raise_recursion"])

    with pytest.raises(AgentUnavailableError):
        await agent.generate("任何主题")


@pytest.mark.asyncio
async def test_agent_timeout_raises_unavailable(agent, monkeypatch):
    _patch_agent(monkeypatch, ["sleep"])
    monkeypatch.setattr(settings, "AGENT_TIMEOUT_SECONDS", 0.05)

    with pytest.raises(AgentUnavailableError):
        await agent.generate("任何主题")
