from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import settings
from app.main import app
from app.models.quiz import DifficultyLevel, Option, Question, QuestionType, QuizResponse
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


@pytest.fixture
def quiz_response():
    return QuizResponse(
        quiz_id="quiz_drill",
        title="向量数据库基础",
        summary="向量数据库专项训练",
        questions=[
            Question(
                id="q1",
                type=QuestionType.SINGLE,
                stem="向量数据库的核心作用是什么？",
                options=[Option(key="A", text="相似度检索"), Option(key="B", text="事务处理")],
                answer=["A"],
                explanation="向量数据库面向高维向量的相似度检索。",
                knowledge_point="向量数据库",
                difficulty=DifficultyLevel.EASY,
            )
        ],
    )


def test_drill_requires_authentication(client):
    response = client.post("/api/v1/quiz/drill", json={})

    assert response.status_code == 401


def test_drill_without_focus_uses_the_top_weak_point_and_persists(
    client,
    auth_header,
    quiz_response,
):
    quiz_service = AsyncMock()
    quiz_service.generate_quiz.return_value = quiz_response
    weak_point_service = AsyncMock()
    weak_point_service.get_weak_points.return_value = WeakPointSummary(
        items=[WeakPointStat(point="向量数据库", count=3, last_seen_at="2026-08-29 10:00:00")],
        total_reports=3,
    )
    record_service = AsyncMock()

    with (
        patch("app.api.v1.routes.quiz.get_quiz_service", return_value=quiz_service),
        patch(
            "app.api.v1.routes.quiz.get_weak_point_service",
            return_value=weak_point_service,
        ),
        patch(
            "app.api.v1.routes.quiz.get_learning_record_service",
            return_value=record_service,
        ),
    ):
        response = client.post("/api/v1/quiz/drill", headers=auth_header, json={})

    assert response.status_code == 200
    generated_request = quiz_service.generate_quiz.await_args.args[0]
    assert "向量数据库" in generated_request.user_input
    assert record_service.save_generated_quiz.await_args.kwargs["user_id"] == 7
    data = response.json()["data"]
    assert data["title"].startswith("专项训练 · ")
    assert data["quiz_id"] == "quiz_drill"


def test_drill_without_any_reported_weak_point_returns_a_friendly_404(
    client,
    auth_header,
    quiz_response,
):
    quiz_service = AsyncMock()
    quiz_service.generate_quiz.return_value = quiz_response
    weak_point_service = AsyncMock()
    weak_point_service.get_weak_points.return_value = WeakPointSummary(
        items=[],
        total_reports=0,
    )

    with (
        patch("app.api.v1.routes.quiz.get_quiz_service", return_value=quiz_service),
        patch(
            "app.api.v1.routes.quiz.get_weak_point_service",
            return_value=weak_point_service,
        ),
    ):
        response = client.post("/api/v1/quiz/drill", headers=auth_header, json={})

    assert response.status_code == 404
    assert "薄弱点" in response.json()["detail"]["message"]
    quiz_service.generate_quiz.assert_not_awaited()


def test_drill_with_explicit_focus_skips_the_weak_point_lookup(
    client,
    auth_header,
    quiz_response,
):
    quiz_service = AsyncMock()
    quiz_service.generate_quiz.return_value = quiz_response
    weak_point_service = AsyncMock()
    record_service = AsyncMock()

    with (
        patch("app.api.v1.routes.quiz.get_quiz_service", return_value=quiz_service),
        patch(
            "app.api.v1.routes.quiz.get_weak_point_service",
            return_value=weak_point_service,
        ),
        patch(
            "app.api.v1.routes.quiz.get_learning_record_service",
            return_value=record_service,
        ),
    ):
        response = client.post(
            "/api/v1/quiz/drill",
            headers=auth_header,
            json={"focus": "三次握手", "question_count": 3},
        )

    assert response.status_code == 200
    weak_point_service.get_weak_points.assert_not_awaited()
    generated_request = quiz_service.generate_quiz.await_args.args[0]
    assert "三次握手" in generated_request.user_input
    assert generated_request.question_count == 3
    record_service.save_generated_quiz.assert_awaited_once()
