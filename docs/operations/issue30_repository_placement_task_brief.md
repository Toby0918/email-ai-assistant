---
last_update: 2026-07-23
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 30 repository placement compatibility seam task brief

## 1. 任务名称

```text
Issue #30 RepositoryPlacement and OperationalLayout compatibility seam
```

## 2. 任务类型

```text
feature
```

## 3. 当前状态

```text
implemented
```

## 4. 任务目标

基于 `origin/master@772a34d` 实现 `RepositoryPlacement` 与
`OperationalLayout` 公共接口，以及与最终两模式契约分离的 flat-layout
transition adapter。接口只验证 placement identity 并解析普通 operational
locations，不创建、移动或删除真实项目数据。

## 5. 非目标

- 不执行 Project Container 或 Repository Root 的真实目录迁移。
- 不创建真实 Managed Container 数据或目录。
- 不接入 launcher、local service、runtime configuration 或 private-path guards。
- 不实现 `ContainerAudit`。
- 不开始 Issue #31 至 #40。
- 不访问 mailbox、provider、vault、credential、key 或 private store。
- 不修改、清理或删除当前根工作区和既有 worktree。

## 6. 背景与依据

- GitHub Issue #29: Project Container specification。
- GitHub Issue #30: approved compatibility-seam implementation ticket。
- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`

## 7. 涉及范围

预计新增或修改:

- `backend/project_layout/`
- `tests/test_project_layout.py`
- placement/layout 相关 architecture、tooling、testing 和 planning 文档
- `docs/operations/project_status_log.md`

九个已批准 Project Container planning paths 必须从根工作区完整移植并保留。

## 8. 技术方案

1. `RepositoryPlacement` 通过注入的只读 path-identity inspector 验证绝对路径、
   非 reparse component、可读目录 identity、canonical alias、exact `main`
   relationship 和二次 identity stability。
2. Managed Container Mode 只接受 canonical `email_ai_assistant/main` 关系；
   Standalone Verification Mode 要求显式 synthetic 或 temporary state root，
   且不推断 Project Container。
3. `OperationalLayout` 只返回七个绝对普通位置: runtime、data、temporary、log、
   artifact、worktree 和 non-secret configuration。
4. 独立 transition adapter 映射当前 flat local-service locations，但不增加第三种
   `RepositoryPlacement` mode。
5. 所有失败只暴露固定 code；返回值不携带 filesystem reader、mailbox、vault、
   credential、key、provider 或 private-store capability。

## 9. 数据结构或接口变化

### 数据库变化

无。

### API 变化

新增纯后端 Python placement/layout 公共接口；无 HTTP API 变化。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱数据。
- [x] 不自动发送、删除或归档邮件。
- [x] 不访问 provider、vault、credential、key 或 private store。
- [x] 不创建、移动、删除或迁移目录。
- [x] 测试只使用 synthetic paths、temporary directories 和 injected evidence。
- [x] native path/identity exception 不进入固定错误输出。

## 11. Prompt Injection 防护

不适用。本任务不处理邮件正文、附件、Prompt 或 provider response。路径和
injected evidence 仍视为不可信输入，不执行其中内容。

## 12. 验收标准

1. 满足 Issue #30 的全部 acceptance criteria。
2. Managed/Standalone 两模式与 transition adapter 边界明确。
3. Missing、unreadable、reparse、wrong name、wrong parent、alias drift 和
   identity drift 均固定失败。
4. Placement resolution 没有目录或外部系统副作用。
5. Focused synthetic/offline tests、完整 regression、状态生成、维护扫描、
   repository leakage scan 和 diff check 通过。
6. Standards review 无 P1/P2，Spec review 无 findings。

## 13. 测试计划

- 每个公共 seam 使用 RED -> GREEN vertical slices。
- 运行 `tests.test_project_layout` focused suite。
- 定期运行 architecture、static-linter 和 mechanical focused suites。
- 完成后运行项目 `.venv` 的完整 unittest discovery、compileall、maintenance
  scan、repository leakage scan 和 `git diff --check`。

## 14. 回滚方案

只需回退本分支的新增 package、测试和文档修改；没有真实目录、runtime、data、
ACL、mailbox、provider 或 private-store 状态需要回滚。

## 15. 需要人工确认的问题

无。Issue #30 已明确接口 seam、实现边界、自动验收条件和允许的 Git/PR 操作。
任何范围扩大、真实迁移、破坏性动作或安全决策变化必须停止并重新询问。

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md` 与项目状态日志。
- [x] 已阅读 tooling、architecture、linter、mechanical、testing 和 review 规则。
- [x] 已核验 Issue #11/#23 closed，Issue #30 open/ready/unblocked。
- [x] 已核验 `origin/master@772a34d` 与根工作区 `master@f071781`。
- [x] 已在独立 worktree/branch 完整移植并 hash 核对九个 planning paths。
- [x] 已明确不会触碰真实邮箱、provider、vault、credential 或客户数据。

## 17. Remote provider private-context checklist

不适用。Provider route、privacy transformation、runtime knowledge 和 budgets 不变。

## 18. Administrator stage-evaluation checklist

不适用。

## 19. Final dataset build and interactive judge checklist

不适用。

## 20. Bounded corpus-to-runtime handoff checklist

不适用。

## 21. 执行后记录

实际修改文件：

- 新增 `backend/project_layout/` 的 placement、identity、operational layout、
  transition adapter 和固定错误接口。
- 新增 `tests/test_project_layout.py`，并在
  `tests/test_architecture_constraints.py` 固化 capability 和任务模板约束。
- 同步 architecture、tooling、testing、project structure、task brief 和状态文档。
- 安全移植并复核九个已批准 Project Container planning paths；未修改根工作区。

测试结果：

- `tests.test_project_layout`：21 tests passed。
- placement、architecture、static-linter、mechanical focused gate：
  86 tests passed。
- 完整项目回归：1685 tests passed，1 skipped。
- `compileall`、10 个 JavaScript syntax checks 和 manifest JSON validation 通过。
- maintenance scan：no findings；repository leakage scan：`total=0`。
- `git diff --check` 通过。
- Standards 复审：0 P1/P2；Spec 复审：no findings。

未完成事项：

- 普通 P3：稳定 identity 的两次读取/比较形状可在后续独立重构中抽取 helper；
  本 Issue 不阻断。
- Issue #31 至 #40 未开始；未执行真实目录迁移或创建 Managed Container 数据。

后续建议：

- 仅通过 Issue #30 PR 评审当前 compatibility seam；不要自动 merge，也不要关闭
  父 Spec #29。
