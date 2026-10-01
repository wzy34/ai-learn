from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import settings
from app.core.exceptions import HistoryNotFoundError, InvalidAvatarError
from app.main import app
from app.models.quiz import DifficultyLevel, Option, Question, QuestionType
from app.models.report import AnswerRecord, ReportResponse
from app.models.quiz import QuizResponse
from app.models.user import (
    LoginResponse,
    QuizHistoryDetail,
    QuizHistoryItem,
    QuizHistoryPage,
    UnfinishedQuizItem,
    UnfinishedQuizList,
    UpdateProfileRequest,
    UserProfile,
    UserSummary,
    WeakPointStat,
    WeakPointSummary,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_header(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-jwt-secret")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    token = create_access_token(user_id=7, openid="wx-openid-1")
    return {"Authorization": f"Bearer {token}"}


class StubUserService:
    def __init__(self):
        self.login_code: str | None = None
        self.updated_request: UpdateProfileRequest | None = None
        self.avatar_bytes: bytes | None = None

    async def update_avatar(self, user_id: int, content: bytes) -> UserProfile:
        assert user_id == 7
        self.avatar_bytes = content
        return UserProfile(
            id=7,
            nickname="学习者",
            avatar_url=f"http://localhost:8000/static/avatars/7/{content[:4].hex()}.png",
            total_xp=18,
            quiz_count=1,
            correct_count=4,
            average_accuracy=80,
        )

    async def login_with_code(self, code: str) -> LoginResponse:
        self.login_code = code
        return LoginResponse(
            token="signed-token",
            user=UserSummary(
                id=7,
                nickname="学习者",
                avatar_url="",
                total_xp=0,
            ),
        )

    async def get_profile(self, user_id: int) -> UserProfile:
        assert user_id == 7
        return UserProfile(
            id=7,
            nickname="学习者",
            avatar_url="",
            total_xp=18,
            quiz_count=1,
            correct_count=4,
            average_accuracy=80,
        )

    async def update_profile(
        self,
        user_id: int,
        request: UpdateProfileRequest,
    ) -> UserProfile:
        assert user_id == 7
        self.updated_request = request
        return UserProfile(
            id=7,
            nickname=request.nickname or "学习者",
            avatar_url=request.avatar_url or "",
            total_xp=18,
            quiz_count=1,
            correct_count=4,
            average_accuracy=80,
        )


class StubHistoryService:
    def __init__(self):
        self.received_page: tuple[int, int, int] | None = None
        self.received_unfinished_limit: tuple[int, int] | None = None
        self.received_session: tuple[int, str] | None = None

    async def list_quizzes(
        self,
        user_id: int,
        page: int,
        page_size: int,
    ) -> QuizHistoryPage:
        self.received_page = (user_id, page, page_size)
        return QuizHistoryPage(
            items=[
                QuizHistoryItem(
                    quiz_id="quiz_123",
                    title="RAG 入门",
                    accuracy=80,
                    question_count=5,
                    created_at="2026-08-24 10:00:00",
                )
            ],
            total=1,
            page=page,
            page_size=page_size,
        )

    async def get_quiz_detail(self, user_id: int, quiz_id: str) -> QuizHistoryDetail:
        assert user_id == 7
        if quiz_id != "quiz_123":
            raise HistoryNotFoundError()

        question = Question(
            id="q1",
            type=QuestionType.SINGLE,
            stem="什么是 RAG？",
            options=[Option(key="A", text="检索增强生成"), Option(key="B", text="普通搜索")],
            answer=["A"],
            explanation="RAG 是检索增强生成。",
            knowledge_point="RAG 定义",
            difficulty=DifficultyLevel.EASY,
        )
        return QuizHistoryDetail(
            quiz_id="quiz_123",
            title="RAG 入门",
            summary="RAG 基础概念",
            questions=[question],
            answer_records=[
                AnswerRecord(
                    question_id="q1",
                    selected_answers=["A"],
                    is_correct=True,
                    duration_ms=1000,
                )
            ],
            report=ReportResponse(
                accuracy=100,
                mastered_points=["RAG 定义"],
                weak_points=["无"],
                three_line_summary=["第一点", "第二点", "第三点"],
                advice=["继续学习"],
                share_quote="继续闯关。",
            ),
            created_at="2026-08-24 10:00:00",
        )

    async def list_unfinished_quizzes(
        self,
        user_id: int,
        limit: int = 20,
    ) -> UnfinishedQuizList:
        self.received_unfinished_limit = (user_id, limit)
        return UnfinishedQuizList(
            items=[
                UnfinishedQuizItem(
                    quiz_id="quiz_456",
                    title="提示词工程",
                    question_count=5,
                    created_at="2026-08-28 09:00:00",
                )
            ]
        )

    async def get_quiz_session(self, user_id: int, quiz_id: str) -> QuizResponse:
        self.received_session = (user_id, quiz_id)
        if quiz_id != "quiz_456":
            raise HistoryNotFoundError()

        return QuizResponse(
            quiz_id="quiz_456",
            title="提示词工程",
            summary="提示词工程基础",
            questions=[
                Question(
                    id="q1",
                    type=QuestionType.SINGLE,
                    stem="什么是少样本示例？",
                    options=[Option(key="A", text="Few-shot"), Option(key="B", text="Zero-shot")],
                    answer=["A"],
                    explanation="少样本示例即 Few-shot。",
                    knowledge_point="提示词工程",
                    difficulty=DifficultyLevel.EASY,
                )
            ],
        )


class StubWeakPointService:
    def __init__(self):
        self.received_user_id: int | None = None

    async def get_weak_points(self, user_id: int) -> WeakPointSummary:
        self.received_user_id = user_id
        return WeakPointSummary(
            items=[
                WeakPointStat(point="向量数据库", count=2, last_seen_at="2026-08-29 10:00:00"),
            ],
            total_reports=3,
        )


def test_wechat_login_returns_standard_response_and_token(client):
    service = StubUserService()

    with patch("app.api.v1.routes.user.get_user_service", return_value=service):
        response = client.post("/api/v1/user/login", json={"code": "wx-login-code"})

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "Login successful",
        "data": {
            "token": "signed-token",
            "user": {
                "id": 7,
                "nickname": "学习者",
                "avatar_url": "",
                "total_xp": 0,
            },
        },
    }
    assert service.login_code == "wx-login-code"


def test_profile_requires_a_valid_bearer_token(client):
    response = client.get("/api/v1/user/profile")

    assert response.status_code == 401


def test_avatar_upload_requires_a_valid_bearer_token(client):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    response = client.post(
        "/api/v1/user/avatar",
        files={"file": ("avatar.png", png, "image/png")},
    )

    assert response.status_code == 401


def test_avatar_upload_stores_the_image_and_updates_the_profile(client, auth_header):
    user_service = StubUserService()
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 16

    with patch("app.api.v1.routes.user.get_user_service", return_value=user_service):
        response = client.post(
            "/api/v1/user/avatar",
            headers=auth_header,
            files={"file": ("avatar.png", png, "image/png")},
        )

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "Avatar updated successfully",
        "data": {
            "id": 7,
            "nickname": "学习者",
            "avatar_url": "http://localhost:8000/static/avatars/7/89504e47.png",
            "total_xp": 18,
            "quiz_count": 1,
            "correct_count": 4,
            "average_accuracy": 80,
        },
    }
    assert user_service.avatar_bytes == png


def test_avatar_upload_rejects_non_image_files(client, auth_header):
    user_service = StubUserService()

    async def fail_update(user_id: int, content: bytes) -> UserProfile:
        raise InvalidAvatarError(detail="Avatar must be a JPG, PNG, or WebP image")

    user_service.update_avatar = fail_update

    with patch("app.api.v1.routes.user.get_user_service", return_value=user_service):
        response = client.post(
            "/api/v1/user/avatar",
            headers=auth_header,
            files={"file": ("avatar.txt", b"definitely not an image", "text/plain")},
        )

    assert response.status_code == 400
    assert (
        response.json()["detail"]["message"]
        == "Avatar must be a JPG, PNG, or WebP image"
    )


def test_profile_update_and_history_use_the_authenticated_user(client, auth_header):
    user_service = StubUserService()
    history_service = StubHistoryService()

    with (
        patch("app.api.v1.routes.user.get_user_service", return_value=user_service),
        patch("app.api.v1.routes.user.get_history_service", return_value=history_service),
    ):
        profile_response = client.get("/api/v1/user/profile", headers=auth_header)
        update_response = client.put(
            "/api/v1/user/profile",
            headers=auth_header,
            json={"nickname": "同学"},
        )
        history_response = client.get(
            "/api/v1/user/quizzes?page=2&page_size=5",
            headers=auth_header,
        )

    assert profile_response.status_code == 200
    assert profile_response.json()["data"]["correct_count"] == 4
    assert update_response.status_code == 200
    assert update_response.json()["data"]["nickname"] == "同学"
    assert user_service.updated_request is not None
    assert user_service.updated_request.nickname == "同学"
    assert history_response.status_code == 200
    assert history_response.json()["data"]["items"][0]["quiz_id"] == "quiz_123"
    assert history_service.received_page == (7, 2, 5)


def test_history_detail_is_scoped_to_the_authenticated_user(client, auth_header):
    history_service = StubHistoryService()

    with patch("app.api.v1.routes.user.get_history_service", return_value=history_service):
        found_response = client.get("/api/v1/user/quizzes/quiz_123", headers=auth_header)
        missing_response = client.get("/api/v1/user/quizzes/not-owned", headers=auth_header)

    assert found_response.status_code == 200
    assert found_response.json()["data"]["report"]["accuracy"] == 100
    assert missing_response.status_code == 404


def test_unfinished_quizzes_require_a_valid_bearer_token(client):
    response = client.get("/api/v1/user/quizzes/unfinished")

    assert response.status_code == 401


def test_unfinished_quizzes_use_the_authenticated_user(client, auth_header):
    history_service = StubHistoryService()

    with patch("app.api.v1.routes.user.get_history_service", return_value=history_service):
        response = client.get("/api/v1/user/quizzes/unfinished", headers=auth_header)

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["quiz_id"] == "quiz_456"
    assert history_service.received_unfinished_limit == (7, 20)


def test_quiz_resume_returns_the_owned_session_without_completion(client, auth_header):
    history_service = StubHistoryService()

    with patch("app.api.v1.routes.user.get_history_service", return_value=history_service):
        found_response = client.get(
            "/api/v1/user/quizzes/quiz_456/resume",
            headers=auth_header,
        )

    assert found_response.status_code == 200
    data = found_response.json()["data"]
    assert data["quiz_id"] == "quiz_456"
    assert data["questions"][0]["id"] == "q1"
    assert "report" not in data
    assert "answer_records" not in data
    assert history_service.received_session == (7, "quiz_456")

    with patch("app.api.v1.routes.user.get_history_service", return_value=history_service):
        missing_response = client.get(
            "/api/v1/user/quizzes/not-owned/resume",
            headers=auth_header,
        )

    assert missing_response.status_code == 404


def test_weak_points_require_a_valid_bearer_token(client):
    response = client.get("/api/v1/user/weak-points")

    assert response.status_code == 401


def test_weak_points_return_the_aggregated_summary(client, auth_header):
    weak_point_service = StubWeakPointService()

    with patch(
        "app.api.v1.routes.user.get_weak_point_service",
        return_value=weak_point_service,
    ):
        response = client.get("/api/v1/user/weak-points", headers=auth_header)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["items"][0]["point"] == "向量数据库"
    assert data["items"][0]["count"] == 2
    assert data["total_reports"] == 3
    assert weak_point_service.received_user_id == 7
