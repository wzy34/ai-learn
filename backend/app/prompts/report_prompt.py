from langchain_core.prompts import ChatPromptTemplate
from app.core.logging import get_logger

logger = get_logger(__name__)


# System prompt for report generation
REPORT_SYSTEM_PROMPT = """你是一名学习复盘教练，擅长分析学员的答题情况，提供鼓励性的学习建议。

你的任务是：
1. 分析学员的答题记录，给出准确的统计
2. 识别掌握较好的知识点和薄弱环节
3. 提供具体、可操作的学习建议
4. 生成适合分享的学习金句

要求：
- 输出必须是合法的 JSON 格式
- 语言风格清晰、鼓励式，但不要空泛
- 分析应基于真实答题情况，不要编造
- 总结要适合移动端阅读，简洁有力
"""

# User prompt template for report generation
REPORT_USER_PROMPT_TEMPLATE = """请根据以下答题记录，生成学习复盘报告。

**学习主题：** {topic}

**答题统计：**
- 总题数：{total_questions}
- 答对题数：{correct_count}
- 答错题数：{wrong_count}
- 正确率：{accuracy}%

**答错的题目：**
{wrong_questions}

**答对的题目：**
{correct_questions}

**JSON 输出格式要求：**
{{
  "accuracy": {accuracy},
  "mastered_points": [
    "掌握的知识点1",
    "掌握的知识点2"
  ],
  "weak_points": [
    "薄弱的知识点1（来自错题）",
    "薄弱的知识点2（来自错题）"
  ],
  "three_line_summary": [
    "第一个关键知识点总结",
    "第二个关键知识点总结",
    "第三个关键知识点总结"
  ],
  "advice": [
    "具体学习建议1",
    "具体学习建议2"
  ],
  "share_quote": "一句话学习金句，适合分享到朋友圈"
}}

**分析要点：**
1. mastered_points：从答对的题目中提取知识点
2. weak_points：从答错的题目中提取知识点
3. three_line_summary：涵盖本次学习的3个核心要点
4. advice：针对薄弱点给出具体改进建议
5. share_quote：简洁有力，10-15个汉字

现在请生成复盘报告："""


def create_report_prompt_template() -> ChatPromptTemplate:
    """Create the report generation prompt template

    Returns:
        Configured ChatPromptTemplate for report generation
    """
    return ChatPromptTemplate.from_messages([
        ("system", REPORT_SYSTEM_PROMPT),
        ("user", REPORT_USER_PROMPT_TEMPLATE)
    ])


def format_report_user_input(
    topic: str,
    questions: list,
    answer_records: list
) -> dict:
    """Format user input for report generation

    Args:
        topic: Learning topic
        questions: List of Question objects
        answer_records: List of AnswerRecord objects

    Returns:
        Formatted input dictionary for the prompt template
    """
    # Calculate statistics
    total_questions = len(answer_records)
    correct_count = sum(1 for r in answer_records if r.is_correct)
    wrong_count = total_questions - correct_count
    accuracy = int((correct_count / total_questions * 100)) if total_questions > 0 else 0

    # Build wrong questions text
    wrong_items = []
    correct_items = []

    for record in answer_records:
        question = next((q for q in questions if q.id == record.question_id), None)
        if not question:
            continue

        if record.is_correct:
            correct_items.append(
                f"- {question.stem}（正确答案：{', '.join(question.answer)}）"
            )
        else:
            user_answer = ', '.join(record.selected_answers) if record.selected_answers else "未作答"
            wrong_items.append(
                f"- {question.stem}（你的答案：{user_answer}，正确答案：{', '.join(question.answer)}）"
            )

    wrong_text = "\n".join(wrong_items) if wrong_items else "无"
    correct_text = "\n".join(correct_items) if correct_items else "无"

    return {
        "topic": topic,
        "total_questions": total_questions,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "accuracy": accuracy,
        "wrong_questions": wrong_text,
        "correct_questions": correct_text
    }
