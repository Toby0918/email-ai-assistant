---
last_update: 2026-08-14
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# R2 Solo Maintainer Windows publication failure task brief

## 1. 任务名称

修复 Solo Maintainer Closure 在 Windows 上保留完整 stage 却未发布最终目录的问题。

## 2. 任务类型

`fix`

## 3. 当前状态

`implemented`

## 4. 任务目标

在不削弱 create-only/no-replace、DACL、oplock、父目录身份和 real-console 门禁的
前提下，修复 Windows 最终目录提交失败。用一个真实 Windows 合成沙箱回归测试锁定
“两份 staged 文件完整但最终 target 不存在”的现场模式。

## 5. 非目标

- 不清理、删除、改名或修复现有失败 stage。
- 不运行真实 `confirm` 或 protected verifier。
- 不修改 GitHub ruleset、Issue #38、Issue #39、分支或远程状态。
- 不运行真实 cutover、migration、preflight 或 evidence publication。
- 不访问 provider、mailbox、vault、private data、凭据或密钥。
- 不放宽 exact target、create-only/no-replace 或 real-console 约束。

## 6. 背景与依据

一次人工 real-console `confirm` 使用了 fresh manifest 和 exact acknowledgement，
但返回 `R2_SOLO_MAINTAINER_CLOSURE_INVALID`。只读现场显示最终 target 不存在，
对应 stage 保留两份完整 canonical artifacts，且三者 DACL 已进入预提交锁定状态。

相关文档:

- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/operations/r2_solo_maintainer_closure_runbook.md`

## 7. 涉及范围

预计修改:

- `backend/r2_solo_maintainer_closure/storage.py`
- `tests/test_close_r2_final_master.py`
- `docs/operations/project_status_log.md`
- 本任务简报

## 8. 技术方案

1. 在 test-owned Windows 临时目录中建立可重复、可清理的 native publication 回路。
2. 对最终提交前各个 native guard 逐项单变量验证，定位失败边界。
3. 先加入可稳定失败的回归测试，再做最小实现修复。
4. 保持最终线性化点仍为最后一次稳定 parent/child/DACL/oplock 核验后紧接
   exact-target no-replace rename。

## 9. 数据结构或接口变化

- 数据库变化: 无。
- API 变化: 无。
- AI 输出 JSON 变化: 无。
- Prompt 变化: 无。
- `prepare()` / `confirm(...)` 公共接口变化: 无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱数据。
- [x] 不自动发送、删除、归档邮件。
- [x] 不接触或暴露 API key、token、凭据或私有数据。
- [x] 测试仅使用固定匿名 bytes 和 test-owned 临时目录。
- [x] 日志和测试输出保持 content-free。

## 11. Prompt Injection 防护

不适用；本任务不处理邮件正文、Prompt 或模型输出。

## 12. 验收标准

1. 新的 Windows native regression test 在修复前稳定捕获同类发布失败。
2. 修复后，合成 stage 只通过 exact-target no-replace rename 发布两份 exact 文件。
3. collision、callback failure、parent drift 和 post-linearization guard 仍 fail closed，
   并保留 stage、拒绝覆盖或清理。
4. 聚焦测试、静态/架构约束、完整 unittest、维护扫描和状态日志生成通过。
5. 真实失败 stage、GitHub 和受保护流程保持不变。

## 13. 测试计划

- `python -B -m unittest discover -s tests -p 'test_close_r2_final_master.py'`
- `python -B -m unittest discover -s tests -p 'test_r2_solo_maintainer_closure.py'`
- `python -B -m unittest discover -s tests -p 'test_r2_solo_maintainer_closure_architecture.py'`
- `python -B -m unittest discover -s tests`
- `python scripts/maintenance_scan.py`

## 14. 回滚方案

若修复不能同时保持 native no-replace 与既有 guard，停止并保留失败测试；仅撤销本任务
新增的 tracked 修改，不触碰真实失败 stage 或其他现场。

## 15. 需要人工确认的问题

无。用户已明确授权修复；任何 real-console `confirm`、protected verifier、GitHub 写入、
commit、push 或 merge 仍需单独授权。

## 16. 执行前检查

- [x] 已完整重读当前 worktree 的 `AGENTS.md`。
- [x] 已读取适用的 Matt Pocock skills、`CONTEXT.md`、ADR 0010 和相关约束。
- [x] 已明确目标、非目标和修改范围。
- [x] 已确认不会触碰真实邮箱、真实密钥、真实客户数据或保留 stage。

## 17. Issue #110 Solo Maintainer Closure checklist

- [x] 公共 seam 仍只有 parameterless `prepare()` 与 `confirm(...)`。
- [x] real-console、两次 visible input 和 half-open 300-second 门禁不变。
- [x] publication 仍为固定两文件、create-only/no-replace。
- [x] target、legacy 和任意 stage collision 仍 fail closed。
- [x] partial stage 仍保留供 incident review，不新增 cleanup/delete/repair 能力。
- [x] protected verifier、Issue #38 approval 和 Issue #39 authority 均不在范围内。
- [x] 验证只使用 synthetic/offline data，不访问 host/provider/mailbox/vault/private data。

## 18. 执行后记录

实际修改文件:

- `backend/r2_solo_maintainer_closure/storage.py`
- `tests/test_close_r2_final_master.py`
- `tests/test_r2_solo_maintainer_closure_architecture.py`
- `docs/operations/project_status_log.md`
- 本任务简报

测试结果:

- Windows native regressions: `2/2 OK`（正常发布和 parent-guard collision）。
- Closure focused: `24/24 OK`、`9/9 OK`、`19/19 OK`。
- Static/architecture/mechanical: `29/29 OK`、`50/50 OK`、`10/10 OK`。
- Full unittest: `2755/2755 OK (skipped=3)`。
- Repository leakage scan: exit `0`，无输出。
- `git diff --check`: exit `0`。
- Maintenance scan: exit `0`，仅固定的十九项 low stale-doc findings。

未完成事项:

- 未运行真实 `confirm`、protected verifier 或任何 GitHub mutation。
- 真实失败 stage 按 incident-review contract 保留，未清理或修改。

后续建议:

- 代码需通过单独授权的 commit/push/PR/merge 流程进入新的 frozen master。
- 只有新 master 的 fresh baseline 与另行授权的人类 real-console confirm 才能继续 closure。
