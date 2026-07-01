---
last_update: 2026-06-29
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 文档维护规则

## 目标

`AGENTS.md` 只保留项目重点、技术基线、安全红线和导航。细节规则应沉淀到 `docs/`，由 `AGENTS.md` 指向目标文件。

## docs/ 目录职责

- `docs/product/`：产品定位、用户流程、功能边界和路线图。
- `docs/knowledge_base/`：邮件分类、优先级、动作建议、风险点、回复准则和业务词表。
- `docs/prompts/`：邮件分析、回复草稿、风险识别 prompt 和版本记录。
- `docs/data/`：数据字典、数据库结构、AI 输出 schema 和样例邮件格式。
- `docs/api/`：后端接口契约、前后端流程和错误码。
- `docs/security/`：隐私、API key、prompt injection 和邮件数据处理规则。
- `docs/constraints/`：工具、依赖、模块职责、数据流和 AI 输出约束。
- `docs/conventions/`：日志等代码约定。
- `docs/decisions/`：重要产品和技术决策记录。
- `docs/operations/`：启动、测试、部署、排障和文档维护规则。
- `docs/templates/`：Agent 任务简报等可复制填写的模板。

## docs/ 文档元信息规则

`docs/` 下的所有 Markdown 文档必须在文件头部包含 YAML front matter，用于标记文档更新时间、文档状态、负责人、复查周期和文档类型。

标准格式如下：

```yaml
---
last_update: 2026-06-29
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---
```

## 字段说明

`last_update` 表示文档最后更新时间，必须使用 `YYYY-MM-DD` 格式。

`status` 表示文档当前状态，只能使用以下三个值：

```text
draft
active
deprecated
```

- `draft`：草稿文档，内容尚未稳定。
- `active`：当前有效文档，开发、Prompt、业务规则和测试应优先以该文档为准。
- `deprecated`：已废弃文档，仅保留历史参考，不应继续用于新开发。

`owner` 表示文档负责人，默认使用：

```text
"@tobyWang"
```

`review_cycle` 表示文档复查周期，只能使用以下值：

```text
weekly
monthly
quarterly
as_needed
```

`source_type` 表示文档类型，只能使用以下值：

```text
product_spec
business_knowledge
prompt_spec
data_schema
api_contract
security_policy
decision_record
operation_guide
```

## source_type 建议

| 目录 | 建议 source_type |
| --- | --- |
| `docs/product/` | `product_spec` |
| `docs/knowledge_base/` | `business_knowledge` |
| `docs/prompts/` | `prompt_spec` |
| `docs/data/` | `data_schema` |
| `docs/api/` | `api_contract` |
| `docs/security/` | `security_policy` |
| `docs/constraints/` | `operation_guide` |
| `docs/conventions/` | `operation_guide` |
| `docs/decisions/` | `decision_record` |
| `docs/operations/` | `operation_guide` |
| `docs/templates/` | `operation_guide` |

## 维护要求

- 不允许使用中文冒号，必须使用英文冒号 `:`。
- `deprecated` 必须拼写正确，不允许写成 `deparecated`。
- `docs/` 下新增 Markdown 文档时，必须先添加 YAML front matter。
- 文档内容发生实质性变更时，必须同步更新 `last_update`。
- `status: active` 的文档代表当前有效规则，代码、Prompt 和测试应尽量与其保持一致。
- `status: deprecated` 的文档不得作为新功能开发依据。
- 文档内容发生实质性变更时，应同步更新相关交叉引用。
- 安全规则变更时，必须检查后端代码、前端代码、测试和 prompt 是否需要调整。
- Prompt 文档必须明确输入、输出、限制和安全边界。
- 数据 schema 文档必须与后端校验逻辑保持一致。
- API 文档必须与前后端实际请求和响应保持一致。
- `docs/knowledge_base/` 不允许存放真实客户邮件全文、API key、密码、真实报价、未脱敏合同或其他敏感资料。


