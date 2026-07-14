---
last_update: 2026-07-14
status: draft
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
- 专用 DeepSeek provider 复用现有 OpenAI-compatible `openai==2.45.0` SDK，不安装 third-party DeepSeek SDK，也不接受可配置的 arbitrary remote base URL。`DEEPSEEK_API_KEY` 只能放在后端环境变量或后端本地 `.env`；默认模型、最大 provider 超时和输出模式分别为 `deepseek-v4-flash`、`25` 秒和 `conservative`，provider 本身仍默认 `disabled`。
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


