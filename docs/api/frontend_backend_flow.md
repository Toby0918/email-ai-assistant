---
last_update: 2026-07-11
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: api_contract
---

# 前后端流程

## 点击分析流程

1. 前端检测当前邮件是否可读取。
2. 用户点击“分析此邮件”。
3. 前端整理当前邮件字段：`subject`、`from`、`to`、`sent_at`、`body_text` 或 `body_html`；仅在此点击路径中有界收集当前邮件可见附件。
4. 受支持的安全字节进入 `attachment_files`；未支持、超限、不可用、读取失败、超时或候选遗漏进入带允许 `code` 的 `resource_limitations`。
5. 前端调用 `POST /api/analyze-current-email`；浏览器边界丢弃未知限制码和伪造的后端运行码。
6. 后端再次校验限制码，用确定性映射生成状态和固定安全限制文本；附件存储或清理失败使用独立保留的运行限制。
7. 后端清洗正文；如后端 AI 未配置、不可用或输出无效，第一版使用本地规则分析器。
8. 后端校验 JSON schema。
9. 后端保存最多 14 个受限 `attachment_insights` 到 SQLite，不保存字节、路径、私有 URL、cookie 或 token。
10. 前端展示结果：摘要、分类、风险和建议动作显示为中文，回复草稿正文保持英文。

## 密钥边界

- OpenAI API key 只存在于 Python 后端环境变量。
- Ollama/Qwen 配置只存在于 Python 后端环境变量。
- 前端不保存、不显示、不转发 API key。
- 前端不直接调用 OpenAI、Ollama、Qwen 或本地模型端点。

## 错误处理

- 后端不可用：提示启动本地服务。
- 邮件为空：提示无法分析空邮件。
- JSON 校验失败：提示分析失败，可重试。
- 触发安全规则：展示人工审核提示。

## 显示语言

- 前端将后端返回的英文枚举值映射为中文标签，例如 `payment` 显示为“付款/发票”，`payment_risk` 显示为“付款风险”。
- 前端不得翻译或改写 `reply_draft.body`，避免把外部回复草稿从英文误变成中文。


