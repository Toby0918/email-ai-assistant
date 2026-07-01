---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Manual Evaluation Fix Task Brief

## 1. 任务名称

```text
fix manual evaluation findings
```

## 2. 任务类型

```text
fix
```

## 3. 当前状态

```text
implemented
```

## 4. 任务目标

目标：修复本地调试页手动测试暴露的三类问题：合同/质量场景分类优先级不准确、空正文错误后仍展示上一封邮件结果、建议动作文案过于泛化。

## 5. 非目标

- 不接入真实邮箱账号。
- 不读取真实邮箱数据。
- 不自动发送邮件。
- 不自动删除或归档邮件。
- 不把 OpenAI API key 放在前端。
- 不修改 API、数据库 schema 或 AI 输出 JSON schema。
- 不新增依赖。

## 6. 背景与依据

背景：用户使用本地调试页测试匿名样例后，截图显示中文合同被付款关键词抢占分类、质量投诉被 delivery 关键词抢占分类、空正文错误后前端仍保留旧结果。

相关文档：
- `AGENTS.md`
- `docs/operations/project_status_log.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/knowledge_base/email_categories.md`
- `docs/knowledge_base/risk_flags.md`
- `docs/knowledge_base/action_rules.md`

## 7. 涉及范围

预计新增或修改：
- `backend/email_agent/rule_analyzer.py`
- `frontend/local_debug_page/app.js`
- `tests/fixtures/sample_emails.json`
- `tests/test_golden_email_analysis.py`
- `tests/test_rule_analyzer.py`
- `tests/test_frontend_local_debug.py`
- `docs/operations/project_status_log.md`

## 8. 技术方案

方案：
1. 先添加 failing tests：合同同时含付款词时主分类应为 `contract`，质量投诉同时含 delivery 时主分类应为 `complaint`，前端错误分支应调用清空结果函数。
2. 调整规则分析器分类优先级：prompt injection > quality complaint > contract > quote/customer inquiry > delivery > payment。
3. 为建议动作生成更具体的描述，不改变 `type`、`owner_hint`、`due_hint` 字段。
4. 前端在分析开始和后端返回错误时清空结果区，避免旧分析误导用户。

## 9. 数据结构或接口变化

### 数据库变化

```text
无
```

### API 变化

```text
无
```

### AI 输出 JSON 变化

```text
无
```

### Prompt 变化

```text
无
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

## 12. 验收标准

验收标准：
1. 中文合同样例主分类为 `contract`，并保留付款/合同风险提示。
2. 质量投诉含 delivery 字样时主分类为 `complaint`，并触发 `quality_risk`。
3. 空正文错误时前端会清空旧摘要、分类、风险、动作、优先级和草稿。
4. 建议动作描述不再使用泛化的 `Review the ... email and prepare a checked response.`。
5. `python -m unittest discover -s tests` 通过。
6. `python scripts/maintenance_scan.py` 无发现。

## 13. 测试计划

测试计划：
- `python -m unittest discover -s tests -p "test_golden_email_analysis.py"`
- `python -m unittest discover -s tests -p "test_rule_analyzer.py"`
- `python -m unittest discover -s tests -p "test_frontend_local_debug.py"`
- `python -m unittest discover -s tests`
- `python scripts/maintenance_scan.py`

## 14. 回滚方案

回滚方案：撤回本任务对规则分析器、前端错误态和新增测试样例的修改，恢复到本任务前状态。

## 15. 需要人工确认的问题

待确认：
- 无。用户已明确要求执行修正。

## 16. 执行前检查

```text
[x] 已阅读 AGENTS.md。
[x] 已阅读相关 docs/ 文件。
[x] 已明确本次任务目标和非目标。
[x] 已确认不会触碰真实邮箱、真实密钥或真实客户数据。
[x] 已确认需要修改的文件范围。
```

## 17. 执行后记录

```text
实际修改文件：
- backend/email_agent/rule_analyzer.py
- frontend/local_debug_page/app.js
- tests/fixtures/sample_emails.json
- tests/test_golden_email_analysis.py
- tests/test_rule_analyzer.py
- tests/test_frontend_local_debug.py
- docs/operations/manual_eval_fix_task_brief.md
- docs/operations/project_status_log.md

测试结果：
- python -m unittest discover -s tests -p "test_golden_email_analysis.py": 3 tests passed
- python -m unittest discover -s tests -p "test_rule_analyzer.py": 5 tests passed
- python -m unittest discover -s tests -p "test_frontend_local_debug.py": 5 tests passed
- python -m unittest discover -s tests: 74 tests passed

未完成事项：
- 无

后续建议：
- 重启本地服务后复测手动样例，确认浏览器正在使用最新后端和前端文件。
```
