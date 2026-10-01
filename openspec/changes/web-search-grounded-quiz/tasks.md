## 1. LangChain 1.x 依赖升级（先升级，后开发）

- [x] 1.1 `requirements.txt` 按 design D2 更新版本矩阵（`langchain==1.3.18`、`langchain-core` 最新 1.6.x、`langchain-openai==1.6.0`、`langchain-tavily==0.2.18`、`langgraph>=1.2.11` 显式钉住，其余不动），虚拟环境重装并验证 `pip check` 无冲突、`python -c "from langchain.agents import create_agent; from langchain_tavily import TavilySearch, TavilyExtract"` 导入成功
- [x] 1.2 迁移 `app/llm/langchain_factory.py`、`app/llm/quiz_chain.py`、`app/llm/report_chain.py` 及各处 import 至 1.x 等价写法（LCEL 管道与 `ChatOpenAI(base_url=...)` 预计保持）；验证：`pytest -v` 全量通过且退出码为 0，确认本组未改任何业务行为
- [x] 1.3 提交本组为独立 commit（升级与功能分离，便于回退与二分）；验证：`git log` 中存在仅含依赖与等价迁移的提交

## 2. 配置与基础模型

- [x] 2.1 `app/core/config.py` 新增 `TAVILY_API_KEY`（默认空）、`SEARCH_ENABLED`（默认 true）、`AGENT_RECURSION_LIMIT`（默认 8）、`AGENT_TIMEOUT_SECONDS`（默认 60）、`TAVILY_MAX_RESULTS`（默认 6），同步更新 `.env.example` 带注释；验证：`python -c "from app.core.config import settings"` 无报错且默认值正确
- [x] 2.2 `app/core/exceptions.py` 新增 `SearchNoResultsError`（HTTP 422，默认文案区分「换个说法或补充背景」与「确认链接有效」两种场景）；验证：现有 pytest 全量通过，异常可被路由层 `QuizAppException` 处理器透传
- [x] 2.3 `app/models/quiz.py` 新增 `SearchSource`（title/url）模型，并为 `QuizResponse` 增加可选字段 `search_used: bool = False`、`sources: list[SearchSource] = []`；验证：旧构造方式不传新字段仍可实例化（向后兼容）

## 3. 工具薄封装（官方 Tavily 工具 + 留痕）

- [x] 3.1 新增 `app/llm/quiz_tools.py`：按 design D4 以子类薄封装 `TavilySearch`/`TavilyExtract`——异常捕获分类（网络/超时/鉴权/服务端）、WARNING 日志、向 agent 返回 `{"tavily_error": "<类别>"}` 结构化标记、调用结论留痕（成功非空/成功空/失败）与 `sources` 抽取（search 取 `results[].title/url`，extract 取 `results[].url`）；扩展暴露 `max_results`（3~8）动态入参，实施首日验证与 `langchain-tavily 0.2.18` 内部实现兼容，不兼容则回退固定默认 6 并注释记录；验证：新增 `tests/test_quiz_tools.py` monkeypatch 底层客户端覆盖成功、空结果、提取全失败、超时、401 五类分支，`pytest tests/test_quiz_tools.py -v` 通过
- [x] 3.2 验证官方工具参数面与文档一致：调用时可设 `query/search_depth/time_range/include_domains/exclude_domains`，`TavilyExtract` 可设 `urls/extract_depth`；验证：`tests/test_quiz_tools.py` 中对参数透传的断言全部通过

## 4. 智能体、Prompt v3 与检索服务

- [x] 4.1 `app/prompts/quiz_prompt.py` 升级 `quiz_prompt_v3`（design D5）：智能体系统提示词（角色 + 工具使用时机 + D3 参数选择指导表 + 事实性约束 + 题库 JSON 输出格式），保留 v2 式降级模板（含「未联网核实」保守引导）；验证：prompt 常量可构建、单测断言关键指导文案存在
- [x] 4.2 新增 `app/llm/quiz_agent.py`（design D1）：`create_agent(ChatOpenAI 实例, [搜索工具, 提取工具], system_prompt=v3)`，`ainvoke` 执行，`recursion_limit` + `asyncio.wait_for` 双约束，捕获 `GraphRecursionError`/超时；最终回复沿用现有 JSON 清洗与 `StructuredQuizOutput` 校验；验证：`tests/test_quiz_agent.py` 注入 fake 模型与 fake 工具脚本化 tool calls 序列，覆盖「先检索后答题」「跳过检索直接答题」「工具全失败」「零结果」「循环超限」五条路径
- [x] 4.3 新增 `app/services/retrieval_service.py`（design D6）：聚合调用留痕输出三态 `ok/no_results/unavailable`，零结果抛 `SearchNoResultsError`（文案按「搜索无结果」vs「网页提取失败」区分），`unavailable` 落入现有 `QuizChain` 降级并标注；`SEARCH_ENABLED=false` 或未配置 `TAVILY_API_KEY` 时完全跳过智能体；`get_retrieval_service()` 单例仿照现有模式；验证：`tests/test_retrieval_service.py` mock 智能体覆盖三态 + 开关关闭 + 未配置 Key，`pytest tests/test_retrieval_service.py -v` 通过

## 5. QuizService 编排与 API 集成回归

- [x] 5.1 `app/services/quiz_service.py` 改为：校验请求 → `retrieval_service` 三态 → `ok` 用智能体结果、`no_results` 透传 422、`unavailable` 用 `QuizChain` 降级；响应填充 `search_used` 与 `sources`（`unavailable` 时 false/空）；`/generate` 与 `/drill` 自动共享该编排；验证：新增 `tests/test_quiz_service_retrieval.py` mock 检索服务覆盖三分支，`pytest tests/test_quiz_service_retrieval.py -v` 通过
- [x] 5.2 新增 `tests/test_search_grounded_quiz_api.py`（TestClient + patch，写法对齐 `tests/test_drill_api.py`）：`/generate` 成功响应含 `search_used=true` 与非空 `sources`；`/drill` 同样携带元数据且输入聚焦薄弱点关键词；无可读资料返回 422 与中文提示；工具故障降级返回题库且 `search_used=false`；未调用工具的自主跳过同样返回题库且 `search_used=false`
- [x] 5.3 全量回归：`pytest -v` 全部通过（含用户系统既有测试），验证退出码为 0

## 6. 前端最小改动（Taro）

- [x] 6.1 `ai-quiz-frontend/src/utils/api.ts`：`QuizData` 增加可选字段 `search_used?: boolean`、`sources?: Array<{ title: string; url: string }>`；验证：`npm run build:weapp` 编译通过，TypeScript 无类型错误
- [ ] 6.2 `ai-quiz-frontend/src/pages/quiz/index.tsx`：题库标题下按 design D8 展示三态标识（`search_used===true` → 「🌐 已联网核实 · N 条资料」；`===false` → 「⚠️ 未经联网核实，请谨慎参考」；字段缺省不展示），沿用现有 Class Component 与 SCSS 风格；仅使用仓库既有 View/Text/路由参数模式，不引入新 Taro API（如确需新 API，先查 Taro 官方文档）；验证：微信开发者工具中新生成题库与历史题库分别展示/不展示标识
- [x] 6.3 `ai-quiz-frontend/src/pages/index/index.tsx`：生成按钮 loading 文案改为「检索资料并生成中...」；验证：编译通过且生成等待期文案正确

## 7. 文档与端到端验收

- [x] 7.1 更新 `backend/README.md`（LangChain 1.x 版本矩阵、新增配置项、`quiz_prompt_v3`、智能体架构、响应新字段与 422 场景、`country` 参数未被官方工具暴露的限制说明）与 `ai-quiz-frontend/README.md`（API 变更、闯关页标识说明）；验证：文档与实际配置项/字段/行为一一对应
- [x] 7.2 端到端手工验收：配置真实 `TAVILY_API_KEY` 后，小程序覆盖六类输入——新概念关键词（如「Harness Engineering」，题目应与检索资料口径一致）、经典中文主题、英文国际主题（观察 include_domains/检索词语言的动态调节）、网页 URL 输入（应提取整页出题且来源含该页）、生造词（应返回无可读资料的 422 提示）、经典老话题（允许 AI 跳过检索并展示「未经联网核实」标识）；再将 `SEARCH_ENABLED=false` 验证降级路径；验证：各路径行为与 specs 场景一致，工具故障与超限时后端日志出现 WARNING， Credits 消耗量级可从日志观察
