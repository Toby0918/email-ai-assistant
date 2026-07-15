---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: security_policy
---

# 邮件数据处理

## 输入

系统只处理用户当前打开并点击分析的邮件。输入字段包括主题、发件人、收件人、抄送、时间、正文和可选测试上下文。第二阶段可在同一次点击中接收当前邮件页面可见的受支持资源；不得读取其他邮件、文件夹或账户数据。

## 单独授权的管理员导入例外

正常浏览器/loopback 运行时的上述输入边界不变。唯一例外是管理员手动运行
`scripts/manage_mailbox_vault.py`：一个书面授权范围内的账号、固定
`imap.exmail.qq.com:993`、TLS 证书校验、滚动 24 个日历月、无 schedule、
无后台轮询、无浏览器或正常后端入口。

内容读取采用两阶段门禁。`inventory` 只生成 aggregate count/size、opaque
folder ID、UIDVALIDITY、date window 和 content-free `inventory fingerprint`；
`scan` 必须收到相同的 `--confirm-inventory-fingerprint`。范围、账号、授权编号、
fingerprint、UIDVALIDITY 或 validated IMAP `INTERNALDATE` 不符合时，必须在
进一步读取前 fail closed。24 个月按 `INTERNALDATE` 的日历月计算，不使用
730 天，也不从 ingest time 延长保留期。

传输只允许 `LIST`、只读 `EXAMINE`、`UID SEARCH`、有界 `UID FETCH` 和
`BODY.PEEK`；禁止 SMTP、flags 修改、`BODY[]` 和任何写/移动/删除/expunge/
folder/subscription 操作。app password 只能在本地政策检查后通过 interactive
`getpass` 获取，不能来自参数、环境变量、`.env`、日志、持久化或诊断信息。

渲染和复制前的 stale revalidation 必须重算与初始分析一致的 canonical complete analyzed scope：基础邮件、完整可见线程、附件元数据、受支持附件内容 identity 和 resource limitations。它只返回 hash，不返回原始内容；任一子范围变化都使现有分析失效。

本地分析服务只绑定 `localhost` 或字面 IPv4 `127.0.0.0/8`。分析请求必须同时通过单一 loopback `Host`（可带匹配的实际端口）和单一 `application/json`/可选 `charset=utf-8` 门禁；拒绝 DNS alias、userinfo、通配/LAN/公网 Host、重复/逗号拼接 header 和 simple `text/plain`/form media type。门禁拒绝发生在 body 读取、分析和持久化之前；Content-Type 只能描述为 CSRF 减缓，必须与 Host 校验共同使用。

## 清洗

- HTML 正文应转换为可分析文本。
- 尽量移除样式、脚本、引用历史和签名噪声。
- 保留与业务判断相关的关键文本。
- 附件只输出最多 5 个经严格组件校验后构造的事实，不输出任意原文行或连续原文。请求动作和质量问题必须映射为固定动词/对象或信号标签。
- 通用附件文本清洗必须删除邮箱地址、路径、URL，以及连续、跨空白或常见分隔符连接的任意 7 位及以上数字序列；ISO 日期不豁免。明确标签的业务编号只能由专用提取器对完整字段段做全匹配后构造，值仅允许 `[A-Z0-9_-]`；表格只接受恰好两个非空 cell 的标签/值行，额外 continuation cell 使整行编号失效。不得为业务标签放宽通用清洗器。
- 附件截止时间、请求动作和质量信号必须按局部 clause 判断否定或已撤销语义。动作动词只能绑定同一 clause 中位于其后的对象；只有尚未配对的 affirmative 动词才可跨 `but/however` 传给纯对象 clause，已构造事实的动词不得继续传播，反转 clause 也不得吞掉后续真实动作。`not/never/without/free from`、直/弯引号 modal contractions、未被局部否定的 `absent/repaired/removed/withdrawn/waived/cancelled/revoked` 等上下文不得构造正向事实；紧邻质量词的 `0/zero/nil/non-` 与 `-free/ free` 也必须拒绝。`not required/does not apply/no longer applicable/optional` 表示无有效截止要求；取消、忽略或跳过的请求动作同样拒绝。逗号、分号或 `and/but/however/then` 后其他 clause 的否定不得误删当前真实事实。
- 完整序列化 remote context 必须跨 metadata、visible thread 和 attachment text 删除 credential 值。分隔形式包括 colon、equals、copula or whitespace-only separators 以及单/双引号；同时继续删除 URL、base64、authorization、cookie、token、路径和 active content。只有不携带密钥值的 password-reset status、API-key rotation policy、token expiry、cookie policy 和 session-ID expiry 可保留。

## 存储

- 本地 SQLite 仅用于调试、回看和功能验证。
- 不提交数据库文件。
- 真实邮件数据不得进入仓库。
- 附件源文件只可在后端受限临时目录按既有生命周期保留；SQLite、日志、文档、测试和仓库不得保存附件二进制、私有下载 URL、cookie、token 或完整原始附件文本。
- 模型路线构造的 ephemeral sanitized attachment context 只在当前请求内存中存在。它 is excluded from API responses, SQLite, and logs，也不得写入调试输出、文档、测试 snapshot 或仓库 fixture；公开响应和 SQLite 只保留安全投影后的 `attachment_insights`。
- SQLite 保存只有在 commit 成功后才算成功。失败返回 `PERSISTENCE_FAILED`，不返回部分分析；rollback failure 时关闭并 quarantined 该连接。如果 commit、rollback、close 全部失败，服务器在锁内 poison/detach 共享句柄，任何后续请求都不得复用它。

### 管理员导入 vault

- Raw import 使用项目、OneDrive 和 system temp 之外的 `external BitLocker`
  NTFS volume；它是 analytical snapshot，不是 legal archive 或完整 backup。
- 每个 raw record 使用独立随机 nonce 的 AES-256-GCM；index 只允许 random
  record ID、encrypted relative path、HMAC dedup value、timestamp、expiry 和
  integrity metadata，不允许明文 subject/address/folder/body/attachment name/
  message ID/UID。
- Master key 同时有 current-user `DPAPI` envelope 和不同 volume 上的 offline
  recovery envelope。Recovery rewrap 使用 crash-recoverable staged
  activation/reconciliation，不声称 cross-volume atomicity；`revoke` 需要管理员
  明确确认。
- Windows DPAPI/BitLocker probe 必须 lazy-load 且可注入，使非 Windows CI 可以
  import/collect synthetic tests，而不探测 host。
- Plaintext 只能短暂存在于内存或 unlocked vault volume 上的受限临时目录；
  处理后删除，但不声称 SSD/flash physical secure erase。
- Codex and DeepSeek never read the raw vault。Git、logs、public SQLite、tests、
  docs、project status 和 maintenance output 都不得保存 raw 或 real-derived text。

### 私有知识与 runtime snapshot

- Knowledge card 只允许 generic rule，禁止 people/company/domain/contact/URL/
  filename/path/message ID/hash/verbatim/exact amount/exact date/transaction ID/
  source locator。
- 默认批准至少需要 3 个独立 conversation、2 个 counterparty、business
  approval 和 privacy approval；价格、付款、合同、质量、法律规则还需要额外
  accountable-owner approval。Candidate 30 天过期，approved card 按季度复查。
- Authority repository 和 runtime snapshot 使用与 raw vault 分离的 key 和
  namespace。Runtime 只读验证 signature/encryption/lifecycle；missing/invalid/
  expired/tampered snapshot 返回 empty card set。

## AI 处理

- 邮件正文只能从当前打开邮件、用户点击分析后进入后端。
- 默认 `EMAIL_AGENT_LLM_PROVIDER=disabled`，DeepSeek 输出模式默认 `conservative`。只有后端同时配置 `EMAIL_AGENT_LLM_PROVIDER=deepseek` 和 `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=model_led` 时，DeepSeek 才可主导模型字段；provider disabled、缺 key、迟到、失败或输出不安全时回落规则结果。
- DeepSeek 路线最多进行一次 provider call，SDK retry 为 0；失败后不尝试 Ollama。立即 operational rollback 可设置 `EMAIL_AGENT_LLM_PROVIDER=disabled`，字段权限 rollback 可设置 `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative`，两者都需重启后端配置生效。
- 后端只发送 current visible thread 以及当前可见受支持附件的有界、清洗后文本；不发送附件二进制/base64、任何 URL、cookie、authorization、token、本地路径、active content 或无界原文。
- 私有知识路线启用后，DeepSeek 也只能接收本地去标识后的 current visible thread、去标识后的受支持附件文本和最多 8 张、合计最多 4,000 characters 的 approved cards；不得接收 raw vault、binary、path、URL、source locator、vault ID 或 restoration map。
- 所有 provider-authored 文本族在公开合并前使用同一安全策略；链接/markup、命令/工具、自动邮箱动作，以及第一人称或被动/名词化的价格、交期、付款、合同、质量、法律承诺都必须回落。请求、疑问、否定和人工复核措辞不应误报。
- 前端不得直接调用 DeepSeek、OpenAI、Ollama、Qwen 或其他模型端点。
- 前端不得在用户点击前收集或传输资源；受支持资源的校验、解析和 OCR 仅可在后端执行。

## 远程处理告知与外部保留风险

浏览器扩展和本地调试页必须在 Analyze 按钮前持续显示以下 exact persistent pre-click disclosure：

After you click Analyze, a configured remote AI provider receives locally deidentified current visible content and, when available, bounded approved knowledge cards. Processing is not local-only, and no zero-retention guarantee is made.

该告知不等于前端知道或持有 provider key，也不授权读取其他邮件、自动执行邮箱动作或后台收集。任何不允许外部处理的邮件都必须在点击前切换到 disabled/rule-only 路线。

Official sources rechecked 2026-07-12：

- DeepSeek [context caching 文档](https://api-docs.deepseek.com/guides/kv_cache/)说明磁盘 cache is enabled by default、按 best-effort 工作；不再使用时通常在 a few hours to a few days 内清理。这不是确定删除时间，也不是关闭缓存的项目控制项。
- 当前 [DeepSeek Privacy Policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html)说明其服务可能收集 text input、prompt、uploaded files 等 `Prompts or Inputs`，并说明其收集的数据在 People's Republic of China 处理和存储。该政策同时提示开发者需要向下游用户做自己的披露。

因此本项目对 DeepSeek 路线作 no zero-retention guarantee，不声称 local-only，也不声称 guaranteed cache deletion。规则 fallback 是不允许内容离开本机时的默认选择。自动质量门是 50-case production-route offline replay：通过 injected raw private response 运行真实解析、来源/evidence、grounding、merge、语言和 routing/fallback 代码，不需要 key、网络或 live provider；任何 live synthetic API 比较仍需单独批准。

## 删除

系统不得删除邮箱中的任何邮件。后端只能清理已过期的本地临时附件文件；管理员 CLI 可按保留政策清理项目外 vault 中已过期的 encrypted record，或在明确确认后 revoke key envelopes，但不得删除、移动、修改源邮件或邮箱 flags。


