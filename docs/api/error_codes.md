---
last_update: 2026-06-29
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: api_contract
---

# 错误码

| 错误码 | HTTP 状态 | 说明 |
| --- | --- | --- |
| `EMAIL_EMPTY` | 400 | 邮件正文为空 |
| `EMAIL_TOO_LARGE` | 413 | 邮件内容超过限制 |
| `INVALID_REQUEST` | 400 | 请求字段缺失或格式错误 |
| `AI_JSON_INVALID` | 502 | AI 返回内容不是可解析 JSON |
| `AI_SCHEMA_INVALID` | 502 | AI 返回 JSON 不符合 schema |
| `AI_SERVICE_UNAVAILABLE` | 503 | AI 服务不可用 |
| `SECURITY_RULE_BLOCKED` | 400 | 请求违反安全规则 |
| `BACKEND_NOT_READY` | 503 | 后端未完成初始化 |

## 前端展示原则

- 对用户显示简短、可操作的错误说明。
- 不显示 API key、内部 prompt、堆栈信息或敏感配置。


