from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable
from app.llm.langchain_factory import LangChainFactory
from app.llm.output_schemas import StructuredQuizOutput
from app.prompts.quiz_prompt import create_quiz_prompt_template, format_quiz_user_input
from app.core.logging import get_logger
import json

logger = get_logger(__name__)


_QUESTION_TYPE_ALIASES = {
    "single": "single",
    "single_choice": "single",
    "radio": "single",
    "multiple": "multiple",
    "multi": "multiple",
    "multi_select": "multiple",
    "multiple_choice": "multiple",
    "checkbox": "multiple",
    "judge": "judge",
    "judgement": "judge",
    "judgment": "judge",
    "boolean": "judge",
    "true_false": "judge",
}


def _normalise_question_types(data: dict) -> dict:
    """Fold common LLM spelling variants of question types onto the schema."""
    for question in data.get("questions") or []:
        if isinstance(question, dict):
            raw = str(question.get("type") or "").strip().lower()
            question["type"] = _QUESTION_TYPE_ALIASES.get(raw, raw)
    return data


def parse_quiz_response(response_text: str) -> StructuredQuizOutput:
    """Clean and validate a raw LLM response into structured quiz output.

    Shared by the grounded agent path and the degraded pure-model path so
    both funnels enforce the same JSON contract. The agent tends to wrap the
    final JSON in prose or code fences, so extraction is tolerant: prefer a
    ```json fenced block, then fall back to the outermost brace span.
    """
    text = response_text.strip()

    fence_start = text.find("```json")
    if fence_start != -1:
        body_start = fence_start + len("```json")
        fence_end = text.find("```", body_start)
        if fence_end != -1:
            text = text[body_start:fence_end]

    # Trim any prose before/after the JSON object itself.
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        text = text[brace_start:brace_end + 1]

    response_data = _normalise_question_types(json.loads(text.strip()))
    return StructuredQuizOutput(**response_data)


class QuizChain:
    """Chain for generating quiz from user input.

    Since the grounded agent took over as the primary path, this pure-model
    chain is the degraded fallback and uses the conservative system prompt.
    """

    def __init__(self):
        self.factory = LangChainFactory()
        self.llm = self.factory.create_chat_llm()
        self.prompt = create_quiz_prompt_template()

    def create_chain(self) -> Runnable:
        """Create the quiz generation chain

        Returns:
            Runnable chain for quiz generation
        """
        # Create chain with string output, then parse JSON
        chain = (
            self.prompt
            | self.llm
            | StrOutputParser()
        )

        return chain

    async def generate_quiz(
        self,
        user_input: str,
        question_count: int = 5,
        difficulty: str = "mixed"
    ) -> StructuredQuizOutput:
        """Generate a quiz from user input

        Args:
            user_input: User's learning content
            question_count: Number of questions to generate
            difficulty: Difficulty level

        Returns:
            StructuredQuizOutput containing generated quiz

        Raises:
            Exception: If generation fails
        """
        logger.info("Generating quiz", user_input_length=len(user_input))

        # Format input
        formatted_input = format_quiz_user_input(
            user_input=user_input,
            question_count=question_count,
            difficulty=difficulty
        )

        # Get chain
        chain = self.create_chain()

        # Invoke chain and get string response
        try:
            response_text = await chain.ainvoke(formatted_input)

            logger.info("Parsing LLM response", response_length=len(response_text))
            quiz_output = parse_quiz_response(response_text)

            logger.info(
                "Quiz generated successfully",
                question_count=len(quiz_output.questions),
                title=quiz_output.title
            )
            return quiz_output

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON", error=str(e))
            raise ValueError(f"Invalid JSON response from LLM: {str(e)}")

        except Exception as e:
            logger.error("Quiz generation failed", error=str(e))
            raise


# Singleton instance
_quiz_chain: QuizChain | None = None


def get_quiz_chain() -> QuizChain:
    """Get or create quiz chain singleton

    Returns:
        QuizChain instance
    """
    global _quiz_chain
    if _quiz_chain is None:
        _quiz_chain = QuizChain()
    return _quiz_chain
