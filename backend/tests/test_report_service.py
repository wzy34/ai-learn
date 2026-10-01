from unittest.mock import AsyncMock

import pytest

from app.llm.output_schemas import StructuredReportOutput
from app.models.quiz import DifficultyLevel, Option, Question, QuestionType
from app.models.report import AnswerRecord, ReportCreateRequest
from app.core.exceptions import ReportValidationError
from app.services.report_service import ReportService


def _single_question(question_id: str) -> Question:
    return Question(
        id=question_id,
        type=QuestionType.SINGLE,
        stem="什么是 RAG？",
        options=[Option(key="A", text="检索增强生成"), Option(key="B", text="普通搜索")],
        answer=["A"],
        explanation="RAG 是检索增强生成。",
        knowledge_point="RAG 定义",
        difficulty=DifficultyLevel.EASY,
    )


def _make_request(
    answers: list[tuple[str, str, bool]],
) -> ReportCreateRequest:
    return ReportCreateRequest(
        quiz_id="quiz_123",
        topic="RAG 入门",
        questions=[_single_question(question_id) for question_id, _, _ in answers],
        answer_records=[
            AnswerRecord(
                question_id=question_id,
                selected_answers=[selected],
                is_correct=is_correct,
                duration_ms=1000,
            )
            for question_id, selected, is_correct in answers
        ],
    )


def _service_returning(output: StructuredReportOutput) -> ReportService:
    service = ReportService()
    service.report_chain = AsyncMock()
    service.report_chain.generate_report.return_value = output
    return service


@pytest.mark.asyncio
async def test_report_accuracy_is_calculated_from_answer_records_not_llm_output():
    service = ReportService()
    service.report_chain = AsyncMock()
    service.report_chain.generate_report.return_value = StructuredReportOutput(
        accuracy=0,
        mastered_points=["RAG 定义"],
        weak_points=["RAG 边界"],
        three_line_summary=["第一点", "第二点", "第三点"],
        advice=["继续学习"],
        share_quote="继续闯关。",
    )
    question = Question(
        id="q1",
        type=QuestionType.SINGLE,
        stem="什么是 RAG？",
        options=[Option(key="A", text="检索增强生成"), Option(key="B", text="普通搜索")],
        answer=["A"],
        explanation="RAG 是检索增强生成。",
        knowledge_point="RAG 定义",
        difficulty=DifficultyLevel.EASY,
    )
    request = ReportCreateRequest(
        quiz_id="quiz_123",
        topic="RAG 入门",
        questions=[question],
        answer_records=[
            AnswerRecord(
                question_id="q1",
                selected_answers=["A"],
                is_correct=True,
                duration_ms=1000,
            )
        ],
    )

    response = await service.generate_report(request)

    assert response.accuracy == 100


@pytest.mark.asyncio
async def test_report_rejects_incomplete_answer_records_before_calling_the_llm():
    service = ReportService()
    service.report_chain = AsyncMock()
    first_question = Question(
        id="q1",
        type=QuestionType.SINGLE,
        stem="什么是 RAG？",
        options=[Option(key="A", text="检索增强生成"), Option(key="B", text="普通搜索")],
        answer=["A"],
        explanation="RAG 是检索增强生成。",
        knowledge_point="RAG 定义",
        difficulty=DifficultyLevel.EASY,
    )
    second_question = Question(
        id="q2",
        type=QuestionType.JUDGE,
        stem="RAG 能完全消除幻觉吗？",
        options=[Option(key="A", text="正确"), Option(key="B", text="错误")],
        answer=["B"],
        explanation="RAG 只能降低幻觉风险。",
        knowledge_point="RAG 边界",
        difficulty=DifficultyLevel.MEDIUM,
    )
    request = ReportCreateRequest(
        quiz_id="quiz_123",
        topic="RAG 入门",
        questions=[first_question, second_question],
        answer_records=[
            AnswerRecord(
                question_id="q1",
                selected_answers=["A"],
                is_correct=True,
                duration_ms=1000,
            )
        ],
    )

    with pytest.raises(ReportValidationError):
        await service.generate_report(request)

    service.report_chain.generate_report.assert_not_awaited()


@pytest.mark.asyncio
async def test_report_rejects_client_claims_that_do_not_match_selected_answers():
    service = ReportService()
    service.report_chain = AsyncMock()
    question = Question(
        id="q1",
        type=QuestionType.SINGLE,
        stem="什么是 RAG？",
        options=[Option(key="A", text="检索增强生成"), Option(key="B", text="普通搜索")],
        answer=["A"],
        explanation="RAG 是检索增强生成。",
        knowledge_point="RAG 定义",
        difficulty=DifficultyLevel.EASY,
    )
    request = ReportCreateRequest(
        quiz_id="quiz_123",
        topic="RAG 入门",
        questions=[question],
        answer_records=[
            AnswerRecord(
                question_id="q1",
                selected_answers=["B"],
                is_correct=True,
                duration_ms=1000,
            )
        ],
    )

    with pytest.raises(ReportValidationError):
        await service.generate_report(request)

    service.report_chain.generate_report.assert_not_awaited()


@pytest.mark.asyncio
async def test_report_all_correct_allows_empty_weak_points():
    """全对时模型自然返回空 weak_points，报告必须照常生成。"""

    service = _service_returning(
        StructuredReportOutput(
            accuracy=100,
            mastered_points=["RAG 定义"],
            weak_points=[],
            three_line_summary=["一", "二", "三"],
            advice=["继续学习"],
            share_quote="继续闯关。",
        )
    )

    response = await service.generate_report(
        _make_request([("q1", "A", True), ("q2", "A", True)])
    )

    assert response.accuracy == 100
    assert response.weak_points == []


@pytest.mark.asyncio
async def test_report_all_wrong_allows_empty_mastered_points():
    """全错时模型自然返回空 mastered_points，报告必须照常生成。"""

    service = _service_returning(
        StructuredReportOutput(
            accuracy=0,
            mastered_points=[],
            weak_points=["RAG 定义"],
            three_line_summary=["一", "二", "三"],
            advice=["继续学习"],
            share_quote="继续闯关。",
        )
    )

    response = await service.generate_report(
        _make_request([("q1", "B", False), ("q2", "B", False)])
    )

    assert response.accuracy == 0
    assert response.mastered_points == []


@pytest.mark.asyncio
async def test_report_rejects_summary_without_exactly_three_lines():
    service = _service_returning(
        StructuredReportOutput(
            accuracy=50,
            mastered_points=["RAG 定义"],
            weak_points=["RAG 边界"],
            three_line_summary=["一", "二"],
            advice=["继续学习"],
            share_quote="继续闯关。",
        )
    )

    with pytest.raises(ReportValidationError):
        await service.generate_report(_make_request([("q1", "A", True)]))


@pytest.mark.asyncio
async def test_report_rejects_overlong_share_quote():
    service = _service_returning(
        StructuredReportOutput(
            accuracy=50,
            mastered_points=["RAG 定义"],
            weak_points=["RAG 边界"],
            three_line_summary=["一", "二", "三"],
            advice=["继续学习"],
            share_quote="长" * 101,
        )
    )

    with pytest.raises(ReportValidationError):
        await service.generate_report(_make_request([("q1", "A", True)]))
