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

`implemented`（第三轮 Windows-native timeout 修复仅存在于本地 worktree，尚未
commit 或 push）

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

- 第二轮改动已 commit/push 为 `5eb3b452967b07140f348c5b4086b4f7926ee652`；
  hosted run `31042241886` 的 portable 和 independent Windows jobs 通过，
  Windows-native job 以固定 `R2_CI_PROVENANCE_INVALID` 失败；
- 未修改 #105，未触碰 dirty 主仓库，未 merge、转 Ready 或关闭任何 issue。

## 20. 第三轮 Windows-native hosted timeout 修复

### 20.1 诊断证据

- 同一 hosted run 中，Windows-independent verifier（包含相同 Git-object package、
  dependency fingerprint 和 leakage 阶段）约 26.9 秒完成；Windows-native verifier
  约 177.5 秒失败，差值约 150.6 秒。
- Windows-native fixed suite 中唯一的 120 秒子进程上限位于完整 synthetic topology
  脚本 proof。前后 Windows-native 用例的约 30 秒预算加该 120 秒上限，与 hosted
  差值吻合。verifier 按设计只公开固定失败码，因此该结论是由时序和排除实验支持的
  最强诊断，不伪称取得了被抑制的私有异常文本。
- 使用 Python 3.12.13、SQLite 3.50.4 和 Git 2.55.0.windows.3 复现：Git-object
  package、31 个锁定依赖 fingerprint、leakage scan 及所有可在 `D:\Projects` 内
  等价运行的 Windows proof 均通过。原 120 秒 topology proof 本地为 39.7 秒，限制为
  两个逻辑核后为 42.0 秒；这证明行为正确，但不能代表 2 核 hosted VM 的 I/O 余量。

### 20.2 最小修复

- Windows-native closed suite 仍运行 35 条 proof；不删除完整 topology 行为。
- 将原模块中的 120 秒 topology 脚本 test 替换为 provenance adapter 自有的同等
  public-script proof。它校验完全相同的 aggregate counts、terminal status、零 provider、
  零 leakage、零 real-host operation、六个 distinct fingerprints 和 forbidden public
  text，并使用有界 300 秒 CI budget。
- 原完整 topology 模块的其余五条 proof 继续逐条进入 closed suite。生产代码、原领域
  测试、workflow 权限/runner/action pins、依赖锁和 receipt schema 均未改变。

### 20.3 RED -> GREEN 与本地验证

- 新增 registry seam 回归测试先在旧 Windows-native module registry 上 RED，修复后
  GREEN。
- 新 CI-budgeted topology proof 在 exact dependency venv 中通过：1 test，52.3 秒。
- focused provenance suites：13 tests，passed。
- provenance/architecture/static/mechanical suites：86 tests，passed。
- maintenance/status/leakage guard suites：51 tests，passed。
- Windows-native loader：35 tests，0 load errors。
- checksum-verified official `actionlint` 1.7.12：exit 0。
- maintenance scan：high 0；仅保留 19 个既有 low stale-doc findings。
- repository leakage scan：0 findings；`git diff --check`：exit 0。
- 未运行本地 full discovery：现有 root-anchor Windows fixtures 会在
  `sys._base_executable` 的 C: 根创建临时目录，违反本任务持续有效的
  `D:\Projects` placement boundary；不得把 focused 结果伪报为 full green。

### 20.4 尚未完成与授权边界

- 第三轮改动尚未 stage、commit 或 push；PR #107 hosted checks 尚未重跑。
- 不运行 final-master verifier，不修改 #105，不触碰 dirty 主仓库，不 merge、不转
  Ready，也不关闭任何 issue。commit、push 和 hosted rerun 仍需另行明确授权。

## 21. 第四轮 Windows-native transaction Git budget 修复

### 21.1 新授权与 hosted 反馈

- 操作员已授权持续修复 PR #107 的 hosted Windows-native failure；后续 hosted
  failure 可直接继续修复，并在本地验证通过后 exact stage、commit、push。
- commit `62051159691721d23c1b02fb2a23858a774c322c` 已 push。Hosted run
  `31048584990` 的 quality、portable 和 Windows-independent jobs 通过；
  Windows-native verifier 运行约 166 秒后仍返回固定
  `R2_CI_PROVENANCE_INVALID`，reconciliation 因依赖失败而跳过。
- 第三轮把失败归因于 topology test 的唯一 120 秒 outer timeout，证据不足。
  Windows-native closed suite 在 topology 前先运行完整 repository-manifest module；
  其中一个 crash-matrix method 本地执行 20 个 physical cases、320 次 fixture Git
  调用并耗时约 177.8 秒。Fixture Git 调用总计约 23.2 秒、最慢约 0.124 秒；主要
  时间位于 transaction/native path，其 bound Git child 仍使用固定 20 秒 wait。

### 21.2 第四轮 initial exact allowlist

- `backend/cutover_repository_transaction/git_runner.py`
- `tests/test_cutover_repository_transaction_windows_scope.py`
- `docs/operations/r2_provenance_yaml_repair_task_brief.md`
- `docs/operations/project_status_log.md`

### 21.3 RED -> GREEN 计划

1. 在 transaction Windows scope tests 中通过真实 `_bounded_process` seam 和 fake
   slow child 建立回归：20 秒预算必须 RED，固定 60 秒有界预算才可完成；仍验证
   process-tree ownership、output ceiling 和 cleanup，不执行真实 Git 或 host mutation。
2. 仅把 test-sandbox bound Git runner 的 child wait 从 20 秒提升到固定 60 秒；不增加
   retry、shell、output、path、environment、Git capability 或 real-host surface。
3. 运行 focused regression、affected repository-manifest tests、provenance/constraint/
   maintenance/leakage checks；full discovery 仍受 `D:\Projects` placement boundary
   限制，不得伪报。
4. exact stage、commit、push 后观察 hosted checks；如仍失败，保留同一治理边界并
   回到诊断反馈环。

### 21.4 持续非目标

- 不修改或启动 #105，不修改/批准/关闭 #38，不修改/启动 #39；
- 不运行 final-master verifier，不访问 real host、provider、mailbox、vault、private
  data、credential、私钥、VeraCrypt 或 `M:`；
- 不触碰 dirty 主仓库，不 merge、不转 Ready、不关闭任何 issue。

### 21.5 第四轮本地证据

- fake slow-child regression 在原 20 秒预算上按预期 RED：1 test，0.001 秒，固定映射为
  `repository_git_runner_invalid`；改为固定 60 秒后同一 test GREEN。
- provenance contract、adapter public class、既有 process-tree/output-overflow guard
  和新增 slow-child guard：14 tests，0.625 秒，passed。
- 修改后真实 repository-manifest heavy crash matrix：1 test，20 个 physical cases，
  176.0 秒，passed。
- 60 秒 budget 仍只允许一次固定 Git child；未增加 retry、shell、output、path、
  environment、Git verb 或 real-host capability，既有 process-tree termination 保持不变。
- architecture/static/mechanical/provenance/repository-transaction constraints：94 tests，
  最终重跑 18.342 秒，passed。
- complete affected Windows Git-runner scope suite：8 tests，40.818 秒，passed。
- status log 已重生成且 bytes 未变化；status/maintenance/repository-leakage guard
  suites：51 tests，5.609 秒，passed。
- actual maintenance scan：high 0；仅保留 19 个既有 low stale-doc findings。
- actual repository leakage scan：0 findings。
- actionlint 1.7.12、changed-Python AST parse 和 `git diff --check` 均通过。
- 双轴 review 的 Spec 结果为 0 findings。Standards 没有 hard violation；指出的 adapter
  test seam 和文件/函数规模风险已通过把回归移到现有 transaction Windows scope
  test 消除：adapter file 249 行、transaction scope file 287 行、新 helper 47 行。
- 未运行 full discovery：其既有 root-anchor fixtures 会在 `C:\` 创建测试目录，与本轮
  synthetic artifacts 必须位于 `D:\Projects` 的 placement boundary 冲突；不得把该项
  伪报为 green。未运行 final-master verifier。

## 22. 第五轮 Windows-native content-free ordinal diagnosis

### 22.1 第四轮反证

- commit `0518e7df1094da70b2f406f2e61e0807781ca9ba` 已 push；hosted run
  `31052262227` 的 quality、portable 和 Windows-independent jobs 通过，Windows-native
  verifier 仍在约 182 秒后返回固定 `R2_CI_PROVENANCE_INVALID`。
- 同一重型 crash matrix 的 2,848 次真实 bound Git child 本地总耗时约 68.8 秒，最慢
  0.151 秒，最大 stdout 2,647 bytes；process handle count 在初始增长后稳定于约
  196--198。20 秒 child timeout 和 pipe ceiling 均未触发。因此第四轮把 20 秒 budget
  当作根因的假设被反证，60 秒放宽及其回归必须撤销。
- 使用与 hosted 相同的 Git `2.55.0.windows.3` 后，重型 method 及完整四-method
  repository-manifest module 本地仍分别通过；Git version 假设也被反证。
- Windows-native closed suite 前七个 modules 本地 29 tests 全部通过。逐 test 计时显示，
  hosted 的稳定失败时间与
  `test_reverse_manifest_and_worktree_gaps_resume_exactly` 的首个
  `manifest_relocation / after_intent` subcase 精确相邻；十个 reverse subcases 本地各约
  10--12 秒，但 Windows Server 2022 上的具体错误仍被固定公开错误码隐藏。

### 22.2 第五轮 exact allowlist 与诊断边界

- `.github/workflows/r2_provenance.yml`
- `backend/cutover_repository_transaction/git_runner.py`
- `tests/test_cutover_repository_transaction_windows_scope.py`
- `docs/operations/r2_provenance_yaml_repair_task_brief.md`
- `docs/operations/project_status_log.md`

本轮先把 Git child timeout 和对应回归精确恢复到第四轮前状态，再在 Windows-native
job 的正式 verifier 前加入一次临时 fail-fast ordinal probe。Probe 只运行 code-fixed
suite 的前七个 synthetic-only modules，重定向并丢弃全部 test stdout/stderr/traceback，
成功不输出；失败只用固定 numeric process exit code 区分非目标 test、十个固定 subcase
或首个 subcase 的固定错误类别。它不输出 path、exception text、test content、Git
metadata 或 private data，不增加 real-host/provider/mailbox/vault capability，也不改变
正式 receipt/verifier/reconciliation 语义。获得 hosted ordinal 后必须移除 probe，并以
新的 RED 回归修复真实 seam；不得把 diagnostic commit 当作 closure evidence。

### 22.3 第五轮诊断提交前证据

- actionlint 1.7.12：passed；provenance contract、adapter 和 architecture：14 tests，
  0.645 秒，passed；`git diff --check`：passed。
- workflow probe 的原样本地 success path 使用 Git `2.55.0.windows.3` 运行前七个
  code-fixed modules：29 tests，431.5 秒，零输出、exit 0。
- 撤销 timeout 后 complete Windows Git-runner scope：7 tests，29.494 秒，passed。
- architecture/static/mechanical/provenance/repository-transaction constraints：94 tests，
  17.570 秒，passed。
- status log 已重生成且 bytes 未变化；status/maintenance/repository-leakage guards：
  51 tests，5.229 秒，passed。
- actual maintenance scan：high 0，仅有 19 个既有 low stale-doc findings；actual
  repository leakage scan：0 findings。
- full discovery 与 final-master verifier 仍按既有 placement/authorization 边界不运行。

## 23. 第六轮 ordinal transport 修复

- diagnostic commit `72ce92504815a9bc6284177078cdc4bd33a78b43` 已 push。Hosted run
  `31055337804` 的 probe 在约 1.1 秒内 fail-fast，但 GitHub-hosted PowerShell 把 Python
  的非零 native exit 提升为通用 step exit 1；正式 verifier 尚未运行。因此该 run 只证明
  首个 failure 很早且不在先前推断的 manifest 尾段，不能解释成 ordinal 1 或业务失败码。
- 本地验证把 `$PSNativeCommandUseErrorActionPreference` 设为 false、立即保存
  `$LASTEXITCODE` 后，可精确保留 Python exit 79。第六轮仅修复这条诊断 transport，并把
  probe 映射收敛为前七 modules 的 29 个固定 test ordinals 乘以八个固定错误类别：
  `10 + (ordinal - 1) * 8 + category`，范围 11--242；未知 test 固定为 250。
- probe 仍重定向并丢弃全部 test stdout/stderr/traceback；numeric exit 不包含 path、异常
  文本、测试内容或 private data。正式 verifier/receipt/reconciliation 与所有非目标边界
  不变。得到 hosted code 后仍必须移除 probe，再实施真实 RED/GREEN 修复。
- transport 修复后本地 reduced success path 零输出、exit 0；in-memory forced first-test
  failure 零输出、精确 exit 18，与公式一致。Actionlint 1.7.12 及 provenance
  contract/adapter/architecture 14 tests 均通过。

## 24. 第七轮 PowerShell-owned ordinal transport

- commit `e64bf8088fbfed68f5f55087ae0db73a6ba0caa7` 已 push。Hosted run
  `31055797629` 的 probe 仍在 Python pipeline 行被 runner 归一化为 step exit 1，正式
  verifier 未运行；因此仍未获得 test/category ordinal。
- 第七轮不再让 Python 返回非零。Python 在全部 test streams 被重定向的条件下只向被
  PowerShell command substitution 捕获的 stdout 写一个固定 integer，并始终 exit 0；
  PowerShell 要求唯一值可解析且位于 0--250，然后由 PowerShell 自身 `exit N`。成功的
  `0` 和失败 numeric code 均不直接打印，parse/interpreter failure 仍固定 exit 1。
- ordinal 公式、suite、failure semantics、正式 verifier/receipt/reconciliation 与
  real-host/private-data 边界均不变。
- PowerShell-owned transport 的本地 reduced success path 为零直接输出、exit 0；固定
  captured code 18 路径为零直接输出、精确 exit 18。Actionlint 1.7.12、provenance
  contract/adapter/architecture 14 tests、repository-leakage 11 tests 和 actual leakage
  scan 均通过。

## 25. 第八轮 argument transport 与固定 transport ordinals

- commit `ee7d3db41d5a9598a97481c08dc00809663a8f3e` 已 push。Hosted run
  `31056116923` 的 probe 仍在约 1.3 秒后返回 1；job log 无 Python traceback，正式
  verifier 未运行。该结果不能区分 interpreter failure、空/multiple captured stdout、
  parse failure 或 range failure。
- 第八轮把 Python source 从 stdin pipeline 改为单一 `python -B -c $probe` argument，
  保留 Python-success/captured-integer/PowerShell-owned-exit 设计；并把五个 transport
  failure branches 固定为 241（interpreter）、242（empty）、243（multiple）、
  244（parse）和 245（range）。所有这些值仍是 content-free numeric diagnostics。
- suite、组合 ordinal、正式 verifier/receipt/reconciliation 与所有授权边界不变。
- `python -c` transport 的本地 reduced success path 为 exit 0，captured code 18 为精确
  exit 18；actionlint 1.7.12、provenance contract/adapter/architecture 14 tests、actual
  repository leakage scan 与 `git diff --check` 均通过。

## 26. 第九轮 fixed content-free marker transport

- commit `82e370155fac376f2297fc398f2818934ecb0a6e` 已 push。Hosted run
  `31056307955` 的 Windows job 仍显示通用 exit 1；完整 job log 证明 probe 只运行约
  1.3 秒且没有 traceback，但 GitHub PowerShell wrapper 不保留任意非零 process code。
- 第九轮在 failure 时只输出一个固定 ASCII marker
  `R2_WINDOWS_NATIVE_PROBE_NNN` 后 exit 1。`NNN` 只能是既有 11--250 组合/未知码或
  241--245 transport 码；不包含 test name、path、exception、traceback、Git metadata、
  内容或 private data。成功仍零输出并继续正式 verifier。
- 这是临时、content-free、synthetic-only 的 hosted diagnostic；取得 marker 后必须移除，
  不得作为正式 receipt 或 closure evidence。其他 suite/receipt/authorization 边界不变。
- 本地固定 captured code 18 只输出 `R2_WINDOWS_NATIVE_PROBE_018` 并 exit 1；success
  code 0 零输出、exit 0。Actionlint 1.7.12、provenance contract/adapter/architecture
  14 tests、actual repository leakage scan 与 `git diff --check` 均通过。

## 27. 第十轮 allowlisted host-error ordinal

- commit `02ec6a54c2fdb0547d4a12ddac2d76ad08c913ae` 已 push。Hosted run
  `31056446767` 返回 `R2_WINDOWS_NATIVE_PROBE_015`：按固定公式精确表示前七 modules
  的 test ordinal 1 与 error category 5，即
  `R2MainPublicationWindowsTests.test_create_only_main_detects_then_repairs_preserved_dacls`
  抛出 `CutoverHostMutationError`。先前 manifest/timeout 假设正式排除。
- `CutoverHostMutationError` 自身只允许 `SAFE_ERROR_CODES`。第十轮仅在 ordinal 1 时把
  18 个既有 allowlisted codes 依固定顺序映射到 marker 201--218，无法匹配则 219；
  不输出 exception text、path 或 native error。其他 test/category 公式不变。
- 取得具体 allowlisted code 后立即移除完整 probe；该诊断仍非正式 evidence，不改变
  verifier/receipt/reconciliation 或任何 real-host/private-data 授权边界。
- 本地映射检查确认 `acl_inheritance_rejected` 精确得到 206；actionlint 1.7.12、
  provenance contract/adapter/architecture 14 tests、actual repository leakage scan 与
  `git diff --check` 均通过。

## 28. 第十一轮 identity throw-site ordinal

- commit `453777414f2d45d53805fc74b4a6f3596f36be11` 已 push。Hosted run
  `31056716749`、Windows job `92475694689` 返回
  `R2_WINDOWS_NATIVE_PROBE_205`，精确对应 ordinal 1 的既有安全错误码
  `acl_identity_changed`；ACL policy、inheritance、authorization 与 filesystem
  error code 均不匹配。
- 同一目标测试在本地 exact Python 3.12.13 连续执行 200 次，33.8 秒内 200/200
  通过。因此第十一轮仅把该安全错误码的 18 个静态 throw/caller site 映射为固定
  marker 220--237，unknown 为 240；匹配只检查受版本控制文件名和行号，不输出
  traceback、path、exception 或 native detail。
- 取得 throw site 后立即移除完整 probe，并以最小回归修复 hosted-only 身份校验
  偏差；该诊断不改变 verifier/receipt/reconciliation 或 real-host/private-data 边界。
- 本地 identity-site 映射检查、actionlint 1.7.12、provenance
  contract/adapter/architecture 15 tests、actual repository leakage scan 与
  `git diff --check` 均通过。
