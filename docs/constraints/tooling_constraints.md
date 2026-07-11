---
last_update: 2026-07-10
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Tooling Constraints and Package Responsibilities

本文件是项目的“约束层”。  
它告诉 Agent 当前项目允许使用哪些包、工具和目录结构，以及每个工具的正确用途。  
Agent 在新增功能、修改代码、调整 Prompt、修改数据结构或引入依赖前，必须先阅读本文件。

## 1. 约束层目标

本文件用于降低 Agent 犯错概率，尤其是以下错误：

- 把前端当作后端使用。
- 把 OpenAI API key 放进前端。
- 随意升级依赖版本。
- 为小功能随意引入新包。
- 用错误工具处理错误任务。
- 把真实邮件、真实密钥、真实客户信息写入日志、测试数据或文档。
- 未经确认就接入真实邮箱或自动发送邮件。
- 让 AI 输出自由文本，而不是结构化 JSON。

## 2. 规则优先级

当规则冲突时，按以下顺序执行：

```text
AGENTS.md
→ docs/constraints/tooling_constraints.md
→ docs/constraints/architecture_constraints.md
→ docs/security/*.md
→ docs/data/*.md
→ docs/api/*.md
→ docs/prompts/*.md
→ docs/knowledge_base/*.md
→ README.md
→ 代码注释
```

如果本文件与 `AGENTS.md` 冲突，以 `AGENTS.md` 为准。  
如果工具约束与可执行架构约束冲突，应先停止修改并同步更新两份约束文档和对应测试。  
如果业务文档与安全文档冲突，以安全文档为准。  
如果需求不清楚，Agent 必须先提出澄清问题，不得自行扩大范围。

## 3. 当前允许的后端技术栈

本项目后端技术栈固定如下。未经明确批准，不允许升级版本或替换工具。

| 工具 / 包 | 固定版本 | 主要用途 | 禁止用途 |
|---|---:|---|---|
| Python | 3.12.13 | 后端运行环境、业务逻辑、测试 | 不允许使用更高版本 |
| SQLite | 3.50.4 | 本地分析结果存储、调试缓存、轻量数据持久化 | 不作为企业级远程数据库；不存储真实敏感邮件全文，除非后续明确授权 |
| beautifulsoup4 | 4.15.0 | 清洗 HTML 邮件正文、去除标签和样式噪声 | 不用于业务规则判断；不用于解析 AI JSON |
| openpyxl | 3.1.5 | 导出本地调试或评估用 Excel 报表 | 不用于核心数据存储；不用于读取真实邮箱 |
| openai | 2.45.0 | 后端调用 AI 模型，生成结构化邮件分析结果 | 不允许在前端直接调用；不允许输出未经校验的自由文本 |
| python-dotenv | 1.2.2 | 本地加载 `.env` 中的后端环境变量 | 不允许把 `.env` 提交到版本库 |
| pypdf | 6.14.2 | 后端提取受限 PDF 文本 | 不解析加密、可执行或未知二进制内容 |
| python-docx | 1.2.0 | 后端提取受限 DOCX 段落和表格文本 | 不运行嵌入式活动内容 |
| Pillow | 12.3.0 | 后端检查图片并为 OCR 准备输入 | 不在前端处理图片内容 |
| pytesseract | 0.3.13 | 后端可选 OCR | Tesseract 缺失时仅降级 OCR，不能阻断规则兜底 |

本地 Ollama/Qwen/Gemma 属于后端运行环境能力，不是新增 Python 依赖。`EMAIL_AGENT_OLLAMA_MODEL` 默认是 `qwen3.6:latest`，可选择 `gemma4`；调用失败或输出无效时必须回落到本地规则分析器。`EMAIL_AGENT_OLLAMA_BASE_URL` 只能使用 `localhost` 或字面 loopback IP，不得包含 userinfo，不得指向远程 HTTP(S) 主机；远程 provider 需要单独架构批准和隐私评审。

## 4. 依赖管理规则

1. 新增依赖前，必须先说明为什么现有工具不能满足需求。
2. 新增依赖必须更新 `requirements.txt`、相关 docs 和测试。
3. 不允许为单个小功能引入大型框架，除非已有明确架构决策记录。
4. 不允许在没有批准的情况下引入 ORM、任务队列、后台调度器、浏览器自动化工具或真实邮箱 SDK。
5. 不允许混用多个功能重叠的包，例如同时引入多个 HTML parser、多个 Excel 库、多个 HTTP 框架。
6. 不允许绕过版本锁定安装最新版依赖。

## 5. 后端模块职责

后端目录建议为：

```text
backend/email_agent/
  __init__.py
  config.py
  logging_config.py
  email_cleaner.py
  analyzer.py
  llm_client.py
  database.py
  exporter.py
  api.py
```

### config.py

职责：

- 读取环境变量。
- 校验必要配置是否存在。
- 提供统一配置对象。

禁止：

- 不得硬编码 OpenAI API key。
- 不得读取前端文件中的密钥。
- 不得把密钥写入日志。

### logging_config.py

职责：

- 配置项目日志格式。
- 控制日志级别。
- 避免重复配置 logger。

禁止：

- 不得输出真实邮件正文。
- 不得输出 API key、OAuth token、邮箱凭据。
- 不得用裸 `print()` 作为业务日志。

### email_cleaner.py

职责：

- 清洗 HTML 邮件正文。
- 提取可读纯文本。
- 降低签名、引用历史、样式和无关链接噪声。

禁止：

- 不得判断最终业务优先级。
- 不得调用 OpenAI。
- 不得修改原始邮件语义。

### analyzer.py

职责：

- 组织邮件分析流程。
- 构造 AI 输入。
- 校验 AI 输出 JSON。
- 根据 docs 中的分类、优先级、风险规则约束输出。

禁止：

- 不得绕过 JSON 校验。
- 不得让邮件正文成为系统指令。
- 不得自动代表用户承诺价格、交期、付款、合同或法律事项。

### llm_client.py

职责：

- 封装后端 AI 调用，包括 OpenAI 或用户明确确认的本地 Ollama/Qwen。
- 控制模型参数。
- 处理 API 调用错误。

禁止：

- 不得从前端接收或暴露 OpenAI API key。
- 不得允许前端直接调用 Ollama、Qwen 或其他本地模型端点。
- 不得在异常信息中输出敏感内容。
- 不得返回未校验的自由文本给业务层。

### database.py

职责：

- 管理 SQLite 连接。
- 创建和维护本地数据表。
- 保存邮件分析结果和调试记录。

禁止：

- 不得保存未授权的真实邮箱数据。
- 不得把数据库文件提交到版本库。
- 不得在业务代码中散落 SQL；SQL 应集中在该模块或明确的数据访问层。

### exporter.py

职责：

- 使用 openpyxl 导出本地调试或评估用 Excel 报表。
- 将已保存的分析结果转换为人工可读表格。

禁止：

- 不得作为主数据存储。
- 不得导出真实敏感邮件内容，除非后续明确授权并经过脱敏。

### api.py

职责：

- 提供前端调用的本地后端接口。
- 接收当前邮件内容。
- 返回结构化分析结果。

禁止：

- 不得默认暴露公网访问。
- 不得接收或返回前端密钥。
- 不得加入自动发送、删除、归档邮件功能。

## 6. 前端工具边界

第一阶段前端路线必须明确选择一种：

```text
Outlook Add-in
Google Workspace Add-on
Chrome / Edge browser extension
local_debug_page
```

前端职责：

- 识别当前打开的邮件。
- 展示“分析此邮件”按钮。
- 将当前邮件必要字段发送给本地 Python 后端。
- 仅在“分析此邮件”点击路径中，传输当前打开邮件页面可见的受支持附件资源。
- 展示结构化分析结果。
- 允许用户复制或参考回复草稿。

前端禁止：

- 不得保存、硬编码或暴露 OpenAI API key。
- 不得直接调用 OpenAI API、Ollama API、Qwen 或任何本地模型端点。
- 不得自动发送邮件。
- 不得自动删除或归档邮件。
- 不得后台扫描整个邮箱。
- 不得默认读取真实邮箱账号，除非后续单独确认。
- 不得把邮件正文写入浏览器控制台日志。
- 不得在点击前收集资源、读取其他邮件或文件夹，或把附件二进制、私有下载 URL、cookie 或 token 传入 SQLite、日志或前端持久化存储。

## 7. docs/ 工具边界

`docs/` 是结构化知识库，不是垃圾箱。

允许存放：

- 产品范围。
- 邮件分类规则。
- 优先级规则。
- 风险标签。
- 回复规范。
- Prompt 规范。
- 数据结构。
- API 约定。
- 安全规则。
- ADR 技术决策。
- 测试和部署清单。

禁止存放：

- 真实客户邮件全文。
- OpenAI API key。
- 邮箱密码。
- OAuth token。
- 真实报价。
- 未脱敏合同。
- 未脱敏客户资料。
- 本地数据库文件。
- 大量临时输出。

## 8. 数据流约束

第一阶段标准数据流如下：

```text
当前打开邮件
→ 辅助窗口提取必要字段
→ 用户点击“分析此邮件”
→ 前端调用本地 Python 后端
→ 后端清洗正文
→ 后端调用 OpenAI 或后端本地 Ollama/Qwen（可选，默认关闭）
→ 后端校验结构化 JSON
→ 后端保存 SQLite
→ 前端展示结果
→ 用户人工确认后使用回复草稿
```

禁止数据流：

```text
前端 → OpenAI
前端 → Ollama/Qwen/local model endpoint
后台扫描全邮箱 → AI
AI 草稿 → 自动发送
真实邮件全文 → 日志
真实邮件全文 → docs/
真实密钥 → 前端
```

## 9. AI 输出约束

AI 分析结果必须是结构化 JSON。  
禁止只返回自由文本。

最低字段必须与 `docs/data/analysis_result_schema.md` 保持一致，建议结构如下：

```json
{
  "summary": "",
  "priority": "urgent | high | normal | low",
  "priority_reason": "",
  "category": "customer_inquiry | order_followup | payment | contract | complaint | new_product_development | internal | marketing | unknown",
  "tags": [],
  "decision_brief": {
    "one_line_conclusion": "",
    "requested_outcome": "",
    "next_steps": [],
    "key_facts": [],
    "must_check": [],
    "missing_info": [],
    "reply_recommendation": {
      "should_reply": true,
      "reply_type": "acknowledge | ask_clarification | provide_info | escalate_first | no_reply",
      "reason": ""
    },
    "confidence": "high | medium | low"
  },
  "risk_flags": [],
  "suggested_actions": [],
  "reply_draft": {
    "subject": "",
    "body": "",
    "needs_human_review": true,
    "review_reasons": []
  }
}
```

Agent 修改 AI 输出结构时，必须同步更新：

```text
docs/data/analysis_result_schema.md
docs/prompts/analyzer_prompt.md
docs/api/backend_api_contract.md
docs/constraints/architecture_constraints.md
tests/
```

## 10. 工具选择规则

### 清洗 HTML 邮件正文

使用：

```text
beautifulsoup4
```

不得使用：

```text
正则表达式硬解析复杂 HTML
OpenAI 直接清洗原始 HTML
前端 DOM 文本作为唯一可信结果
```

### 保存分析结果

使用：

```text
SQLite
```

不得使用：

```text
Excel 作为主数据库
JSON 文件作为长期主存储
浏览器 localStorage 保存敏感邮件内容
```

### 导出调试报表

使用：

```text
openpyxl
```

不得使用：

```text
手写 xlsx 二进制文件
把 Excel 当作核心业务数据库
```

### 读取配置

使用：

```text
python-dotenv
环境变量
```

不得使用：

```text
硬编码密钥
把密钥写进前端
把密钥写进 docs/
```

### 调用 AI

使用：

```text
openai 包
本地 Ollama HTTP API（仅 backend/email_agent/llm_client.py，且默认关闭）
后端封装 llm_client.py
```

不得使用：

```text
前端直接调用 OpenAI
前端直接调用 Ollama/Qwen
非正规 API 渠道
把邮件正文当作系统指令
```

## 11. 新增工具审批模板

如果 Agent 认为必须新增工具或依赖，必须先填写：

```text
工具名称：
用途：
为什么现有工具不够：
替代方案：
安全影响：
新增文件：
需要更新的 docs：
需要新增的测试：
是否影响部署：
```

未填写前，不得修改 `requirements.txt`。

## 12. 执行前检查

Agent 每次开始任务前，必须确认：

```text
[ ] 已阅读 AGENTS.md。
[ ] 已阅读本文件。
[ ] 已阅读相关 docs/ 文件。
[ ] 没有新增未批准依赖。
[ ] 没有改变真实邮箱接入边界。
[ ] 没有把密钥放进前端。
[ ] 没有把真实邮件写入日志、docs、tests 或 outputs。
[ ] 涉及 AI 输出时，已确认 JSON schema。
```

## 13. 执行后检查

Agent 每次完成任务后，必须确认：

```text
[ ] 修改范围与任务模板一致。
[ ] 未新增未批准依赖。
[ ] 测试已补充或说明原因。
[ ] 相关 docs 已同步更新。
[ ] 没有提交 `.env`、数据库文件、真实邮件、密钥或 token。
[ ] 没有引入自动发送、删除、归档邮件功能。
```
