---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Cleanup Task Template

> Cleanup Agent 在执行任何清理修复前，必须先填写本模板。  
> 每个清理任务必须独立，不得把多个无关问题混在同一个修复里。

## 1. 清理任务名称

```text
例如：split oversized analyzer module
```

## 2. 问题类型

```text
oversized_file | oversized_function | missing_test | stale_doc | todo_fixme | temp_file | linter_failure | architecture_failure | security_hygiene | other
```

## 3. 当前状态

```text
draft | approved | in_progress | implemented | blocked
```

## 4. 问题描述

```text
❌ 什么错：
```

## 5. 修复方式

```text
✅ 怎么改：
```

## 6. 参考文档

```text
📖 去哪里看：
- AGENTS.md
- docs/operations/cleanup_agent.md
- docs/constraints/mechanical_rule_translation.md
```

## 7. 涉及文件

```text
预计修改：
- 
```

## 8. 不允许做的事

```text
- 不接入真实邮箱。
- 不自动发送、删除、归档邮件。
- 不新增依赖，除非单独批准。
- 不修改安全边界，除非单独批准。
- 不删除业务文件，除非人工确认。
- 不放宽测试、linter 或架构约束。
```

## 9. 验收标准

```text
[ ] 修改范围只包含该清理任务。
[ ] 没有混入无关格式化。
[ ] 相关测试通过。
[ ] 没有新增安全风险。
[ ] 如果发现重复问题，已登记到 code_review_rule_register.md。
```

## 10. 测试命令

```bash
python -m unittest discover -s tests
```

## 11. 执行后记录

```text
实际修改文件：
- 

测试结果：
- 

是否需要后续 PR：
- 
```
