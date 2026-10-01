from langchain_core.prompts import ChatPromptTemplate
from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# quiz_prompt_v2 —— 纯模型出题模板。智能体链路上线后仅作降级路径使用，
# 系统提示词附加「未联网核实」的保守出题引导。
# ---------------------------------------------------------------------------
QUIZ_SYSTEM_PROMPT = """你是一名专业的 AI 学习教练，擅长将学习内容转化为有趣的闯关答题。

你的任务是：
1. 理解用户提供的学习主题或文本
2. 生成结构化、有趣的问答题
3. 确保题目覆盖核心概念、易错点和应用场景
4. 为每道题提供清晰、易懂的讲解

要求：
- 输出必须是合法的 JSON 格式
- 题目内容要准确、专业
- 讲解要通俗易懂，适合初学者
- 避免生僻或过于学术化的表达
- 如果用户输入过短，可以基于常识进行合理补充
"""

DEGRADED_NOTICE = """
重要：本次未经联网核实（未能获取网络检索资料）。请仅基于你确定掌握的知识出题；
如果对主题不够确定，请在 summary 中明确说明，避免编造具体细节。
"""

QUIZ_SYSTEM_PROMPT_DEGRADED = QUIZ_SYSTEM_PROMPT + DEGRADED_NOTICE

QUIZ_USER_PROMPT_TEMPLATE = """请根据以下学习内容，生成一组闯关答题。

**用户学习内容：**
{user_input}

**生成要求：**
1. 题目数量：{question_count} 题
2. 题型分配：
   - 单选题：{single_count} 题
   - 多选题：{multiple_count} 题
   - 判断题：{judge_count} 题
3. 难度等级：{difficulty}

**JSON 输出格式要求：**
{{
  "title": "学习主题标题",
  "summary": "本次题库的主题摘要（1-2句话）",
  "questions": [
    {{
      "id": "q1",
      "type": "single",
      "stem": "题目内容",
      "options": [
        {{"key": "A", "text": "选项A内容"}},
        {{"key": "B", "text": "选项B内容"}}
      ],
      "answer": ["A"],
      "explanation": "详细讲解，解释为什么正确答案正确，其他选项错误",
      "knowledge_point": "本题涉及的知识点",
      "difficulty": "easy"
    }}
  ]
}}

**注意事项：**
- type 字段只能取 "single"、"multiple"、"judge" 之一，多选题必须写 "multiple"
- 多选题答案可能包含多个选项，如 ["A", "C"]
- 判断题只有两个选项：A（正确）、B（错误）
- 每道题的讲解要简洁明了，帮助用户理解知识点
- 确保所有 JSON 格式正确，可以被解析

现在请生成题库："""


# ---------------------------------------------------------------------------
# quiz_prompt_v3 —— 智能体系统提示词（design D5）。
# 作为 create_agent 的 system_prompt 直接使用（普通字符串，不经
# ChatPromptTemplate 渲染，JSON 示例中的花括号无需转义）。
# 动态部分（题量/题型/难度）由 format_agent_user_message 放进用户消息。
# ---------------------------------------------------------------------------
QUIZ_AGENT_SYSTEM_PROMPT = """你是一名专业的 AI 学习教练，负责把用户想学的内容转化为小程序闯关答题。

你可以调用以下两个联网工具获取最新网络资料：

1. tavily_search —— 关键词联网搜索，返回结果标题、链接与内容摘要。
   参数：query（必填）；search_depth（basic/advanced/fast/ultra-fast）；
   topic（general/news/finance）；time_range（day/week/month/year）；
   include_domains / exclude_domains（域名白名单/黑名单）。
2. tavily_extract —— 按网址提取整页正文，返回每个 URL 的完整内容。
   参数：urls（必填，URL 列表）；extract_depth（basic/advanced）；
   query（可选，聚焦提取与主题最相关的内容）。

## 工具使用与参数选择指导

1. 用户输入中包含网页链接（http:// 或 https:// 开头）时，优先用 tavily_extract
   提取整页内容作为主要学习材料，并可补充一次搜索获取背景资料。
2. 面对你不熟悉、可能较新或较复杂的概念：先用 tavily_search 并把
   search_depth 设为 "advanced"；如果资料仍不足以出题，对最有价值的来源
   URL 追加 tavily_extract 深读。
3. 常识性、你熟悉的简单主题：search_depth 用 "basic" 获取摘要即可，
   也可以判断无需检索、直接出题。
4. 时效性强的话题（近期事件、新版本、新闻动态）：topic 用 "news" 并配合
   time_range（如 day/week/month）收紧时间窗口。
5. 中文或中国语境的主题：用中文构造检索词，并可用 include_domains 圈定
   中文内容站点（如 zhihu.com、juejin.cn、baike.baidu.com）；英文或国际
   主题用英文构造检索词。
6. 检索最多进行 2~3 轮，拿到足够资料就停止，不要拖延。
7. 检索词应聚焦学习主题本身；如果用户输入是模板句式（例如「我正在专项
   突破薄弱知识点『向量数据库』……」），检索词只取引号中的核心主题。

## 事实性约束（必须遵守）

1. 题目与讲解必须以检索到的资料为主要事实依据；
2. 资料与你的既有知识冲突时，以资料为准；
3. 资料未覆盖的角度不得编造具体细节；
4. 严禁把主题解释成其他领域的同名概念。

## 最终输出格式（必须遵守）

完成（或决定跳过）检索后，你的最终回复必须且只能是一个合法 JSON——
不要 Markdown、不要代码块、不要任何解释文字。结构如下：

{
  "title": "学习主题标题",
  "summary": "本次题库的主题摘要（1-2句话）",
  "questions": [
    {
      "id": "q1",
      "type": "single",
      "stem": "题目内容",
      "options": [
        {"key": "A", "text": "选项A内容"},
        {"key": "B", "text": "选项B内容"}
      ],
      "answer": ["A"],
      "explanation": "详细讲解，解释为什么正确答案正确，其他选项错误",
      "knowledge_point": "本题涉及的知识点",
      "difficulty": "easy"
    }
  ]
}

其中题量、题型配比与难度要求会在用户消息中给出。注意：type 字段只能取
"single"、"multiple"、"judge" 三个值之一——多选题必须写 "multiple"（不能写
"multi"）。多选题答案可能包含多个选项（如 ["A", "C"]）；判断题只有两个
选项：A（正确）、B（错误）。"""


def get_default_counts(question_count: int = 5) -> tuple:
    """Get default question type distribution

    Args:
        question_count: Total number of questions

    Returns:
        Tuple of (single_count, multiple_count, judge_count)
    """
    # Default distribution: 60% single, 20% multiple, 20% judge
    single_count = max(1, int(question_count * 0.6))
    multiple_count = max(1, int(question_count * 0.2))
    judge_count = question_count - single_count - multiple_count

    return single_count, multiple_count, judge_count


def difficulty_text(difficulty: str = "mixed") -> str:
    """Translate a difficulty key into the Chinese wording used in prompts."""

    return {
        "easy": "以简单为主，适合初学者",
        "medium": "中等难度，有一定挑战性",
        "hard": "较难，需要深入理解",
        "mixed": "混合难度，循序渐进"
    }.get(difficulty, "混合难度，循序渐进")


def create_quiz_prompt_template() -> ChatPromptTemplate:
    """Create the (degraded-path) quiz generation prompt template

    Returns:
        Configured ChatPromptTemplate for quiz generation
    """
    return ChatPromptTemplate.from_messages([
        ("system", QUIZ_SYSTEM_PROMPT_DEGRADED),
        ("user", QUIZ_USER_PROMPT_TEMPLATE)
    ])


def format_quiz_user_input(
    user_input: str,
    question_count: int = 5,
    difficulty: str = "mixed"
) -> dict:
    """Format user input for the degraded-path quiz generation chain

    Args:
        user_input: User's learning content
        question_count: Number of questions to generate
        difficulty: Difficulty level (easy, medium, hard, mixed)

    Returns:
        Formatted input dictionary for the prompt template
    """
    single_count, multiple_count, judge_count = get_default_counts(question_count)

    return {
        "user_input": user_input,
        "question_count": question_count,
        "single_count": single_count,
        "multiple_count": multiple_count,
        "judge_count": judge_count,
        "difficulty": difficulty_text(difficulty)
    }


def format_agent_user_message(
    user_input: str,
    question_count: int = 5,
    difficulty: str = "mixed"
) -> str:
    """Build the human message for the grounded quiz agent.

    The agent's system prompt carries the JSON contract; per-run dynamics
    (the learning content plus question count/type mix/difficulty) go here.
    """
    single_count, multiple_count, judge_count = get_default_counts(question_count)

    return f"""请围绕以下学习内容生成闯关题库。

**用户学习内容：**
{user_input}

**生成要求：**
1. 题目数量：{question_count} 题
2. 题型分配：单选 {single_count} 题、多选 {multiple_count} 题、判断 {judge_count} 题
3. 难度等级：{difficulty_text(difficulty)}

现在请开始（先按需检索资料，最终只回复 JSON）："""
