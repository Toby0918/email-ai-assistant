---
last_update: 2026-07-03
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

## 回复草稿不合适

- 检查回复 prompt。
- 检查邮件分类和风险识别结果。
- 确认草稿已标记为需要人工审核。


