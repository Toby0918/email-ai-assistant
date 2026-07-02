---
last_update: 2026-07-02
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: product_spec
---

# 功能边界

## 第一阶段支持

- 识别当前打开的一封邮件。
- 用户点击按钮后分析当前邮件。
- 提取主题、发件人、收件人、时间和正文。
- 清洗 HTML 邮件正文。
- 生成摘要、优先级、分类、风险点、建议动作和回复草稿。
- 将分析结果保存到本地 SQLite，用于调试和回看。
- 使用本地调试页面或待选辅助窗口前端验证流程。

## 第一阶段不支持

- 自动发送邮件。
- 自动删除邮件。
- 自动归档邮件。
- 自动扫描整个邮箱。
- 自动分析所有未读邮件。
- 接入真实邮箱账号，除非后续单独确认。
- 前端保存或暴露 OpenAI API key。
- 前端直接调用 OpenAI API。
- 代表用户承诺价格、交期、付款、合同或法律事项。

## 后续可评估

- Outlook Add-in。
- 第二阶段已选择：Chrome / Edge browser extension for Tencent Exmail Web (`https://exmail.qq.com/*`)。
- Tencent Exmail Web 原型只允许用户点击后分析当前打开邮件。
- Gmail / Google Workspace Add-on。
- 团队级规则配置。
- 人工确认后的草稿插入邮箱编辑器。


