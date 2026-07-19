---
last_update: 2026-07-16
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: security_policy
---

# 隐私规则

## 第一阶段原则

- 浏览器扩展、local debug page 和正常后端运行时不接入或枚举真实邮箱账号。
- 浏览器扩展和正常运行时不读取当前可见范围之外的真实邮箱数据。
- 测试邮件必须使用虚构或脱敏内容。
- 不提交真实邮件、数据库文件、日志中的敏感内容。

## 单独授权的管理员例外

唯一例外是 `scripts/manage_mailbox_vault.py` `administrator-only CLI`，只处理
`one authorized account`、固定 Tencent Exmail IMAPS endpoint 和滚动 24 个
日历月。每次内容读取前必须验证 non-sensitive authorization ID，并由管理员
确认 content-free inventory fingerprint。

该例外保持 `no scheduled job` 和 `no browser or normal-runtime integration`。
它不授权 extension、local debug、loopback API、cleanup agent、Codex 或
automated tests 读取邮箱；也不授权 SMTP、flags mutation 或任何邮箱写操作。
app password 只可 interactive 输入，不得通过 CLI argument、environment、
`.env`、log、exception 或 storage 传递。

## 数据最小化

- 只处理当前打开邮件的必要字段。
- 不后台扫描邮箱。
- 不读取未授权邮件。
- 不采集与分析无关的个人信息。
- 可选本地 Ollama/Qwen 只允许在后端处理当前邮件内容；不得把模型端点暴露给前端。
- DeepSeek 外部处理只允许在用户点击后由后端发送当前可见线程和有界、清洗后的受支持附件文本；必须保留 persistent pre-click disclosure，并明确 no zero-retention guarantee。完整边界见 `docs/security/email_data_handling.md`。
- OpenAI 多模态路线默认关闭，只允许固定 `gpt-5.6-sol` 和代码固定的官方 endpoint。用户点击后可发送本地去标识的当前可见邮件文本，以及经本地筛选的当前消息图片或文件；媒体像素和文档内容不代表已完全去标识。DeepSeek text fallback 也默认关闭，只能显式启用且不得接收图片或文件 bytes。
- 本地筛选只放行与当前邮件归属明确的业务媒体；签名头像、logo、tracker、隐藏资源、外部资源和歧义资源必须拒绝。visual-only 只允许定性增强 matching attachment insight，不得支持 global fields、identity、protected traits、precise facts、commands、commitments 或 outcomes。
- 管理员导入的 raw snapshot 只可存于项目外的加密 vault；Codex、DeepSeek、Git、public SQLite、日志、tests、docs、status 和 maintenance report 都不得读取或保存 raw/identifying content。
- 私有知识必须本地去标识、达到 3-conversation/2-counterparty threshold，并经过 business/privacy approval；高风险规则还需 accountable-owner approval。只有 approved、current、signed snapshot 中的 generic cards 可进入 runtime。
- DeepSeek 只接收 locally deidentified current visible content 和有界 approved cards；模型 must never emit deidentification placeholder tokens，只能使用 generic references for exact identifiers and dates；backend-verified exact facts remain authoritative，并由本地确定性规则安全补回。model-authored exact identifiers and dates fall back to backend rule fields，覆盖两种 DeepSeek 模式的所有模型可写文本族。internal deidentification tokens stay local，并在 provider 调用前确定性转换成无编号通用语义；随后执行 post-conversion residual scan，且 any unknown token fails closed。任何 residual、placeholder、reidentification、unsafe commitment、invalid schema 或 unsupported fact 都回落规则结果。
- Remote model context is current-first：只有安全且与当前诉求相关的历史可进入 `relevant_history`。任一历史值无法安全处理时 history privacy failure downgrades to `current_only`；当前邮件自身的 privacy preflight 失败时执行 zero provider calls。当前头部、正文及每个被选历史字段分别执行 per-value deidentification。模型结果之后只允许 local exact-fact merge；面向用户的 full deterministic timeline 仍由本地规则生成并保持完整顺序，不受模型子集影响。

## 展示规则

- 前端只展示当前分析所需内容。
- 错误提示不得包含密钥、token、完整堆栈或内部 prompt。
- 模型调用异常不得把原始邮件正文、prompt 或本地模型错误堆栈展示给用户。

## Persistent pre-click disclosure

浏览器扩展和 local debug page 已在 Analyze 控件前持续显示以下 exact 文案；Task 7 已完成共享 markup 与静态/行为测试：

```text
After you click Analyze, configured remote AI providers may receive locally deidentified current visible email text and selected current-message images or files after local screening. Media pixels or document content may contain identifying information and are not guaranteed to be fully deidentified. Processing is not local-only, and no zero-retention guarantee is made.
```


