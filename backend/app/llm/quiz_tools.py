"""Thin wrappers around the official langchain-tavily tools.

The wrappers keep the tools' argument semantics untouched and add what the
grounded-quiz pipeline needs (design D4):

1. Call recording — every invocation appends a ``ToolCallRecord`` so the
   retrieval service can aggregate ``ok`` / ``no_results`` / ``unavailable``.
2. Error normalisation — upstream swallows provider exceptions into
   ``{"error": <exception>}``; we classify them (timeout/auth/rate_limit/
   network/server), log a WARNING, and hand the agent a structured
   ``{"tavily_error": <category>}`` marker instead, so aggregation stays
   deterministic. Zero-result searches/extracts are raised by the library
   itself as ``ToolException`` — recorded as "empty" and re-raised so the
   agent still sees the library's own retry suggestions.
3. Source extraction — title/url of every usable result, which become the
   quiz response's ``sources`` metadata.

Note: ``max_results``/``country`` can only be set at instantiation in
langchain-tavily 0.2.18 (invocation-time values are rejected by the library
on purpose), so the dynamic per-call knobs promised in the original design
degrade to fixed instantiation values; region/language tuning happens
through the agent-settable ``include_domains``/``exclude_domains`` and the
search-query language instead.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import ToolException
from langchain_tavily import TavilyExtract, TavilySearch
from pydantic import Field

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RetrievedSource:
    """A web source returned by one of the retrieval tools."""

    title: str
    url: str


@dataclass(frozen=True)
class ToolCallRecord:
    """Outcome of a single retrieval tool invocation."""

    tool: str
    # ok: usable material; empty: service reachable but nothing usable;
    # error: provider-level failure.
    status: Literal["ok", "empty", "error"]
    category: str = ""
    query: str = ""
    sources: Tuple[RetrievedSource, ...] = ()
    failed_urls: Tuple[str, ...] = ()


def classify_error(exc: BaseException) -> str:
    """Map a provider exception to a coarse, log-friendly category."""

    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if isinstance(exc, asyncio.TimeoutError) or "timeout" in name or "timed out" in text:
        return "timeout"
    if (
        isinstance(exc, ConnectionError)
        or "connection" in name
        or "connection" in text
        or "getaddrinfo" in text
        or "resolve" in text
    ):
        return "network"
    if "401" in text or "403" in text or "unauthorized" in text or "invalid api key" in text:
        return "auth"
    if "429" in text or "rate limit" in text or "quota" in text:
        return "rate_limit"
    return "server"


class GroundedTavilySearch(TavilySearch):
    """TavilySearch with call recording and error normalisation."""

    call_log: List[ToolCallRecord] = Field(default_factory=list)

    def _run(
        self,
        query: str,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        search_depth: Optional[str] = None,
        include_images: Optional[bool] = None,
        time_range: Optional[str] = None,
        topic: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            result = super()._run(
                query=query,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                search_depth=search_depth,
                include_images=include_images,
                time_range=time_range,
                topic=topic,
                start_date=start_date,
                end_date=end_date,
                run_manager=run_manager,
                **kwargs,
            )
        except ToolException:
            self._record("empty", query=query)
            raise
        return self._consume_result(result, query=query)

    async def _arun(
        self,
        query: str,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        search_depth: Optional[str] = None,
        include_images: Optional[bool] = None,
        time_range: Optional[str] = None,
        topic: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            result = await super()._arun(
                query=query,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                search_depth=search_depth,
                include_images=include_images,
                time_range=time_range,
                topic=topic,
                start_date=start_date,
                end_date=end_date,
                run_manager=run_manager,
                **kwargs,
            )
        except ToolException:
            self._record("empty", query=query)
            raise
        return self._consume_result(result, query=query)

    def _consume_result(
        self, result: Dict[str, Any], query: str
    ) -> Dict[str, Any]:
        error = result.get("error") if isinstance(result, dict) else None
        if error is not None:
            category = classify_error(error)
            self._record("error", query=query, category=category)
            return {"tavily_error": category}

        sources = tuple(
            RetrievedSource(
                title=str(item.get("title") or item.get("url") or ""),
                url=str(item.get("url") or ""),
            )
            for item in result.get("results", [])
        )
        self._record("ok", query=query, sources=sources)
        return result

    def _record(
        self,
        status: Literal["ok", "empty", "error"],
        query: str,
        category: str = "",
        sources: Tuple[RetrievedSource, ...] = (),
        failed_urls: Tuple[str, ...] = (),
    ) -> None:
        self.call_log.append(
            ToolCallRecord(
                tool=self.name,
                status=status,
                category=category,
                query=query,
                sources=sources,
                failed_urls=failed_urls,
            )
        )
        if status == "error":
            logger.warning(
                "Retrieval tool failed",
                tool=self.name,
                query=query[:100],
                category=category,
            )
        elif status == "empty":
            logger.info("Retrieval tool returned no usable results", tool=self.name, query=query[:100])


class GroundedTavilyExtract(TavilyExtract):
    """TavilyExtract with call recording and error normalisation."""

    call_log: List[ToolCallRecord] = Field(default_factory=list)

    def _run(
        self,
        urls: List[str],
        extract_depth: Optional[str] = None,
        include_images: Optional[bool] = None,
        query: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            result = super()._run(
                urls=urls,
                extract_depth=extract_depth,
                include_images=include_images,
                query=query,
                run_manager=run_manager,
                **kwargs,
            )
        except ToolException:
            self._record("empty", query=", ".join(urls), failed_urls=tuple(urls))
            raise
        return self._consume_result(result, urls=urls)

    async def _arun(
        self,
        urls: List[str],
        extract_depth: Optional[str] = None,
        include_images: Optional[bool] = None,
        query: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            result = await super()._arun(
                urls=urls,
                extract_depth=extract_depth,
                include_images=include_images,
                query=query,
                run_manager=run_manager,
                **kwargs,
            )
        except ToolException:
            self._record("empty", query=", ".join(urls), failed_urls=tuple(urls))
            raise
        return self._consume_result(result, urls=urls)

    def _consume_result(
        self, result: Dict[str, Any], urls: List[str]
    ) -> Dict[str, Any]:
        error = result.get("error") if isinstance(result, dict) else None
        if error is not None:
            category = classify_error(error)
            self._record("error", query=", ".join(urls), category=category)
            return {"tavily_error": category}

        extracted = result.get("results", [])
        failed_urls = tuple(
            str(item.get("url") or "")
            for item in result.get("failed_results", [])
        )
        sources = tuple(
            RetrievedSource(
                title=str(item.get("url") or ""),
                url=str(item.get("url") or ""),
            )
            for item in extracted
        )
        self._record(
            "ok",
            query=", ".join(urls),
            sources=sources,
            failed_urls=failed_urls,
        )
        return result

    def _record(
        self,
        status: Literal["ok", "empty", "error"],
        query: str,
        category: str = "",
        sources: Tuple[RetrievedSource, ...] = (),
        failed_urls: Tuple[str, ...] = (),
    ) -> None:
        self.call_log.append(
            ToolCallRecord(
                tool=self.name,
                status=status,
                category=category,
                query=query,
                sources=sources,
                failed_urls=failed_urls,
            )
        )
        if status == "error":
            logger.warning(
                "Retrieval tool failed",
                tool=self.name,
                urls=query[:200],
                category=category,
            )
        elif status == "empty":
            logger.info(
                "Retrieval tool returned no usable results",
                tool=self.name,
                urls=query[:200],
            )


def create_grounded_tools() -> Tuple[GroundedTavilySearch, GroundedTavilyExtract]:
    """Build fresh tool instances for one agent run.

    Fresh instances keep each generation's ``call_log`` isolated. The API key
    is passed explicitly so the app works even though pydantic-settings only
    loads it into ``Settings`` and never exports it as an environment variable.
    """

    search = GroundedTavilySearch(
        max_results=settings.TAVILY_MAX_RESULTS,
        topic="general",
        search_depth="basic",
        include_answer=False,
        include_raw_content=False,
        include_images=False,
        tavily_api_key=settings.TAVILY_API_KEY,
    )
    extract = GroundedTavilyExtract(
        extract_depth="basic",
        include_images=False,
        tavily_api_key=settings.TAVILY_API_KEY,
    )
    return search, extract
