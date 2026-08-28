---
last_update: 2026-08-28
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Issue #38 Protected Verifier Windows Mode Identity Fix Task Brief

## 1. 任务名称

修复 exact-master protected verifier 在 Windows 上误判稳定普通文件身份漂移。

## 2. 任务类型

`fix`

## 3. 当前状态

`implemented`

## 4. 任务目标

使 `scripts/verify_r2_final_master_closure.py` 在 Windows 对同一稳定普通文件的
path metadata 与 open-handle metadata 进行身份比较时，忽略 Windows Python 合成的
权限位差异，同时继续核对对象类型、device、inode/file index、大小、完整 bytes、
reparse/symlink/junction 和 Git tree mode 约束。

## 5. 非目标

- 不放宽 tracked/untracked、hidden index、raw Git blob、safe path 或 exact-master 门禁。
- 不修改 closure `prepare`/`confirm`、Issue #39 execution confirmation 或迁移协议。
- 不修改正式 closure artifact、Issue、ruleset 或真实 Project Container 状态。
- 不读取真实邮箱、provider、vault、凭据或私有数据。

## 6. 背景与依据

在 clean、detached、exact master `fab06503d278430930e2b74e925f770cbbff6cb2`
审核工作树运行无参数 protected verifier，固定返回
`R2_SOLO_MAINTAINER_CLOSURE_INVALID`。逐层只读反馈循环把首个失败定位到
`restart_local_service.cmd`：文件 bytes 与 Git blob 完全一致，device、inode/file
index 和 size 稳定，但 `os.lstat()` 报告 mode `0o100777`，同一打开句柄的
`os.fstat()` 报告 `0o100666`。现实现把完整 `st_mode` 纳入身份元组，因此误判漂移。

相关文档：

- `AGENTS.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`
- `docs/operations/r2_solo_maintainer_closure_runbook.md`

## 7. 涉及范围

- `scripts/verify_r2_final_master_closure.py`
- `tests/test_close_r2_final_master.py`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`
- `docs/templates/agent_task_brief_template.md`
- `docs/operations/r2_solo_maintainer_closure_runbook.md`
- `tests/test_architecture_constraints.py`
- `tests/test_mechanical_rule_constraints.py`
- `docs/operations/project_status_log.md`
- 本任务简报

## 8. 技术方案

1. 先在真实 Windows path/open-handle 边界加入回归测试并确认 red。
2. 仅在 Windows 将身份元组中的 mode 归一化为 `stat.S_IFMT(st_mode)`；POSIX 继续
   使用完整 mode。
3. 保留现有普通文件类型检查、safe component metadata、前后 identity、完整 bytes
   和非 Windows executable-bit 检查。
4. 通过定向测试、完整测试和机械/架构/静态/维护/泄漏护栏验证。

## 9. 数据结构或接口变化

- 数据库变化：无。
- API 变化：无。
- AI 输出 JSON 变化：无。
- Prompt 变化：无。
- CLI 变化：无；无参数 protected verifier 的成功/失败契约保持不变。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱数据。
- [x] 不自动发送、删除或归档邮件。
- [x] 不接触或暴露 API key、token、凭据或私有数据。
- [x] 不弱化 reparse、link、类型、大小或 byte-identity 检查。
- [x] 不改变 provider、runtime、vault、浏览器或真实迁移边界。

## 11. Prompt Injection 防护

不适用；本任务不处理邮件内容、AI 输入或回复草稿。

## 12. 验收标准

1. Windows 稳定普通文件即使 path/handle 合成权限位不同也通过 identity 检查。
2. Windows 对象类型、device、inode/file index、大小或 bytes 漂移仍 fail closed。
3. 非 Windows 完整 mode 与 Git executable-bit 语义保持不变。
4. 定向测试、完整测试、维护扫描、泄漏扫描和约束护栏通过。
5. 项目状态日志在最终代码状态下重新生成。

## 13. 测试计划

- Red：运行 Windows path/open-handle 真实边界回归测试。
- Green：应用最小 identity 归一化后重跑定向测试。
- 运行 `python -m unittest tests.test_close_r2_final_master`。
- 运行 `python -m unittest discover -s tests`。
- 运行 architecture、mechanical、static、maintenance 和 leakage guardrails。
- 合并后在新的 clean exact-master LF 审核工作树运行真实无参数 verifier。

## 14. 回滚方案

未合并前丢弃隔离分支；合并后以新的 revert commit 恢复，不重写历史，不修改或
删除已有 closure/incident artifacts。

## 15. 需要人工确认的问题

无。维护者已授权连续自动执行；协议强制的真实 TTY 确认仍必须由维护者本人完成。

## 16. 执行前检查

- [x] 已阅读当前 `AGENTS.md`、项目状态日志和适用 constraints。
- [x] 已完整读取 `ask-matt`、`diagnosing-bugs` 与 `tdd` skill。
- [x] 已建立可重复的最小反馈循环并定位到 path/open-handle mode 差异。
- [x] 已确认不触碰真实邮箱、真实密钥、真实客户数据或真实迁移。

## 17. Issue #110 Solo Maintainer Closure / Execution Confirmation checklist

- [x] Closure public seam、十四个 gates、八个 gap proofs 和固定 GitHub GET 证据不变。
- [x] Protected verifier 仍固定无参数、isolated mode、exact repository、exact master。
- [x] Raw Git blob、clean tracked/untracked/hidden-index 和 safe Windows path 检查不变。
- [x] Windows 仅忽略 path/handle 间无身份意义的合成 permission bits；对象类型仍比较。
- [x] Closure 与 Execution Confirmation 仍为 zero Issue #39 authority/execution。
- [x] 验证不访问或修改 real host、provider、mailbox、vault、private data 或 signer。

## 18. 其余专项清单

远程 provider、管理员评估、corpus handoff 和 Project Container host contract 均不变，
相关专项清单不适用。

## 19. 执行后记录

实际修改：

- protected verifier 仅在 Windows 将 identity mode 归一化为文件类型位。
- 增加真实 path/open-handle mode 差异回归测试及文档机械守卫。
- 同步 architecture/tooling/mechanical constraints、runbook 和任务模板。

当前验证：

- Red：回归测试在旧实现上因 `_read_exact_tracked_file` 抛出 `ValueError`。
- Green：聚焦回归 1 项和 closure CLI 模块 20 项通过。
- architecture、mechanical、static 三组共 89 项通过。
- maintenance scan 与 repository leakage scan 直接通过。
- 第一轮全量运行 `Ran 2850 tests`，唯一失败为 Windows spawn 子进程
  `Bad file descriptor` 后 hanging-worker terminate 计数未发生；该用例随后单独
  连续 6 次通过。
- 第二轮全量运行 `Ran 2850 tests`，唯一错误为运行约 66 分钟后 maintenance scan
  子进程超过固定 10 秒；该用例随后 2.784 秒通过，直接 scan 2.822 秒通过。
- 因两轮全套未在同一次进程中全绿，本地完整套件状态如实保留为有环境时序缺陷；
  发布仍必须由五项独立 CI 全部成功门禁。

待完成：

- 双轴 code review、PR 和五项 CI。
- 合并后在新 exact-master LF 工作树运行真实无参数 protected verifier。
