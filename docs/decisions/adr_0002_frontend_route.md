---
last_update: 2026-07-02
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: decision_record
---

# ADR 0002：辅助窗口前端路线

## 状态

已决定。

## 背景

辅助窗口可能通过 Outlook Add-in、Google Workspace Add-on、Chrome / Edge 浏览器扩展或本地调试页面实现。第二阶段目标邮箱环境已明确为 Tencent Exmail Web。

## 决策

第一阶段继续允许使用本地调试页面或模拟前端验证交互和 API。

第二阶段正式前端原型路线选择 Chrome / Edge browser extension for Tencent Exmail Web (`https://exmail.qq.com/*`)。
正常路径只在 after the explicit analyze click 分析 current opened Tencent Exmail message，并调用本地 Python 后端。
selected-text fallback 只允许在 DOM 提取无法识别字段时使用 opened message 中的 user-selected email content。This fallback is not background page scraping and is not arbitrary webpage analysis。
它不做真实邮箱账号集成，不读取凭据或 token，不扫描邮箱，不自动发送、删除、归档、移动或回复邮件。

## 约束

- 前端不得保存 OpenAI API key。
- 前端不得直接调用 OpenAI API。
- 不默认接入真实邮箱账号。
- 不读取邮箱凭据、OAuth token、cookie 或其他账号凭据。
- 不扫描邮箱，不自动发送、删除、归档、移动或回复邮件。
- 引入前端框架或构建工具前必须更新 `AGENTS.md` 和相关文档。


