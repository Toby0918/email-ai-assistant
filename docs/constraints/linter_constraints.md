---
last_update: 2026-07-13
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

## 11. 对应测试文件

自定义静态检查实现文件：

```text
tests/test_static_linter_constraints.py
```

运行方式：

```bash
python -m unittest discover -s tests -p "test_static_linter_constraints.py"
```

建议在提交前同时运行：

```bash
python -m unittest discover -s tests
```

## 12. 修改规则

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
