from langchain_core.runnables import Runnable
from app.llm.langchain_factory import LangChainFactory
from app.llm.output_schemas import StructuredReportOutput
from app.prompts.report_prompt import create_report_prompt_template, format_report_user_input
from app.core.logging import get_logger

logger = get_logger(__name__)


class ReportChain:
    """Chain for generating learning report from quiz results"""

    def __init__(self):
        self.factory = LangChainFactory()
        self.llm = self.factory.create_chat_llm_for_report()
        self.prompt = create_report_prompt_template()

    def create_chain(self) -> Runnable:
        """Create the report generation chain

        Returns:
            Runnable chain for report generation
        """
        # Create chain with structured output.
        # method must stay explicit: langchain-openai 1.x defaults to
        # "json_schema", which DeepSeek rejects with a 400
        # ("This response_format type is unavailable now").
        chain = (
            self.prompt
            | self.llm.with_structured_output(
                schema=StructuredReportOutput,
                method="function_calling",
            )
        )

        return chain

    async def generate_report(
        self,
        topic: str,
        questions: list,
        answer_records: list
    ) -> StructuredReportOutput:
        """Generate a learning report

        Args:
            topic: Learning topic
            questions: List of Question objects
            answer_records: List of AnswerRecord objects

        Returns:
            StructuredReportOutput containing generated report

        Raises:
            Exception: If generation fails
        """
        logger.info(
            "Generating report",
            topic=topic,
            answer_count=len(answer_records)
        )

        # Format input
        formatted_input = format_report_user_input(
            topic=topic,
            questions=questions,
            answer_records=answer_records
        )

        # Get chain
        chain = self.create_chain()

        # Invoke chain
        try:
            result = await chain.ainvoke(formatted_input)
            logger.info(
                "Report generated successfully",
                accuracy=result.accuracy,
                weak_points_count=len(result.weak_points)
            )
            return result
        except Exception as e:
            logger.error("Report generation failed", error=str(e))
            raise


# Singleton instance
_report_chain: ReportChain | None = None


def get_report_chain() -> ReportChain:
    """Get or create report chain singleton

    Returns:
        ReportChain instance
    """
    global _report_chain
    if _report_chain is None:
        _report_chain = ReportChain()
    return _report_chain
