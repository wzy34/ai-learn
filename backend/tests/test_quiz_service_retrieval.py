"""Tests for QuizService's retrieval orchestration (task 5.1)."""

import json
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import SearchNoResultsError
from app.llm.output_schemas import StructuredQuizOutput
from app.llm.quiz_agent import AgentRunResult
from app.llm.quiz_tools import RetrievedSource, ToolCallRecord
from app.models.quiz import QuizCreateRequest
from app.services.quiz_service import MAX_RESPONSE_SOURCES, QuizService
from app.services.retrieval_service import RetrievalOutcome, RetrievalResult

VALID_JSON = json.dumps({
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

REQUEST = QuizCreateRequest(user_input="Harness Engineering 是什么")


def _service_with_retrieval(monkeypatch, retrieval_result: RetrievalResult | Exception) -> QuizService:
    service = QuizService()
    fake = type("R", (), {})()
    if isinstance(retrieval_result, Exception):
        fake.run = AsyncMock(side_effect=retrieval_result)
    else:
        fake.run = AsyncMock(return_value=retrieval_result)
    monkeypatch.setattr("app.services.quiz_service.get_retrieval_service", lambda: fake)
    service.quiz_chain = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_ok_outcome_uses_agent_text_and_marks_metadata(monkeypatch):
    sources = [
        RetrievedSource(title=f"source {i}", url=f"https://example.com/{i}")
        for i in range(10)  # more than the response cap
    ]
    service = _service_with_retrieval(
        monkeypatch,
        RetrievalResult(outcome=RetrievalOutcome.OK, response_text=VALID_JSON, sources=sources),
    )

    response = await service.generate_quiz(REQUEST)

    assert response.search_used is True
    assert len(response.sources) == MAX_RESPONSE_SOURCES
    assert response.sources[0].title == "source 0"
    service.quiz_chain.generate_quiz.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_results_propagates_422_error(monkeypatch):
    service = _service_with_retrieval(
        monkeypatch,
        SearchNoResultsError("未能在网络检索到该主题的资料"),
    )

    with pytest.raises(SearchNoResultsError):
        await service.generate_quiz(REQUEST)

    service.quiz_chain.generate_quiz.assert_not_awaited()


@pytest.mark.asyncio
async def test_unavailable_outcome_falls_back_to_pure_chain(monkeypatch):
    service = _service_with_retrieval(
        monkeypatch,
        RetrievalResult(outcome=RetrievalOutcome.UNAVAILABLE),
    )
    service.quiz_chain.generate_quiz.return_value = StructuredQuizOutput.model_validate_json(VALID_JSON)

    response = await service.generate_quiz(REQUEST)

    assert response.search_used is False
    assert response.sources == []
    service.quiz_chain.generate_quiz.assert_awaited_once()
