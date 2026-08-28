---
last_update: 2026-08-28
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Issue #38 Closure Maintenance Drift Fix Task Brief

## 1. 任务名称

修复 exact-master Solo Maintainer Closure maintenance 分类漂移。

## 2. 任务类型

`fix`

## 3. 当前状态

`implemented`

## 4. 任务目标

使 `scripts/close_r2_final_master.py prepare` 在当前 frozen master 的 maintenance
扫描只包含已人工识别的低风险 stale-doc 项时能够生成审核候选，同时继续拒绝任何
未分类、重复、遗漏或高风险 finding。

## 5. 非目标

- 不伪造三份 stale 文档的复审日期或宣称其内容已更新。
- 不修改 closure confirmation、protected verifier 或 Issue #39 执行协议。
- 不读取真实邮箱、provider、vault、凭据或私有数据。
- 不执行真实 Project Container cutover。

## 6. 背景与依据

2026-08-28 在 exact master `1445aeb6adec406adb424465fcb93ec1085cfd93`
上执行 live `prepare`，固定返回
`R2_SOLO_MAINTAINER_CLOSURE_EVIDENCE_REJECTED`。只读定位证明 repository、GitHub
hosted evidence 和前 26 项本地证明通过；maintenance scan 比冻结注册表多出三项
合法的低风险 `stale_doc` finding。

相关文档:

- `AGENTS.md`
- `CONTEXT.md`
- `docs/operations/r2_solo_maintainer_closure_task_brief.md`
- `docs/operations/r2_final_operator_runbook.md`
- `docs/operations/cleanup_agent.md`

## 7. 涉及范围

- `backend/r2_solo_maintainer_closure/local_evidence.py`
- `tests/test_r2_solo_maintainer_closure.py`
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

1. 通过现有 closure public seam 的测试固定当前 22 项完整分类集合。
2. 将三份已识别 stale 文档加入封闭注册表。
3. 保留集合精确相等、唯一性和未分类 finding 的 fail-closed 检查。
4. 测试中的 22-path literal 刻意独立于 production registry，作为不会随实现自动
   漂移的规范 oracle；这不是待抽取的共享实现常量。

## 9. 数据结构或接口变化

- 数据库变化: 无。
- API 变化: 无。
- AI 输出 JSON 变化: 无。
- Prompt 变化: 无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱数据。
- [x] 不自动发送、删除或归档邮件。
- [x] 不接触或暴露 API key、token、凭据或私有数据。
- [x] 测试只使用合成数据和 content-free finding。
- [x] 不改变 provider、runtime、vault 或浏览器边界。

## 11. Prompt Injection 防护

不适用；本任务不处理邮件内容、AI 输入或回复草稿。

## 12. 验收标准

1. 当前 22 项已识别低风险 stale-doc 分类可生成 fresh maintenance proof。
2. 任意新增、遗漏或重复 finding 继续返回 evidence rejected。
3. closure 定向测试、完整测试、维护扫描和泄漏扫描通过。
4. 项目状态日志在最终代码状态下重新生成。

## 13. 测试计划

- 先修改 public closure seam 测试并确认 red。
- 最小实现后运行定向 closure 测试。
- 运行 `python -m unittest discover -s tests`。
- 运行 maintenance、leakage、architecture、mechanical 和 static guardrails。

## 14. 回滚方案

在未合并前丢弃该隔离分支；合并后通过新的 revert commit 恢复，不重写历史。

## 15. 需要人工确认的问题

无。维护者已授权连续自动执行；协议强制的本人确认仍按其固定交互门禁处理。

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md`、项目状态日志和适用 constraints。
- [x] 已明确任务目标、非目标和修改范围。
- [x] 已确认不触碰真实邮箱、真实密钥或真实客户数据。
- [x] 已确认 public test seam 为 closure `prepare` 的 fresh maintenance proof。

## 17. Issue #110 Solo Maintainer Closure / Execution Confirmation checklist

- [x] `backend.r2_solo_maintainer_closure` 仍恰好包含十个文件，公开 seam 仍只有
  parameterless `prepare()` 和 `confirm(...)`。
- [x] Closure 仍绑定恰好五个 hosted check records 和一个 GitHub guardrail snapshot；
  frozen master、GitHub Actions app、checks、ruleset、bypass 和 classic protection 漂移均 fail closed。
- [x] Guardrail observation 仍只使用 code-fixed Windows GitHub CLI、固定 keyring identity
  和三个 authenticated GET；没有 caller URL、credential、method、fallback 或 cache。
- [x] Python 不读取或输出 GitHub token；ambient token、host、repository、config 和 proxy override
  仍不进入 child environment。
- [x] `required_reviewers` wire field 仍只接受 absent 或 exact `[]`。
- [x] `require_extra_approval_for_unattributed_changes` 仍只接受 absent 或 exact Boolean
  `true`，且 approving review count 必须是 exact integer zero。
- [x] Closure 仍保留十四个 gates、八个 ordered gap proofs 和全部 zero-count 安全边界。
- [x] Fresh maintenance evidence 现在要求恰好 22 个已审查 low-risk classification；
  missing、duplicate 或 additional classification 继续 fail closed。
- [x] `confirm()` 的 stable real Windows console、two once-only inputs 和 half-open
  300-second wall-plus-monotonic freshness 不变。
- [x] Publication 仍是 create-only/no-replace；不 repair、overwrite、delete 或 cleanup，
  partial stage 仍保留供 incident review。
- [x] Protected verifier 仍独立重算 Git/canonical evidence，只接受 manifest 和 Solo
  Maintainer Attestation，并拒绝 legacy V1 artifacts。
- [x] `ApprovedCutoverBindingV3`、one operator、zero independent reviewers、zero external
  signers 和 no signature authority input 均不变。
- [x] Execution Confirmation 的 binding、journal、transition、claim/attempt consumption 不变。
- [x] Restart historical reconstruction 不产生 fresh authority。
- [x] Production roots 在读取 argv/TTY/clocks/artifacts/Adapters 前仍返回
  `DORMANT_NO_ISSUE39_APPROVAL`。
- [x] Closure 与 Execution Confirmation 仍具有 zero Issue #38 approval 和 zero Issue #39
  authority/execution。
- [x] 验证仅使用 synthetic/offline 数据；不访问或修改 real host、provider、mailbox、vault、
  private data、signer 或 cleanup surface。

## 18. 其余专项清单

远程 provider、管理员评估、corpus handoff 和 Project Container host contract 均不变，
相关专项清单不适用。

## 19. 执行后记录

实际修改文件:

- closure maintenance registry 与 public-seam 测试。
- architecture/tooling/mechanical constraints、Issue #110 模板、closure runbook 和对应约束测试。
- 本任务简报和重新生成的项目状态日志。

测试结果:

- Red: 新 public `prepare` seam 测试在 19-entry registry 上返回
  `R2_SOLO_MAINTAINER_CLOSURE_EVIDENCE_REJECTED`。
- Green: closure 定向测试 41 项通过。
- 完整测试两轮均为 `Ran 2849 tests`、`OK (skipped=4)`。
- architecture 50、static 29、mechanical 10、maintenance 和 leakage 均通过。

未完成事项:

- 提交后的 PR、CI、exact-master closure 和 Issue #39 迁移尚待后续治理步骤。

后续建议:

- 合并后在新的 LF exact-master 审核工作树重新运行 closure prepare。
