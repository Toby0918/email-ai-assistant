---
last_update: 2026-06-30
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Project Status Log Guide

本文档定义 Agent 可读项目进度日志的用途、位置、生成方式和更新规则。

## 1. 目标

项目进度日志用于帮助 Agent 接手任务前快速理解：

```text
项目当前处于什么阶段
哪些护栏已经建立
哪些关键文件已经存在
下一步应该做什么
哪些边界不能碰
```

该日志不是普通开发日志，也不是人工流水账。它是 Agent 接手项目时的上下文入口。

## 2. 标准位置

当前项目进度日志固定为：

```text
docs/operations/project_status_log.md
```

Agent 在开始非小型任务前，应先阅读：

```text
AGENTS.md
docs/operations/project_status_log.md
```

## 3. 生成工具

项目进度日志由以下脚本生成：

```text
scripts/generate_project_status.py
```

运行方式：

```bash
python scripts/generate_project_status.py --output docs/operations/project_status_log.md
```

该脚本只使用 Python 标准库，不新增依赖。

## 4. 日志内容

项目进度日志应包含：

```text
生成时间
当前阶段
Git 状态
护栏建立情况
关键文件存在情况
docs 文档状态统计
推荐下一步
禁止触碰的边界
Agent 接手说明
```

## 5. 更新频率

建议在以下场景更新：

```text
新增重要 docs 文件
新增或调整约束层规则
新增测试或维护脚本
完成阶段性功能
准备让 Agent 接手新任务
每周 Cleanup Agent 扫描后
```

## 6. 安全边界

进度日志禁止包含：

```text
真实邮件正文
OpenAI API key
OAuth token
邮箱密码
真实客户报价
未脱敏合同
未脱敏客户资料
数据库文件内容
```

## 7. 与 AGENTS.md 的关系

`AGENTS.md` 只保留导航和最高层规则。项目阶段、已完成事项、当前文件状态和下一步建议写入 `docs/operations/project_status_log.md`。

不要把项目进度流水账写入 `AGENTS.md`。
