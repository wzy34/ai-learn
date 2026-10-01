import uuid
from typing import Optional
from app.models.quiz import Quiz, QuizCreateRequest, Question, Option, QuizResponse, SearchSource, DifficultyLevel, QuestionType
from app.llm.quiz_chain import get_quiz_chain, parse_quiz_response
from app.llm.output_schemas import StructuredQuizOutput, StructuredQuestion, QuizOption as SchemaOption
from app.core.exceptions import QuizGenerationError, QuizValidationError, SearchNoResultsError
from app.services.retrieval_service import RetrievalOutcome, get_retrieval_service
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

# Cap on the number of web sources echoed back in the response (design D9).
MAX_RESPONSE_SOURCES = 8


class QuizService:
    """Service for quiz generation and validation.

    Primary path is the grounded agent (web retrieval, AI-driven); the
    pure-model chain remains as the degraded fallback (design D1/D6).
    """

    def __init__(self):
        self.quiz_chain = get_quiz_chain()

    async def generate_quiz(self, request: QuizCreateRequest) -> QuizResponse:
        """Generate a quiz from user input

        Args:
            request: Quiz creation request

        Returns:
            QuizResponse with generated quiz and retrieval metadata

        Raises:
            QuizValidationError: If request validation fails
            SearchNoResultsError: If retrieval ran but found no usable material
            QuizGenerationError: If generation fails
        """
        # Validate request
        self._validate_request(request)

        try:
            logger.info("Starting quiz generation", user_input=request.user_input[:100])

            retrieval = await get_retrieval_service().run(
                user_input=request.user_input,
                question_count=request.question_count,
                difficulty=request.difficulty,
            )

            if retrieval.outcome == RetrievalOutcome.OK:
                structured_output = parse_quiz_response(retrieval.response_text)
                search_used = True
                sources = retrieval.sources
            else:
                # Degraded path: agent skipped tools, failed, or is disabled.
                structured_output = await self.quiz_chain.generate_quiz(
                    user_input=request.user_input,
                    question_count=request.question_count,
                    difficulty=request.difficulty
                )
                search_used = False
                sources = []

            # Validate output
            self._validate_structured_output(structured_output)

            # Convert to domain models
            quiz = self._convert_to_quiz(
                structured_output=structured_output,
                user_input=request.user_input
            )

            logger.info(
                "Quiz generated successfully",
                quiz_id=quiz.quiz_id,
                search_used=search_used,
                source_count=len(sources),
            )
            return QuizResponse(
                quiz_id=quiz.quiz_id,
                title=quiz.title,
                summary=quiz.summary,
                questions=quiz.questions,
                search_used=search_used,
                sources=[
                    SearchSource(title=source.title, url=source.url)
                    for source in sources[:MAX_RESPONSE_SOURCES]
                ],
            )

        except SearchNoResultsError:
            logger.warning(
                "Quiz rejected: retrieval found no readable material",
                user_input=request.user_input[:100],
            )
            raise
        except Exception as e:
            logger.error("Quiz generation failed", error=str(e))
            raise QuizGenerationError(f"Failed to generate quiz: {str(e)}")

    def _validate_request(self, request: QuizCreateRequest) -> None:
        """Validate quiz creation request

        Args:
            request: Request to validate

        Raises:
            QuizValidationError: If validation fails
        """
        if not request.user_input or not request.user_input.strip():
            raise QuizValidationError("User input cannot be empty")

        if len(request.user_input) > 5000:
            raise QuizValidationError("User input too long (max 5000 characters)")

        if request.question_count < 1 or request.question_count > 10:
            raise QuizValidationError("Question count must be between 1 and 10")

    def _validate_structured_output(self, output: StructuredQuizOutput) -> None:
        """Validate LLM structured output

        Args:
            output: Structured output to validate

        Raises:
            QuizValidationError: If validation fails
        """
        if not output.title:
            raise QuizValidationError("Generated quiz missing title")

        if not output.summary:
            raise QuizValidationError("Generated quiz missing summary")

        if not output.questions or len(output.questions) == 0:
            raise QuizValidationError("Generated quiz has no questions")

        # Validate each question
        for idx, question in enumerate(output.questions):
            if not question.id:
                raise QuizValidationError(f"Question {idx + 1} missing ID")

            if not question.stem:
                raise QuizValidationError(f"Question {idx + 1} missing stem")

            if not question.options or len(question.options) < 2:
                raise QuizValidationError(f"Question {idx + 1} must have at least 2 options")

            if not question.answer or len(question.answer) == 0:
                raise QuizValidationError(f"Question {idx + 1} missing answer")

            if not question.explanation:
                raise QuizValidationError(f"Question {idx + 1} missing explanation")

            # Validate answer keys exist in options
            option_keys = {opt.key for opt in question.options}
            for ans_key in question.answer:
                if ans_key not in option_keys:
                    raise QuizValidationError(
                        f"Question {idx + 1} answer key '{ans_key}' not in options"
                    )

    def _convert_to_quiz(
        self,
        structured_output: StructuredQuizOutput,
        user_input: str
    ) -> Quiz:
        """Convert structured output to domain Quiz model

        Args:
            structured_output: LLM structured output
            user_input: Original user input

        Returns:
            Quiz domain model
        """
        quiz_id = f"quiz_{uuid.uuid4().hex[:12]}"

        questions = []
        for sq in structured_output.questions:
            options = [
                Option(key=opt.key, text=opt.text)
                for opt in sq.options
            ]

            questions.append(Question(
                id=sq.id,
                type=sq.type,
                stem=sq.stem,
                options=options,
                answer=sq.answer,
                explanation=sq.explanation,
                knowledge_point=sq.knowledge_point,
                difficulty=sq.difficulty
            ))

        return Quiz(
            quiz_id=quiz_id,
            title=structured_output.title,
            summary=structured_output.summary,
            source_type="text",
            user_input=user_input,
            questions=questions
        )


# Singleton instance
_quiz_service: Optional[QuizService] = None


def get_quiz_service() -> QuizService:
    """Get or create quiz service singleton

    Returns:
        QuizService instance
    """
    global _quiz_service
    if _quiz_service is None:
        _quiz_service = QuizService()
    return _quiz_service
