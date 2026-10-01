"""Grounded quiz agent: DeepSeek driving the official Tavily tools.

Builds a LangChain 1.x ``create_agent`` (langgraph core) with
``TavilySearch``/``TavilyExtract`` and the quiz_prompt_v3 system prompt
(design D1/D5). The agent decides on its own whether to retrieve, which
tool to call, and how to fill parameters; the loop is bounded by
``AGENT_RECURSION_LIMIT`` and ``AGENT_TIMEOUT_SECONDS`` and every breach
raises :class:`AgentUnavailableError` so the caller can degrade to the
pure-model chain.
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Optional

from langchain.agents import create_agent
from langgraph.errors import GraphRecursionError

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.langchain_factory import LangChainFactory
from app.prompts.quiz_prompt import QUIZ_AGENT_SYSTEM_PROMPT, format_agent_user_message
from app.llm.quiz_tools import (
    RetrievedSource,
    ToolCallRecord,
    create_grounded_tools,
)

logger = get_logger(__name__)


class AgentUnavailableError(Exception):
    """Raised when the agent loop cannot deliver a final answer."""


@dataclass
class AgentRunResult:
    """Raw outcome of one agent run, before outcome aggregation."""

    response_text: str
    records: List[ToolCallRecord] = field(default_factory=list)
    sources: List[RetrievedSource] = field(default_factory=list)


def _message_text(content: object) -> str:
    """Flatten a message content value into plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return str(content)


class QuizAgent:
    """Assemble and run the grounded quiz agent."""

    def __init__(self):
        self.factory = LangChainFactory()
        self.model = self.factory.create_chat_llm()

    def build_agent(self, search_tool, extract_tool):
        """Compile the agent graph. Kept separate for testability."""
        return create_agent(
            self.model,
            [search_tool, extract_tool],
            system_prompt=QUIZ_AGENT_SYSTEM_PROMPT,
        )

    async def generate(
        self,
        user_input: str,
        question_count: int = 5,
        difficulty: str = "mixed",
    ) -> AgentRunResult:
        """Run one grounded quiz generation.

        Returns:
            AgentRunResult with the final JSON text and retrieval records.

        Raises:
            AgentUnavailableError: on timeout, recursion-limit breach or any
                other agent-level failure — callers must degrade gracefully.
        """
        search_tool, extract_tool = create_grounded_tools()
        agent = self.build_agent(search_tool, extract_tool)

        messages = [{
            "role": "user",
            "content": format_agent_user_message(
                user_input=user_input,
                question_count=question_count,
                difficulty=difficulty,
            ),
        }]

        try:
            result_state = await asyncio.wait_for(
                agent.ainvoke(
                    {"messages": messages},
                    config={"recursion_limit": settings.AGENT_RECURSION_LIMIT},
                ),
                timeout=settings.AGENT_TIMEOUT_SECONDS,
            )
        except (GraphRecursionError, asyncio.TimeoutError) as exc:
            logger.warning(
                "Grounded quiz agent breached its run budget",
                error=str(exc),
                recursion_limit=settings.AGENT_RECURSION_LIMIT,
                timeout_seconds=settings.AGENT_TIMEOUT_SECONDS,
            )
            raise AgentUnavailableError(str(exc)) from exc
        except Exception as exc:
            logger.error("Grounded quiz agent failed unexpectedly", error=str(exc))
            raise AgentUnavailableError(str(exc)) from exc

        state_messages = result_state.get("messages", []) if isinstance(result_state, dict) else []
        response_text = _message_text(getattr(state_messages[-1], "content", "")) if state_messages else ""
        if not response_text.strip():
            logger.warning("Grounded quiz agent returned an empty final answer")
            raise AgentUnavailableError("empty final answer")

        records: List[ToolCallRecord] = list(search_tool.call_log) + list(extract_tool.call_log)
        sources: List[RetrievedSource] = []
        seen_urls: set[str] = set()
        for record in records:
            for source in record.sources:
                if source.url and source.url not in seen_urls:
                    seen_urls.add(source.url)
                    sources.append(source)

        logger.info(
            "Grounded quiz agent finished",
            tool_calls=len(records),
            usable_calls=sum(1 for r in records if r.status == "ok"),
            sources=len(sources),
            response_length=len(response_text),
        )
        return AgentRunResult(
            response_text=response_text,
            records=records,
            sources=sources,
        )


# Singleton instance
_quiz_agent: Optional[QuizAgent] = None


def get_quiz_agent() -> QuizAgent:
    """Get or create quiz agent singleton."""
    global _quiz_agent
    if _quiz_agent is None:
        _quiz_agent = QuizAgent()
    return _quiz_agent
