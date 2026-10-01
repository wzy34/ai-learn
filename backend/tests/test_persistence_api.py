from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import settings
from app.main import app
from app.models.quiz import DifficultyLevel, Option, Question, QuestionType, QuizResponse
from app.models.report import ReportResponse


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
        quiz_id="quiz_123",
        title="RAG 入门",
        summary="RAG 基础概念",
        questions=[
            Question(
                id="q1",
                type=QuestionType.SINGLE,
                stem="什么是 RAG？",
                options=[Option(key="A", text="检索增强生成"), Option(key="B", text="普通搜索")],
                answer=["A"],
                explanation="RAG 是检索增强生成。",
                knowledge_point="RAG 定义",
                difficulty=DifficultyLevel.EASY,
            )
        ],
    )


def test_authenticated_quiz_generation_persists_a_session(client, auth_header, quiz_response):
    quiz_service = AsyncMock()
    quiz_service.generate_quiz.return_value = quiz_response
    record_service = AsyncMock()

    with (
        patch("app.api.v1.routes.quiz.get_quiz_service", return_value=quiz_service),
        patch(
            "app.api.v1.routes.quiz.get_learning_record_service",
            return_value=record_service,
        ),
    ):
        response = client.post(
            "/api/v1/quiz/generate",
            headers=auth_header,
            json={"user_input": "我想学习 RAG", "question_count": 1, "difficulty": "easy"},
        )

    assert response.status_code == 200
    record_service.save_generated_quiz.assert_awaited_once()
    assert record_service.save_generated_quiz.await_args.kwargs["user_id"] == 7
    assert record_service.save_generated_quiz.await_args.kwargs["quiz"] == quiz_response


def test_anonymous_quiz_generation_keeps_the_existing_non_persistent_behavior(client, quiz_response):
    quiz_service = AsyncMock()
    quiz_service.generate_quiz.return_value = quiz_response
    record_service = AsyncMock()

    with (
        patch("app.api.v1.routes.quiz.get_quiz_service", return_value=quiz_service),
        patch(
            "app.api.v1.routes.quiz.get_learning_record_service",
            return_value=record_service,
        ),
    ):
        response = client.post(
            "/api/v1/quiz/generate",
            json={"user_input": "我想学习 RAG", "question_count": 1, "difficulty": "easy"},
        )

    assert response.status_code == 200
    record_service.save_generated_quiz.assert_not_awaited()


def test_invalid_optional_token_keeps_quiz_generation_anonymous(client, quiz_response):
    quiz_service = AsyncMock()
    quiz_service.generate_quiz.return_value = quiz_response
    record_service = AsyncMock()

    with (
        patch("app.api.v1.routes.quiz.get_quiz_service", return_value=quiz_service),
        patch(
            "app.api.v1.routes.quiz.get_learning_record_service",
            return_value=record_service,
        ),
    ):
        response = client.post(
            "/api/v1/quiz/generate",
            headers={"Authorization": "Bearer malformed-token"},
            json={"user_input": "我想学习 RAG", "question_count": 1, "difficulty": "easy"},
        )

    assert response.status_code == 200
    record_service.save_generated_quiz.assert_not_awaited()


def test_authenticated_report_generation_persists_completion_without_changing_response_shape(
    client,
    auth_header,
    quiz_response,
):
    report_service = AsyncMock()
    report_service.generate_report.return_value = ReportResponse(
        accuracy=100,
        mastered_points=["RAG 定义"],
        weak_points=["无"],
        three_line_summary=["第一点", "第二点", "第三点"],
        advice=["继续学习"],
        share_quote="继续闯关。",
    )
    record_service = AsyncMock()
    record_service.save_completed_quiz.return_value = 12

    with (
        patch("app.api.v1.routes.report.get_report_service", return_value=report_service),
        patch(
            "app.api.v1.routes.report.get_learning_record_service",
            return_value=record_service,
        ),
    ):
        response = client.post(
            "/api/v1/report/generate",
            headers=auth_header,
            json={
                "quiz_id": quiz_response.quiz_id,
                "topic": quiz_response.title,
                "questions": [question.model_dump(mode="json") for question in quiz_response.questions],
                "answer_records": [
                    {
                        "question_id": "q1",
                        "selected_answers": ["A"],
                        "is_correct": True,
                        "duration_ms": 1000,
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["accuracy"] == 100
    assert "earned_xp" not in response.json()["data"]
    record_service.save_completed_quiz.assert_awaited_once()
    assert record_service.save_completed_quiz.await_args.kwargs["user_id"] == 7
