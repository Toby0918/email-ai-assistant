---
last_update: 2026-07-11
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
- 后端启动时会加载项目根目录 `.env`；显式进程环境变量优先于 `.env`。
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
- 请求分析路径继续执行既有过期清理。没有后台邮箱 poller、任务队列或常驻清理 scheduler。
- 成功只报告删除数量和服务状态。失败返回通用错误并中止 start/restart；不报告附件名、内容、私有 URL、cookie、token、OCR 文本或异常中的私有路径。
- `python scripts/manage_local_service.py status` 与 `GET http://127.0.0.1:8765/api/health` 只提供本地服务健康信息，不读取附件内容。

## 前端配置

- 前端仅调用本地或受控后端 API。
- 前端不保存 API key。
- 前端不直接调用 OpenAI、Ollama、Qwen 或本地模型端点。
- 前端只在用户点击按钮后提交当前邮件。
- Chrome / Edge unpacked extension 当前版本为 `0.2.2`。部署或替换文件后，在扩展管理页点击 `Reload`，再刷新 Tencent Exmail 页面。

## Troubleshooting and rollback

- 清理失败：验证 `EMAIL_AGENT_ATTACHMENT_TEMP_DIR` 指向后端可写目录及权限，修复后重试；不要把具体私有路径复制到 issue 或日志。
- 后端不可达：运行 `status` 和 `/api/health`，确认 loopback 端口 `8765` 未冲突，再执行 `restart`。
- 图片无法 OCR：安装 Tesseract 可执行程序并配置 PATH，或接受 metadata-only 降级。
- 本地模型失败：把 `EMAIL_AGENT_LLM_PROVIDER` 恢复为 `disabled`，重启服务并使用规则兜底。
- 扩展回滚：在扩展管理页移除或禁用 unpacked extension；恢复上一份已验证的 `frontend/browser_extension` 文件后重新 `Load unpacked`/`Reload`。后端回滚使用上一已验证提交，再重新运行完整 release checklist。

## Release gate

1. 按 `docs/operations/testing_checklist.md` 的 repeatable phase-two release checklist 运行状态生成、完整 Python suite、maintenance scan、七个 Node 检查、manifest/doc guards 和 staged snapshot 检查。
2. 确认 provider 仍默认 `disabled`，没有新增依赖、后台 mailbox scheduler 或真实邮箱访问。
3. 确认 staged scope 不含 `.env`、数据库、日志、附件源文件、真实邮件、凭据或 token。
4. 自动化和合成验证通过后，可交付 unpacked extension `0.2.2` 供用户测试。
5. 真实 Tencent Exmail 邮件 smoke test 未由本任务执行，仍是需要用户单独授权并运行的外部 release validation；在它完成前不得声称真实邮箱验证完成。

## 上线前必须确认

- 目标邮箱平台。
- 授权范围。
- 数据留存策略。
- 日志脱敏策略。
- 人工审核流程。
- 用户执行真实 Tencent Exmail smoke validation 的授权、匿名测试邮件和验收记录。


