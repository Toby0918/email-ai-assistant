---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: data_schema
---

# 数据库设计

第一阶段使用本地 SQLite 保存调试和回看用分析结果。数据库不得提交到代码仓库。

## 表：email_analysis

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 自增分析记录 ID |
| `subject` | text | 邮件主题 |
| `sender` | text | 发件人 |
| `analysis_json` | text | 分析结果 JSON |
| `created_at` | text | 创建时间 |

## 规则

- 不保存 API key、token 或邮箱密码。
- 不提交 SQLite 数据库文件。
- 测试数据必须脱敏或使用虚构内容。


