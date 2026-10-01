"""报告链结构化输出方式契约与离线生成路径测试。

langchain-openai 1.x 把 with_structured_output 的默认 method 改成了
"json_schema"，而 DeepSeek 不支持该响应格式（400: This response_format
type is unavailable now）。这里的测试把 method="function_calling" 固化为
显式契约，防止未来默认值再次漂移时报告链路悄悄回归。
"""

from unittest.mock import MagicMock

import pytest
from langchain_core.runnables import RunnableLambda

from app.llm.output_schemas import StructuredReportOutput
from app.llm.report_chain import ReportChain
from app.models.quiz import DifficultyLevel, Option, Question, QuestionType
from app.models.report import AnswerRecord, ReportCreateRequest
from app.services.report_service import ReportService


def _make_question(question_id: str, answer_key: str) -> Question:
    return Question(
        id=question_id,
        type=QuestionType.SINGLE,
        stem="什么是 RAG？",
        options=[Option(key="A", text="检索增强生成"), Option(key="B", text="普通搜索")],
        answer=[answer_key],
        explanation="RAG 是检索增强生成。",
        knowledge_point="RAG 定义",
        difficulty=DifficultyLevel.EASY,
    )


def _make_record(question_id: str, selected: str, is_correct: bool) -> AnswerRecord:
    return AnswerRecord(
        question_id=question_id,
        selected_answers=[selected],
        is_correct=is_correct,
        duration_ms=1000,
    )


def _structured_llm_stub(output: StructuredReportOutput):
    """返回一个记录 with_structured_output 入参的 spy LLM。"""

    spy_llm = MagicMock()
    spy_llm.with_structured_output.return_value = RunnableLambda(lambda _: output)
    return spy_llm


def test_report_chain_pins_structured_output_to_function_calling():
    """报告链必须显式以 function_calling 方式请求结构化输出。"""

    chain = ReportChain()
    spy_llm = _structured_llm_stub(
        StructuredReportOutput(
            accuracy=100,
            mastered_points=["RAG 定义"],
            weak_points=["RAG 边界"],
            three_line_summary=["一", "二", "三"],
            advice=["继续学习"],
            share_quote="继续闯关。",
        )
    )
    chain.llm = spy_llm

    chain.create_chain()

    spy_llm.with_structured_output.assert_called_once()
    call_kwargs = spy_llm.with_structured_output.call_args.kwargs
    assert call_kwargs.get("schema") is StructuredReportOutput
    assert call_kwargs.get("method") == "function_calling"


@pytest.mark.asyncio
async def test_report_service_offline_path_derives_accuracy_from_records():
    """离线跑通主流程：fake LLM 出合法结构，service 产出 ReportResponse，
    accuracy 取后端统计而非模型返回值。"""

    chain = ReportChain()
    # 模型声称 accuracy=0，实际记录为对一错一，应为 50。
    spy_llm = _structured_llm_stub(
        StructuredReportOutput(
            accuracy=0,
            mastered_points=["RAG 定义"],
            weak_points=["RAG 边界"],
            three_line_summary=["一", "二", "三"],
            advice=["继续学习"],
            share_quote="继续闯关。",
        )
    )
    chain.llm = spy_llm
    service = ReportService()
    service.report_chain = chain

    response = await service.generate_report(
        ReportCreateRequest(
            quiz_id="quiz_123",
            topic="RAG 入门",
            questions=[
                _make_question("q1", "A"),
                _make_question("q2", "A"),
            ],
            answer_records=[
                _make_record("q1", "A", True),
                _make_record("q2", "B", False),
            ],
        )
    )

    assert response.accuracy == 50
    assert response.mastered_points == ["RAG 定义"]
    assert response.weak_points == ["RAG 边界"]
    spy_llm.with_structured_output.assert_called_once()
