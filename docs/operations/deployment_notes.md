---
last_update: 2026-07-15
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 部署说明

## 第一阶段部署形态

第一阶段建议使用本地开发部署，用于验证 Python 后端和辅助窗口交互。不接入真实邮箱账号。

## 后端配置

- Python 固定为 3.12.13。
- 依赖版本遵守 `AGENTS.md`。
- 当前 provider 默认保持 `EMAIL_AGENT_LLM_PROVIDER=disabled`。如后续单独启用 OpenAI，API key 只能放在后端环境变量或后端本地 `.env`。
- 专用 DeepSeek provider 复用现有 OpenAI-compatible `openai==2.45.0` SDK，不安装 third-party DeepSeek SDK，也不接受可配置的 arbitrary remote base URL。`DEEPSEEK_API_KEY` 只能放在后端环境变量或后端本地 `.env`；默认模型、最大 provider 超时和输出模式分别为 `deepseek-v4-flash`、`10` 秒和 `conservative`，provider 本身仍默认 `disabled`。所有 DeepSeek 出站内容必须先通过本地去标识与 residual scan，且前端必须显示 exact persistent pre-click disclosure。
- 后端启动时会加载项目根目录 `.env`；显式进程环境变量优先于 `.env`。
- 本地 HTTP 服务 `--host` 只支持 `localhost` 或字面 IPv4 loopback（`127.0.0.0/8`），默认 `127.0.0.1`；通配地址、LAN/公网地址、DNS alias、userinfo 和 IPv6 在 bind 前拒绝。浏览器扩展固定调用 `http://127.0.0.1:8765`。
- `/api/analyze-current-email` 在读 body 前要求单一且匹配实际端口的 loopback `Host`，并要求单一 `application/json`（可选 `charset=utf-8`）Content-Type。Host 门禁与 media-type CSRF 减缓必须同时保留。
- 可选本地 Ollama/Qwen 只通过后端环境变量或后端本地 `.env` 启用：`EMAIL_AGENT_LLM_PROVIDER=ollama`、`EMAIL_AGENT_OLLAMA_BASE_URL=http://127.0.0.1:11434`、`EMAIL_AGENT_OLLAMA_MODEL=qwen3.6:latest`。
- `EMAIL_AGENT_OLLAMA_BASE_URL` 只允许 `localhost` 或字面 loopback IP（`127.0.0.0/8`、`::1` 等 `ipaddress.is_loopback` 地址）；禁止 userinfo 和任何远程 HTTP(S) 主机。未来远程 provider 必须单独审批并完成隐私评审。
- `EMAIL_AGENT_OLLAMA_MODEL` 可改为 `gemma4`，默认超时 `EMAIL_AGENT_OLLAMA_TIMEOUT_SECONDS=30`。
- 默认 `EMAIL_AGENT_LLM_PROVIDER=disabled`；本地模型不可用或输出无效时，后端回落到规则分析器。
- 本地模型返回可解析但字段不完整的 JSON 时，后端会用规则分析结果补齐 schema，再统一校验。
- SQLite 数据库文件仅保存在本地，不提交。
- 附件临时目录默认 `outputs/attachment_temp`，保留 `24` 小时；单次最多 `5` 个文件，单文件最多 `10485760` bytes，总计最多 `26214400` bytes。仅支持 image、PDF、XLSX 和 DOCX。
- Tesseract 可执行程序只用于可选图片 OCR。缺失、超时或失败时返回图片元数据和限制说明，不阻断正文分析或规则兜底。

## Local service lifecycle

- `python scripts/manage_local_service.py start` 在启动服务进程前运行一次过期附件清理。
- `python scripts/manage_local_service.py restart` 在 stop/start 序列前运行一次清理，并绕过 start 路径的第二次清理。
- `scripts/run_local_debug.py` 在启动 HTTP server 前初始化仅属于 `backend.email_agent.analysis_diagnostics` 的 UTF-8 rotating diagnostic sink。file handler 不挂 root、diagnostic logger 不传播，活动文件为 `outputs/local_debug_service.log`，达到 `1 MB` 后轮转并保留 `two backups`；该文件及备份都属于本地忽略输出。
- 请求分析路径继续执行既有过期清理。没有后台邮箱 poller、任务队列或常驻清理 scheduler。
- 成功只报告删除数量和服务状态。失败返回通用错误并中止 start/restart；不报告附件名、内容、私有 URL、cookie、token、OCR 文本或异常中的私有路径。
- `python scripts/manage_local_service.py status` 与 `GET http://127.0.0.1:8765/api/health` 只提供本地服务健康信息，不读取附件内容。

## Backend-only fallback diagnostics

- 模型尝试结束于规则兜底时，后端在本地日志写入 `exactly one terminal allowlisted event`，事件名为 `analysis_fallback`。它只包含固定 reason/stage/provider/model/output-mode/detail 值和非负 `elapsed_ms`；固定字段使用 `detail=<allowlisted detail>`。

```text
event=analysis_fallback code=<allowlisted code> stage=<allowlisted stage> provider=<allowlisted provider> model=<allowlisted model> output_mode=<allowlisted mode> detail=<allowlisted detail> elapsed_ms=<non-negative integer>
```

- 规则兜底继续返回成功的公开分析，不增加错误响应；provider/account reason code 不得进入 `public API`、`SQLite` 或 `frontend`。
- `provider_output_placeholder_echo` 固定表示 provider 在业务 parser 前回显去标识占位符；它使用 `stage=safety`、`detail=not_applicable`，不得记录实际 token 或 provider output。
- detail allowlist 是 `not_applicable`、`json_syntax`、`top_level_shape`、`schema_version`、`analysis_shape`、`attachment_shape` 和 `field_evidence_shape`。每个非 envelope fallback 都使用 `not_applicable`。这是 operator-only 日志字段，不会添加到 `public API` 或 `SQLite`。不得包含 provider output、JSON keys、paths、values 或 exception text，也不得用于重建这些内容。
- Backend-only diagnostic verification 要求 `code=envelope_invalid` 使用六个 envelope detail 之一；其他 allowlisted reason code 必须使用 `detail=not_applicable`。未知 detail 必须 fail closed，不得扩展事件内容。
- operator 只使用以下命令查看最新事件，不读取或复制完整日志:

```powershell
Get-Content outputs\local_debug_service.log -Tail 30 | Select-String 'event=analysis_'
```

- 日志不得包含 key、prompt、邮件或线程内容、附件名或内容、provider output、`raw exception`、traceback、URL、路径或 customer identifier。预期 fallback 路径不得记录 exception object 或 traceback。
- 自动 release verification 只使用 synthetic mocks/fixtures，并保持 provider disabled；Automated verification does not call DeepSeek.

## 前端配置

- 前端仅调用本地或受控后端 API。
- 前端不保存 API key。
- 前端不直接调用 OpenAI、Ollama、Qwen 或本地模型端点。
- 前端只在用户点击按钮后提交当前邮件。
- Chrome / Edge unpacked extension 当前版本为 `0.2.2`。部署或替换文件后，在扩展管理页点击 `Reload`，再刷新 Tencent Exmail 页面。

## Troubleshooting and rollback

- 清理失败：验证 `EMAIL_AGENT_ATTACHMENT_TEMP_DIR` 指向后端可写目录及权限，修复后重试；不要把具体私有路径复制到 issue 或日志。
- 后端不可达：运行 `status` 和 `/api/health`，确认使用受支持的 `localhost`/IPv4 loopback 且端口 `8765` 未冲突，再执行 `restart`；不要改用 `0.0.0.0` 或 LAN 地址。
- 图片无法 OCR：安装 Tesseract 可执行程序并配置 PATH，或接受 metadata-only 降级。
- 本地模型失败：把 `EMAIL_AGENT_LLM_PROVIDER` 恢复为 `disabled`，重启服务并使用规则兜底。
- 扩展回滚：在扩展管理页移除或禁用 unpacked extension；恢复上一份已验证的 `frontend/browser_extension` 文件后重新 `Load unpacked`/`Reload`。后端回滚使用上一已验证提交，再重新运行完整 release checklist。

## Release gate

1. 按 `docs/operations/testing_checklist.md` 的 repeatable phase-two release checklist 运行状态生成、完整 Python suite、maintenance scan、七个 Node 检查、manifest/doc guards 和 staged snapshot 检查。
2. 确认 provider 仍默认 `disabled`，没有新增依赖、后台 mailbox scheduler 或真实邮箱访问。
3. 确认 staged scope 不含 `.env`、数据库、日志、附件源文件、真实邮件、凭据或 token。
4. 自动化和合成验证通过后，可交付 unpacked extension `0.2.2` 供用户测试。
5. 真实 Tencent Exmail 邮件 smoke test 未由本任务执行，仍是需要用户单独授权并运行的外部 release validation；在它完成前不得声称真实邮箱验证完成。
6. 用户触发的 synthetic live DeepSeek diagnostic 是本次诊断补丁唯一 deferred item；自动测试、维护扫描和 health smoke 都不得发起分析 POST 或 provider request。

## 上线前必须确认

- 目标邮箱平台。
- 授权范围。
- 数据留存策略。
- 日志脱敏策略。
- 人工审核流程。
- 用户执行真实 Tencent Exmail smoke validation 的授权、匿名测试邮件和验收记录。

## Separately authorized administrator workflow

离线实现完成不等于批准真实运行。`scripts/manage_mailbox_vault.py` 是唯一允许
导入邮箱的管理员入口，并且 remains default-off、不可调度、不可由浏览器或
normal backend 调用。现场顺序必须是 `init`、content-free `inventory`、人工
fingerprint confirmation、`scan`、经 attachment approval 的第二遍
`attachments`（最多 50 个）、`verify`，再按保留/撤销决定执行
`purge-expired`、`revoke` 或 `rewrap-recovery`。

所有现场命令都从项目根目录使用 module entrypoint。先只运行：

```powershell
python -B -m scripts.manage_mailbox_vault init --vault $VaultRoot --authorization-id $AuthorizationId --account $Account --recovery-key $RecoveryKey
python -B -m scripts.manage_mailbox_vault inventory --vault $VaultRoot --authorization-id $AuthorizationId --account $Account
```

**STOP after inventory.** 只有本地负责人审核 content-free inventory 并另行确认
未变化的 fingerprint 后，才可运行：

```powershell
python -B -m scripts.manage_mailbox_vault scan --vault $VaultRoot --authorization-id $AuthorizationId --account $Account --confirm-inventory-fingerprint $Fingerprint
```

后续知识和评估入口同样固定为 `python -B -m scripts.manage_private_knowledge`
和 `python -B -m scripts.evaluate_private_deepseek`；不得依赖 `PYTHONPATH` 或直接按
文件路径执行这些管理员 CLI。

经单独业务/隐私审核的 `StageEvaluationSelectionV1` 必须 exactly 200 条、未过期，
且每条只绑定 raw record ID 与 UUIDv4 case ID/production metadata。部署前必须分别
核对 authorization `scope_fingerprint` 和审核 inventory 的 `inventory_fingerprint`；
handoff 必须使用 evaluation-only source，在 plaintext release 前核对 inventory，
保持 no evidence accumulation，并在处理下一条前释放 raw-derived identifiers。之后
管理员才可运行：

```powershell
python -B -m scripts.manage_mailbox_vault stage-evaluation --vault $VaultRoot --authorization-id $AuthorizationId --account $Account --selection-manifest $EvaluationSelection --staging-dataset $EvaluationStage
```

`$EvaluationStage` 必须是外部 `.pkevalstage`；command 使用 hidden interactive
base64 key、no mailbox app password、one record at a time cleanup，并以 distinct
magic, purpose, and namespace 写密文。成功只允许 `evaluation_stage_complete` 与
200/0 counts。它不运行 provider、不生成最终 `.pkeval`、不暴露 case/record ID、
path、text、mapping 或 exception detail。

外置 vault 是分析快照，`not a legal archive`，也有 `no automatic second backup`。
恢复密钥只恢复解锁能力，不能恢复损坏或丢失的数据。Python 删除临时明文不构成
SSD/flash 物理安全擦除。Windows volume/reparse/path-race 检查只提供
`best-effort` 进程内缓解，不声明对同用户权限攻击者的绝对防护或跨介质原子性。

## Private knowledge publication and rollback

Candidate 只可接收本地脱敏且 residual-clean 的加密批次。知识晋升要求证据阈值、
business/privacy `dual approval`，以及价格、付款、合同、质量和法律规则的责任人
审批。发布只生成项目外、加密、签名、只读 snapshot。snapshot 缺失、过期、
签名/解密失败时，日常分析必须使用 `generic rule fallback`，不得把 authority
repository、key path 或 raw vault 接入正常服务。

回滚知识时先撤下 runtime snapshot 访问并确认规则兜底，再在 authority CLI 中
deprecate/revoke 对应卡片并发布新的已审核 snapshot。不得编辑已发布密文或把
真实派生文本复制到 Git、issue、日志或状态报告。

## DeepSeek privacy, evaluation, and rollback

DeepSeek 的交互预算固定为 browser `15` 秒、backend `13` 秒、provider 最多
`10` 秒、最少剩余 `5` 秒；解析预算为 `8` 秒并保留 `2` 秒 response margin。
远程提供方只接收本地脱敏后的当前可见内容和有界批准知识，提示不得承诺
`zero-retention`。provider 默认 disabled，输出模式默认 conservative，单次调用、
零重试、JSON-only、thinking disabled、`max_tokens=2400` 和人工审核保持不变。

私有评估默认在构造 client 前返回 `human_judge_unavailable`。真实评估必须另行
提供本地、不序列化样本的人工 judge 和独立操作批准。20-case gate 任一
schema/safety/grounding/privacy/serialization 违规或 p95 超过 12 秒即停止；通过后
才允许剩余 180 Flash 和批准的 40-case paired comparison。候选结论仅报告
聚合指标，`no automatic production model switch`。

DeepSeek rollback：设置 `EMAIL_AGENT_LLM_PROVIDER=disabled` 并重启后端；撤下
private snapshot 访问以确认 generic rule fallback；不删除 vault、不更改邮箱，
也不把 provider output 写入诊断。点击前披露必须继续说明远程提供方接收本地
脱敏内容，且不得声称 local-only 或 zero-retention。

## Incident stop

以下任一情况触发 `incident stop`：授权/账号/日期范围改变，inventory
fingerprint 或 UIDVALIDITY 改变，flags 前后不一致，TLS/BitLocker/NTFS 证据失败，
路径/reparse 复核失败，身份残留，密钥/签名/完整性错误，模型 schema/safety/
grounding 违规，延迟门失败，或 repository leakage finding 非零。立即停止当前
操作、保持 provider disabled、只记录固定 code/scope/count，并交由业务与
隐私/安全负责人决定恢复、重做审批或撤销；不得自动重试、自动删除或扩大扫描。


