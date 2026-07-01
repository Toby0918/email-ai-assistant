---
last_update: 2026-06-29
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: decision_record
---

# ADR 0002：辅助窗口前端路线

## 状态

待决定。

## 背景

辅助窗口可能通过 Outlook Add-in、Google Workspace Add-on、Chrome / Edge 浏览器扩展或本地调试页面实现。

## 决策

第一阶段允许先使用本地调试页面或模拟前端验证交互和 API。正式企业邮箱接入路线需要后续根据目标邮箱环境单独确认。

## 约束

- 前端不得保存 OpenAI API key。
- 前端不得直接调用 OpenAI API。
- 不默认接入真实邮箱账号。
- 引入前端框架或构建工具前必须更新 `AGENTS.md` 和相关文档。


