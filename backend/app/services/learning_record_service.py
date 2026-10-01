from app.models.quiz import QuizCreateRequest, QuizResponse
from app.models.report import ReportCreateRequest, ReportResponse
from app.repositories.quiz_repository import QuizRepository, get_quiz_repository


class LearningRecordService:
    """Persist quiz data without changing the anonymous learning contract."""

    def __init__(self, repository: QuizRepository | None = None) -> None:
        self._repository = repository or get_quiz_repository()

    async def save_generated_quiz(
        self,
        *,
        user_id: int,
        request: QuizCreateRequest,
        quiz: QuizResponse,
    ) -> None:
        await self._repository.create_quiz_session(
            user_id=user_id,
            quiz_id=quiz.quiz_id,
            title=quiz.title,
            summary=quiz.summary,
            user_input=request.user_input,
            questions=quiz.questions,
        )

    async def save_completed_quiz(
        self,
        *,
        user_id: int,
        request: ReportCreateRequest,
        report: ReportResponse,
    ) -> int:
        total_questions = len(request.answer_records)
        correct_count = sum(
            1 for answer_record in request.answer_records if answer_record.is_correct
        )
        accuracy = round(correct_count / total_questions * 100)
        earned_xp = 10 + correct_count * 2
        was_persisted = await self._repository.persist_completion(
            user_id=user_id,
            quiz_id=request.quiz_id,
            answer_records=request.answer_records,
            total_questions=total_questions,
            correct_count=correct_count,
            accuracy=accuracy,
            report=report,
            earned_xp=earned_xp,
        )
        return earned_xp if was_persisted else 0


_learning_record_service: LearningRecordService | None = None


def get_learning_record_service() -> LearningRecordService:
    """Get the shared learning-record persistence service."""

    global _learning_record_service
    if _learning_record_service is None:
        _learning_record_service = LearningRecordService()
    return _learning_record_service
