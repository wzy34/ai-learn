from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.models.quiz import Question
from app.models.report import AnswerRecord, ReportResponse


class UserSummary(BaseModel):
    """User fields safe to return to the mini program."""

    id: int
    nickname: str
    avatar_url: str
    total_xp: int


class LoginRequest(BaseModel):
    """WeChat login code received from Taro.login."""

    code: Annotated[str, Field(min_length=1, max_length=1024)]


class LoginResponse(BaseModel):
    token: str
    user: UserSummary


class UserProfile(UserSummary):
    quiz_count: int
    correct_count: int
    average_accuracy: float


class UpdateProfileRequest(BaseModel):
    nickname: Annotated[str | None, Field(default=None, min_length=1, max_length=100)]
    avatar_url: Annotated[str | None, Field(default=None, max_length=500)]

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "UpdateProfileRequest":
        if self.nickname is None and self.avatar_url is None:
            raise ValueError("At least one profile field must be provided")

        if self.nickname is not None:
            self.nickname = self.nickname.strip()
            if not self.nickname:
                raise ValueError("Nickname cannot be blank")

        if self.avatar_url is not None:
            self.avatar_url = self.avatar_url.strip()

        return self


class QuizHistoryItem(BaseModel):
    quiz_id: str
    title: str
    accuracy: float
    question_count: int
    created_at: str


class QuizHistoryPage(BaseModel):
    items: list[QuizHistoryItem]
    total: int
    page: int
    page_size: int


class QuizHistoryDetail(BaseModel):
    quiz_id: str
    title: str
    summary: str
    questions: list[Question]
    answer_records: list[AnswerRecord]
    report: ReportResponse
    created_at: str


class UnfinishedQuizItem(BaseModel):
    quiz_id: str
    title: str
    question_count: int
    created_at: str


class UnfinishedQuizList(BaseModel):
    items: list[UnfinishedQuizItem]


class WeakPointStat(BaseModel):
    point: str
    count: int
    last_seen_at: str


class WeakPointSummary(BaseModel):
    items: list[WeakPointStat]
    total_reports: int
