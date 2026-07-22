---
last_update: 2026-07-21
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# 领域文档

本文件说明工程技能探索代码库前应如何读取领域上下文和架构决策。

## 当前布局

本仓库采用 single-context 布局:

```text
/
├── CONTEXT.md
├── docs/decisions/
├── backend/
└── frontend/
```

`CONTEXT.md` 当前可以不存在。领域建模技能会在真正形成领域术语或模型决策时按需创建它。

本仓库已经使用 `docs/decisions/` 保存 ADR 和其他重要产品、技术决策，因此不另建重复的 `docs/adr/`。

## 探索前读取

开始探索前:

- 如果根目录存在 `CONTEXT.md`，读取其中与任务有关的术语、边界和领域规则。
- 如果以后经过明确迁移而出现 `CONTEXT-MAP.md`，读取 map 以及与当前任务相关的 context。
- 阅读 `docs/decisions/` 中与当前修改范围有关的决策记录。

如果这些文件不存在，应继续执行，不要仅因缺少文件而阻塞，也不要预先建议创建空文档。

## 使用领域词汇

issue 标题、重构建议、假设和测试名称应使用 `CONTEXT.md` 定义的领域术语，不要改用其中明确排除的同义词。

需要的概念尚未出现在词汇表时，应先判断是否使用了项目外术语。如果确实存在领域空缺，再交由 `/domain-modeling` 处理。

## 标记 ADR 冲突

如果建议与现有决策记录冲突，必须明确指出，不得静默覆盖:

> 与 ADR-0007 冲突，但值得重新讨论，因为……
