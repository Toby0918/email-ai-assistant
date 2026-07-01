---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 可执行架构约束

本项目的可执行架构约束见：

```text
docs/constraints/architecture_constraints.md
```

对应自动化检查见：

```text
tests/test_architecture_constraints.py
```

Agent 在新增模块、调整目录结构、修改依赖方向、改变前后端数据流、调整 AI 输出 JSON 或引入新依赖前，必须先阅读架构约束，并确保测试通过：

```bash
python -m unittest discover -s tests -p "test_architecture_constraints.py"
```

架构约束不得因单个功能需求被随意放宽。确需改变时，必须同步更新 `docs/constraints/architecture_constraints.md`、`docs/constraints/tooling_constraints.md`、任务模板和对应测试。
