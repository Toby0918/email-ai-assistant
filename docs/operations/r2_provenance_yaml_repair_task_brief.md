---
last_update: 2026-08-04
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# R2 Provenance Workflow YAML Repair Task Brief

## 1. 任务名称

Repair the R2 provenance workflow YAML parse failure.

## 2. 任务类型

`fix`

## 3. 当前状态

`implemented`

## 4. 任务目标

修复 `.github/workflows/r2_provenance.yml` 中三个依赖安装步骤的 YAML
plain-scalar 解析错误，使 GitHub Actions 能创建四个既有 jobs。保留命令、依赖锁、
runner、action pin、权限、触发器和 provenance 行为不变。

## 5. 非目标

- 不修改 #104、#105、#38 或 #39 的状态、实现或授权边界。
- 不运行 final-master verifier，不生成密钥、签名或 production artifact。
- 不访问 real host、provider、mailbox、vault、private data、credential 或私钥。
- 不改变 workflow jobs、命令语义、依赖、actions、runner 或 provenance 合约。
- 不提交、push、创建 PR、merge 或关闭 issue；这些动作需要另行授权。
- 不触碰 dirty 主仓库。

## 6. 背景与依据

GitHub Actions run `30938857063` 在创建 job 前以 YAML syntax error 失败；公开注释定位
到 line 29。`actionlint` 对原文件报告 `mapping values are not allowed in this context`。
三个未加引号的 `run:` plain scalars 都包含 `:all:` 后接空格，触发 YAML mapping
delimiter 解析。内存验证表明只给这三个完整命令加双引号即可通过 `actionlint`。

相关文档：

- `AGENTS.md`
- `CONTEXT.md`
- `docs/operations/project_status_log.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/ci_guardrails.md`
- `docs/constraints/mechanical_rule_translation.md`

## 7. 涉及范围

Exact allowlist：

- `.github/workflows/r2_provenance.yml`
- `tests/test_r2_ci_provenance_v2_adapter.py`
- `docs/operations/r2_provenance_yaml_repair_task_brief.md`

## 8. 技术方案

1. 先补一个针对 committed workflow 的回归测试，要求三个依赖安装 `run` scalar 均为
   YAML-safe quoted form，并拒绝已知无效的 unquoted form。
2. 运行 focused test 证明 RED。
3. 只给三个完整 `run` scalar 加双引号，命令字节内容和执行语义保持不变。
4. 运行 focused test、官方 `actionlint`、相关约束测试、全量测试、维护扫描和泄漏扫描。

## 9. 数据结构或接口变化

### 数据库变化

无。

### API 变化

无。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱数据。
- [x] 不自动发送、删除、归档邮件。
- [x] 不在前端保存或暴露 API key。
- [x] 不改变不可信邮件输入处理。
- [x] 不改变 AI 输出解析或校验。
- [x] 不输出真实邮件、客户信息、credential、key 或 token。
- [x] 测试只读取版本库中的公开 synthetic/configuration 内容。

## 11. Prompt Injection 防护

不适用。本任务不读取邮件正文，也不改变 prompt、provider 或分析路径。

## 12. 验收标准

1. 原始 workflow 上新增回归测试为 RED，修复后为 GREEN。
2. 官方 `actionlint` 对完整 `.github/workflows/r2_provenance.yml` 返回 exit 0。
3. 三个安装命令除 YAML quoting 外完全不变，且恰好保留三个 `--require-hashes`。
4. 相关约束测试、全量单元测试、维护扫描和泄漏扫描通过。
5. Git diff 仅包含 exact allowlist，dirty 主仓库和受保护 issue 状态不变。

## 13. 测试计划

- `python -m unittest tests.test_r2_ci_provenance_v2_adapter`
- `python -m unittest tests.test_r2_ci_provenance_v2 tests.test_r2_ci_provenance_v2_adapter`
- 官方 checksum-verified `actionlint -oneline .github/workflows/r2_provenance.yml`
- 相关 architecture/static/mechanical/documentation tests
- `python -m unittest discover -s tests`
- `python scripts/maintenance_scan.py --fail-on-high`
- repository leakage scan

## 14. 回滚方案

在未提交的隔离 clone 中撤销 exact allowlist 的本地改动；不操作 dirty 主仓库，也不删除
或改写任何既有提交。

## 15. 需要人工确认的问题

实现本地修复以及 exact allowlist 的 stage、local commit 已获直接授权。push、PR、
merge 和 issue 状态变更仍需另行明确授权。

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md`。
- [x] 已阅读相关 `docs/` 文件。
- [x] 已明确任务目标、非目标和 exact allowlist。
- [x] 已确认不会触碰真实邮箱、真实密钥或真实客户数据。
- [x] 已确认 dirty 主仓库未被触碰。

## 17. 不适用的专项检查清单

Remote provider private-context、administrator stage-evaluation、final dataset judge、
bounded corpus handoff 和 Repository placement 均不在本修复范围内；其既有边界保持不变。

## 18. 执行后记录

实际修改文件：

- `.github/workflows/r2_provenance.yml`
- `tests/test_r2_ci_provenance_v2_adapter.py`
- `docs/operations/r2_provenance_yaml_repair_task_brief.md`

测试结果：

- 新回归测试在原 workflow 上按预期 RED，修复后 GREEN。
- focused provenance suites: 9 tests, passed。
- architecture/static/mechanical/maintenance/status/leakage suites: 135 tests, passed。
- 官方 checksum-verified `actionlint`: exit 0。
- full discovery: 2721 tests，2717 passed，3 skipped，1 个 checkout-only CRLF
  failure；同一 Git tree 的 LF checkout 上单独复跑该 exact runbook-byte test 通过。
- maintenance scan: high 0；仅保留 19 个既有 low stale-doc findings。
- repository leakage scan（含本简报）: total 0。

未完成事项：

- 尚未 push、创建 PR 或触发修复分支远端 CI。

后续建议：

- 经另行授权后 push 修复分支并创建 PR，再以 GitHub Actions 实际创建四个 jobs
  作为最终 hosted-workflow 证据。
