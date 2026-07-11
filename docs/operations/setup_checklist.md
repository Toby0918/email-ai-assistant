---
last_update: 2026-07-11
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
- 如后续单独启用 OpenAI，再把 API key 配置到后端环境变量或后端本地 `.env`；当前 provider 默认保持关闭。
- 确认后端会从项目根目录 `.env` 读取配置；显式进程环境变量仍会覆盖 `.env`。
- 如使用本地 Ollama，设置 `EMAIL_AGENT_LLM_PROVIDER=ollama`、`EMAIL_AGENT_OLLAMA_BASE_URL=http://127.0.0.1:11434`、`EMAIL_AGENT_OLLAMA_MODEL=qwen3.6:latest`、`EMAIL_AGENT_OLLAMA_TIMEOUT_SECONDS=30`；可把模型改为 `gemma4`。不使用时保持 `EMAIL_AGENT_LLM_PROVIDER=disabled`。
- 确认附件默认配置：`EMAIL_AGENT_ATTACHMENT_TEMP_DIR=outputs/attachment_temp`、`EMAIL_AGENT_ATTACHMENT_RETENTION_HOURS=24`、`EMAIL_AGENT_ATTACHMENT_MAX_FILES=5`、`EMAIL_AGENT_ATTACHMENT_MAX_FILE_BYTES=10485760`、`EMAIL_AGENT_ATTACHMENT_MAX_TOTAL_BYTES=26214400`。
- 受支持类型仅为当前页面可见的 image、PDF、XLSX 和 DOCX；单次最多 5 个、单文件 10 MiB、总计 25 MiB。
- 图片 OCR 可选安装 Tesseract 可执行程序；缺失或执行失败时仅降级为图片元数据，不阻断邮件正文分析或规则兜底。
- 运行 `python scripts/manage_local_service.py start` 启动本地后端分析服务。
- 确认 `start` 输出一次安全的附件清理删除计数；`restart` 也只在 stop/start 序列前清理一次。不得出现文件名、私有路径、内容、URL、cookie、token 或 OCR 文本。
- 运行 `python scripts/manage_local_service.py status` 检查服务状态。
- Windows 用户也可以双击 `start_local_service.cmd`、`status_local_service.cmd`、`restart_local_service.cmd`、`stop_local_service.cmd`。
- 调用 `GET http://127.0.0.1:8765/api/health` 验证服务返回 HTTP 200。

## 前端

- 确认当前使用本地调试页面或已确认的辅助窗口路线。
- 打开 `http://127.0.0.1:8765` 验证本地调试页面可访问。
- 确认前端没有 OpenAI API key。
- 确认前端没有 Ollama/Qwen、本地模型端点或 `127.0.0.1:11434`。
- 确认前端只在用户点击按钮后调用分析接口。

## Tencent Exmail extension setup

- Start the local backend before using the extension.
- Load `frontend/browser_extension` as an unpacked extension in Chrome or Edge with `Load unpacked`.
- Confirm the unpacked extension reports version `0.2.2`.
- After replacing or updating extension files, click `Reload` on the extension card before each smoke-test cycle.
- Use the extension only on `https://exmail.qq.com/*`.
- Click the extension icon to open the persistent side panel.
- Keep the extension pointed at `http://127.0.0.1:8765`.

## 排障

- `Attachment cleanup failed`：检查后端临时目录配置和权限后重试；错误信息故意不显示具体私有路径。
- `status` 显示 `stopped`：运行 `start`，再检查 `/api/health`。
- `status` 显示 `unknown`：确认端口 `8765` 没有被其他非受管服务占用，停止冲突进程后重试。
- 扩展显示后端不可用：确认服务健康、扩展版本为 `0.2.2`，再 reload 扩展和 Tencent Exmail 页面。
- 图片只有元数据：确认已安装 Tesseract 可执行程序及其 PATH；不安装也属于受支持的安全降级。

## 数据

- 使用虚构或脱敏邮件样本。
- 不接入真实邮箱账号，除非后续单独确认。
- 本清单的自动化和合成验证已可执行；真实 Tencent Exmail 邮件 smoke test 未执行，仍由用户在单独授权后完成。


