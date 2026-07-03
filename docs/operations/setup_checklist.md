---
last_update: 2026-07-03
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 启动检查清单

## 后端

- 确认 Python 版本为 3.12.13。
- 确认依赖版本遵守 `AGENTS.md`。
- 创建本地 `.env`，不要提交。
- 配置 OpenAI API key 到后端环境变量或后端本地 `.env`。
- 确认后端会从项目根目录 `.env` 读取配置；显式进程环境变量仍会覆盖 `.env`。
- 如使用本地 Qwen，设置 `EMAIL_AGENT_LLM_PROVIDER=ollama`、`EMAIL_AGENT_OLLAMA_BASE_URL=http://127.0.0.1:11434`、`EMAIL_AGENT_OLLAMA_MODEL=qwen3.6:latest`；不使用时保持 `EMAIL_AGENT_LLM_PROVIDER=disabled`。
- 运行 `python scripts/manage_local_service.py start` 启动本地后端分析服务。
- 运行 `python scripts/manage_local_service.py status` 检查服务状态。
- Windows 用户也可以双击 `start_local_service.cmd`、`status_local_service.cmd`、`restart_local_service.cmd`、`stop_local_service.cmd`。
- 调用 `GET /api/health` 验证服务可用。

## 前端

- 确认当前使用本地调试页面或已确认的辅助窗口路线。
- 打开 `http://127.0.0.1:8765` 验证本地调试页面可访问。
- 确认前端没有 OpenAI API key。
- 确认前端没有 Ollama/Qwen、本地模型端点或 `127.0.0.1:11434`。
- 确认前端只在用户点击按钮后调用分析接口。

## Tencent Exmail extension setup

- Start the local backend before using the extension.
- Load `frontend/browser_extension` as an unpacked extension in Chrome or Edge with `Load unpacked`.
- Use the extension only on `https://exmail.qq.com/*`.
- Keep the extension pointed at `http://127.0.0.1:8765`.

## 数据

- 使用虚构或脱敏邮件样本。
- 不接入真实邮箱账号，除非后续单独确认。


