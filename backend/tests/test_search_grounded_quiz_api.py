"""API-level tests for the grounded quiz endpoints (task 5.2)."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import settings
from app.core.exceptions import SearchNoResultsError
from app.main import app
from app.models.quiz import DifficultyLevel, Option, Question, QuestionType, QuizResponse, SearchSource
from app.models.user import WeakPointStat, WeakPointSummary


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_header(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-jwt-secret")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    token = create_access_token(user_id=7, openid="wx-openid-1")
    return {"Authorization": f"Bearer {token}"}


def _quiz_response(**overrides) -> QuizResponse:
    payload = dict(
        quiz_id="quiz_grounded",
        title="Harness Engineering",
        summary="联网核实后的题库",
        questions=[
            Question(
                id="q1",
                type=QuestionType.SINGLE,
                stem="Harness Engineering 指的是什么？",
                options=[Option(key="A", text="AI 开发工作流"), Option(key="B", text="马术装备")],
                answer=["A"],
                explanation="以检索资料为准。",
                knowledge_point="Harness Engineering",
                difficulty=DifficultyLevel.EASY,
            )
        ],
    )
    payload.update(overrides)
    return QuizResponse(**payload)


def _service_mock(return_value=None, side_effect=None):
    service = AsyncMock()
    if side_effect is not None:
        service.generate_quiz.side_effect = side_effect
    else:
        service.generate_quiz.return_value = return_value
    return service


def test_generate_returns_search_metadata(client):
    service = _service_mock(
        _quiz_response(
            search_used=True,
            sources=[SearchSource(title="Tavily result", url="https://example.com/he")],
        )
    )
    with patch("app.api.v1.routes.quiz.get_quiz_service", return_value=service):
        response = client.post(
            "/api/v1/quiz/generate",
            json={"user_input": "Harness Engineering", "question_count": 5},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["search_used"] is True
    assert data["sources"] == [{"title": "Tavily result", "url": "https://example.com/he"}]


def test_generate_degraded_response_carries_unverified_flag(client):
    service = _service_mock(_quiz_response())

    with patch("app.api.v1.routes.quiz.get_quiz_service", return_value=service):
        response = client.post(
            "/api/v1/quiz/generate",
            json={"user_input": "什么是递归"},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["search_used"] is False
    assert data["sources"] == []


def test_generate_no_readable_material_returns_422_with_guidance(client):
    service = _service_mock(side_effect=SearchNoResultsError("未能在网络检索到该主题的资料，请换个说法或补充更多背景信息后再试"))

    with patch("app.api.v1.routes.quiz.get_quiz_service", return_value=service):
        response = client.post(
            "/api/v1/quiz/generate",
            json={"user_input": "生造词xyz"},
        )

    assert response.status_code == 422
    assert "换个说法" in response.json()["detail"]["message"]


def test_drill_returns_search_metadata_and_persists(client, auth_header):
    service = _service_mock(
        _quiz_response(
            search_used=True,
            sources=[SearchSource(title="向量数据库入门", url="https://example.com/vdb")],
        )
    )
    record_service = AsyncMock()

    with (
        patch("app.api.v1.routes.quiz.get_quiz_service", return_value=service),
        patch(
            "app.api.v1.routes.quiz.get_weak_point_service",
            return_value=_weak_points_mock(),
        ),
        patch(
            "app.api.v1.routes.quiz.get_learning_record_service",
            return_value=record_service,
        ),
    ):
        response = client.post(
            "/api/v1/quiz/drill",
            headers=auth_header,
            json={"focus": "向量数据库"},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["search_used"] is True
    assert data["sources"][0]["url"] == "https://example.com/vdb"
    assert data["title"].startswith("专项训练 · ")
    record_service.save_generated_quiz.assert_awaited_once()


def _weak_points_mock():
    weak_point_service = AsyncMock()
    weak_point_service.get_weak_points.return_value = WeakPointSummary(
        items=[WeakPointStat(point="向量数据库", count=2, last_seen_at="2026-08-30 10:00:00")],
        total_reports=2,
    )
    return weak_point_service
