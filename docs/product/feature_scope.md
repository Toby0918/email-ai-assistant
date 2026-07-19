---
last_update: 2026-07-16
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: product_spec
---

# 功能边界

## 当前支持范围

- 识别当前打开的一封邮件。
- 用户点击按钮后分析当前邮件。
- 提取主题、发件人、收件人、时间和正文。
- 清洗 HTML 邮件正文。
- 生成摘要、优先级、分类、风险点、建议动作和回复草稿。
- 将分析结果保存到本地 SQLite，用于调试和回看。
- 使用本地调试页面或待选辅助窗口前端验证流程。
- 用户点击后，浏览器扩展可传输当前打开邮件页面可见的图片、PDF、XLSX 和 DOCX 资源给本地后端；附件内容解析只在后端完成，并受文件数量、单文件大小、总大小和临时保留时间限制。
- 只有显式后端配置 `EMAIL_AGENT_LLM_PROVIDER=openai` 时，当前可见线程和经过本地筛选的当前消息图片或文件才可进入固定 `gpt-5.6-sol` 远程多模态路线；显式 `EMAIL_AGENT_TEXT_FALLBACK_PROVIDER=deepseek` 只允许在主路线失败且剩余预算至少 12 秒时进行一次文本调用。

## 当前不支持

- 自动发送邮件。
- 自动删除邮件。
- 自动归档邮件。
- 自动扫描整个邮箱。
- 自动分析所有未读邮件。
- 浏览器扩展、local debug page 或正常后端运行时接入真实邮箱账号、枚举邮箱或读取其他邮件。
- 前端保存或暴露 OpenAI API key。
- 前端直接调用 OpenAI API。
- 可配置的 OpenAI 远程 endpoint、未列入 allowlist 的 OpenAI 模型、provider SDK retry，或将 DeepSeek 文本 fallback 默认开启。
- 代表用户承诺价格、交期、付款、合同或法律事项。
- 在用户点击前收集邮件、附件或会话数据。
- 读取其他邮件、文件夹或账户数据，或使用 OAuth、邮箱 SDK、后台轮询和全邮箱扫描。
- 将附件二进制、私有下载 URL、cookie、token 或完整原始附件内容写入 SQLite、日志、文档、测试或仓库。

## 远程处理点击前告知

浏览器扩展和 local debug page 已在 Analyze 控件前持续展示以下 exact persistent pre-click disclosure；Task 7 已完成共享 markup 与静态/行为测试：

```text
After you click Analyze, configured remote AI providers may receive locally deidentified current visible email text and selected current-message images or files after local screening. Media pixels or document content may contain identifying information and are not guaranteed to be fully deidentified. Processing is not local-only, and no zero-retention guarantee is made.
```

该告知不授权 mailbox scan、后台收集、其他邮件读取或任何自动邮箱动作。provider 默认关闭时继续使用本地规则结果。

## 单独授权的管理员导入范围

唯一例外是管理员手动运行的 `scripts/manage_mailbox_vault.py`
`administrator-only CLI`。它只可处理 `one authorized account`，使用固定
`imap.exmail.qq.com:993` 和 TLS 证书校验，并把范围限制为
`rolling 24-month window`。先运行 content-free inventory，再由管理员明确
确认相同的 inventory fingerprint，才可读取有界内容。

该流程无自动触发、无后台轮询、无定时任务、无浏览器或正常运行时入口。
The browser extension remains click-only，仍只分析当前打开并可见的邮件及其
可见受支持资源。扩展 permissions、host permissions、公开 API、public
SQLite 和人工复核要求均不改变。

管理员导入只允许只读 IMAP：`LIST`、`EXAMINE`、`UID SEARCH`、
`UID FETCH` 和 `BODY.PEEK`。禁止 SMTP、flags 修改和任何邮箱写操作。
导入快照只能进入项目外的外部加密 vault，不得自动进入 DeepSeek 或现有
SQLite。

## 后续可评估

- Outlook Add-in。
- 第二阶段已选择：Chrome / Edge browser extension for Tencent Exmail Web (`https://exmail.qq.com/*`)；只允许用户点击后分析当前打开邮件及其可见受支持资源。
- Gmail / Google Workspace Add-on。
- 团队级规则配置。
- 人工确认后的草稿插入邮箱编辑器。
- 在全部离线安全门通过后，由管理员单独运行授权 inventory/scan、知识审核和聚合评估；这不是浏览器产品功能。


