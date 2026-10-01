## Why

当前出题链路（`QuizService -> QuizChain -> DeepSeek`）完全依赖模型参数化知识，没有任何联网检索环节。大模型训练数据存在截止时间，遇到训练截止后出现的新概念（例如「Harness Engineering」）时，模型会把它错误地套到旧领域的知识上，生成张冠李戴的题目和讲解；此外用户可能直接输入一个网页地址作为学习材料，现有链路既无法读取网页内容，也无法检索其背景知识。需求分析文档第 2 节明确要求「AI 自动从全网获取知识补充」，现在需要把联网资料获取能力补进出题链路。

## What Changes

- 出题链路改造为「AI 自主调用联网工具」模式（已与用户确认）：把 LangChain 官方 Tavily 集成的两个工具同时提供给出题智能体，由 AI 自主决定是否调用、调用哪个、调用几次以及如何填参——`TavilySearch`（关键词联网搜索）与 `TavilyExtract`（按网址提取整页内容），覆盖两类输入：
  - 关键词/一段话输入 → AI 构造检索词发起搜索；
  - 输入中包含网页 URL → AI 优先提取整页内容（可再补充搜索背景资料）。
- AI 动态选择工具参数以兼顾国内外用户与主题复杂度（已与用户确认）：复杂/陌生知识 → `search_depth="advanced"` 获取更完整内容并可用 `TavilyExtract` 深读；简单知识 → `basic` 搜索摘要即可；时效性强的话题 → `topic="news"` + `time_range`；地域相关性 → 动态填 `include_domains/exclude_domains`（如中文主题圈定中文内容站点）并选择检索词语言。
- 运行机制采用 LangChain 1.x 官方 `create_agent`（langgraph 内核，已与用户确认），模型为现有 DeepSeek；支持循环步数与总时长上限，超限自动降级。
- 兜底策略延续「区分对待」原则并适配自主模式（已与用户确认 AI 完全自主决定是否检索）：AI 调用了工具但所有调用均无可读资料 → 返回明确业务错误（提示换个说法/补充背景）；工具故障、超时、循环超限或 AI 未调用工具 → 降级为纯模型出题并在响应标注 `search_used=false`；`SEARCH_ENABLED=false` 时完全跳过智能体直接纯模型出题。
- 出题 Prompt 升级为 `quiz_prompt_v3`：智能体系统提示词内含工具选择指导、参数选择指导、事实性约束（资料与模型既有知识冲突时以资料为准、不编造资料外细节、禁止跨领域套用）与最终 JSON 输出格式。
- 生成响应新增可选元数据 `search_used` 与 `sources`（标题 + URL，来源含搜索结果与被提取网页），向后兼容；仅生成时返回，不持久化。
- **BREAKING（依赖）**：LangChain 0.3.7 → 1.x（含 `langchain-core`、`langchain-openai` 同步升级，新增 `langgraph`、`langchain-tavily`）——这是启用官方 Tavily 工具集的前提，已获用户确认；升级需迁移并回归出题、报告两条既有链路。
- 前端闯关页在题库标题下展示联网核实状态标识；首页生成按钮文案体现「检索资料并生成」。
- **不做**：检索结果持久化与缓存；来源完整列表 UI；报告生成链路的功能改动（仅随依赖升级做等价迁移）；自建搜索适配层（`app/clients/tavily_client.py` 方案废弃，改用官方集成包）。

## Capabilities

### New Capabilities

- `search-grounded-quiz-generation`: 出题链路的联网资料获取增强——关键词搜索与网址提取双通道、AI 自主工具调用与参数动态选择、资料注入出题的事实性约束、三类失败路径（无可读资料/工具故障或未调用/功能关闭）的差异化兜底、响应检索元数据，以及对 `/generate` 与 `/drill` 两个入口的一致约束。

### Modified Capabilities

（无——`openspec/specs/` 目前为空，本次是该项目第一批规格。）

## Impact

- **依赖（BREAKING）**：`requirements.txt` 中 `langchain==0.3.7 / langchain-core==0.3.21 / langchain-openai==0.2.10` 升级到 1.x 对应版本；新增 `langchain-tavily`（官方 Tavily 集成，读 `TAVILY_API_KEY` 环境变量）与 `langgraph`（`create_agent` 运行内核）。出题链与报告链的既有写法需按 1.x 迁移并全量回归。
- **后端新增**：`app/llm/quiz_agent.py`（基于 `create_agent` 的出题智能体：装配两个 Tavily 工具、循环上限、结果聚合）、`app/llm/quiz_tools.py`（官方工具薄封装：错误分类留痕、来源抽取、`max_results` 动态入参）、`app/services/retrieval_service.py`（三态聚合与差异化兜底策略）。
- **后端修改**：`app/prompts/quiz_prompt.py`（v3 智能体系统提示词）、`app/llm/quiz_chain.py`（保留为降级路径并适配 1.x）、`app/llm/langchain_factory.py`（1.x 适配）、`app/llm/report_chain.py`（仅依赖迁移）、`app/services/quiz_service.py`（智能体优先、降级兜底的编排）、`app/models/quiz.py`（`QuizResponse` 可选字段与 `SearchSource`）、`app/core/config.py`（Tavily/智能体配置项）、`app/core/exceptions.py`（无可读资料业务异常）、`.env.example`、两份 README。
- **API 变更**：`POST /api/v1/quiz/generate` 与 `POST /api/v1/quiz/drill` 响应体新增可选字段 `search_used`、`sources`（向后兼容）；新增「无可读资料」业务错误分支。
- **外部依赖**：Tavily API（search 与 extract 两个端点；免费额度每月 1000 credits，advanced 搜索消耗更多）。
- **前端修改**：`src/utils/api.ts`（`QuizData` 可选字段）、`src/pages/quiz/index.tsx`（核实状态标识）、`src/pages/index/index.tsx`（生成中文案）。
- **测试**：新增工具封装、智能体编排、兜底聚合与 API 集成测试；依赖升级后现有全部测试需保持通过（行为等价迁移）。
- **延迟与成本**：智能体模式延迟不确定性更高（多次工具往返），以循环步数上限 + 总时长上限 + 降级路径约束；每次出题成本增加检索 credits，属已确认取舍。
