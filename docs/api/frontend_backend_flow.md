---
last_update: 2026-07-18
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: api_contract
---

# 前后端流程

## 点击分析流程

Analyze 控件前必须持续展示以下 exact persistent disclosure：

> After you click Analyze, configured remote AI providers may receive locally deidentified current visible email text and selected current-message images or files after local screening. Media pixels or document content may contain identifying information and are not guaranteed to be fully deidentified. Processing is not local-only, and no zero-retention guarantee is made.

1. 前端只在顶层或唯一可见、同源 `mainFrame` 中检测当前邮件；若线程无法可靠分段，则固定降级为 current-only，不把整页伪装为历史线程。
2. 用户点击“分析此邮件”。
3. 前端整理当前邮件字段：`subject`、`from`、`to`、`sent_at`、`body_text` 或 `body_html`；签名头像、logo、tracker、隐藏资源、外部资源和归属歧义资源必须拒绝。仅在此点击路径中有界收集当前邮件可见的 selected current-message images/files。
4. 经本地筛查的业务内联图和附件使用 opaque `attachment_files` payload；未支持、超限、不可用、读取失败、超时或候选遗漏进入带允许 `code` 的 `resource_limitations`。响应头已声明超限时，前端只做非阻塞的 best-effort body cancel，并立即返回 `frontend_limit`，不得等待 cancel promise settle。
5. 20-second resource collection 独立结束后，前端调用 `POST /api/analyze-current-email` 并使用 60-second POST wait；浏览器边界丢弃未知限制码和伪造的后端运行码。
6. 后端再次校验限制码，用确定性映射生成状态和固定安全限制文本；附件存储或清理失败使用独立保留的运行限制。
7. 后端共享 55-second cooperative target：8-second parser 后，显式启用时执行最多 one OpenAI multimodal primary call（35-second cap）；只有 eligible OpenAI failure、剩余至少 12-second 且允许 fallback 时才执行 one DeepSeek text-only fallback（10-second cap），并保留 5-second response/persistence reserve。deterministic rules last，全部 provider 默认关闭且 `max_retries=0`。
8. 后端校验 JSON schema。
9. 后端保存最多 14 个受限 `attachment_insights` 到 SQLite，不保存字节、路径、私有 URL、cookie 或 token。
10. 前端通过共享 renderer 展示结果：任务结论和当前动作优先，回复草稿正文保持目标语言。

### Current-message attachment lifecycle

1. The extension first extracts and fingerprints the already opened current message after Analyze is clicked.
2. A verified same-origin legacy control may then be fetched once into browser memory. No resource is fetched on popup load.
3. Manually selected files are not read on picker selection or change. They are read only inside the Analyze click lifecycle, after the initial current-message fingerprint.
4. Automatic and manual resources are projected to the same existing `attachment_files` shape, with manual-first deduplication and shared limits of 5 files, 10 MiB per file, and 25 MiB total.
5. The current-message fingerprint is revalidated after resource reads and before the API call. A stale result makes zero backend calls and releases file references.
6. The backend uses request-local temporary files and deletes them from request `finally` on success and every failure. The 24-hour mtime cleanup is crash recovery only, not routine retention or a scheduled job.
7. The UI derives status only from the returned enum: only `attachment_insights[].status == "parsed"` proves content parsing. Discovery, metadata, counts, `metadata_only`, `unavailable`, or `failed` do not.

When verified visible-thread segmentation is incomplete, the frontend may send the
backward-compatible optional request boolean `thread_context_limited`. Only literal
`true` is honored. It carries no diagnostic text or page-derived value and does not
change the public response schema.

## 共享结果呈现契约

- Chrome / Edge extension 与 local debug page 共同使用 `frontend/browser_extension/shared/render_analysis.js` 和 `frontend/browser_extension/shared/analysis_components.css`，不得维护两套字段解释或 CSS 排版。
- 320px 侧栏首屏以 task card 依次展示处理结论、当前诉求、下一步、关键事实和必须核查项。
- 会话历史、附件、风险依据、更多动作和技术信息使用 closed native `<details>`，初始均为折叠状态。
- Task 7 的 Option C UI allowlist 只信任 `OpenAI GPT-5.6 Sol`、`DeepSeek V4 Flash text fallback`、`DeepSeek V4 Pro text fallback` 和 `Rule fallback`。OpenAI 成功时显示 `OpenAI GPT-5.6 Sol`；DeepSeek text fallback 时固定显示：`OpenAI 多模态结果未采用，本次使用 DeepSeek 文本回退。`
- `analysis_engine.source=rule_fallback` 时固定显示：`远程模型结果未采用，本次使用安全规则结果。`；其他 backend-compatible legacy labels（`OpenAI`、`DeepSeek V4 Flash`、`DeepSeek V4 Pro`、`DeepSeek`、`Local Qwen`、`Local Gemma`、`Local AI model`）以及任何未知或不一致的 engine 元数据一律进入固定 unknown-engine 展示：`分析引擎信息未确认，请人工核查本次结果。`，不得把旧标签或规则结果伪装为 Option C 已确认模型结果。
- 请求进行中固定显示：`正在分析当前邮件及所选图片/文件，最长可能需要 60 秒。`
- 草稿独立展示 subject、body 和人工审核原因；复制动作只复制草稿，不发送邮件。
- 当前 unpacked extension 版本为 `0.2.3`。

## 密钥边界

- OpenAI API key 与 DeepSeek API key 只存在于 Python 后端环境变量。
- Ollama/Qwen 配置只存在于 Python 后端环境变量。
- 前端不保存、不显示、不转发 API key。
- 前端不直接调用 OpenAI、DeepSeek、Ollama、Qwen 或本地模型端点。

## 错误处理

- 后端不可用：提示启动本地服务。
- 邮件为空：提示无法分析空邮件。
- JSON 校验失败：提示分析失败，可重试。
- 触发安全规则：展示人工审核提示。

## 显示语言

- 前端将后端返回的英文枚举值映射为中文标签，例如 `payment` 显示为“付款/发票”，`payment_risk` 显示为“付款风险”。
- 前端不得翻译或改写 `reply_draft.body`，避免把外部回复草稿从英文误变成中文。


