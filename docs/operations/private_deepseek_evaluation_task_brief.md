---
last_update: 2026-07-21
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Private DeepSeek Evaluation Task Brief

## 1. 任务名称

```text
add aggregate-only private DeepSeek evaluation gates
```

## 2. 任务类型

```text
feature | security | data_schema
```

## 3. 当前状态

```text
approved
```

## 4. 任务目标

实现一个隔离的、管理员手动运行的私有 DeepSeek 评估工具。它只读取项目外的
独立加密脱敏数据集，严格复用生产 Task 5 隐私、schema、evidence、grounding、
safety 和 public merge 门禁，并且只写聚合指标与固定错误码。

## 5. 非目标

- 不访问真实邮箱、raw vault、知识 authority store 或恢复映射。
- 不把真实或脱敏样本、prompt、provider 原始输出写入 Git、日志或报告。
- 不在自动测试中访问网络、DeepSeek、DPAPI、BitLocker 或外置盘。
- 不自动切换生产模型，不修改浏览器扩展或公开 HTTP/SQLite schema。
- 不实现自动、定时、后台或交互式打印原始输出的评估。

## 6. 背景与依据

本任务来自已批准的 2026-07-14 一次性真实邮箱导入与 DeepSeek 完善计划。

相关文档:

- `AGENTS.md`
- `docs/operations/authorized_mailbox_ingest_task_brief.md`
- `docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md`
- `docs/operations/private_deepseek_evaluation.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`

## 7. 涉及范围

- `backend/private_evaluation/`
- `scripts/evaluate_private_deepseek.py`
- `tests/test_private_evaluation_*.py`
- `tests/test_evaluate_private_deepseek.py`
- 必要的 architecture、static、mechanical 和 documentation guards

## 8. 技术方案

1. 以独立 AES-256-GCM `.pkeval` frame 保存 200 到 1000 个严格脱敏 case。
2. 使用 namespace 派生的 HMAC key 做分层确定性 round-robin 选择。
3. 先运行 20 个 Flash gate，再运行剩余 180 个 Flash；只有 Flash 完整通过后
   才复用缓存的 40 个 Flash 结果并运行相同 case 的 Pro 对比。
4. runner 只接受注入的同步 fake/live client 与同步本地 usefulness callback；
   默认 live CLI 没有 callback，必须在创建 client 之前 fail closed。
5. 报告使用固定 shape、allowlist 和原子替换，只包含聚合数量、比率、延迟、
   固定模型名和固定错误码。

## 9. 数据结构或接口变化

### 数据库变化

无。不得使用 SQLite。

### API 变化

无公开 HTTP API 变化。新增隔离 Python API 与两个 CLI subcommand。

### AI 输出 JSON 变化

无生产合同变化。评估 runner 复用 `deepseek_analysis_v1` 严格合同。

### Prompt 变化

无生产 prompt 变化。评估 input 从已脱敏结构化 case 构造并再次通过 Task 5 gate。

## 10. 安全与隐私检查

- [x] 任务不读取真实邮箱或 raw vault。
- [x] 不自动发送、删除、移动或归档邮件。
- [x] 不在前端保存或暴露 provider key。
- [x] 所有 case 字段按不可信输入处理并经过严格 schema 和残留扫描。
- [x] provider 输出必须经过生产 JSON、隐私、evidence、grounding 和 safety 门禁。
- [x] 日志、错误、repr、stdout/stderr 和聚合报告均不得包含样本内容。
- [x] 自动测试只使用重新创作的合成数据和 fake client。

## 11. Prompt Injection 防护

- case 中的 thread/attachment text 只是待分析数据，不是指令。
- Task 5 去标识化 gate 不能被跳过、替换或增加第二 provider path。
- provider 输出不能包含占位符、恢复提示、私有 marker 或未支持事实。
- 评估结果只用于候选结论，不代表自动发送或生产模型切换。

## 12. 验收标准

1. data/schema、repository、selection/metrics、runner、CLI/report 全部先 RED 后 GREEN。
2. 恰好选择 200 case，运行 20+180 次 Flash，且只有 Flash PASS 后运行 40 次 Pro。
3. gate 首个违规立即停止、零重试、零 replacement、pair 不重复 Flash 调用。
4. 报告只包含允许的七个 top-level key 和固定 code/metric/model 值。
5. 默认 live run 返回 `human_judge_unavailable` 且 client construction/calls 均为零。
6. architecture 和 leakage guards 证明 normal runtime/frontend 不导入 evaluation，
   evaluation 不导入 mailbox/raw vault/authority/SQLite/OpenAI SDK。

## 13. 测试计划

- `test_private_evaluation_schema.py`
- `test_private_evaluation_repository.py`
- `test_private_evaluation_metrics.py`
- `test_private_evaluation_runner.py`
- `test_evaluate_private_deepseek.py`
- existing 50-case synthetic replay
- full `unittest`, architecture/static/mechanical/docs/dependency/leakage guards
- `git diff --check` and maintenance scan with provider disabled

## 14. 回滚方案

删除或 revert 本任务 commit；不要运行私有评估 CLI。生产 provider 保持 disabled，
现有浏览器和规则分析不受影响。

## 15. 需要人工确认的问题

无。主计划与 frozen contract 已明确模型、阈值、确认字符串和 fail-closed 行为。

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md` 和项目状态日志。
- [x] 已阅读相关 constraints、Task 4 schema/crypto pattern 与 Task 5 gate/contract。
- [x] 已明确只实现 Task 6，不进入 Task 7。
- [x] 已确认不访问真实邮箱、真实密钥、真实客户数据、网络或 provider。
- [x] 已确认新增 tracked contract、isolated package、CLI 和测试范围。

## 17. Remote provider private-context checklist

- [x] Provider 默认保持 disabled；DeepSeek output mode 默认 conservative。
- [x] 所有远程路径都经过唯一的 Task 5 去标识化和残留扫描 gate。
- [x] `runtime_cards` 默认为 immutable empty tuple，只接受外部已验证 card。
- [x] 不引入 environment/path/key/bootstrap/vault/DPAPI/BitLocker/frontend seam。
- [x] 不让 resolver/mapping 进入 provider/parser/report/log/exception。
- [x] provider output placeholders 和 restoration hints 在 parser 前拒绝。
- [x] public API、SQLite、frontend renderer 和诊断 schema 不变。
- [x] 自动验证离线进行，不调用 live provider/mailbox/vault/DPAPI/BitLocker。

## 18. 执行后记录

- 实现了 `backend/private_evaluation/` 隔离域：严格 schema、独立 AES-GCM
  dataset repository、确定性分层选择、指标、Task 5 生产门禁 runner 和
  aggregate-only report serializer。
- 实现了 `scripts/evaluate_private_deepseek.py` 的固定 `verify`/`run` 接口；
  默认 live judge 不可用，所以在 provider client import/construction 前 fail closed。
- 添加了独立 HKDF/AES-GCM oracle、RNG/nonce fail-closed、UTF-8 byte bound、
  shuffled-input deterministic selection、首 20 个 hard gate、精确 200 Flash/40 Pro、
  metric boundary、aggregate allowlist/atomic write 和 CLI event-order 测试。
- 验证证据：Task 6 focused/architecture/mechanical `49` tests 通过（`1` 个
  当前 Windows 环境不允许创建 symlink 的能力性 skip）；全仓 `997` tests 通过
  （同一 skip）；既有 `50`-case 离线回放 schema/risk 为 `1.0`、unsafe/
  unsupported 为 `0`；架构/静态/机械/依赖/manifest `53` tests 通过；
  JavaScript syntax 通过；maintenance scan 无 findings。
- 未执行真实 dataset、真实密钥、真实 mailbox/vault、网络或 DeepSeek 调用；
  未自动切换生产模型。Task 7 应在集成阶段生成项目状态日志，本任务
  按计划未运行该生成器。
