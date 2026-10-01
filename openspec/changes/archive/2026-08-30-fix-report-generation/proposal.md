## Why

LangChain 1.x 升级（commit 46c579e，`langchain-openai` 0.2.10 → 1.6.0）改变了 `with_structured_output` 的默认方法：0.x 默认 `function_calling`，1.x 默认 `json_schema`（已在本地安装包 `langchain_openai/chat_models/base.py:3723` 确认）。报告链路 `report_chain.py:27` 依赖默认值，于是向 DeepSeek 发送其不支持的 `response_format: json_schema`，DeepSeek 返回 400 `invalid_request_error: This response_format type is unavailable now`（已用项目 venv 对真实 API 实测复现）。出题链路因走纯文本输出 + 宽松 JSON 解析而不受影响，因此表现为「前面全部跑通，最后生成报告必现失败」，前端展示「报告生成失败，请重试」。同一升级把出题链路改成了智能体模式并做了回归，报告链路被遗漏了等价迁移。

实测结论（DeepSeek `deepseek-chat`）：
- `with_structured_output(schema)` 默认方法 → 400 失败；
- `method="function_calling"` → 成功返回合法的 `StructuredReportOutput`；
- `method="json_mode"` → 需要提示词含 "json" 才可用，非首选。

## What Changes

- 报告链路显式指定 `with_structured_output(schema=StructuredReportOutput, method="function_calling")`，修复 400 错误；API 请求/响应契约不变，接口从必现失败恢复为成功。
- 新增回归单测固化该契约（断言报告链以 function_calling 方式请求结构化输出），防止未来再次被上游默认值变更破坏。
- 边界兜底：现校验硬性要求 `weak_points`、`mastered_points` 非空，而全对答题记录下模型自然产出空 `weak_points`（全错同理 `mastered_points`），会以另一种路径复现「报告生成失败」；将校验改为允许这两类边界为空，保证全对/全错也能出报告。
- 不做：报告 Prompt 重写、报告响应结构变更、前端改动、学习记录落库链路改动（MySQL 本地可连通，用户系统已验证可用，不在本次失败路径上）。

## Capabilities

### New Capabilities

- `learning-report-generation`: 学习报告生成能力——合法输入下 `POST /api/v1/report/generate` 必须返回完整六字段报告；报告必须经由与模型服务端兼容的结构化输出机制生成；accuracy 由后端确定性计算；全对/全错边界照常生成；非法输入与不合规模型输出返回业务错误而非 500。

### Modified Capabilities

（无——`openspec/specs/` 当前为空，报告链路此前没有规格。）

## Impact

- **后端修改**：`backend/app/llm/report_chain.py`（显式 `method="function_calling"`）、`backend/app/services/report_service.py`（`_validate_structured_output` 边界兜底）。
- **测试**：`backend/tests/` 新增报告链结构化输出方式回归单测；更新 `test_report_service.py` 覆盖全对/全错边界。
- **API**：`POST /api/v1/report/generate` 契约无变化，仅行为从失败恢复为成功；错误分支（400 业务错误 / 500）语义不变。
- **外部依赖**：DeepSeek API 的 function calling 能力（`deepseek-chat` 支持，实测可用）。
- **前端**：无改动（空 `weak_points` 列表现有渲染安全）。
- **风险**：DeepSeek function calling 的 schema 遵循度弱于服务端 json_schema 硬约束，靠既有 `_validate_structured_output` 校验兜底；若未来 DeepSeek 支持 `json_schema`，可再评估切回以获得更强约束。
