## 1. 主路径修复

- [x] 1.1 在 `backend/app/llm/report_chain.py` 的 `create_chain` 中为 `with_structured_output` 显式传入 `method="function_calling"`，并核对该文件中无其他依赖默认值的结构化输出调用；验证：`grep -n "with_structured_output" backend/app -r` 仅命中一处且带 `method="function_calling"`

## 2. 回归测试固化契约

- [x] 2.1 新增 `backend/tests/test_report_chain.py`：以 spy/fake LLM 替换 `LangChainFactory.create_chat_llm_for_report`，断言构建报告链时 `with_structured_output` 收到 `method="function_calling"`（或等价断言：链的绑定参数含工具 schema 而不含 `response_format`）；验证：`cd backend && venv/bin/python -m pytest tests/test_report_chain.py -q` 通过，且人为把 method 改回默认时该测试变红
- [x] 2.2 为 `generate_report` 主流程补一条离线单测（fake LLM 返回合法 `StructuredReportOutput`，断言返回 `ReportResponse` 且 `accuracy` 来自后端统计而非模型值）；验证：`venv/bin/python -m pytest tests/test_report_chain.py -q` 通过

## 3. 全对/全错边界兜底

- [x] 3.1 在 `backend/app/services/report_service.py` 的 `_validate_structured_output` 中放行 `mastered_points`、`weak_points` 为空列表（保持列表类型校验），`three_line_summary` 恰好 3 条、`advice` 非空、`share_quote` 非空且 ≤100 字的约束不变；验证：`cd backend && venv/bin/python -m pytest tests/test_report_service.py -q` 通过
- [x] 3.2 在 `backend/tests/test_report_service.py` 中补边界用例：全对（`weak_points=[]`）与全错（`mastered_points=[]`）时 `generate_report` 正常返回报告；非法输出（总结非 3 条 / `share_quote` 超 100 字）仍返回 `ReportValidationError`；验证：`venv/bin/python -m pytest tests/test_report_service.py -q` 通过

## 4. 整体回归与真实验证

- [x] 4.1 全量测试回归：`cd backend && venv/bin/python -m pytest -q` 全部通过（含既有 `test_report_service.py` 与出题链路各测试）
- [x] 4.2 真实链路验证（手动，一次性）：启动后端后，用合法题目 + 答题记录（含一错一全对两份）`curl POST /api/v1/report/generate`，均返回 `code=0` 与完整六字段报告；预期默认路径不再出现 `This response_format type is unavailable now`
- [x] 4.3 前端确认：小程序报告页完成一次闯关后能正常展示报告（含「最该补的 N 点」卡片；全对场景展示 0 点不报错）
