from app.models.report import ReportCreateRequest, ReportResponse, AnswerRecord
from app.llm.report_chain import get_report_chain
from app.llm.output_schemas import StructuredReportOutput
from app.core.exceptions import ReportValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)


class ReportService:
    """Service for learning report generation"""

    def __init__(self):
        self.report_chain = get_report_chain()

    async def generate_report(self, request: ReportCreateRequest) -> ReportResponse:
        """Generate a learning report from quiz results

        Args:
            request: Report creation request

        Returns:
            ReportResponse with generated report

        Raises:
            ReportValidationError: If request validation fails
        """
        # Validate request
        self._validate_request(request)

        logger.info(
            "Starting report generation",
            quiz_id=request.quiz_id,
            answer_count=len(request.answer_records)
        )

        structured_output = await self.report_chain.generate_report(
            topic=request.topic,
            questions=request.questions,
            answer_records=request.answer_records
        )

        self._validate_structured_output(structured_output)

        accuracy = self._calculate_accuracy(request.answer_records)
        logger.info("Report generated successfully", accuracy=accuracy)

        return ReportResponse(
            accuracy=accuracy,
            mastered_points=structured_output.mastered_points,
            weak_points=structured_output.weak_points,
            three_line_summary=structured_output.three_line_summary,
            advice=structured_output.advice,
            share_quote=structured_output.share_quote
        )

    def _validate_request(self, request: ReportCreateRequest) -> None:
        """Validate report creation request

        Args:
            request: Request to validate

        Raises:
            ReportValidationError: If validation fails
        """
        if not request.quiz_id:
            raise ReportValidationError("Quiz ID is required")

        if not request.topic:
            raise ReportValidationError("Topic is required")

        if not request.questions or len(request.questions) == 0:
            raise ReportValidationError("Questions list is empty")

        if not request.answer_records or len(request.answer_records) == 0:
            raise ReportValidationError("Answer records list is empty")

        if len(request.answer_records) != len(request.questions):
            raise ReportValidationError(
                "Every question must have exactly one answer record"
            )

        questions_by_id = {question.id: question for question in request.questions}
        if len(questions_by_id) != len(request.questions):
            raise ReportValidationError("Questions must have unique IDs")

        answered_question_ids: set[str] = set()
        for record in request.answer_records:
            question = questions_by_id.get(record.question_id)
            if question is None:
                raise ReportValidationError(
                    f"Answer record question_id '{record.question_id}' not found in questions"
                )
            if record.question_id in answered_question_ids:
                raise ReportValidationError(
                    f"Question '{record.question_id}' has duplicate answer records"
                )
            answered_question_ids.add(record.question_id)

            selected_answers = set(record.selected_answers)
            if not selected_answers:
                raise ReportValidationError(
                    f"Question '{record.question_id}' has no selected answer"
                )
            if len(selected_answers) != len(record.selected_answers):
                raise ReportValidationError(
                    f"Question '{record.question_id}' has duplicate selected answers"
                )

            option_keys = {option.key for option in question.options}
            if not selected_answers.issubset(option_keys):
                raise ReportValidationError(
                    f"Question '{record.question_id}' has an invalid selected answer"
                )

            is_correct = selected_answers == set(question.answer)
            if record.is_correct != is_correct:
                raise ReportValidationError(
                    f"Question '{record.question_id}' correctness does not match selected answers"
                )

    def _validate_structured_output(self, output: StructuredReportOutput) -> None:
        """Validate LLM structured output

        Args:
            output: Structured output to validate

        Raises:
            ReportValidationError: If validation fails
        """
        if not 0 <= output.accuracy <= 100:
            raise ReportValidationError("Accuracy must be between 0 and 100")

        # 知识点列表允许为空（schema 保证其为列表）：全对时模型自然返回空
        # weak_points（错题为「无」），全错时同理 mastered_points 为空。
        # 这两类边界不应导致报告生成失败。

        if len(output.three_line_summary) != 3:
            raise ReportValidationError("Three line summary must have exactly 3 items")

        if not output.advice:
            raise ReportValidationError("Advice cannot be empty")

        if not output.share_quote or len(output.share_quote) > 100:
            raise ReportValidationError("Share quote is required and must be under 100 characters")

    @staticmethod
    def _calculate_accuracy(answer_records: list[AnswerRecord]) -> int:
        """Make score statistics deterministic instead of trusting model text."""

        correct_count = sum(
            1 for answer_record in answer_records if answer_record.is_correct
        )
        return round(correct_count / len(answer_records) * 100)


# Singleton instance
_report_service: ReportService | None = None


def get_report_service() -> ReportService:
    """Get or create report service singleton

    Returns:
        ReportService instance
    """
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service
