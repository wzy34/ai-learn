"""Aggregate grounded-agent runs into the three-state retrieval contract.

Implements design D6 (and the corresponding spec requirement): with web
retrieval being fully agent-driven, the system still distinguishes

* ``ok``          — at least one tool call returned usable material;
* ``no_results``  — calls succeeded but everything came back empty, which
  must raise :class:`SearchNoResultsError` instead of silently generating
  possibly off-topic questions;
* ``unavailable`` — the agent skipped tools, every call failed, or the run
  breached its budget — callers degrade to the pure-model chain and mark
  the quiz as not web-verified.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from app.core.config import settings
from app.core.exceptions import SearchNoResultsError
from app.core.logging import get_logger
from app.llm.quiz_agent import AgentUnavailableError, get_quiz_agent
from app.llm.quiz_tools import RetrievedSource

logger = get_logger(__name__)


class RetrievalOutcome(str, Enum):
    """Outcome of one grounded generation attempt."""

    OK = "ok"
    NO_RESULTS = "no_results"
    UNAVAILABLE = "unavailable"


@dataclass
class RetrievalResult:
    """What the quiz service needs to know about one retrieval attempt."""

    outcome: RetrievalOutcome
    response_text: Optional[str] = None
    sources: List[RetrievedSource] = field(default_factory=list)


class RetrievalService:
    """Run the grounded quiz agent and aggregate its tool-call records."""

    async def run(
        self,
        *,
        user_input: str,
        question_count: int = 5,
        difficulty: str = "mixed",
    ) -> RetrievalResult:
        if not settings.SEARCH_ENABLED or not settings.TAVILY_API_KEY:
            logger.warning(
                "Web retrieval disabled; degrading to pure-model generation",
                search_enabled=settings.SEARCH_ENABLED,
                key_configured=bool(settings.TAVILY_API_KEY),
            )
            return RetrievalResult(outcome=RetrievalOutcome.UNAVAILABLE)

        try:
            run_result = await get_quiz_agent().generate(
                user_input=user_input,
                question_count=question_count,
                difficulty=difficulty,
            )
        except AgentUnavailableError as exc:
            logger.warning(
                "Grounded agent unavailable; degrading to pure-model generation",
                error=str(exc),
            )
            return RetrievalResult(outcome=RetrievalOutcome.UNAVAILABLE)

        records = run_result.records
        if any(record.status == "ok" for record in records):
            return RetrievalResult(
                outcome=RetrievalOutcome.OK,
                response_text=run_result.response_text,
                sources=run_result.sources,
            )

        if records and all(record.status == "empty" for record in records):
            logger.info(
                "Retrieval ran but yielded no usable material",
                tool_calls=len(records),
            )
            raise self._no_results_error(records)

        logger.warning(
            "Retrieval tool calls failed; degrading to pure-model generation",
            tool_calls=len(records),
            failed=sum(1 for record in records if record.status == "error"),
        )
        return RetrievalResult(outcome=RetrievalOutcome.UNAVAILABLE)

    @staticmethod
    def _no_results_error(records) -> SearchNoResultsError:
        """Pick the actionable message based on what the agent attempted.

        Extract-only attempts point the user at the link itself; anything
        involving search suggests rephrasing or adding background.
        """
        if records and all(record.tool == "tavily_extract" for record in records):
            return SearchNoResultsError(
                detail="该网页内容提取失败，请确认链接有效，或改用文字描述想学的内容后再试"
            )
        return SearchNoResultsError()


# Singleton instance
_retrieval_service: Optional[RetrievalService] = None


def get_retrieval_service() -> RetrievalService:
    """Get or create retrieval service singleton."""
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = RetrievalService()
    return _retrieval_service
