---
last_update: 2026-07-15
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Static Linter Constraints

本文件定义项目的自定义静态检查规则。  
它的目的不是替代单元测试，而是把容易被 Agent 忽略的工程边界变成可执行检查。

本项目当前不引入额外 lint 依赖。第一阶段使用 Python 标准库 `unittest`、`ast`、`re` 实现静态检查。

## 1. 目标

静态检查必须覆盖以下风险：

- 后端业务代码使用裸 `print()`。
- 后端业务代码使用 `traceback.print_exc()`。
- 出现裸 `except:`。
- 前端出现 OpenAI/DeepSeek API key、DeepSeek/OpenAI 直接调用、Ollama/Qwen/Gemma 直接调用、本地模型端点或 `.env` 访问。
- 前端出现自动发送、删除、归档、移动、转发或回复邮件的高风险调用。
- 项目中出现疑似真实密钥、token 或数据库文件。
- `docs/` 下 Markdown 文件缺少 YAML front matter。
- 架构边界被破坏，例如 `email_cleaner.py` 调用 OpenAI 或数据库。
- 管理员 mailbox ingest 出现任意 IMAP passthrough、write/flag-mutation command、SMTP、非 PEEK body fetch，或被浏览器/正常 runtime 引用。

## 2. Linter 报错格式

每一条自定义 linter 报错都必须尽量包含三类信息：

```text
❌ 什么错：说明具体违反了哪条规则。
✅ 怎么改：给出最小修复方式。
📖 去哪里看：指向对应 docs 文件。
```

示例：

```text
❌ 什么错：backend/email_agent/analyzer.py 使用了裸 print() 输出业务日志。
✅ 怎么改：改用 logging.getLogger(__name__)，并避免输出真实邮件正文。
📖 去哪里看：docs/conventions/logging.md
```

该格式的作用是把 linter 错误变成 Agent 可执行的修复提示。  
Agent 看到报错后，应按提示修复，而不是绕过测试或删除规则。

## 3. 禁止裸 print()

业务代码中禁止使用裸 `print()` 作为日志。  
应使用 Python 标准库 `logging`。

禁止：

```python
print("analysis result", result)
```

允许：

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Email analysis completed for email_id=%s", email_id)
```

注意：日志中不得输出真实邮件正文、API key、OAuth token、邮箱凭据、真实报价、未脱敏客户信息。

参考：

```text
docs/conventions/logging.md
```

## 4. 禁止 traceback.print_exc()

业务代码中禁止使用 `traceback.print_exc()`。  
异常必须通过 logger 记录，并保留上下文。

禁止：

```python
import traceback

try:
    run()
except Exception:
    traceback.print_exc()
```

允许：

```python
try:
    run()
except Exception:
    logger.exception("Failed to analyze email_id=%s", email_id)
    raise
```

## 5. 禁止裸 except

禁止：

```python
try:
    run()
except:
    pass
```

允许：

```python
try:
    run()
except ValueError as exc:
    logger.warning("Invalid AI response: %s", exc)
    raise
```

## 6. 前端禁止云端/本地模型 provider 直接调用

前端不得出现以下内容：

```text
OPENAI_API_KEY
DEEPSEEK_API_KEY
sk-
api.openai.com
api.deepseek.com
/v1/responses
/v1/chat/completions
new OpenAI(...)
require("openai")
from "openai"
require("deepseek")
from "deepseek"
127.0.0.1:11434
localhost:11434
/api/generate
/api/chat
ollama
qwen3.6
gemma4
process.env
.env
```

OpenAI/DeepSeek API key 和本地 Ollama/Qwen/Gemma 配置只能存在后端环境变量中，由后端 `llm_client.py` 使用。前端禁止引入 OpenAI 或 third-party DeepSeek SDK，也禁止配置或调用任何远程模型端点。

## 7. 前端禁止高风险邮箱动作

第一阶段前端不得出现自动发送、删除、归档邮件动作。

禁止高风险关键词包括：

```text
sendMail
gmail.users.messages.send
archiveMessage
deleteMessage
trashMessage
messages.trash
messages.modify
moveMessage
forwardMessage
```

如果未来确实要加入这些能力，必须先更新：

```text
AGENTS.md
docs/product/feature_scope.md
docs/security/email_data_handling.md
docs/constraints/architecture_constraints.md
docs/constraints/linter_constraints.md
tests/
```

并且必须经过人工确认。

## 8. 密钥和敏感文件检查

项目中不得提交：

```text
.env
*.db
*.sqlite
*.sqlite3
*.token
*.secret
```

文本文件中不得出现疑似密钥：

```text
sk-...
ya29....
password = "..."
```

如需测试，应使用明显的假值：

```text
OPENAI_API_KEY=your_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

## 9. 依赖精确版本冲突检查

`requirements.txt` 中同一个规范化包名不得同时出现不同的 `==` 版本。包名比较忽略大小写，并将 `-`、`_`和 `.` 视为等价分隔符。重复的相同版本可以解析，但任何冲突版本都必须使静态约束失败。

可执行实现位于 `scripts/repo_utils.py` 的 `parse_pinned_dependency_versions()`，并由 `tests/test_repo_utils.py` 的合成冲突用例和 `tests/test_static_linter_constraints.py` 的真实 `requirements.txt` 检查共同覆盖。

## 10. 文档元信息检查

`docs/` 下所有 Markdown 文件必须包含 YAML front matter：

```yaml
---
last_update: 2026-06-29
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---
```

## 11. Authorized mailbox transport policy

静态约束必须把 isolated mailbox import 视为一个窄 allowlist，而不是一般邮箱
SDK。Endpoint 固定为 `imap.exmail.qq.com:993`，且 there is no arbitrary IMAP command passthrough。唯一允许 import `backend.mailbox_ingest` 的外部文件是
`scripts/manage_mailbox_vault.py`；frontend、backend/email_agent、其他 scripts、
server、cleanup 和 scheduled workflow 都不得引用该 package。

允许的 transport token：

```text
`LIST`
`EXAMINE`
`UID SEARCH`
`UID FETCH`
`BODY.PEEK`
```

禁止的 transport token/operation：

```text
`STORE`
`APPEND`
`COPY`
`MOVE`
`EXPUNGE`
`CREATE`
`DELETE`
`RENAME`
`SUBSCRIBE`
`UNSUBSCRIBE`
`SMTP`
`BODY[]`
```

Mechanical test 必须拒绝 `smtplib`、SMTP client/send method、non-PEEK
`BODY[]` 和 wrapper public interface 中不在 allowlist 的 method。它还必须证明
浏览器 manifest 仍只有 `activeTab`/`sidePanel` 和既有两个 host permission，
不得新增 mailbox/OAuth/background-enumeration permission。

Windows DPAPI/BitLocker module 必须 lazy-load behind injected probes；静态和
import tests 不得在 CI collection 时探测 host。Recovery rewrap code/documentation
不得声称 cross-volume atomicity。

## 12. 对应测试文件

自定义静态检查实现文件：

```text
tests/test_static_linter_constraints.py
tests/test_architecture_constraints.py
tests/test_mailbox_transport_constraints.py
```

运行方式：

```bash
python -m unittest discover -s tests -p "test_static_linter_constraints.py"
```

建议在提交前同时运行：

```bash
python -m unittest discover -s tests
```

## 13. Private context mechanical guards

Executable constraints must enforce all of the following:

- only `private_context_gate.py` may import Task 4 deidentification/residual-pattern modules from `backend.private_knowledge`;
- only `private_knowledge_context.py` may import `backend.private_knowledge.runtime_schema`;
- no frontend source or browser renderer may reference `runtime_cards`, `private_context`, `placeholder_mapping`, `card_id`, `snapshot_id`, `vault_id`, or a deidentification placeholder;
- no public API or SQLite result may gain private context or knowledge-card fields;
- DeepSeek provider output containing a placeholder, restoration/re-identification instruction, or private metadata marker is rejected before either parser runs;
- `backend.exact_fact_patterns` is the canonical exact-fact recognizer for
  outbound deidentification, provider-output rejection, and grounding; all three
  boundaries must import it and parity tests must cover compact identifiers,
  `: # - / _ . = ( )` plus `number`/`no.`/`ID`/`ref.`/`reference` separated
  forms, supported numeric/Chinese/month-name calendar-date forms (including
  dotted abbreviations and `日`/`号`), and safe punctuated or bare
  count/section phrases;
- logs and exceptions remain content-free; the diagnostic field shape remains frozen,
  general privacy refusal uses `safety_rejected_all` / `safety` / `not_applicable`,
  and only placeholder echo may use the fixed
  `provider_output_placeholder_echo` / `safety` / `not_applicable` tuple;
- exact budget constants are 13/10/8/5/2 seconds and the frontend analysis POST wait is 15 seconds.

These guards belong in `tests/test_architecture_constraints.py`, the frontend static suites, and the public response/persistence canaries. They must run with synthetic data and no network.

### Private evaluation mechanical guards

Executable checks must enforce that `backend/private_evaluation/` cannot import
mailbox ingest, raw-vault/private-knowledge stores, SQLite, OpenAI SDK, IMAP, SMTP,
or frontend code. Normal runtime and frontend files cannot reference that package;
only `scripts/manage_mailbox_vault.py` and `scripts/evaluate_private_deepseek.py`
are allowlisted bridges. The mailbox CLI may import only the evaluation
`staging`, `staging_contract`, and `staging_repository` modules for local
`stage-evaluation`; it must not import the runner, provider, final-dataset reader,
metrics, reporting, or selection path.

Mechanical checks must keep `stage-evaluation` outside `NETWORK_COMMANDS`, require
exactly 200 unique reviewed record/case bindings, one record at a time cleanup,
hidden interactive base64 key input with no mailbox app password, and exact
`.pkevalstage` suffix. `scope_fingerprint` and `inventory_fingerprint` are separate
required fields; the evaluation-only source validates the latter before plaintext
release, performs no evidence accumulation, and retains no raw-derived identifier
between records. The real writer/validator test must prove post-replacement checks
exclude only the exact target while sibling and descendant stores remain rejected.
The stage frame has distinct magic, purpose, and namespace from `.pkeval`; public
success is only `evaluation_stage_complete` with 200/0 counts, parse/local failure
is only `argument_invalid`, and repr/errors/output contain no IDs, paths, text,
matches, keys, or exception detail.

Import checks must canonicalize every relative `ImportFrom.level` against the
containing package and apply a positive import allowlist to all modules, not only
`backend.*` names. Unlisted standard-library/network modules such as `ftplib` and
relative escapes into mailbox ingest must fail.

The evaluation CLI must expose only the frozen `verify` and `run` surfaces. It
must not accept model, endpoint, key, key-file, prompt, case-count, threshold,
retry, stream, batch, force, or production-switch overrides. Provider construction
must remain a lazy function reached only after local validation, exact confirmation,
provider configuration, and human-judge availability checks. Static and unit tests
must run offline with the provider disabled.

The aggregate serializer must reject unknown keys/codes, boolean counts, non-finite
numbers, arbitrary strings, and nested sample-like fields. Errors, repr, stdout,
stderr, test output, and maintenance output must remain content-free.

## 14. 修改规则

如果新增或修改 linter 规则，必须同步更新：

```text
docs/constraints/linter_constraints.md
docs/conventions/logging.md
tests/test_static_linter_constraints.py
```

如果 linter 规则会影响架构边界，还必须同步更新：

```text
docs/constraints/architecture_constraints.md
```
