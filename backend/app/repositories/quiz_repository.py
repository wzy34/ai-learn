import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiomysql
from pydantic import BaseModel

from app.core.db import Database, database
from app.core.exceptions import DatabaseError, HistoryNotFoundError
from app.models.quiz import Question
from app.models.report import AnswerRecord, ReportResponse


@dataclass(frozen=True)
class StoredQuizHistoryItem:
    quiz_id: str
    title: str
    accuracy: float
    question_count: int
    created_at: str


@dataclass(frozen=True)
class StoredQuizHistoryPage:
    items: list[StoredQuizHistoryItem]
    total: int


@dataclass(frozen=True)
class StoredQuizHistoryDetail:
    quiz_id: str
    title: str
    summary: str
    questions: list[Question]
    answer_records: list[AnswerRecord]
    report: ReportResponse
    created_at: str


@dataclass(frozen=True)
class StoredUnfinishedQuiz:
    quiz_id: str
    title: str
    question_count: int
    created_at: str


@dataclass(frozen=True)
class StoredQuizSession:
    quiz_id: str
    title: str
    summary: str
    questions: list[Question]
    created_at: str


@dataclass(frozen=True)
class StoredReportEntry:
    report: ReportResponse
    created_at: str


class QuizRepository:
    """MySQL persistence for user-owned quiz sessions and completed records."""

    def __init__(self, db: Database = database) -> None:
        self._db = db

    async def create_quiz_session(
        self,
        *,
        user_id: int,
        quiz_id: str,
        title: str,
        summary: str,
        user_input: str,
        questions: list[Question],
    ) -> None:
        questions_json = self._serialize_json(questions)
        async with self._db.transaction() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO quiz_sessions (
                        quiz_id,
                        user_id,
                        title,
                        summary,
                        user_input,
                        questions_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (quiz_id, user_id, title, summary, user_input, questions_json),
                )

    async def persist_completion(
        self,
        *,
        user_id: int,
        quiz_id: str,
        answer_records: list[AnswerRecord],
        total_questions: int,
        correct_count: int,
        accuracy: int,
        report: ReportResponse,
        earned_xp: int,
    ) -> bool:
        """Persist one completion transaction and return whether XP was awarded."""

        async with self._db.transaction() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT id
                    FROM quiz_sessions
                    WHERE quiz_id = %s AND user_id = %s
                    FOR UPDATE
                    """,
                    (quiz_id, user_id),
                )
                if await cursor.fetchone() is None:
                    raise HistoryNotFoundError(
                        "Quiz session not found for the authenticated user"
                    )

                await cursor.execute(
                    """
                    SELECT id
                    FROM reports
                    WHERE quiz_id = %s AND user_id = %s
                    FOR UPDATE
                    """,
                    (quiz_id, user_id),
                )
                if await cursor.fetchone() is not None:
                    return False

                await cursor.execute(
                    """
                    INSERT INTO answer_records (
                        quiz_id,
                        user_id,
                        records_json,
                        total_questions,
                        correct_count,
                        accuracy
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        quiz_id,
                        user_id,
                        self._serialize_json(answer_records),
                        total_questions,
                        correct_count,
                        accuracy,
                    ),
                )
                await cursor.execute(
                    """
                    INSERT INTO reports (quiz_id, user_id, report_json)
                    VALUES (%s, %s, %s)
                    """,
                    (quiz_id, user_id, self._serialize_json(report)),
                )
                await cursor.execute(
                    """
                    UPDATE users
                    SET total_xp = total_xp + %s
                    WHERE id = %s
                    """,
                    (earned_xp, user_id),
                )
                if cursor.rowcount != 1:
                    raise DatabaseError("Unable to award learning experience")

        return True

    async def list_completed_quizzes(
        self,
        *,
        user_id: int,
        page: int,
        page_size: int,
    ) -> StoredQuizHistoryPage:
        offset = (page - 1) * page_size
        async with self._db.connection() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        qs.quiz_id,
                        qs.title,
                        ar.accuracy,
                        ar.total_questions AS question_count,
                        ar.created_at
                    FROM quiz_sessions AS qs
                    INNER JOIN answer_records AS ar
                        ON ar.quiz_id = qs.quiz_id AND ar.user_id = qs.user_id
                    WHERE qs.user_id = %s
                    ORDER BY ar.created_at DESC, ar.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_id, page_size, offset),
                )
                rows = await cursor.fetchall()
                await cursor.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM answer_records
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                count_row = await cursor.fetchone()

        if count_row is None:
            raise DatabaseError("Unable to count learning history")
        return StoredQuizHistoryPage(
            items=[
                StoredQuizHistoryItem(
                    quiz_id=str(row["quiz_id"]),
                    title=str(row["title"]),
                    accuracy=float(row["accuracy"]),
                    question_count=int(row["question_count"]),
                    created_at=self._format_datetime(row["created_at"]),
                )
                for row in rows
            ],
            total=int(count_row["total"]),
        )

    async def get_completed_quiz(
        self,
        *,
        user_id: int,
        quiz_id: str,
    ) -> StoredQuizHistoryDetail:
        async with self._db.connection() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        qs.quiz_id,
                        qs.title,
                        qs.summary,
                        qs.questions_json,
                        ar.records_json,
                        r.report_json,
                        ar.created_at
                    FROM quiz_sessions AS qs
                    INNER JOIN answer_records AS ar
                        ON ar.quiz_id = qs.quiz_id AND ar.user_id = qs.user_id
                    INNER JOIN reports AS r
                        ON r.quiz_id = qs.quiz_id AND r.user_id = qs.user_id
                    WHERE qs.user_id = %s AND qs.quiz_id = %s
                    """,
                    (user_id, quiz_id),
                )
                row = await cursor.fetchone()

        if row is None:
            raise HistoryNotFoundError()
        try:
            questions = [
                Question.model_validate(item)
                for item in self._deserialize_json(row["questions_json"])
            ]
            answer_records = [
                AnswerRecord.model_validate(item)
                for item in self._deserialize_json(row["records_json"])
            ]
            report = ReportResponse.model_validate(
                self._deserialize_json(row["report_json"])
            )
        except (TypeError, ValueError) as error:
            raise DatabaseError("Stored learning history is invalid") from error

        return StoredQuizHistoryDetail(
            quiz_id=str(row["quiz_id"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            questions=questions,
            answer_records=answer_records,
            report=report,
            created_at=self._format_datetime(row["created_at"]),
        )

    async def list_unfinished_quizzes(
        self,
        *,
        user_id: int,
        limit: int = 20,
    ) -> list[StoredUnfinishedQuiz]:
        """List generated quizzes that have no completion record yet."""

        async with self._db.connection() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        qs.quiz_id,
                        qs.title,
                        JSON_LENGTH(qs.questions_json) AS question_count,
                        qs.created_at
                    FROM quiz_sessions AS qs
                    LEFT JOIN answer_records AS ar
                        ON ar.quiz_id = qs.quiz_id AND ar.user_id = qs.user_id
                    WHERE qs.user_id = %s AND ar.quiz_id IS NULL
                    ORDER BY qs.created_at DESC, qs.id DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                rows = await cursor.fetchall()

        return [
            StoredUnfinishedQuiz(
                quiz_id=str(row["quiz_id"]),
                title=str(row["title"]),
                question_count=int(row["question_count"] or 0),
                created_at=self._format_datetime(row["created_at"]),
            )
            for row in rows
        ]

    async def get_quiz_session(
        self,
        *,
        user_id: int,
        quiz_id: str,
    ) -> StoredQuizSession:
        """Return an owned quiz session regardless of completion state."""

        async with self._db.connection() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT quiz_id, title, summary, questions_json, created_at
                    FROM quiz_sessions
                    WHERE user_id = %s AND quiz_id = %s
                    """,
                    (user_id, quiz_id),
                )
                row = await cursor.fetchone()

        if row is None:
            raise HistoryNotFoundError()
        try:
            questions = [
                Question.model_validate(item)
                for item in self._deserialize_json(row["questions_json"])
            ]
        except (TypeError, ValueError) as error:
            raise DatabaseError("Stored quiz session is invalid") from error

        return StoredQuizSession(
            quiz_id=str(row["quiz_id"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            questions=questions,
            created_at=self._format_datetime(row["created_at"]),
        )

    async def list_recent_reports(
        self,
        *,
        user_id: int,
        limit: int = 20,
    ) -> list[StoredReportEntry]:
        """Return the user's newest reports for downstream aggregation."""

        async with self._db.connection() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT report_json, created_at
                    FROM reports
                    WHERE user_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                rows = await cursor.fetchall()

        entries: list[StoredReportEntry] = []
        for row in rows:
            try:
                report = ReportResponse.model_validate(
                    self._deserialize_json(row["report_json"])
                )
            except (TypeError, ValueError) as error:
                raise DatabaseError("Stored learning report is invalid") from error
            entries.append(
                StoredReportEntry(
                    report=report,
                    created_at=self._format_datetime(row["created_at"]),
                )
            )
        return entries

    @staticmethod
    def _serialize_json(value: BaseModel | list[BaseModel]) -> str:
        if isinstance(value, BaseModel):
            payload: Any = value.model_dump(mode="json")
        else:
            payload = [item.model_dump(mode="json") for item in value]
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _deserialize_json(value: str | bytes | dict[str, Any] | list[Any]) -> Any:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if isinstance(value, str):
            return json.loads(value)
        return value

    @staticmethod
    def _format_datetime(value: datetime | str) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value)


_quiz_repository: QuizRepository | None = None


def get_quiz_repository() -> QuizRepository:
    """Get the shared quiz repository."""

    global _quiz_repository
    if _quiz_repository is None:
        _quiz_repository = QuizRepository()
    return _quiz_repository
