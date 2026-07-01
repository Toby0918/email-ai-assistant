---
last_update: 2026-06-29
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
- OpenAI API key 放在后端环境变量。
- SQLite 数据库文件仅保存在本地，不提交。

## 前端配置

- 前端仅调用本地或受控后端 API。
- 前端不保存 API key。
- 前端只在用户点击按钮后提交当前邮件。

## 上线前必须确认

- 目标邮箱平台。
- 授权范围。
- 数据留存策略。
- 日志脱敏策略。
- 人工审核流程。


