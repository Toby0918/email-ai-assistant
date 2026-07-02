---
last_update: 2026-06-29
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: security_policy
---

# API Key 规则

## 必须遵守

- OpenAI API key 只能存放在 Python 后端环境变量或本地受控配置中。
- 本地 Ollama/Qwen provider 配置只能存放在 Python 后端环境变量或本地受控配置中。
- `.env` 不得提交到仓库。
- `.env.example` 只能提供占位符。
- 前端不得保存、硬编码、打印或展示 API key。
- 前端不得直接调用 OpenAI API、Ollama API、Qwen 或任何本地模型端点。

## 禁止

- 把 API key 写入浏览器扩展代码。
- 把 API key 写入 Add-in 页面代码。
- 把 API key 放进请求体从前端传给后端。
- 把 `127.0.0.1:11434`、`/api/generate`、`ollama` 或 `qwen3.6` 写入前端代码。
- 在日志、错误信息或测试快照中输出 API key。

## 轮换

如果怀疑 API key 泄露，应立即吊销旧 key，生成新 key，并检查日志和提交历史。


