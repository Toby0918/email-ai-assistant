---
last_update: 2026-08-21
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 39 LF-independent synthetic commit fixture task brief

## 1. 任务名称

Issue 39 Windows production-flow synthetic commit fixture 的 LF 无关修复。

## 2. 任务类型

`test`

## 3. 当前状态

`publication_authorized_in_progress`

## 4. 任务目标

让 Issue 39 的完整 Windows production-flow 测试在测试自有临时 clone 中创建一个
显式、无语义、确定性的内容差异，使合成提交不再依赖源工作树与 clone 的换行符
差异。修复后应在 LF 保持工作树中完成同一 27-action 合成生产流程，并保持所有
生产边界和真实执行授权不变。

## 5. 非目标

- 不修改 Issue 39 生产模块、固定 operator command 或真实 cutover 行为。
- 不修改 `scripts/run_local_debug.py` 的仓库内容或运行时语义。
- 不执行 incident disposition、Solo Maintainer closure confirmation、protected
  verifier、Issue 修改、ruleset 修改或真实 Project Container cutover。
- 不执行 fetch、prune、tag、checkout、detach、worktree 创建/删除/修复或现场清理。
- 不 stage、commit、push 或创建/修改 PR。
- 不把换行符差异重新作为测试前置条件。

## 6. 背景与依据

- `AGENTS.md` 要求非小型修复先建立任务简报，并在完成后运行完整单元测试与维护
  扫描。
- `docs/decisions/0012-issue39-project-container-cutover-orchestration.md` 只批准实现和
  synthetic verification，且明确真实执行需要后续单独授权。
- `docs/operations/issue39_one_command_cutover_task_brief.md` 要求 Windows 测试只改动
  测试自有临时目录，并以完整 27-action 流程作为合成验证。
- LF 保持工作树中，测试 clone 使用 `core.autocrlf=false`；把当前工作树中的
  `scripts/run_local_debug.py` 复制回相同 HEAD clone 不产生 Git 内容差异，因此合成
  `git commit` 确定性失败。

## 7. 涉及范围

新增：

- `docs/operations/issue39_lf_independent_synthetic_commit_fixture_task_brief.md`

修改：

- `tests/test_r2_issue39_production_flow_windows.py`
- `docs/operations/r2_github_guardrail_unattributed_approval_compatibility_task_brief.md`
  （仅在完整验证后记录先前独立阻塞已解除）
- `docs/operations/project_status_log.md`（由既有生成器更新）

明确不修改：

- `backend/r2_issue39_orchestrator/`
- `scripts/execute_project_container_cutover.py`
- `scripts/run_local_debug.py`
- GitHub workflows、Issue、PR、ruleset 和任何现场 worktree 配置。

## 8. 技术方案

保留完整 Windows production-flow 测试作为调用方可见回归缝。测试 clone 创建后，
在 clone 内的 `scripts/run_local_debug.py` 末尾追加固定的、合法 Python 注释，再按
原路径执行 `git add` 和 synthetic commit。该注释只存在于测试自有临时 clone，
显式产生内容差异，且不依赖源 checkout 的 CRLF/LF 转换。

删除仅用于把相同文件复制回 clone 的 `shutil.copyfile` 路径；若 `shutil` 无其他用途，
同时删除未使用 import。除这一个 fixture setup 细节外，不改变 27-action 流程、
生产 handler、观察、恢复或断言。

## 9. 数据结构或接口变化

### API 变化

无。

### 数据库变化

无。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 仅使用匿名合成值和测试自有临时目录。
- [x] 不读取真实邮箱、附件、vault、私有评估或客户数据。
- [x] 不调用远程 provider，不读取密钥。
- [x] 不发送、删除、归档或遍历邮件。
- [x] 不修改真实 repository/worktree 拓扑或 Project Container。
- [x] 真实 cutover 和所有 closure gate 继续需要单独授权。

## 11. Prompt Injection 防护

不适用。本任务不处理邮件、模型输入或外部不可信指令。

## 12. 验收标准

1. 修复前，现有完整 production-flow 测试在 LF 工作树中确定性 RED，失败点为无内容
   差异的 synthetic commit。
2. 修复后，同一测试无需换行符转换即可 GREEN，并完成既有 27-action 流程。
3. 合成内容差异只写入测试自有临时 clone，仓库中的生产文件内容不变。
4. 不新增任意路径、force、cleanup、adapter 或真实执行能力。
5. 聚焦测试、约束测试、维护扫描、泄漏扫描、compileall 和 `git diff --check` 通过。
6. `python -m unittest discover -s tests` 完整结束且无失败或错误。
7. HEAD/tree、未暂存交付边界和外部 GitHub 状态不因本任务改变。

## 13. 测试计划

- RED：运行
  `tests.test_r2_issue39_production_flow_windows.Issue39ProductionFlowWindowsTest.test_fixed_production_graph_completes_27_actions_in_test_owned_layout`。
- GREEN：最小 fixture 修改后重跑同一测试。
- 运行完整 `tests.test_r2_issue39_production_flow_windows` 模块。
- 运行与 architecture、mechanical rules、static linter、status generation 和文档
  contracts 相关的聚焦测试。
- 使用项目固定 Python 3.12.13 运行 `python -m unittest discover -s tests`。
- 运行 `scripts/maintenance_scan.py`、`scripts/leakage_scan.py`、`compileall` 和
  `git diff --check`。

## 14. 回滚方案

在尚未 stage/commit 的前提下，仅撤销本任务新增任务简报、测试 fixture 修改和对应
生成状态记录。不得使用 `git reset --hard`、`git checkout --` 或其他会覆盖用户既有
改动的命令。

## 15. 需要人工确认的问题

无。用户已于 2026-08-21 明确授权 fixture 修复与完整测试，并在 fresh GET-only
pre-publication preflight 通过后授权把本任务作为同一精确 publication batch 的独立
提交 push 到新分支并创建 draft PR。merge、Issue/ruleset mutation、closure gate 与
真实 cutover 仍不在授权内。

## 16. 执行前检查

- [x] 完整重读当前项目 `AGENTS.md`、状态日志和适用 constraints。
- [x] 核对本 session skills，并确认项目禁止 Superpowers workflow/skill。
- [x] 按 `ask-matt` 路由读取 `diagnosing-bugs` 与 `tdd`。
- [x] HEAD 为 `2b116ab059ba316d5e30c273c272ebbff99415bb`。
- [x] tree 为 `b0aabfd86f5c3b0b2f26159c29a5ccf0c293bb6e`。
- [x] staged diff 为空；保留现有 Issue 38 guardrail compatibility 未暂存改动。
- [x] 已有完整 public-seam Windows production-flow 回归测试。

## 17. Remote provider private-context checklist

不适用。provider 保持关闭，本任务不进入分析请求或 private-context 路径。

## 18. Administrator stage-evaluation checklist

不适用。不读取或生成 `.pkevalstage`，不接触 raw vault 或 evaluation key。

## 19. Final dataset build and interactive judge checklist

不适用。不读取或生成 `.pkeval`，不创建 provider/judge，不执行网络调用。

## 20. Bounded corpus-to-runtime handoff checklist

不适用。不修改 corpus、runtime cards、authority envelope 或知识快照。

## 21. Repository placement and operational layout checklist

- [x] 仅在既有、精确位于目标 HEAD/tree 的 LF 保持工作树中修改测试和文档。
- [x] fixture 的所有 Git/worktree 行为仍限制在 `TemporaryDirectory` 下的测试自有 clone。
- [x] 不修改 canonical repository placement、真实 linked worktree 或 Git admin state。
- [x] 不执行真实 prepare、confirmation、verifier 或 cutover command。

## 22. Issue #110 Solo Maintainer Closure / Execution Confirmation checklist

不适用。本任务不生成、消费或复用任何 closure/execution confirmation，不修改 Issue
38/39 状态，也不声明绿色测试构成真实执行授权。

## 23. 执行后记录

已完成：

- RED：2026-08-21，精确 production-flow 测试在 `7.095s` 后按预期失败；失败点为
  `git commit -m "synthetic issue39 entry"`，stderr 为空。
- GREEN：使用显式 fixture-only Python 注释产生内容差异后，同一测试在
  `1432.983s` 后 `OK`，完整通过既有 27-action 合成流程。
- `tests/test_r2_issue39_production_flow_windows.py` 只有这一条测试，因此该精确 GREEN
  同时覆盖完整模块。

- 聚焦/约束集合：185 tests / 52.850s，`OK`。
- maintenance scan exit 0，仅 22 个既有 low stale-doc 提示；
  `scripts/repository_leakage_scan.py` 和 compileall 均 exit 0。
- `git diff --check` exit 0。
- 最终 full discovery：2848 tests / 7516.969s，`OK (skipped=4)`，无
  failure/error。
- publication batch 已授权，stage、commit、push 与 draft PR 结果待记录；未执行
  Issue/ruleset 修改、closure gate、merge 或真实 cutover。

- 最终只读审计：root 为
  `D:/Projects/email_ai_assistant/.worktrees/issue38-r2-governed-handoff-lf-2b116ab0`，
  HEAD `2b116ab059ba316d5e30c273c272ebbff99415bb`，tree
  `b0aabfd86f5c3b0b2f26159c29a5ccf0c293bb6e`，branch
  `codex/issue38-github-guardrail-unattributed-compat`。
- 25 个 tracked 修改与 2 个 untracked 任务简报均未暂存；27 个文件 raw CRLF count
  为 0、lone CR count 为 0；`git diff --check` exit 0。
