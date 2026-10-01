from types import SimpleNamespace

import pytest

from app.core.auth import decode_access_token
from app.core.config import settings
from app.core.exceptions import InvalidAvatarError, UserNotFoundError
from app.models.quiz import DifficultyLevel, Option, Question, QuestionType, QuizCreateRequest, QuizResponse
from app.models.report import AnswerRecord, ReportCreateRequest, ReportResponse
from app.models.user import UpdateProfileRequest
from app.services.avatar_storage import AvatarStorage
from app.services.learning_record_service import LearningRecordService
from app.services.user_service import UserService


@pytest.fixture
def jwt_settings(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-jwt-secret")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")


class FakeWechatClient:
    async def exchange_code(self, code: str):
        assert code == "valid-login-code"
        return SimpleNamespace(openid="wx-openid-1")


class FakeUserRepository:
    def __init__(self):
        self.received_openids: list[str] = []

    async def get_or_create_by_openid(self, openid: str):
        self.received_openids.append(openid)
        return SimpleNamespace(
            id=7,
            openid=openid,
            nickname="学习者",
            avatar_url="",
            total_xp=0,
        )


class FakeLearningRecordRepository:
    def __init__(self, completion_results: list[bool]):
        self.created_sessions: list[dict] = []
        self.completions: list[dict] = []
        self._completion_results = completion_results

    async def create_quiz_session(self, **kwargs):
        self.created_sessions.append(kwargs)

    async def persist_completion(self, **kwargs) -> bool:
        self.completions.append(kwargs)
        return self._completion_results.pop(0)


def build_quiz() -> QuizResponse:
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
            ),
            Question(
                id="q2",
                type=QuestionType.JUDGE,
                stem="RAG 可以完全消除幻觉吗？",
                options=[Option(key="A", text="正确"), Option(key="B", text="错误")],
                answer=["B"],
                explanation="RAG 只能降低幻觉风险。",
                knowledge_point="RAG 边界",
                difficulty=DifficultyLevel.MEDIUM,
            ),
        ],
    )


def build_report_request() -> ReportCreateRequest:
    quiz = build_quiz()
    return ReportCreateRequest(
        quiz_id=quiz.quiz_id,
        topic=quiz.title,
        questions=quiz.questions,
        answer_records=[
            AnswerRecord(
                question_id="q1",
                selected_answers=["A"],
                is_correct=True,
                duration_ms=1000,
            ),
            AnswerRecord(
                question_id="q2",
                selected_answers=["A"],
                is_correct=False,
                duration_ms=1200,
            ),
        ],
    )


def build_report_response() -> ReportResponse:
    return ReportResponse(
        accuracy=50,
        mastered_points=["RAG 定义"],
        weak_points=["RAG 边界"],
        three_line_summary=["第一点", "第二点", "第三点"],
        advice=["复习 RAG 边界"],
        share_quote="继续闯过知识关卡。",
    )


@pytest.mark.asyncio
async def test_wechat_login_registers_user_and_issues_a_user_bound_token(jwt_settings):
    repository = FakeUserRepository()
    service = UserService(
        user_repository=repository,
        wechat_client=FakeWechatClient(),
    )

    result = await service.login_with_code("valid-login-code")

    assert repository.received_openids == ["wx-openid-1"]
    assert result.user.id == 7
    assert decode_access_token(result.token).user_id == 7
    assert decode_access_token(result.token).openid == "wx-openid-1"


@pytest.mark.asyncio
async def test_generated_quiz_is_persisted_with_its_original_input():
    repository = FakeLearningRecordRepository(completion_results=[])
    service = LearningRecordService(repository=repository)
    request = QuizCreateRequest(user_input="我想学习 RAG", question_count=2, difficulty="mixed")
    quiz = build_quiz()

    await service.save_generated_quiz(user_id=7, request=request, quiz=quiz)

    assert repository.created_sessions == [
        {
            "user_id": 7,
            "quiz_id": "quiz_123",
            "title": "RAG 入门",
            "summary": "RAG 基础概念",
            "user_input": "我想学习 RAG",
            "questions": quiz.questions,
        }
    ]


@pytest.mark.asyncio
async def test_completion_awards_xp_once_and_persists_calculated_statistics():
    repository = FakeLearningRecordRepository(completion_results=[True, False])
    service = LearningRecordService(repository=repository)
    request = build_report_request()
    report = build_report_response()

    first_award = await service.save_completed_quiz(
        user_id=7,
        request=request,
        report=report,
    )
    repeated_award = await service.save_completed_quiz(
        user_id=7,
        request=request,
        report=report,
    )

    assert first_award == 12
    assert repeated_award == 0
    assert repository.completions[0]["total_questions"] == 2
    assert repository.completions[0]["correct_count"] == 1
    assert repository.completions[0]["accuracy"] == 50
    assert repository.completions[0]["earned_xp"] == 12


class FakeProfileRepository:
    """Profile read/write stand-in that tracks the current avatar URL."""

    def __init__(self, avatar_url: str = ""):
        self.avatar_url = avatar_url
        self.updated_requests: list[UpdateProfileRequest] = []

    async def get_profile(self, user_id: int):
        return SimpleNamespace(
            id=user_id,
            openid="wx-openid-1",
            nickname="学习者",
            avatar_url=self.avatar_url,
            total_xp=0,
            quiz_count=0,
            correct_count=0,
            average_accuracy=0,
        )

    async def update_profile(self, user_id: int, request: UpdateProfileRequest):
        self.updated_requests.append(request)
        if request.avatar_url is not None:
            self.avatar_url = request.avatar_url
        return await self.get_profile(user_id)


class FakeAvatarStorage:
    def __init__(self):
        self.saved: list[tuple[int, bytes]] = []
        self.deleted: list[str] = []
        self.next_url = "http://localhost:8000/static/avatars/7/new.png"

    def save(self, user_id: int, content: bytes) -> str:
        self.saved.append((user_id, content))
        return self.next_url

    def delete(self, avatar_url: str) -> None:
        self.deleted.append(avatar_url)


def test_avatar_storage_saves_images_and_returns_their_public_url(tmp_path):
    storage = AvatarStorage(
        upload_dir=tmp_path / "avatars",
        base_url="http://testserver:8000",
        max_size_bytes=1024,
    )

    png_url = storage.save(7, b"\x89PNG\r\n\x1a\npng-bytes")
    webp_url = storage.save(7, b"RIFF\x00\x00\x00\x00WEBPwebp-bytes")

    assert png_url.startswith("http://testserver:8000/static/avatars/7/")
    assert png_url.endswith(".png")
    assert webp_url.endswith(".webp")
    saved = list((tmp_path / "avatars" / "7").iterdir())
    assert len(saved) == 2


def test_avatar_storage_rejects_empty_non_image_and_oversized_files(tmp_path):
    storage = AvatarStorage(upload_dir=tmp_path, max_size_bytes=8)

    for bad_content in (b"", b"plain text", b"\xff\xd8\xff" + b"0" * 16):
        with pytest.raises(InvalidAvatarError):
            storage.save(7, bad_content)


def test_avatar_storage_delete_only_removes_its_own_files(tmp_path):
    storage = AvatarStorage(
        upload_dir=tmp_path / "avatars",
        base_url="http://testserver",
        max_size_bytes=1024,
    )
    url = storage.save(7, b"\x89PNG\r\n\x1a\npng-bytes")
    avatar_file = tmp_path / "avatars" / "7" / url.rsplit("/", 1)[-1]
    assert avatar_file.exists()

    storage.delete("https://third-party.example.com/avatar.png")
    storage.delete("http://testserver/static/avatars/999/missing.png")
    assert avatar_file.exists()

    storage.delete(url)
    assert not avatar_file.exists()


@pytest.mark.asyncio
async def test_avatar_upload_replaces_the_stored_image_and_cleans_the_old_one():
    repository = FakeProfileRepository(
        avatar_url="http://localhost:8000/static/avatars/7/old.png"
    )
    storage = FakeAvatarStorage()
    service = UserService(user_repository=repository, avatar_storage=storage)

    profile = await service.update_avatar(7, b"\x89PNG\r\n\x1a\nnew-image")

    assert storage.saved == [(7, b"\x89PNG\r\n\x1a\nnew-image")]
    assert repository.updated_requests[0].avatar_url == storage.next_url
    assert profile.avatar_url == storage.next_url
    assert storage.deleted == ["http://localhost:8000/static/avatars/7/old.png"]


@pytest.mark.asyncio
async def test_failed_avatar_update_removes_the_orphan_image():
    repository = FakeProfileRepository(avatar_url="http://localhost:8000/static/avatars/7/old.png")
    storage = FakeAvatarStorage()
    service = UserService(user_repository=repository, avatar_storage=storage)

    async def failing_update(user_id: int, request: UpdateProfileRequest):
        raise UserNotFoundError()

    repository.update_profile = failing_update

    with pytest.raises(UserNotFoundError):
        await service.update_avatar(7, b"\xff\xd8\xffjpeg-bytes")

    assert storage.deleted == [storage.next_url]
