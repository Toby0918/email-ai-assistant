---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Golden Sample Expansion Task Brief

## 1. 任务名称

```text
expand anonymized golden email samples
```

## 2. 任务类型

```text
test
```

## 3. 当前状态

```text
implemented
```

## 4. 任务目标

目标：扩展匿名 golden 样例，覆盖中文交期邮件、报价请求和历史引用噪声。根据 failing tests 做最小规则增强，让本地 MVP 在无 OpenAI API key 时仍能稳定演示第一阶段核心流程。

## 5. 非目标

- 不接入真实邮箱账号。
- 不读取真实邮箱数据。
- 不自动发送邮件。
- 不自动删除或归档邮件。
- 不把 OpenAI API key 放在前端。
- 不修改 API、数据库 schema 或 AI 输出 JSON schema。
- 不新增依赖。

## 6. 背景与依据

背景：`docs/operations/project_status_log.md` 的推荐下一步包括扩展 golden 样例覆盖中文邮件、报价请求和历史引用。

相关文档：
- `AGENTS.md`
- `docs/operations/project_status_log.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/knowledge_base/email_categories.md`
- `docs/knowledge_base/priority_rules.md`
- `docs/knowledge_base/risk_flags.md`
- `docs/knowledge_base/action_rules.md`

## 7. 涉及范围

预计新增或修改：
- `tests/fixtures/sample_emails.json`
- `tests/test_golden_email_analysis.py`
- `tests/test_email_cleaner.py`
- `backend/email_agent/email_cleaner.py`
- `backend/email_agent/rule_analyzer.py`
- `docs/operations/project_status_log.md`

## 8. 技术方案

方案：
1. 先添加匿名 golden 样例和正文清洗测试，确认现有实现无法通过新增场景。
2. 在 `email_cleaner.py` 中剔除 HTML `blockquote` 和常见纯文本历史引用分隔线之后的内容。
3. 在 `rule_analyzer.py` 中补充中文交期、付款、合同、质量、报价关键词，并对报价/价格类请求标记 `commitment_risk`。
4. 保持 API、数据库、AI JSON schema 不变。

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
1. 新增中文交期 golden 样例可分析为 `order_followup`，包含 `delivery_risk` 和 `check_delivery`。
2. 新增报价请求 golden 样例可分析为 `customer_inquiry`，包含 `commitment_risk` 和 `prepare_quote`。
3. 新增历史引用样例不会被引用内容中的旧付款风险抬高优先级。
4. `python -m unittest discover -s tests` 通过。
5. `python scripts/maintenance_scan.py` 无发现。

## 13. 测试计划

测试计划：
- 先运行 `python -m unittest discover -s tests -p "test_golden_email_analysis.py"` 确认新增 golden 样例失败。
- 先运行 `python -m unittest discover -s tests -p "test_email_cleaner.py"` 确认新增正文清洗测试失败。
- 实现最小代码后运行上述目标测试。
- 最后运行 `python -m unittest discover -s tests` 和 `python scripts/maintenance_scan.py`。

## 14. 回滚方案

回滚方案：撤回本任务新增的样例、测试和规则增强，恢复到本任务前的规则分析器和正文清洗行为。

## 15. 需要人工确认的问题

待确认：
- 无。用户已允许按项目日志推荐方向继续执行。

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
- backend/email_agent/email_cleaner.py
- backend/email_agent/rule_analyzer.py
- tests/fixtures/sample_emails.json
- tests/test_email_cleaner.py
- tests/test_golden_email_analysis.py
- docs/operations/golden_sample_expansion_task_brief.md
- docs/operations/project_status_log.md

测试结果：
- python -m unittest discover -s tests -p "test_golden_email_analysis.py": 3 tests passed
- python -m unittest discover -s tests -p "test_email_cleaner.py": 5 tests passed
- python -m unittest discover -s tests: 70 tests passed

未完成事项：
- 无

后续建议：
- 继续用匿名样例手动评估本地调试页，并在确定正式前端路线前保持 local_debug_page 边界。
```
