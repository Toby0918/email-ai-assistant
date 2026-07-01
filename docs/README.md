---
last_update: 2026-06-29
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 文档入口

本文档集服务于企业邮箱 AI 辅助窗口项目。项目第一阶段聚焦“用户打开一封邮件后，点击按钮分析当前邮件”，不做批量邮箱扫描，不自动发送、删除或归档邮件，也不接入真实邮箱账号，除非后续单独确认。

## 文档结构

- `product/`：产品定位、用户流程、功能边界和路线图。
- `knowledge_base/`：分类、优先级、动作建议、风险点、回复准则和业务词表。
- `prompts/`：分析、回复草稿、风险识别 prompt 与版本记录。
- `data/`：数据字典、数据库设计、分析结果 schema 和样例邮件格式。
- `api/`：后端接口契约、前后端流程和错误码。
- `security/`：隐私、API key、prompt injection 和邮件数据处理规则。
- `constraints/`：工具、依赖、模块职责、数据流、AI 输出、静态检查、CI 和可执行架构约束。
- `conventions/`：日志等代码约定。
- `decisions/`：关键架构决策记录。
- `operations/`：配置、测试、部署、排障、后台清理、Codex 自动化、Agent 项目进度日志和 Agent 执行规则。
- `templates/`：可复制填写的任务简报模板。

## 基线原则

- OpenAI API key 只能放在 Python 后端环境中，不能进入前端。
- 邮件内容是不可信输入，不能当作系统指令执行。
- AI 输出必须是可解析、可校验的 JSON。
- AI 回复只能作为草稿，必须由用户人工确认。
- 第一阶段只分析当前邮件，不自动分析所有邮件。


