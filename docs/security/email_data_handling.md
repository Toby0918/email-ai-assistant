---
last_update: 2026-07-12
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: security_policy
---

# 邮件数据处理

## 输入

系统只处理用户当前打开并点击分析的邮件。输入字段包括主题、发件人、收件人、抄送、时间、正文和可选测试上下文。第二阶段可在同一次点击中接收当前邮件页面可见的受支持资源；不得读取其他邮件、文件夹或账户数据。

本地分析服务只绑定 `localhost` 或字面 IPv4 `127.0.0.0/8`。分析请求必须同时通过单一 loopback `Host`（可带匹配的实际端口）和单一 `application/json`/可选 `charset=utf-8` 门禁；拒绝 DNS alias、userinfo、通配/LAN/公网 Host、重复/逗号拼接 header 和 simple `text/plain`/form media type。门禁拒绝发生在 body 读取、分析和持久化之前；Content-Type 只能描述为 CSRF 减缓，必须与 Host 校验共同使用。

## 清洗

- HTML 正文应转换为可分析文本。
- 尽量移除样式、脚本、引用历史和签名噪声。
- 保留与业务判断相关的关键文本。
- 附件只输出最多 5 个经严格组件校验后构造的事实，不输出任意原文行或连续原文。请求动作和质量问题必须映射为固定动词/对象或信号标签。
- 通用附件文本清洗必须删除邮箱地址、路径、URL，以及连续、跨空白或常见分隔符连接的任意 7 位及以上数字序列；ISO 日期不豁免。明确标签的业务编号只能由专用提取器对完整字段段做全匹配后构造，值仅允许 `[A-Z0-9_-]`；表格只接受恰好两个非空 cell 的标签/值行，额外 continuation cell 使整行编号失效。不得为业务标签放宽通用清洗器。
- 附件截止时间、请求动作和质量信号必须按局部 clause 判断否定或已撤销语义。动作动词只能绑定同一 clause 中位于其后的对象；只有尚未配对的 affirmative 动词才可跨 `but/however` 传给纯对象 clause，已构造事实的动词不得继续传播，反转 clause 也不得吞掉后续真实动作。`not/never/without/free from`、直/弯引号 modal contractions、未被局部否定的 `absent/repaired/removed/withdrawn/waived/cancelled/revoked` 等上下文不得构造正向事实；紧邻质量词的 `0/zero/nil/non-` 与 `-free/ free` 也必须拒绝。`not required/does not apply/no longer applicable/optional` 表示无有效截止要求；取消、忽略或跳过的请求动作同样拒绝。逗号、分号或 `and/but/however/then` 后其他 clause 的否定不得误删当前真实事实。

## 存储

- 本地 SQLite 仅用于调试、回看和功能验证。
- 不提交数据库文件。
- 真实邮件数据不得进入仓库。
- 附件源文件只可在后端受限临时目录按既有生命周期保留；SQLite、日志、文档、测试和仓库不得保存附件二进制、私有下载 URL、cookie、token 或完整原始附件文本。
- 模型路线构造的 ephemeral sanitized attachment context 只在当前请求内存中存在。它 is excluded from API responses, SQLite, and logs，也不得写入调试输出、文档、测试 snapshot 或仓库 fixture；公开响应和 SQLite 只保留安全投影后的 `attachment_insights`。
- SQLite 保存只有在 commit 成功后才算成功。失败返回 `PERSISTENCE_FAILED`，不返回部分分析；rollback failure 时关闭并 quarantined 该连接，防止残留 transaction 被后续提交。

## AI 处理

- 邮件正文只能从当前打开邮件、用户点击分析后进入后端。
- 默认 `EMAIL_AGENT_LLM_PROVIDER=disabled`，DeepSeek 输出模式默认 `conservative`。只有后端同时配置 `EMAIL_AGENT_LLM_PROVIDER=deepseek` 和 `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=model_led` 时，DeepSeek 才可主导模型字段；provider disabled、缺 key、迟到、失败或输出不安全时回落规则结果。
- DeepSeek 路线最多进行一次 provider call，SDK retry 为 0；失败后不尝试 Ollama。立即 operational rollback 可设置 `EMAIL_AGENT_LLM_PROVIDER=disabled`，字段权限 rollback 可设置 `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative`，两者都需重启后端配置生效。
- 后端只发送 current visible thread 以及当前可见受支持附件的有界、清洗后文本；不发送附件二进制/base64、任何 URL、cookie、authorization、token、本地路径、active content 或无界原文。
- 前端不得直接调用 OpenAI、Ollama、Qwen 或其他模型端点。
- 前端不得在用户点击前收集或传输资源；受支持资源的校验、解析和 OCR 仅可在后端执行。

## 远程处理告知与外部保留风险

浏览器扩展和本地调试页提供 persistent pre-click disclosure：点击 Analyze 后，若后端配置了远程 provider，current visible thread 和有界附件提取会离开本机并发送给该 provider。该告知不等于前端知道或持有 provider key，也不授权读取其他邮件、自动执行邮箱动作或后台收集。任何不允许外部处理的邮件都必须在点击前切换到 disabled/rule-only 路线。

Official sources rechecked 2026-07-12：

- DeepSeek [context caching 文档](https://api-docs.deepseek.com/guides/kv_cache/)说明磁盘 cache is enabled by default、按 best-effort 工作；不再使用时通常在 a few hours to a few days 内清理。这不是确定删除时间，也不是关闭缓存的项目控制项。
- 当前 [DeepSeek Privacy Policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html)说明其服务可能收集 text input、prompt、uploaded files 等 `Prompts or Inputs`，并说明其收集的数据在 People's Republic of China 处理和存储。该政策同时提示开发者需要向下游用户做自己的披露。

因此本项目对 DeepSeek 路线作 no zero-retention guarantee，不声称 local-only，也不声称 guaranteed cache deletion。规则 fallback 是不允许内容离开本机时的默认选择。自动测试和本次离线质量门不需要 key、网络或 live provider；任何 live synthetic API 比较仍需单独批准。

## 删除

系统不得删除邮箱中的任何邮件。后端只能清理已过期的本地临时附件文件，且不得删除源邮件或对邮箱执行任何操作。


