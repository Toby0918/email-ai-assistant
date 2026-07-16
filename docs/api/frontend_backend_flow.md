---
last_update: 2026-07-15
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
4. 受支持的安全字节进入 `attachment_files`；未支持、超限、不可用、读取失败、超时或候选遗漏进入带允许 `code` 的 `resource_limitations`。响应头已声明超限时，前端只做非阻塞的 best-effort body cancel，并立即返回 `frontend_limit`，不得等待 cancel promise settle。
5. 前端调用 `POST /api/analyze-current-email`；浏览器边界丢弃未知限制码和伪造的后端运行码。
6. 后端再次校验限制码，用确定性映射生成状态和固定安全限制文本；附件存储或清理失败使用独立保留的运行限制。
7. 后端清洗正文；如后端 AI 未配置、不可用或输出无效，第一版使用本地规则分析器。
8. 后端校验 JSON schema。
9. 后端保存最多 14 个受限 `attachment_insights` 到 SQLite，不保存字节、路径、私有 URL、cookie 或 token。
10. 前端通过共享 renderer 展示结果：任务结论和当前动作优先，回复草稿正文保持目标语言。

## 共享结果呈现契约

- Chrome / Edge extension 与 local debug page 共同使用 `frontend/browser_extension/shared/render_analysis.js` 和 `frontend/browser_extension/shared/analysis_components.css`，不得维护两套字段解释或 CSS 排版。
- 320px 侧栏首屏以 task card 依次展示处理结论、当前诉求、下一步、关键事实和必须核查项。
- 会话历史、附件、风险依据、更多动作和技术信息使用 closed native `<details>`，初始均为折叠状态。
- `analysis_engine.source=rule_fallback` 时固定显示中文横幅：`未使用 DeepSeek：本次结果由本地规则生成。`；固定诊断原因可以显示，但不得把规则结果伪装为模型结果。
- 草稿独立展示 subject、body 和人工审核原因；复制动作只复制草稿，不发送邮件。
- 当前 unpacked extension 版本为 `0.2.3`。

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


