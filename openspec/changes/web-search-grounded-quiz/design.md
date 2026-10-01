## Context

当前出题链路为 `QuizService.generate_quiz()` → `QuizChain`（`ChatPromptTemplate | ChatOpenAI | StrOutputParser`）→ JSON 清洗与 `StructuredQuizOutput` 校验，全程无联网环节；`/quiz/generate` 与 `/quiz/drill` 共用该 Service。本次按用户确认的新思路重构为「AI 自主调用联网工具」模式，并已完成官方文档与依赖核实：

- LangChain 官方 Tavily 集成为 `langchain-tavily` 包：`TavilySearch`（关键词搜索）与 `TavilyExtract`（按 URL 提取整页），均原生支持 async，凭证读 `TAVILY_API_KEY` 环境变量。
- 参数面（官方文档核对）：`TavilySearch` 实例化参数为 `max_results/topic/include_answer/include_raw_content/include_images/include_image_descriptions/search_depth/time_range/include_domains/exclude_domains`；**调用时**可由 agent 动态设置的仅 `query/include_images/search_depth/time_range/include_domains/exclude_domains`；`include_answer/include_raw_content`（响应体积相关）与 `max_results/topic` 不可在调用时修改。`TavilyExtract` 调用参数 `urls`，`extract_depth/include_images` 可实例化或调用时设置；返回 `results[].raw_content` 与 `failed_results`。
- 运行机制：LangChain 1.x `from langchain.agents import create_agent`（langgraph 内核，`langchain` 1.x 已传递依赖 `langgraph>=1.2.11`），`agent.invoke/ainvoke({"messages": [...]})`，支持 `response_format`（`ToolStrategy`/`ProviderStrategy`）与 middleware。
- 版本约束：`langchain-tavily` 最新 0.2.18 要求 `langchain>=1.0`、`langchain-core>=1.2.11`，与现有锁定 `langchain==0.3.7 / langchain-core==0.3.21` 不兼容；用户已确认升级 LangChain 1.x。升级目标版本矩阵：`langchain==1.3.18`（要求 `langchain-core>=1.6.0`、`langgraph>=1.2.11`）、`langchain-openai==1.6.0`、`langchain-tavily==0.2.18`、`pydantic>=2.7.4`（现有 2.9.2 满足）。
- 动机与行为契约见 proposal.md 与 specs/；用户已确认的三个关键决策：升级 LangChain 1.x、`create_agent` 运行机制、AI 完全自主决定是否检索。

## Goals / Non-Goals

**Goals:**

- 出题智能体同时持有搜索与提取两个官方工具，由 DeepSeek 自主决策调用时机、工具与参数，覆盖关键词与网页 URL 两类输入。
- 参数动态选择落地为系统提示词内的明确指导规则（复杂度→深度、时效→news/time_range、地域语言→include/exclude_domains+检索词语言），并兜住官方工具「部分参数不可调用时设置」的限制。
- 失败路径严格三分：无资料可用（工具成功但空）→ 业务报错；故障或未调用/循环超限 → 降级标注；开关关闭 → 跳过智能体。响应元数据可观测。
- 依赖升级与功能新增分两步走：先完成 1.x 升级且全部既有测试通过，再叠加智能体能力，保证每一步可验证、可回退。

**Non-Goals:**

- 不做 LangGraph 深度特性（自定义 state、middleware 编排、多智能体、持久化 checkpoint）；`create_agent` 仅作标准工具循环使用。
- 不做检索结果持久化、缓存、来源完整列表 UI；不改报告链路的功能语义（仅依赖等价迁移）。
- 不追求覆盖 Tavily 全部参数（images、answer 等与出题无关的能力不启用）。

## Decisions

### D1. 智能体架构：`create_agent` + 双官方工具，现有 `QuizChain` 保留为降级路径

新增 `app/llm/quiz_agent.py`：以 `LangChainFactory` 产出的 DeepSeek `ChatOpenAI` 实例与两个工具构建 `create_agent(model, tools, system_prompt=...)`，对外提供 `generate_quiz(user_input, ...)`，返回「题库 JSON 文本 + 聚合后的检索结论」。`QuizService` 先走智能体，按聚合结论走三种路径（D6）；智能体失败、超时、超限或未获得资料时，回落到现有 `QuizChain`（纯模型出题），该链路同时就是降级路径——不新增第二套生成实现。

- 备选一：Service 层确定性检索 + 固定 Prompt 注入（上一版方案）——被用户否决，AI 无法针对 URL 输入提取整页，也无法按主题复杂度调参。
- 备选二：手写 `bind_tools` 循环——不加依赖可控性强，但用户已确认采用官方 `create_agent`（langgraph），循环控制、工具调度、错误传播均为官方实现。

### D2. LangChain 0.3.7 → 1.x 升级（BREAKING，已获用户确认）

`requirements.txt` 目标矩阵（实施时以当周最新稳定 patch 为准）：`langchain==1.3.18`、`langchain-core` 同步升到 `>=1.6.0` 最新、`langchain-openai==1.6.0`、`langchain-tavily==0.2.18`、`langgraph>=1.2.11`（显式钉住）。迁移点与验证：

1. `app/llm/langchain_factory.py`：`ChatOpenAI`（`langchain_openai`）在 1.x 仍存在，`base_url/api_key/temperature/max_tokens/timeout/max_retries` 参数签名保持，预计零改动或仅 import 调整。
2. `app/llm/quiz_chain.py` / `report_chain.py`：`ChatPromptTemplate | llm | StrOutputParser` 的 LCEL 管道与 `with_structured_output` 在 1.x 均保留；`StrOutputParser` 从 `langchain_core.output_parsers` 导入不变。
3. 升级后先跑全量 `pytest` 确认既有行为等价，再进入功能开发（任务分组即按此排序）。
- 风险对冲：升级与功能分两个提交/任务组，升级组若发现 1.x 破坏性变更过大，可回退依赖重新评估；此时整体方案退回「保 0.3.7 + 旧版工具包或自定义工具」需再次与用户确认。

### D3. 工具装配与参数动态选择

`create_agent` 的模型为 `ChatOpenAI(model=deepseek-chat, base_url=...)`（DeepSeek 官方支持 OpenAI 风格 function calling）。工具实例化基线：

- `TavilySearch(max_results=6, topic="general", search_depth="basic", include_answer=False, include_raw_content=False, include_images=False)`
- `TavilyExtract(extract_depth="basic", include_images=False)`

系统提示词内置参数选择指导表（对应规格「AI 自主决策」需求）：

| 主题特征 | 指导规则 |
| --- | --- |
| 新概念/生疏/复杂 | 搜索用 `search_depth="advanced"`；资料仍不足时对高价值来源 URL 追加 `TavilyExtract` |
| 常识性/简单 | `search_depth="basic"` 取摘要即可 |
| 近期动态/时效强 | `topic` 配合 `time_range`（day/week/month/year）收紧时间窗 |
| 中文/中国语境 | 检索词用中文 + `include_domains` 圈定中文内容站点；国际主题用英文检索词并可 `exclude_domains` 排除噪声域 |
| 结果数量期望 | 经薄封装暴露的 `max_results`（3~8）按主题宽窄调节（见下） |

两处官方工具限制的处理：

- `country`（国别）参数未被 `langchain-tavily` 暴露（REST API 有但工具未开放）→ 「地域范围动态调节」以 `include_domains/exclude_domains` + 检索词语言实现，并在 README 中如实记录该限制。
- `max_results` 不可调用时设置 → 以薄封装子类扩展工具入参 schema 暴露 `max_results`（透传给底层客户端，缺省用实例化默认值），由 AI 动态填 3~8；实施时验证子类机制与安装版本的兼容性，若内部实现不兼容则回退为固定默认 6 并在代码注释与 README 记录（不影响其余需求）。

### D4. 工具薄封装：错误分类与结果留痕

`app/llm/quiz_tools.py` 以子类薄封装两个官方工具，不改变工具的参数语义与返回结构，只做两件事：

1. **错误分类留痕**：捕获底层异常（网络、超时、鉴权、服务端错误），记录 WARNING 日志并向 agent 返回结构化错误标记（如 `{"tavily_error": "<类别>"}`），避免 langgraph 工具节点直接抛异常终止整个图；同时把每次调用的「成功且非空 / 成功但空 / 失败」结论写入模块级调用记录，供聚合层判定（D6）与 `sources` 抽取（搜索取 `results[].title/url`，提取取 `results[].url`）。
2. **参数扩展**：`max_results` 动态入参（见 D3）。

备选：直接使用官方工具让 langgraph 默认 `handle_tool_errors` 处理——错误以非结构化文本回流，聚合层无法确定性区分「故障」与「空结果」，兜底规格无法落实，故封装是必要的。

### D5. Prompt v3：智能体系统提示词重构

`quiz_prompt.py` 升级 `quiz_prompt_v3`，拆分为两部分：

- 智能体系统提示词（`create_agent(system_prompt=...)`）：角色设定（AI 学习教练）、两个工具的使用时机与 D3 参数选择指导、事实性约束（资料为准、不编造、禁止跨领域套用）、以及最终答案格式（与 v2 相同的题库 JSON schema、禁止输出 JSON 之外内容——用户消息即学习输入，最终回复必须是纯 JSON）。
- 降级路径模板：现有 v2 式模板保留（含 `{user_input}` 与题型配比），供 `QuizChain` 降级使用，并加入「本次未联网核实」的保守出题引导；版本常量按 README 约定标注 `quiz_prompt_v2_degraded`。

不采用 `response_format=ToolStrategy(StructuredQuizOutput)`：虽然官方支持，但会改变最终答案的产出方式（结构化工具调用）并把大 JSON 塞进 tool args，调试与既有解析/校验链路都要重写；维持「最终回复为纯 JSON 文本 + 现有 JSON 清洗与 `StructuredQuizOutput` 校验」，风险最小。

### D6. 兜底聚合三分支（适配「AI 完全自主」模式）

`app/services/retrieval_service.py` 对外提供与上一版方案相同形状的三态接口，内部改为聚合智能体运行结果（依据 D4 留痕）：

| 聚合结论 | 条件 | 行为 |
| --- | --- | --- |
| `ok` | 至少一次工具调用成功且获得非空资料 | 注入留痕来源出题，`search_used=true`、`sources` 非空 |
| `no_results` | 有工具调用且全部成功，但所有结果为空 / 网页提取全部失败（含 `failed_results`） | 抛 `SearchNoResultsError`（HTTP 422，文案区分「换个说法补充背景」与「确认链接有效」），**不返回题目** |
| `unavailable` | 模型未调用任何工具；或所有调用均失败；或智能体超时/超限被中止 | 落入 `QuizChain` 纯模型出题，`search_used=false`，记录 WARNING |

`SEARCH_ENABLED=false` 或 `TAVILY_API_KEY` 未配置 → 完全跳过智能体，直接走降级路径（同样标注）。智能体循环约束：`config={"recursion_limit": AGENT_RECURSION_LIMIT(默认 8)}` + `asyncio.wait_for(AGENT_TIMEOUT_SECONDS 默认 60s)`，捕获 `GraphRecursionError` 与超时异常归入 `unavailable`。

### D7. 检索元数据仅在生成响应返回，不持久化

`QuizResponse` 增加可选字段 `search_used: bool = False`、`sources: list[SearchSource] = []`（`SearchSource = {title, url}`，标题缺失时以 URL 兜底）。`create_quiz_session` 与历史/续答/详情链路不动——元数据是「生成时刻」信息，规格已要求无元数据的历史题库必须正常渲染。

### D8. 前端最小改动，按字段缺省区分三种展示态

- `src/utils/api.ts`：`QuizData` 增加 `search_used?: boolean`、`sources?: Array<{ title: string; url: string }>`（`quizData` 以 JSON 序列化经路由参数透传，字段自然携带）。
- 闯关页标题区：`search_used === true` → 「🌐 已联网核实 · N 条资料」；`=== false` → 「⚠️ 未经联网核实，请谨慎参考」；字段缺省（历史/续答）→ 不展示。
- 首页生成按钮 loading 文案改为「检索资料并生成中...」；422 业务错误经现有 `ApiError → errorMessage` 链路展示。仅使用仓库既有 Taro 组件与模式，不引入新 Taro API。

### D9. 配置与资料规模控制

`config.py`/`.env.example` 新增：`TAVILY_API_KEY`（默认空）、`SEARCH_ENABLED`（默认 true）、`AGENT_RECURSION_LIMIT`（默认 8）、`AGENT_TIMEOUT_SECONDS`（默认 60）、`TAVILY_MAX_RESULTS`（默认 6）。注入 Prompt 的资料预算（常量）：单条搜索摘要截断 500 字符、单页提取正文截断 1500 字符、注入总量 3000 字符——extract 的整页 `raw_content` 尤其必须截断，防止挤占 `max_tokens=2000` 的输出空间。截断在智能体消息回流后、最终出题前不适用（工具消息由 agent 自行阅读），预算作用于**降级路径的上下文拼装**与最终响应 `sources` 数量上限（≤8 条）。

> 说明：智能体模式下工具消息直接进入模型上下文，无法在不干预 langgraph 的前提下逐条截断；若实测出现上下文膨胀问题，后续可引入 `@wrap_tool_call` middleware 做消息级截断，本期不引入（记入 Open Questions 的验证点）。

### D10. 可测试性

- `retrieval_service` 与 `quiz_agent` 均走工厂单例；`QuizService` 测试用 `unittest.mock.patch` 替换（与 `test_drill_api.py` 同款写法）。
- 智能体测试不发起真实请求：注入 fake 模型与 fake 工具（脚本化「先调工具再答」的 tool calls 序列），覆盖 ok / no_results / unavailable / 超限四类路径。
- 工具薄封装单测：monkeypatch 底层客户端抛异常/返回空，断言分类标记与留痕正确。
- 既有 mock `QuizService` 的 API 测试不受影响。

## Risks / Trade-offs

- [1.x 升级回归面覆盖出题+报告两条链路] → 升级单独成组、先全量 `pytest` 通过再开发新功能；两步分开提交便于二分定位与回退。
- [AI 完全自主可能跳过检索，新话题风险重现] → 用户已明确接受；通过响应标注让风险可感知，上线后可观察 `search_used=false` 占比再决定是否收紧提示词约束。
- [DeepSeek function calling 稳定性（乱填参、循环不收敛）] → 提示词给出参数规则与「最多检索 2~3 轮」软约束 + 硬性 recursion/timeout 上限 + 降级路径兜底。
- [国内服务器访问 Tavily 不稳定] → 工具层异常快速归类为 `unavailable` 降级，可用性不受损；`SEARCH_ENABLED` 一键关闭。
- [`max_results` 子类依赖工具内部实现] → 实施首日验证，不兼容即回退固定默认值（已在 D3 预设降级方案，不影响规格）。
- [智能体多轮往返使延迟方差变大（数秒~一分钟）] → recursion_limit=8 + 60s 总超时硬约束；前端文案同步预期。
- [成本：advanced 搜索与 extract 消耗更多 credits（免费 1000/月）] → 提示词引导默认 basic；credits 用量可通过日志观察，必要时收紧。

## Migration Plan

1. 提交一（依赖升级）：更新 `requirements.txt` 版本矩阵，迁移 `langchain_factory/quiz_chain/report_chain` 至 1.x 等价写法，全量 `pytest` 通过——此时线上行为不变。
2. 提交二（功能）：智能体、工具封装、Prompt v3、元数据、前端展示。`.env` 配置真实 `TAVILY_API_KEY` 后重启生效；未配置时自动降级，不影响可用性。
3. 回滚：`SEARCH_ENABLED=false` 即回到纯模型出题（响应字段保留、前端标识自然回退）；依赖回退以提交一为还原点。无数据库迁移。

## Open Questions

无阻塞性问题。两个实施期待验证点（均已有预设降级方案，不影响规格与任务拆分）：① `max_results` 薄封装与 `langchain-tavily 0.2.18` 内部的兼容性；② 智能体多轮工具消息是否引发上下文膨胀（必要时下期引入 `@wrap_tool_call` 截断）。
