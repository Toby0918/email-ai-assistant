---
last_update: 2026-07-02
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: product_spec
---

# 功能边界

## 当前支持范围

- 识别当前打开的一封邮件。
- 用户点击按钮后分析当前邮件。
- 提取主题、发件人、收件人、时间和正文。
- 清洗 HTML 邮件正文。
- 生成摘要、优先级、分类、风险点、建议动作和回复草稿。
- 将分析结果保存到本地 SQLite，用于调试和回看。
- 使用本地调试页面或待选辅助窗口前端验证流程。
- 用户点击后，浏览器扩展可传输当前打开邮件页面可见的图片、PDF、XLSX 和 DOCX 资源给本地后端；附件内容解析只在后端完成，并受文件数量、单文件大小、总大小和临时保留时间限制。

## 当前不支持

- 自动发送邮件。
- 自动删除邮件。
- 自动归档邮件。
- 自动扫描整个邮箱。
- 自动分析所有未读邮件。
- 接入真实邮箱账号，除非后续单独确认。
- 前端保存或暴露 OpenAI API key。
- 前端直接调用 OpenAI API。
- 代表用户承诺价格、交期、付款、合同或法律事项。
- 在用户点击前收集邮件、附件或会话数据。
- 读取其他邮件、文件夹或账户数据，或使用 OAuth、邮箱 SDK、后台轮询和全邮箱扫描。
- 将附件二进制、私有下载 URL、cookie、token 或完整原始附件内容写入 SQLite、日志、文档、测试或仓库。

## 后续可评估

- Outlook Add-in。
- 第二阶段已选择：Chrome / Edge browser extension for Tencent Exmail Web (`https://exmail.qq.com/*`)；只允许用户点击后分析当前打开邮件及其可见受支持资源。
- Gmail / Google Workspace Add-on。
- 团队级规则配置。
- 人工确认后的草稿插入邮箱编辑器。


