---
last_update: 2026-08-05
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

`implemented`（第二轮改动仅存在于本地 worktree，尚未 commit 或 push）

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

## 19. 第二轮 hosted CI 修复授权

2026-08-05，操作员明确扩展 #104 allowlist，授权在 Draft PR #107 上继续第二轮
CI 修复；#105、dirty 主仓库、merge 和 issue 关闭仍保持禁止。Hosted run
`30964539395` 证明第一轮 YAML 修复已经使四个 jobs 成功创建，但暴露两个后续
执行缺陷：

1. portable discovery 遇到合法 Windows-only end-to-end test 的精确 skip reason
   `Windows sandbox evidence only; no Linux NTFS or ACL claim`，该 reason 尚未进入
   closed native skip registry，因此在运行测试前 fail closed；
2. `actions/setup-python` 无法在 `windows-2022` runner 提供 source-only 的
   Python 3.12.13。Windows jobs 必须改用固定 immutable release URL 和固定
   SHA-256 的 x86-64 Windows CPython 3.12.13 distribution，并以官方 SQLite
   3.50.4 DLL archive 的固定 SHA3-256 替换 distribution 自带的较新 SQLite；使用前
   必须同时验证摘要、`sys.version_info` 和 `sqlite3.sqlite_version_info`。不得降级
   Python、提高 SQLite 基线或使用 floating/latest 下载。

### 19.1 第二轮 exact allowlist

- `.github/workflows/r2_provenance.yml`
- `backend/r2_ci_provenance_v2/suites.py`
- `tests/test_r2_ci_provenance_v2.py`
- `tests/test_r2_ci_provenance_v2_adapter.py`
- `docs/operations/r2_provenance_yaml_repair_task_brief.md`
- `docs/operations/project_status_log.md`

### 19.2 已确认测试 seams

- portable slice 只通过公开的
  `portable_native_skip_reason_registry_v2()` / fixed-suite fingerprint interface
  观察 exact registered native reason；不测试私有遍历实现；
- Windows slice 只通过 committed `.github/workflows/r2_provenance.yml` interface
  观察 fixed Python/SQLite URLs、SHA-256/SHA3-256、两个 version checks、PATH
  publication 和两个 Windows jobs 的 exact provisioning；不增加 helper script、
  local action 或生产接口。

### 19.3 纵向 RED -> GREEN 顺序

1. 先新增 portable registry 回归测试，记录 RED；只加入一个已观察到的 exact
   Windows-native reason 后记录 GREEN；
2. 再新增 committed workflow runtime-provisioning 回归测试，记录 RED；只替换两个
   Windows `setup-python` steps，保持 portable/reconciliation setup、runner、依赖锁、
   三个 `--require-hashes` installs 和 provenance commands 不变后记录 GREEN；
3. 运行 focused、actionlint、constraint、full discovery、maintenance 和 leakage
   验证。Local checkout 若存在已记录的 CRLF-only byte assertion 差异，必须单独报告，
   不得伪报全绿；hosted checks 必须在另行授权 commit/push 后重新观察。

### 19.4 第二轮非目标

- 不修改或启动 #105，不修改/批准/关闭 #38，不修改/启动 #39；
- 不访问 real host、provider、mailbox、vault、private data、credential、私钥、
  VeraCrypt 或 `M:`；
- 不生成密钥、签名或 production artifact，不运行 final-master verifier；
- 不触碰 dirty 主仓库，不在 `D:\Projects` 外创建本地 worktree、workflow fixture、
  synthetic repository 或测试临时目录；
- 未获另行授权不 commit、push、merge、转 Ready 或关闭 #104。

### 19.5 第二轮实现与本地证据

- portable registry test 先在缺少 exact reason 时 RED；加入唯一观察到的
  `Windows sandbox evidence only; no Linux NTFS or ACL claim` 后 GREEN；
- Windows workflow contract test 先在四个 `actions/setup-python` steps 上 RED；
  改为 fixed CPython artifact 后，进一步验证发现该 distribution 自带 SQLite 3.53.1，
  因此收紧测试再次 RED。最终两个 Windows jobs 使用 2026-07-18 CPython 3.12.13
  install-only artifact（SHA-256
  `56c9dd9681c4810cb8bfdec277ee2606d8ab17e678e5bc2bd138eb8098e330b6`）并替换为
  official SQLite 3.50.4 DLL archive（SHA3-256
  `8454a8ef362b4b2d5a259a54948ed278ef943128bf1ba74b5cbd87ebc58e5b85`）后 GREEN；
- 按 workflow step 等价执行完整下载、摘要核对、解压、DLL 替换、版本核对、pip
  probe 和 PATH publication，实际得到 Python 3.12.13 / SQLite 3.50.4，退出 0；
- focused provenance suites: 11 tests, passed；
- architecture/static/mechanical suites: 84 tests, passed；
- maintenance/status/leakage guard suites: 60 tests, passed；
- official checksum-verified `actionlint` 1.7.12: exit 0；
- maintenance scan: high 0；仅保留 19 个既有 low stale-doc findings；
- repository leakage scan: total 0；
- `full unittest discover` 没有在当前第二轮最终树上宣称 GREEN。现有
  `tests/cutover_managed_activation_fixtures.py` fixture 将临时目录固定在
  `sys._base_executable` 的 drive root；继续运行会违反操作员要求的
  `D:\Projects` placement boundary，因此停止该验证，等待 hosted jobs 覆盖完整
  discovery；
- 在识别上述 fixture 之前，一次 adapter test 命令遗漏 TEMP override，另一次已中止的
  full-discovery 诊断触发了该 fixture 的 drive-root temporary directory。两者均已自动
  清理；随后对 `C:\issue57-approved-python-source-*` 和 `C:\issue57-synthetic-*`
  做了 exact residue check，结果为空。此偏差不计作通过证据；之后所有本地临时目录
  均限制在 `D:\Projects`。

### 19.6 尚未完成

- 尚未 commit 或 push 第二轮改动；PR #107 的 hosted checks 尚未基于本地最终树重跑；
- 未修改 #105，未触碰 dirty 主仓库，未 merge、转 Ready 或关闭任何 issue。
