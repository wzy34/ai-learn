from app.models.quiz import QuizResponse
from app.models.user import (
    QuizHistoryDetail,
    QuizHistoryItem,
    QuizHistoryPage,
    UnfinishedQuizItem,
    UnfinishedQuizList,
)
from app.repositories.quiz_repository import QuizRepository, get_quiz_repository


class HistoryService:
    """Application service for completed learning-history queries."""

    def __init__(self, repository: QuizRepository | None = None) -> None:
        self._repository = repository or get_quiz_repository()

    async def list_quizzes(
        self,
        user_id: int,
        page: int,
        page_size: int,
    ) -> QuizHistoryPage:
        history = await self._repository.list_completed_quizzes(
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
        return QuizHistoryPage(
            items=[
                QuizHistoryItem(
                    quiz_id=item.quiz_id,
                    title=item.title,
                    accuracy=item.accuracy,
                    question_count=item.question_count,
                    created_at=item.created_at,
                )
                for item in history.items
            ],
            total=history.total,
            page=page,
            page_size=page_size,
        )

    async def get_quiz_detail(
        self,
        user_id: int,
        quiz_id: str,
    ) -> QuizHistoryDetail:
        detail = await self._repository.get_completed_quiz(
            user_id=user_id,
            quiz_id=quiz_id,
        )
        return QuizHistoryDetail(
            quiz_id=detail.quiz_id,
            title=detail.title,
            summary=detail.summary,
            questions=detail.questions,
            answer_records=detail.answer_records,
            report=detail.report,
            created_at=detail.created_at,
        )

    async def list_unfinished_quizzes(
        self,
        user_id: int,
        limit: int = 20,
    ) -> UnfinishedQuizList:
        quizzes = await self._repository.list_unfinished_quizzes(
            user_id=user_id,
            limit=limit,
        )
        return UnfinishedQuizList(
            items=[
                UnfinishedQuizItem(
                    quiz_id=item.quiz_id,
                    title=item.title,
                    question_count=item.question_count,
                    created_at=item.created_at,
                )
                for item in quizzes
            ]
        )

    async def get_quiz_session(
        self,
        user_id: int,
        quiz_id: str,
    ) -> QuizResponse:
        """Return an owned quiz session so an unfinished run can be continued."""

        session = await self._repository.get_quiz_session(
            user_id=user_id,
            quiz_id=quiz_id,
        )
        return QuizResponse(
            quiz_id=session.quiz_id,
            title=session.title,
            summary=session.summary,
            questions=session.questions,
        )


_history_service: HistoryService | None = None


def get_history_service() -> HistoryService:
    """Get the shared history service."""

    global _history_service
    if _history_service is None:
        _history_service = HistoryService()
    return _history_service
