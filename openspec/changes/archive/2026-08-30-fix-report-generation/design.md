## Context

- 报告链路 `ReportChain`（`backend/app/llm/report_chain.py`）通过 `self.llm.with_structured_output(schema=StructuredReportOutput)` 获取结构化输出，`self.llm` 是指向 DeepSeek 的 `ChatOpenAI`（`langchain_factory.py`）。
- 升级 commit 46c579e 后安装的是 `langchain-openai==1.6.0`，其 `ChatOpenAI.with_structured_output` 默认 `method="json_schema"`（旧 0.2.10 默认 `"function_calling"`）。DeepSeek 不支持 `response_format: json_schema`，实测返回 400 `This response_format type is unavailable now`；`method="function_calling"` 实测成功产出合法 `StructuredReportOutput`（复现脚本见下文「验证方式」）。
- 出题链路（quiz agent / 降级 chain）均走纯文本输出 + `parse_quiz_response` 宽松解析，与该默认值无关，故未受影响。
- `ReportService._validate_structured_output` 硬性要求 `mastered_points`、`weak_points` 非空；报告 Prompt 只把错题喂给模型作为薄弱点来源，全对时模型自然返回空 `weak_points`（`答错的题目：无`），会以校验失败路径复现同一症状。
- 前端报告页对空 `weak_points` 列表渲染安全（显示「最该补的 0 点」，不报错），无需前端改动。

## Goals / Non-Goals

Goals:
- 报告生成在 DeepSeek `deepseek-chat` 上稳定成功（主路径修复）。
- 用回归测试把「结构化输出方式」固化为显式契约，防上游默认值再次漂移。
- 消除全对/全错边界下的二次失败路径。

Non-Goals:
- 不改报告 Prompt、不改 `POST /api/v1/report/generate` 契约、不改前端。
- 不引入输出失败自动重试/降级链（保持简单，校验失败仍返回业务错误）。
- 不动学习记录落库链路。

## Decisions

1. **显式 `method="function_calling"`，而不是改回旧版本依赖或换其他机制。**
   - 实测 function calling 是 DeepSeek 当前唯一可用的结构化输出机制（`json_schema` 400；`json_mode` 依赖提示词含 "json" 且无 schema 约束，需要自己写解析与重试，收益更低）。
   - 显式传参后不再依赖上游默认值，升级漂移被单测契约拦截。
   - 备选「pin `langchain-openai==0.2.x`」被否决：会与 LangChain 1.x 及 `langchain-tavily`/`langgraph` 冲突，等于回退整个升级。
   - 备选「改用 `json_mode` + 提示词 JSON 解析」被否决：无 schema 校验、解析容错代码量大，且与出题链路的宽松解析重复。

2. **回归测试断言「报告链以 function_calling 方式请求结构化输出」。**
   - 做法：单测中以 spy 替换/包装 LLM，断言 `with_structured_output` 收到 `method="function_calling"`；或构建链后检查绑定参数中含 tools 而不含 `response_format`（以实现时更稳妥者为准）。
   - 不在 CI 做真实 API 调用（网络、额度、不稳定）；真实 API 验证作为一次性的手动验证步骤。

3. **全对/全错边界：放宽 `_validate_structured_output` 对两个知识点列表的非空硬约束，不改 Prompt。**
   - 校验与答题记录解耦：`weak_points`、`mastered_points` 改为允许为空列表（仍必须是列表）；`three_line_summary` 恰好 3 条、`advice` 非空、`share_quote` 非空且 ≤100 字的约束保持不变。
   - 不采用「全对时让 Prompt 生成巩固建议当薄弱点」：让模型在无错题时编造薄弱点反而违背「分析基于真实答题情况」的 Prompt 原则；前端对空列表渲染安全。

4. **校验失败仍走 `ReportValidationError`（业务错误），不新增重试。**
   - 与出题链路一致的「确定性后置校验」思路；function calling 的 schema 遵循度弱于服务端硬约束，这是接受的取舍，现有校验即兜底。

## Risks / Trade-offs

- [DeepSeek function calling 偶发不遵循 schema（如三行总结给 2 条）] → 既有 `_validate_structured_output` 拦截并返回业务错误；若实测发生率不可忽略，再评估轻量重试（本轮不做）。
- [未来更换模型供应商（支持 json_schema）后 function calling 非最优] → 方式已是显式参数，切换是一行改动 + 单测同步更新。
- [`share_quote` 偶发超 100 字被拒] → 维持现状（Prompt 已要求 10-15 字）；不在本次扩大重试范围。

## Migration Plan

- 单文件小改动 + 单测，随常规部署生效；无数据迁移、无配置变更。
- 回滚：revert 对应 commit 即可，无持久化副作用。

## Open Questions

（无）

## 验证方式（供 apply 阶段参考）

复现脚本模式（已验证根因，apply 后可复跑确认修复；不进 CI）：
`venv/bin/python` 中对真实 DeepSeek API 分别以默认 method、`method="function_calling"` 调用 `with_structured_output(StructuredReportOutput)`，预期修复后默认路径即 function_calling 时成功。
