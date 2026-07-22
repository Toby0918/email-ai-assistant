---
last_update: 2026-07-22
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Mechanical Rule Translation

本文件定义如何把人工 code review 中反复出现的主观要求，翻译成可执行、可检测、可由 CI 阻止的机械规则。

核心原则：

```text
如果一条规则在 code review 中被提及超过 3 次，就应该被写成 linter 规则或可执行测试。
```

## 1. 为什么需要机械规则

人工 review 适合判断设计质量、业务理解和异常场景，但不适合反复提醒同一类低级错误。

如果同一问题反复出现，说明它不应该继续依赖人工记忆，而应该进入：

```text
docs/constraints/
tests/
CI pipeline
```

这样 Agent 下次犯同类错误时，CI 会直接失败，并给出修复提示。

## 2. 三次提及规则

同一类 code review 评论累计出现次数达到 3 次后，必须执行以下动作：

```text
1. 在 docs/templates/code_review_rule_register.md 记录该规则。
2. 判断该规则是否可以机械化检查。
3. 如果可以机械化检查，新增或更新 tests/ 中的约束测试。
4. 如果暂时不能机械化检查，写入 docs/operations/review_checklist.md。
5. 更新 docs/constraints/mechanical_rule_translation.md 或相关约束文档。
6. 将该检查加入 CI。
```

## 3. 主观规则到机械规则的翻译表

| 人工 review 说法 | 机械化规则 | 推荐实现位置 |
|---|---|---|
| 方法太长 | 单个 Python 函数不超过 50 行 | `tests/test_mechanical_rule_constraints.py` |
| 文件太长 | 单个后端 `.py` 文件不超过 300 行 | `tests/test_mechanical_rule_constraints.py` |
| 日志不规范 | 禁止裸 `print()`、禁止 `traceback.print_exc()` | `tests/test_static_linter_constraints.py` |
| 异常处理太随意 | 禁止裸 `except:` | `tests/test_static_linter_constraints.py` |
| 前端不该碰密钥 | `frontend/` 禁止出现环境变量读取和密钥关键词 | `tests/test_static_linter_constraints.py` |
| 前端不该直接调 AI | `frontend/` 禁止出现 OpenAI 直接调用痕迹 | `tests/test_static_linter_constraints.py` |
| 不要自动处理邮箱 | 禁止自动发送、删除、归档邮件关键词 | `tests/test_static_linter_constraints.py` |
| 架构层次乱了 | 禁止指定模块之间的反向依赖 | `tests/test_architecture_constraints.py` |
| 文档缺少维护信息 | `docs/*.md` 必须包含 YAML front matter | `tests/test_static_linter_constraints.py` |
| 依赖版本冲突 | 同一规范化包名不得出现不同的 `==` 版本 | `tests/test_repo_utils.py` + `tests/test_static_linter_constraints.py` |
| AI 输出不稳定 | AI 结果必须可解析、可校验 JSON | analyzer 相关单元测试 |
| Prompt 边界不清 | Prompt 文档必须写清输入、输出、限制、安全边界 | 文档测试或 review checklist |
| 安全边界被改了 | 修改安全边界必须同步更新 docs 和测试 | CI + review checklist |

## 4. 机械规则设计要求

一条好的机械规则必须满足：

```text
可检测：可以用脚本、AST、正则、schema 或单元测试检查。
可解释：失败信息能说明哪里错。
可修复：失败信息能告诉 Agent 怎么改。
可追踪：能指向对应 docs 文档。
可维护：规则不应过度复杂，不应误伤大量正常代码。
```

## 5. Linter 报错格式

所有自定义机械规则失败信息应尽量使用以下格式：

```text
❌ 什么错：说明违反了哪条规则。
✅ 怎么改：给出最小修复方式。
📖 去哪里看：指向对应 docs 文件。
```

示例：

```text
❌ 什么错：backend/email_agent/api.py 中函数 analyze_current_email 超过 50 行。
✅ 怎么改：拆分请求校验、分析调用和响应构造逻辑。
📖 去哪里看：docs/constraints/mechanical_rule_translation.md
```

## 6. 不能机械化的规则怎么办

不是所有 review 评论都适合立刻变成 linter。  
例如：

```text
这个回复语气不够专业
这个分类规则不够符合业务
这个功能体验不够自然
```

这类问题应先写入：

```text
docs/operations/review_checklist.md
docs/knowledge_base/reply_guidelines.md
docs/knowledge_base/email_categories.md
```

如果后来能总结出明确规则，再翻译成机械检查。

## 7. 规则生命周期

每条机械规则应经历以下状态：

```text
observed
candidate
active
deprecated
```

含义：

```text
observed: code review 中已经出现，但次数不足 3 次。
candidate: 已出现 3 次，正在准备规则化。
active: 已经写入 docs、tests 和 CI。
deprecated: 已不再适用，仅保留历史参考。
```

## 8. Agent 执行要求

Agent 在每次修复 review 评论时必须判断：

```text
这是否是重复出现的问题？
是否已经出现 3 次？
是否可以转成 linter 规则？
需要更新哪个 docs 文件？
需要新增或修改哪个测试？
```

如果用户明确说“这个问题以后不要再犯”，Agent 应优先考虑把它写入机械规则。

## 9. Write-only current-evidence rule

The write-only current-evidence boundary is executable, not a review convention.
`tests/test_current_evidence_handoff.py` proves strict synthetic contract
validation, immutable/redacted values, one append call, and fixed content-free
failures. `test_current_evidence_handoff_is_contract_only_and_write_only` in
`tests/test_architecture_constraints.py` pins the exact package import allowlist,
single public append function, forbidden reader/store/mailbox/authority markers,
and the public exports. The static-linter governance test keeps the API, security,
tooling, logging, task template, and project-structure descriptions synchronized.
