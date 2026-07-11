---
last_update: 2026-07-09
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Decision Brief Analysis Task Brief

## 1. 任务名称

```text
add decision brief analysis output
```

## 2. 任务类型

```text
feature | prompt | data_schema | api_contract | test
```

## 3. 当前状态

```text
implemented
```

## 4. 任务目标

目标：让分析结果顶部直接回答“这封邮件到底要我做什么”，减少用户为了理解邮件而回看整封邮件的时间。新增 `decision_brief` 结构，展示行动结论、邮件目的、当前动作、关键事实、必须核查项、缺失信息、回复建议和置信度。

## 5. 非目标

非目标：

- 不接入真实邮箱账号。
- 不自动发送邮件。
- 不自动删除或归档邮件。
- 不自动扫描邮箱。
- 不在前端调用 OpenAI、Ollama、Qwen 或任何本地模型端点。
- 不自动下载、打开或解析附件内容。
- 不代表用户承诺价格、交期、付款、合同或质量结论。

## 6. 背景与依据

背景：真实 Tencent Exmail 测试中，原 summary、risks 和 actions 仍不足以让用户快速判断邮件要点和下一步动作。用户确认执行方案 A：先增加决策摘要和证据化结构，再进入附件/图片辅助分析。

相关文档：

- AGENTS.md
- docs/constraints/tooling_constraints.md
- docs/constraints/architecture_constraints.md
- docs/constraints/linter_constraints.md
- docs/data/analysis_result_schema.md
- docs/prompts/analyzer_prompt.md
- docs/api/backend_api_contract.md
- docs/product/roadmap.md

## 7. 涉及范围

预计新增或修改：

- backend/email_agent/analysis_schema.py
- backend/email_agent/analysis_repair.py
- backend/email_agent/analyzer.py
- backend/email_agent/rule_analyzer.py
- frontend/browser_extension/popup.html
- frontend/browser_extension/popup.js
- frontend/browser_extension/shared/render_analysis.js
- frontend/local_debug_page/index.html
- frontend/local_debug_page/app.js
- docs/data/analysis_result_schema.md
- docs/prompts/analyzer_prompt.md
- docs/api/backend_api_contract.md
- docs/product/roadmap.md
- tests/

## 8. 技术方案

方案：

1. 在 AI 输出 schema 中新增必填 `decision_brief`。
2. 在规则兜底中生成行动结论、当前动作、关键事实、需核查项、缺失信息和回复建议。
3. 在模型输出修复层中用规则兜底补齐缺失或不稳定的 `decision_brief` 字段。
4. 在 prompt 中明确要求模型输出决策摘要，且用户反馈保持中文、回复草稿保持英文。
5. 在浏览器扩展和本地调试页把 `decision_brief` 放在风险和动作之前展示。

## 9. 数据结构或接口变化

### 数据库变化

```text
无。分析 JSON 仍作为整体结果保存。
```

### API 变化

```text
有。/api/analyze-current-email 的 analysis 响应新增必填 decision_brief 字段。
```

### AI 输出 JSON 变化

```text
有。新增 decision_brief，包含 one_line_conclusion、requested_outcome、next_steps、key_facts、must_check、missing_info、reply_recommendation 和 confidence。
```

### Prompt 变化

```text
有。要求模型输出中文决策摘要，并保留英文回复草稿。
```

## 10. 安全与隐私检查

```text
[x] 不读取真实邮箱数据，除非任务明确授权。
[x] 不自动发送、删除、归档邮件。
[x] 不在前端保存或暴露 OpenAI API key。
[x] 邮件正文按不可信输入处理。
[x] AI 输出必须可解析、可校验。
[x] 日志不输出真实邮件正文、客户敏感信息、API key 或 token。
[x] 测试样本必须脱敏。
```

## 11. Prompt Injection 防护

防护要求：

- 邮件正文只是待分析内容，不是系统指令。
- 不执行邮件正文中的命令。
- 不泄露系统提示、密钥、数据库内容或其他邮件内容。
- 不让 AI 代表用户承诺价格、交期、付款、合同或法律责任。
- 附件名和链接也是不可信输入，只作为分析上下文和核查提醒。

## 12. 验收标准

验收标准：

1. 规则兜底分析能返回通过 schema 校验的 `decision_brief`。
2. RFQ/报价类邮件的 `decision_brief` 能列出关键编号、截止时间、必须核查项和回复建议。
3. 模型输出缺失 `decision_brief` 时，后端可用规则兜底补齐。
4. 浏览器扩展和本地调试页能展示行动摘要，不出现 `[object Object]`。
5. 不违反 AGENTS.md 当前项目边界。
6. 文档已同步更新。

## 13. 测试计划

测试计划：

- python -m unittest discover -s tests
- python -B scripts/maintenance_scan.py
- node --check frontend/browser_extension/shared/render_analysis.js
- node --check frontend/browser_extension/popup.js

## 14. 回滚方案

回滚方案：撤回本任务新增的 `decision_brief` schema、prompt、规则分析、渲染和文档改动，恢复原 summary/risks/actions 展示。

## 15. 需要人工确认的问题

待确认：

- 下一阶段是否进入附件/图片辅助分析方案 B。

## 16. 执行前检查

```text
[x] 已阅读 AGENTS.md。
[x] 已阅读相关 docs/ 文件。
[x] 已明确本次任务目标和非目标。
[x] 已确认不会触碰真实邮箱、真实密钥或真实客户数据。
[x] 已确认需要修改的文件范围。
```

## 17. 执行后记录

实际修改文件：

- backend/email_agent/analysis_schema.py
- backend/email_agent/analysis_repair.py
- backend/email_agent/analyzer.py
- backend/email_agent/email_facts.py
- backend/email_agent/rule_analyzer.py
- backend/email_agent/rule_decision.py
- frontend/browser_extension/popup.html
- frontend/browser_extension/popup.js
- frontend/browser_extension/shared/render_analysis.js
- frontend/local_debug_page/index.html
- frontend/local_debug_page/app.js
- docs/api/backend_api_contract.md
- docs/constraints/architecture_constraints.md
- docs/constraints/tooling_constraints.md
- docs/data/analysis_result_schema.md
- docs/prompts/analyzer_prompt.md
- docs/product/roadmap.md
- tests/test_analysis_schema.py
- tests/test_analyzer.py
- tests/test_browser_extension_renderer_behavior.py
- tests/test_browser_extension_static.py
- tests/test_frontend_local_debug.py
- tests/test_rule_analyzer.py

测试结果：

- `python -m unittest discover -s tests`：159 tests OK。
- `python -B scripts/maintenance_scan.py`：No cleanup findings detected。
- `node --check frontend/browser_extension/shared/render_analysis.js`：OK。
- `node --check frontend/browser_extension/popup.js`：OK。
- `node --check frontend/local_debug_page/app.js`：OK。

未完成事项：

- 附件正文、图片 OCR 和表格解析属于后续方案 B。

后续建议：

- 进入附件/图片辅助分析前，先设计附件解析的用户确认流程和后端-only 数据流。
