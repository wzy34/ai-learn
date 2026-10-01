// Curated learning topics for the 题库 tab. Each topic generates a quiz
// through the existing /quiz/generate endpoint with a pre-written prompt.

export interface QuizTopic {
  icon: string
  title: string
  description: string
  prompt: string
}

export const QUIZ_TOPICS: QuizTopic[] = [
  {
    icon: '🤖',
    title: 'AI 大模型基础',
    description: 'LLM 是什么、能做什么',
    prompt:
      '我想入门大语言模型（LLM），请帮我搞懂：什么是大语言模型、它和传统程序的区别、Token 和上下文窗口是什么、幻觉是什么意思。最好通过闯关题帮我记住这些重点。'
  },
  {
    icon: '🔍',
    title: 'RAG 检索增强',
    description: '让 AI 的回答有据可依',
    prompt:
      '我想学习 RAG（检索增强生成），重点搞懂：RAG 和传统搜索的区别、向量检索是怎么工作的、为什么要用向量数据库、RAG 的典型流程是什么。最好通过闯关题帮我巩固。'
  },
  {
    icon: '✍️',
    title: '提示词工程',
    description: '把 AI 问对、问明白',
    prompt:
      '我想学习提示词工程（Prompt Engineering），请覆盖：清晰指令的写法、角色设定、少样本示例（Few-shot）、思维链（CoT）和常见误区。最好通过闯关题帮我记住要点。'
  },
  {
    icon: '🧠',
    title: '机器学习入门',
    description: '从监督学习开始打基础',
    prompt:
      '我想入门机器学习，重点搞懂：监督学习和无监督学习的区别、训练集和测试集、过拟合是什么、常见算法适合什么场景。最好通过闯关题帮我打基础。'
  },
  {
    icon: '🐍',
    title: 'Python 基础',
    description: '语法与常用数据结构',
    prompt:
      '我想巩固 Python 基础，重点覆盖：列表/字典/元组的区别、切片操作、函数与作用域、常见易错语法。最好通过闯关题帮我查漏补缺。'
  },
  {
    icon: '🌐',
    title: '计算机网络',
    description: '从 HTTP 到 TCP',
    prompt:
      '我想学习计算机网络基础，重点搞懂：TCP 和 UDP 的区别、三次握手、HTTP 和 HTTPS 的区别、从输入网址到页面显示的过程。最好通过闯关题帮我记住重点。'
  }
]
