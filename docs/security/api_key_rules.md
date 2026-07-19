---
last_update: 2026-07-16
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: security_policy
---

# API Key 规则

## 必须遵守

- OpenAI `OPENAI_API_KEY` is backend only：只能存放在 Python 后端环境变量或本地受控配置中。
- DeepSeek API key 只能存放在 Python 后端环境变量 `DEEPSEEK_API_KEY` 或本地受控配置中。
- 本地 Ollama/Qwen provider 配置只能存放在 Python 后端环境变量或本地受控配置中。
- OpenAI 只允许 backend client 使用代码固定 official endpoint `https://api.openai.com/v1` 和模型 `gpt-5.6-sol`；there is no configurable OpenAI base URL，`OPENAI_BASE_URL` 与 `EMAIL_AGENT_OPENAI_BASE_URL` 都不能改变路由。
- 环境中存在 `OPENAI_ORG_ID`、`OPENAI_PROJECT_ID`、`OPENAI_CUSTOM_HEADERS` 或 `OPENAI_ADMIN_KEY` 时，OpenAI client 必须 fail closed，不能继承 ambient account/routing context。
- DeepSeek 只允许 `llm_client.py` 使用代码固定后端端点 `https://api.deepseek.com`；禁止提供任意远程 base URL。
- `.env` 不得提交到仓库。
- `.env.example` 只能提供占位符。
- API key 不得进入 HTTP response、SQLite、日志、frontend、tests、测试快照或异常文本；前端不得保存、硬编码、打印或展示 API key。
- 前端不得直接调用 DeepSeek API、OpenAI API、Ollama API、Qwen 或任何远程/本地模型端点。

## 禁止

- 把 API key 写入浏览器扩展代码。
- 把 API key 写入 Add-in 页面代码。
- 把 API key 放进请求体从前端传给后端。
- 把 `api.deepseek.com`、`127.0.0.1:11434`、`/api/generate`、`ollama` 或 `qwen3.6` 写入前端代码。
- 在 HTTP response、SQLite、日志、错误信息、frontend 或 tests 中输出 API key。

## 轮换

如果怀疑 API key 泄露，应立即吊销旧 key，生成新 key，并检查日志和提交历史。


