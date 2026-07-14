---
last_update: 2026-07-13
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 排障指南

## 后端无法启动

- 检查 Python 是否为 3.12.13。
- 检查依赖版本是否符合 `AGENTS.md`。
- 检查 `.env` 是否存在于本地且未提交。
- 检查服务重启后是否读取了 `.env`；`EMAIL_AGENT_LLM_PROVIDER=ollama` 才会尝试本地 Qwen。
- 检查 OpenAI API key 是否配置在后端环境变量中。
- 如启用本地 Qwen，检查 Ollama 是否运行、`qwen3.6:latest` 是否存在，以及 `EMAIL_AGENT_LLM_PROVIDER=ollama` 是否只配置在后端环境中。
- 运行 `python scripts/manage_local_service.py status` 检查服务状态。
- 如服务状态异常，运行 `python scripts/manage_local_service.py restart`。
- 如果存在过期 PID 文件，运行 `python scripts/manage_local_service.py stop` 清理后再启动。

## 前端提示后端不可用

- 检查后端服务是否启动。
- 调用 `GET /api/health`。
- 检查前端 API 地址配置。

## 分析失败

- 检查邮件正文是否为空。
- 检查 AI 返回是否为可解析 JSON。
- 本地模型不可用、超时或返回不可解析 JSON 时，后端应回落到规则分析器；可解析但字段不完整的 JSON 会先经过 schema repair。
- 如果界面持续显示 `Rule fallback`，优先检查 `.env` 是否加载、Ollama 是否运行、模型是否存在，以及服务是否已重启。
- 如果 `Local Qwen` 调用接近超时时长后才 fallback，检查 `ollama ps`；必要时运行 `ollama stop qwen3.6:latest` 卸载卡住的模型会话，再重启本地后端。
- 检查是否触发安全规则。
- 查看后端日志，但不要输出密钥或真实邮件内容。

## DeepSeek 规则兜底诊断

界面显示 `Rule fallback` 且分析响应 `ok=true` 时，公开分析仍然成功；不要把规则兜底误报为 API 失败。provider/account 诊断不会进入 `public API`、`SQLite` 或 `frontend`，只写入 operator-only 的 `outputs/local_debug_service.log`。

每个结束于规则兜底的模型尝试会产生恰好一条终态 allowlisted `event=analysis_fallback`。只读取最新事件行:

```powershell
Get-Content outputs\local_debug_service.log -Tail 30 | Select-String 'event=analysis_'
```

常见 reason code 的处理边界:

- `provider_auth`: 检查后端受控环境中的认证配置和服务重启；不要打印、复制或记录 key。
- `provider_permission_or_balance`: 在 provider 管理面核对权限或余额；浏览器和公共响应不提供账户细节。
- `provider_timeout`: 检查既定 provider deadline 和网络状态；不要通过增加重试绕过 one-call contract。
- `envelope_invalid`: provider 返回未通过内部 envelope 解析；不要记录 provider output。
- `evidence_invalid`: provider 字段缺少允许来源或 grounding；保持规则结果。
- `safety_rejected_all`: 所有模型字段在安全合并中被拒绝；保持规则结果和人工审核边界。

其他 reason code 及完整 allowlist 见 `docs/conventions/logging.md`。日志只允许固定事件字段；不得粘贴或扩展为原始 provider 错误、响应、邮件、线程、附件、URL、路径或客户信息。自动测试不会调用 DeepSeek；需要 provider 用量的合成 Analyze 操作只能由用户在完成部署后单独触发。

## 回复草稿不合适

- 检查回复 prompt。
- 检查邮件分类和风险识别结果。
- 确认草稿已标记为需要人工审核。


