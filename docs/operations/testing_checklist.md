---
last_update: 2026-07-23
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 测试检查清单

## Standalone Verification Mode

- Use one pre-created absolute temporary directory with
  `--standalone-state-root` for start, status, health, analysis, restart, and
  stop.
- Verify health and analysis only with injected adapters in automated tests;
  use a synthetic `example.test` request for an explicitly authorized manual
  loopback smoke.
- Assert SQLite, attachment temporary files, logs, and PID state stay below the
  temporary root and do not enter repository `outputs/`.
- Reject injected reparse identity for operational directories and reject
  reparse writable file targets before lifecycle actions.
- Assert the ignored repository `.env` is not loaded and every provider,
  mailbox ingest, private evaluation, private knowledge, and raw-vault
  capability remains disabled.
- Re-run existing configuration, server, lifecycle, architecture, frontend
  safety, attachment-limit, click-confirmation, persistence, and cleanup tests.
- Confirm the check does not create Managed Container state or perform a real
  Project Container migration.

## Repository placement compatibility seam and protected private stores

- Focused tests call only the public `RepositoryPlacement`,
  `OperationalLayout`, `ProtectedLocationPolicy`, and flat transition adapter
  interfaces.
- Managed synthetic fixtures prove the exact canonical
  `email_ai_assistant\main` relationship and the complete Project Container
  protected-root set.
- Standalone fixtures require an explicit synthetic or temporary state root,
  reject overlap, retain the state classification, and never infer a Project
  Container.
- Missing/unreadable identity, wrong names/parents, reparse evidence, alias
  drift, and identity changes return only fixed placement codes.
- All seven operational locations are absolute; Managed paths use the approved
  Project Container siblings and Standalone paths stay under the explicit state
  root.
- The transition adapter preserves current `.venv`, `outputs`,
  `outputs/attachment_temp`, and `.worktrees` locations without adding a third
  placement mode.
- Managed policy uses one Project Container root and rejects the container,
  `main`, `Runtimes`, `LocalData`, `RuntimeTemp`, `Logs`, `Artifacts`,
  `Worktrees`, `Config`, `OperatorPrivate`, and every descendant for private
  knowledge, private evaluation, mailbox vault/recovery, and strict external
  sales-policy locations.
- Positive synthetic external authority, candidate, snapshot, evaluation,
  vault, recovery, and sales-policy paths retain their existing separation and
  fixed-error contracts.
- Vault tests preserve NTFS, removable, full-encryption, protection, unlocked,
  and separate-volume evidence. Recovery rewrap validates and revalidates both
  current and new recovery paths before private material is opened.
- Architecture tests pin exact internal consumers, reject arbitrary-root
  construction, strip hostile request roots, and reject environment/config/
  frontend/CLI weakening seams.
- Package guards reject mutating or external-capability imports/calls. Automated
  tests remain synthetic/offline and create no real Managed Container data.

## Option C 多模态离线门

- all providers disabled by default；自动化只使用 synthetic DOM/media fixtures、fake provider 和 injected clock，不读取邮箱、不访问网络、不读取 `.env` 或 key。
- 覆盖 `exmail_visible_context.js` 的顶层/唯一可见同源 frame、可靠线程分段与 current-only 降级；覆盖 `exmail_visible_resource_classifier.js` 对业务内联图、签名头像、logo、tracker、隐藏/外部/归属歧义资源的分类。
- 覆盖图片、PDF 页面、DOCX/XLSX 内嵌媒体的清洗、大小限制、临时文件清理与 source 绑定；无文字业务照片只允许视觉定性结论。
- 覆盖 `openai_multimodal_client.py` 的固定 `https://api.openai.com/v1`、`gpt-5.6-sol`、Responses API、`text={"verbosity":"low"}`、`store=false`、`max_retries=0`、no tools 和 2,400 output tokens。OpenAI omits `text.format`; the JSON-only prompt is enforced by strict local validation.
- 覆盖 one OpenAI multimodal primary call、eligible failure 后 one DeepSeek text-only fallback、deterministic rules last；privacy/private-artifact/routing/budget block 必须是 zero fallback calls。
- 预算矩阵固定为 60-second POST wait、55-second backend、35-second OpenAI、10-second DeepSeek、12-second fallback minimum、8-second parser、5-second reserve；前端另有独立的 20-second resource collection。
- 覆盖 text/hybrid evidence、matching attachment insight 的 visual-only 定性增强、body-only fixed cross-language bridge，以及拒绝 global fields、identity、protected traits、precise facts、commands、commitments 和 outcomes。
- Tasks 1-7 的离线实现已通过各任务 review-clean 门；Task 8 只对齐文档。Task 9 synthetic provider and current-clicked Tencent smokes are complete。
- Task 9 forced OpenAI-to-DeepSeek synthetic fallback is complete: one OpenAI attempt was intercepted before network access, exactly one DeepSeek text-only request was made, DeepSeek SDK retries were zero, and no SQLite write occurred. The root `.env` was unchanged.
- Attachment Task 5 remains valid acquisition/cleanup evidence only. Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. Current/history alignment, attachment coverage, deterministic reconciliation, and private human gold-standard gates now pass offline; branch integration and any new live operation still require their own authorization. Any new live operation still requires fresh explicit authorization. All providers remain disabled by default.

## Labeled MOQ grounding release checks

- Verify the finite accepted labels are `MOQ`, `minimum order qty`, `minimum order quantity`, `最低起订量`, and `最低订购量`; tests use recreated synthetic quantities only.
- Verify one-to-four alternatives only and the closed canonical unit set; an unknown-unit remains a local negative.
- Verify parser-owned source spans and that the complete alternative set is indivisible: consumers cannot split or omit one member.
- Verify bare slash pairs, dates, ratios, phone-like values, contact/signature clauses, compact quotation rows, and pending/non-final claims produce no final labeled MOQ fact.
- Verify invalid, unitless, unknown-unit, non-final, omitted-member, changed-member, and invented-unit model MOQ claims fail closed.
- Verify final labeled MOQ closes only the quantity request; sample, attachment, lead-time, quotation, and other open items retain their independent evidence state.
- Verify provider claim that a locally known MOQ remains pending falls back only for the conflicting public field, while unrelated grounded fields remain eligible.
- Verify local extraction remains the authority for exact MOQ alternatives; a provider cannot invent, replace, or complete an alternative member.

### Release markers

- Accepted label: `MOQ`
- Accepted label: `minimum order qty`
- Accepted label: `minimum order quantity`
- Accepted label: `最低起订量`
- Accepted label: `最低订购量`
- Local unknown-unit rejection.
- Conflicting public field fallback.
- Unrelated grounded fields remain eligible.

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
- `start` 在启动进程前恰好清理一次过期附件，且新鲜附件保留。
- `restart` 在 stop/start 序列前恰好清理一次，不通过嵌套 `start` 重复清理。
- 附件清理失败返回通用可操作错误，不停止或启动服务，也不暴露文件名、内容、私有 URL、cookie、token、OCR 文本或私有路径。
- `status` 和 `/api/health` 不读取或显示附件内容。

## Tencent Exmail extension checks

- Click the extension icon and verify the side panel remains open after clicking or scrolling inside Tencent Exmail.
- Open one Tencent Exmail message and click `Analyze current email`.
- Verify one current-email payload is sent after the click.
- Verify message-scoped selected-text fallback works only for user-selected email content in the currently opened Tencent Exmail message.
- Verify local backend unavailable state is readable.
- Verify the extension does not send, delete, archive, move, or reply to mail.
- Confirm unpacked extension version `0.2.3`, and click `Reload` after updating its files.
- Verify only image, PDF, XLSX, and DOCX resources visibly associated with the opened message are eligible after the click.
- Verify the configured bounds: 5 files, 10 MiB per file, and 25 MiB total.
- If Tesseract is unavailable, verify image OCR degrades to metadata-only while email-body/rule analysis continues.
- At 320px width, verify the task card shows conclusion, current request, next step, key facts, and must-check items before any detail section.
- Verify history, attachments, risk rationale, extra actions, and technical information are closed native `<details>` on first render.
- Verify extension and local debug use shared `render_analysis.js` plus `analysis_components.css`.
- OpenAI success shows `OpenAI GPT-5.6 Sol`; DeepSeek fallback shows exactly `OpenAI 多模态结果未采用，本次使用 DeepSeek 文本回退。`.
- Rule fallback shows exactly `远程模型结果未采用，本次使用安全规则结果。`; invalid engine metadata shows exactly `分析引擎信息未确认，请人工核查本次结果。`.
- Loading shows exactly `正在分析当前邮件及所选图片/文件，最长可能需要 60 秒。`.
- Confirm the persistent disclosure before Analyze is exactly: `After you click Analyze, configured remote AI providers may receive locally deidentified current visible email text and selected current-message images or files after local screening. Media pixels or document content may contain identifying information and are not guaranteed to be fully deidentified. Processing is not local-only, and no zero-retention guarantee is made.`

### Current-message attachment acquisition release gate

- Recreated legacy-control fixtures must prove one same-origin, redirect-failing, current-message-only in-memory fetch after Analyze and zero fetches for missing target, wrong path/origin, body/signature ownership, unsupported metadata, redirect, or stale context.
- Manual-picker fixtures must prove selection/change performs zero reads, Analyze performs one bounded read, stale revalidation makes zero backend calls, and every exit clears the input and releases arrays.
- Both routes must preserve 5 files, 10 MiB per file, and 25 MiB total; the manifest permissions remain exactly `activeTab` and `sidePanel`.
- Static guards must reject `chrome.downloads`, `showOpenFilePicker`, File System Access handles, `localStorage`, `sessionStorage`, `IndexedDB`, `chrome.storage`, and local path fields.
- Backend tests must prove request `finally` deletes request-local files on success and provider failure. The 24-hour mtime cleanup is crash recovery only; it is not normal retention and is not scheduled.
- Only `attachment_insights[].status == "parsed"` proves content parsing. Array length, metadata, acquisition, `metadata_only`, `unavailable`, and `failed` do not.
- The bounded smoke proved acquisition, parsing status, routing, and cleanup only. Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. No follow-up operation may navigate, scan, send, or output message content without fresh authorization; all providers remain disabled by default.

## 安全检查

- 前端没有 API key。
- `.env` 未被提交。
- 日志不包含真实邮件和密钥。
- 回复草稿不会自动发送。
- 用户未点击按钮时不会触发分析。
- Cleanup Agent 不自动删除文件、不修改 Prompt、不放宽约束。
- 生命周期清理只在请求处理和本地服务 start/restart 路径运行，不存在后台邮箱轮询器或常驻调度器。

## 质量要求

- 新增业务代码必须配套测试。
- 涉及 AI 输出解析和邮件清洗的逻辑必须覆盖异常输入。
- 非小型任务完成后，必须更新项目状态日志，再运行完整测试和维护扫描。
- 修改邮件分类、优先级、风险点或建议动作规则时，必须运行 `tests/test_golden_email_analysis.py`。

## Repeatable phase-two release checklist

在项目根目录按顺序运行：

```powershell
python scripts/generate_project_status.py --output docs/operations/project_status_log.md
python -m unittest discover -s tests
python -B scripts/maintenance_scan.py
node --check frontend/browser_extension/content/current_message_collector.js
node --check frontend/browser_extension/content/exmail_adapter.js
node --check frontend/browser_extension/shared/api_client.js
node --check frontend/browser_extension/shared/render_analysis.js
node --check frontend/browser_extension/popup.js
node --check frontend/browser_extension/background.js
node --check frontend/local_debug_page/app.js
python -c "import json, pathlib; json.loads(pathlib.Path('frontend/browser_extension/manifest.json').read_text(encoding='utf-8')); print('manifest json: OK')"
python -m unittest tests.test_browser_extension_manifest tests.test_architecture_constraints tests.test_static_linter_constraints
git diff --cached --check
git diff --cached --name-status
```

通过条件：完整 Python suite 无失败；maintenance scan 无 findings；全部 Node 和 manifest 检查退出 0；文档/front-matter guards 通过；staged snapshot 只包含本次生命周期、文档、状态和计划收尾范围，且不包含 `.env`、数据库、日志、真实邮件、密钥或 token。

## Validation status

- 自动化单元测试、约束检查、JavaScript 语法检查和合成附件/线程样例属于本仓库内可执行验证。
- 真实 Tencent Exmail 邮件 smoke test **未在本任务执行**。它仍是用户在单独授权、确认最小范围并准备测试邮件后的外部验证项；不得把自动化或合成结果描述为真实邮箱验证。

## Authorized private-analysis offline closeout

以下步骤分为“自动离线发布门”和“后续管理员现场操作”。自动测试只执行
第一部分；不得为了验证本仓库而连接真实邮箱、打开外置 vault、读取私有
`.pkeval`、调用 DeepSeek、探测 DPAPI/BitLocker 或输入真实密钥。

### Automated offline release gate

在项目根目录设置 `EMAIL_AGENT_LLM_PROVIDER=disabled` 后执行：

```powershell
python -B -m unittest tests.test_repository_leakage_scan tests.test_rollout_closeout_contracts tests.test_maintenance_scan tests.test_generate_project_status
python -B scripts/evaluate_deepseek_analysis.py
python -B -m unittest discover -s tests
python -B scripts/generate_project_status.py --output docs/operations/project_status_log.md
python -B scripts/maintenance_scan.py --fail-on-high
git diff --check
```

`scripts/maintenance_scan.py` 集成只读 `repository_leakage_scan`。其泄漏结果
只允许固定 code、粗粒度 scope 和 count；不得回显 matched text、真实标识、
密钥或具体文件路径，也不得自动删除或改写文件。范围只限 Git tracked 文件及
仓库内明确的日志、测试输出、公开 SQLite fixture 和生成状态日志；不得打开
项目外 vault 或私有 `.pkeval`。

### Separately authorized administrator runbook

以下命令只是现场顺序合同，不属于自动验证，也不能被定时任务调用。每次真实
操作前都需要本地书面授权、单一账号、外置 NTFS + BitLocker To Go 证据及独立
恢复介质：

邮箱扫描、私有评估和生产 DeepSeek API 启用需要 separate operator confirmations；
no credentials are supplied to Codex，且浏览器、正常后端和自动化流程保持 no
automatic mailbox scan。所有管理员入口只使用下列 `python -B -m ...` 模块命令。

1. `python -B -m scripts.manage_mailbox_vault init --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account --recovery-key $RecoveryKey`
   初始化外置分析快照与分离的恢复封装。
2. `python -B -m scripts.manage_mailbox_vault inventory --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account` 只生成 content-free
   清单和 fingerprint。
3. **STOP after inventory.** 人工核对 content-free 结果并另行确认相同 fingerprint
   后，才可运行 `python -B -m scripts.manage_mailbox_vault scan --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account
   --confirm-inventory-fingerprint $Fingerprint --sales-policy $SalesPolicy`
   读取固定 24 个月窗口的正文。`$SalesPolicy` 必须是完整 Project Container
   protected root、OneDrive、系统临时目录和 raw vault 之外、经本地负责人维护的
   绝对路径；其值不会进入公开输出。
4. `scan` 完成后立即运行第一次
   `python -B -m scripts.manage_mailbox_vault verify --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account`。只有完整性失败数为零，
   才能进入附件审批。
5. attachment approval 必须由业务与隐私双审清单明确选中，随后才可运行
   `python -B -m scripts.manage_mailbox_vault attachments --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account --manifest $AttachmentManifest`；
   总数不得超过 `50`，并继续执行 10 MiB 单文件和 25 MiB 单会话上限。
6. `attachments` 完成后再次运行
   `python -B -m scripts.manage_mailbox_vault verify --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account`。第二次完整性失败数也必须
   为零，否则立即 incident stop。
7. 只有另行审核的 `StageEvaluationSelectionV1` 已严格绑定 exactly 200 条、
   authorization `scope_fingerprint` 与双审清单 `inventory_fingerprint` 分别通过，
   且本地 staging/evaluation key 已准备由 hidden getpass 输入时，才可运行
   `python -B -m scripts.manage_mailbox_vault stage-evaluation --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account
   --selection-manifest $EvaluationSelection
   --staging-dataset $EvaluationStage`。`$EvaluationStage` 必须是完整 Project
   Container protected root、OneDrive、temp、raw vault 和其他 private store
   之外的 `.pkevalstage`；命令请求 no mailbox
   app password。测试必须证明 handoff 使用 evaluation-only source、在 plaintext
   释放前拒绝 inventory mismatch、保持 no evidence accumulation，并在下一条前释放
   raw-derived identifiers；成功只输出 `evaluation_stage_complete` 和 200/0 counts。
8. 按授权使用
   `python -B -m scripts.manage_mailbox_vault purge-expired --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account`、
   `python -B -m scripts.manage_mailbox_vault revoke --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account --confirm $RevokeConfirmation`
   或 crash-recoverable `python -B -m scripts.manage_mailbox_vault rewrap-recovery
   --vault $VaultRoot --authorization-id $AuthorizationId --account $Account
   --current-recovery-key $RecoveryKey --new-recovery-key $NewRecoveryKey
   --confirm $RewrapConfirmation`。
9. `python -B -m scripts.manage_private_knowledge import-candidate
   --authority-root $AuthorityRoot --authority-id $AuthorityId --batch-root $BatchRoot
   --batch-id $BatchId --candidate-id $CandidateId` 后按顺序完成业务、隐私及必要的
   责任人审批，再运行 `python -B -m scripts.manage_private_knowledge approve
   --authority-root $AuthorityRoot --authority-id $AuthorityId --card-id $CardId` 和
   `python -B -m scripts.manage_private_knowledge publish --authority-root $AuthorityRoot
   --authority-id $AuthorityId --snapshot $Snapshot --snapshot-id $SnapshotId`。拒绝、
   过期、deprecate 或 revoke 后重新发布；签名/密钥/文件无效时正常服务必须退回
   generic rule fallback。
10. 在 stage 完成后，以 same operator-supplied 32-byte hidden key 运行
   `python -B -m scripts.evaluate_private_deepseek build --staging $EvaluationStage
   --dataset $Dataset`。stage 与 final 必须位于独立外部目录；final 使用 fresh UUIDv4
   namespace 和 distinct final magic/purpose/nonce，create-only 且不自动删除 stage。
   Build revalidates exactly 200/full strata/current dual approval/at least 40 Pro，
   并创建 zero provider/judge/network/transcript。
11. `python -B -m scripts.evaluate_private_deepseek verify --dataset $Dataset` 只做本地
   预检。真实 `python -B -m scripts.evaluate_private_deepseek run --dataset $Dataset
   --report $AggregateReport --confirm-private-evaluation I_CONFIRM_200_FLASH_40_PRO
   --interactive-judge` 还要求 stdin/stdout 均为 real local TTY；缺少该 flag 时固定
   `human_judge_unavailable`。TTY 后必须先完成 fixed exact-y readiness；EOF/cancel/
   invalid readiness 在 key/client 前固定失败。adapter 只接收
   `UsefulnessJudgeView`、拒绝 ESC/C0/C1/bidi/format controls、每 case 一次 exact y/n；
   invalid/EOF/terminal failure 在下一次
   provider call 前固定为 `human_judge_failed`。程序 no transcript，但不能阻止外部
   terminal capture。只有 aggregate-only report 持久化；仍是 20 Flash + 180 Flash /
   40 Pro、zero retry 和 no automatic production model switch。

任一步出现授权范围变化、UIDVALIDITY/fingerprint 变化、flags 变化、残留身份、
vault/签名/密钥错误、schema/safety/grounding 违规、p95 超限、泄漏 finding 或
不可解释的计数时，立即 incident stop；保持 provider disabled，保全内容无关
错误码和计数，并由本地负责人决定恢复或撤销。


