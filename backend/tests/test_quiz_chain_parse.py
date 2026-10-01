"""Tests for the tolerant quiz JSON extractor (parse_quiz_response)."""

import json

import pytest

from app.llm.quiz_chain import parse_quiz_response

VALID_QUIZ = {
    "title": "Harness Engineering",
    "summary": "s",
    "questions": [{
        "id": "q1",
        "type": "single",
        "stem": "s?",
        "options": [{"key": "A", "text": "a"}, {"key": "B", "text": "b"}],
        "answer": ["A"],
        "explanation": "e",
        "knowledge_point": "k",
        "difficulty": "easy",
    }],
}


def test_plain_json_passes_through():
    output = parse_quiz_response(json.dumps(VALID_QUIZ, ensure_ascii=False))
    assert output.title == "Harness Engineering"


def test_json_with_leading_prose_and_fences():
    raw = "好的，以下是根据网络资料生成的题库：\n```json\n" + json.dumps(VALID_QUIZ, ensure_ascii=False) + "\n```\n希望对你有帮助！"
    output = parse_quiz_response(raw)
    assert output.title == "Harness Engineering"


def test_json_with_prose_but_no_fences():
    raw = "这是题目：\n" + json.dumps(VALID_QUIZ, ensure_ascii=False) + "\n以上。"
    output = parse_quiz_response(raw)
    assert output.title == "Harness Engineering"


def test_unparsable_text_still_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_quiz_response("完全不是 JSON 的回复")


def test_multi_type_alias_is_normalised():
    variant = {**VALID_QUIZ, "questions": [{**VALID_QUIZ["questions"][0], "type": "multi"}]}
    output = parse_quiz_response(json.dumps(variant, ensure_ascii=False))
    assert output.questions[0].type.value == "multiple"
