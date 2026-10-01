from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LangChainFactory:
    """Factory for creating LangChain components"""

    @staticmethod
    def create_chat_llm() -> BaseChatModel:
        """
        Create a ChatOpenAI instance configured for DeepSeek

        Returns:
            Configured ChatOpenAI instance
        """
        if not settings.DEEPSEEK_API_KEY:
            logger.warning("DEEPSEEK_API_KEY not configured, using placeholder")
            # For testing purposes without API key
            return ChatOpenAI(
                model=settings.DEEPSEEK_MODEL,
                base_url=settings.DEEPSEEK_BASE_URL,
                api_key="placeholder",  # Will fail in real calls
                temperature=settings.DEEPSEEK_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                timeout=settings.LLM_TIMEOUT,
            )

        logger.info(
            "Creating ChatOpenAI for DeepSeek",
            model=settings.DEEPSEEK_MODEL,
            base_url=settings.DEEPSEEK_BASE_URL,
        )

        return ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            base_url=settings.DEEPSEEK_BASE_URL,
            api_key=settings.DEEPSEEK_API_KEY,
            temperature=settings.DEEPSEEK_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
            max_retries=settings.LLM_MAX_RETRIES,
        )

    @staticmethod
    def create_chat_llm_for_report() -> BaseChatModel:
        """
        Create a ChatOpenAI instance for report generation

        Uses slightly higher temperature for more varied, helpful responses

        Returns:
            Configured ChatOpenAI instance for reports
        """
        if not settings.DEEPSEEK_API_KEY:
            return ChatOpenAI(
                model=settings.DEEPSEEK_MODEL,
                base_url=settings.DEEPSEEK_BASE_URL,
                api_key="placeholder",
                temperature=0.5,  # Higher temperature for reports
                max_tokens=settings.LLM_MAX_TOKENS,
                timeout=settings.LLM_TIMEOUT,
            )

        return ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            base_url=settings.DEEPSEEK_BASE_URL,
            api_key=settings.DEEPSEEK_API_KEY,
            temperature=0.5,  # Higher temperature for reports
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
            max_retries=settings.LLM_MAX_RETRIES,
        )
