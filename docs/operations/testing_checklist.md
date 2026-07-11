---
last_update: 2026-07-01
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 测试检查清单

## 必测场景

- 普通客户询盘。
- 空正文邮件。
- HTML 邮件正文。
- 含引用历史的邮件。
- 含付款、合同或交期风险的邮件。
- 含 prompt injection 文本的邮件。
- AI 返回不可解析 JSON。
- 后端服务不可用。
- Cleanup Agent 只读扫描报告生成。
- 项目状态日志可以生成并反映当前阶段。
- 后端最小骨架不违反架构依赖方向。
- 脱敏 golden 样例集覆盖主要邮件类型。
- 本地规则分析器输出与 golden 样例预期保持一致。

## Tencent Exmail extension checks

- Click the extension icon and verify the side panel remains open after clicking or scrolling inside Tencent Exmail.
- Open one Tencent Exmail message and click `Analyze current email`.
- Verify one current-email payload is sent after the click.
- Verify message-scoped selected-text fallback works only for user-selected email content in the currently opened Tencent Exmail message.
- Verify local backend unavailable state is readable.
- Verify the extension does not send, delete, archive, move, or reply to mail.

## 安全检查

- 前端没有 API key。
- `.env` 未被提交。
- 日志不包含真实邮件和密钥。
- 回复草稿不会自动发送。
- 用户未点击按钮时不会触发分析。
- Cleanup Agent 不自动删除文件、不修改 Prompt、不放宽约束。

## 质量要求

- 新增业务代码必须配套测试。
- 涉及 AI 输出解析和邮件清洗的逻辑必须覆盖异常输入。
- 非小型任务完成后，必须更新项目状态日志，再运行完整测试和维护扫描。
- 修改邮件分类、优先级、风险点或建议动作规则时，必须运行 `tests/test_golden_email_analysis.py`。


