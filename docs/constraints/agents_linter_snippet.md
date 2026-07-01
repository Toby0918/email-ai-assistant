---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 自定义静态检查约束

自定义静态检查规则见：

```text
docs/constraints/linter_constraints.md
```

日志规范见：

```text
docs/conventions/logging.md
```

对应可执行检查见：

```text
tests/test_static_linter_constraints.py
```

Agent 在提交任何代码或文档变更前，必须运行：

```bash
python -m unittest discover -s tests -p "test_static_linter_constraints.py"
```

每条自定义 linter 报错应尽量包含：

```text
❌ 什么错
✅ 怎么改
📖 去哪里看
```

Agent 不得通过删除测试、放宽规则或绕过检查来修复 linter 失败。确需修改规则时，必须同步更新 `docs/constraints/linter_constraints.md`、相关规范文档和测试。
