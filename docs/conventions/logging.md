---
last_update: 2026-07-15
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Logging Convention

本文件定义项目日志规范。  
日志用于排查系统问题，不用于保存邮件正文、客户信息或密钥。

## 1. 基本规则

后端业务代码必须使用 Python 标准库 `logging`。

禁止：

```python
print("debug info")
traceback.print_exc()
```

允许：

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Email analysis completed for email_id=%s", email_id)
```

## 2. 日志中禁止出现的内容

日志中不得输出：

```text
真实邮件正文
OpenAI API key
OAuth token
邮箱密码
真实客户报价
未脱敏合同
未脱敏客户资料
完整邮箱账号凭据
```

## 3. 推荐日志级别

```text
DEBUG: 本地开发时的低风险调试信息，不包含邮件正文和密钥。
INFO: 关键流程完成，例如分析完成、导出完成。
WARNING: 可恢复问题，例如 AI JSON 首次解析失败。
ERROR: 任务失败，但系统仍可继续运行。
EXCEPTION: 捕获异常并需要记录堆栈时使用 logger.exception。
```

## 4. 异常处理方式

推荐：

```python
try:
    result = analyze_email(email)
except ValueError as exc:
    logger.warning("Invalid email analysis input: %s", exc)
    raise
except Exception:
    logger.exception("Unexpected failure while analyzing email_id=%s", email_id)
    raise
```

禁止：

```python
try:
    result = analyze_email(email)
except:
    pass
```

禁止：

```python
try:
    result = analyze_email(email)
except Exception:
    traceback.print_exc()
```

## 5. 邮件相关日志

允许记录：

```text
email_id
分析是否成功
处理耗时
错误类型
模块名称
```

谨慎记录：

```text
subject
sender domain
category
priority
```

禁止记录：

```text
完整正文
完整邮件线程
附件全文
客户真实报价
API key
token
```

## 6. Agent 修复原则

如果静态检查提示日志违规，Agent 应按以下顺序修复：

```text
1. 删除裸 print()。
2. 引入 logging.getLogger(__name__)。
3. 使用 logger.info / logger.warning / logger.exception。
4. 确认日志不包含真实正文、密钥或敏感业务数据。
5. 重新运行 tests/test_static_linter_constraints.py。
```

## 7. Model fallback diagnostic contract

`scripts/run_local_debug.py` 在启动本地服务前为 `backend.email_agent.analysis_diagnostics` 配置 operator-only dedicated diagnostic sink。活动文件固定为 `outputs/local_debug_service.log`；标准库 rotating handler 在 `1 MB`（`1_000_000` bytes）时轮转，并最多保留 `two backups`。不得把活动日志或备份提交到版本库。

该 file handler is never attached to the root logger。diagnostic logger 使用 `propagate=False`，logger 和 handler 都有独立于一般服务 level 的 fixed `WARNING` threshold。重复配置会移除并关闭旧 diagnostic handler，最终只保留一个 writer；file mode 只使用一个 UTF-8 rotating handler，no-file mode 只使用一个受同样过滤的 diagnostic stream handler。

Rule fallback remains a successful public analysis response. 每个结束于规则兜底的模型尝试只写 `exactly one terminal allowlisted event`：

```text
event=analysis_fallback code=<allowlisted code> stage=<allowlisted stage> provider=<allowlisted provider> model=<allowlisted model> output_mode=<allowlisted mode> detail=<allowlisted detail> elapsed_ms=<non-negative integer>
```

`detail` allowlist 固定为:

```text
not_applicable
json_syntax
top_level_shape
schema_version
analysis_shape
attachment_shape
field_evidence_shape
```

每个非 envelope fallback 都使用 `not_applicable`。这是 operator-only 日志字段，不会添加到 `public API` 或 `SQLite`。不得包含 provider output、JSON keys、paths、values 或 exception text，也不得用于重建这些内容。未知 detail、字符串子类和与 reason code 不匹配的 envelope detail 都 fail closed to `not_applicable`。

初始 allowlisted reason codes 为:

```text
provider_not_enabled
budget_exhausted
missing_key
unsupported_model
provider_timeout
provider_auth
provider_permission_or_balance
provider_rate_limit
provider_connection_error
provider_server_error
provider_http_error
provider_request_failed
response_incomplete
response_empty
envelope_invalid
evidence_invalid
provider_output_placeholder_echo
safety_rejected_all
public_schema_invalid
public_language_invalid
unexpected_analysis_error
```

`provider_output_placeholder_echo` 只表示 provider 输出在业务 parser 前回显了去标识占位符；固定映射为 `stage=safety`、`detail=not_applicable`，不得记录实际 token 或 provider output。其他 provider 输出安全拒绝继续使用 `safety_rejected_all`。

诊断是本地运行信息，不得进入 `public API`、`SQLite` 或 `frontend`。日志函数只接收上面的固定枚举、allowlisted detail 和非负耗时，不能接收请求、邮件、线程、附件、Prompt、provider response、异常对象、URL、路径或客户字段。

Writing handler 只接受 exact fallback-event template 和 exact built-in allowlisted arguments；它拒绝 OpenAI, HTTPX, HTTP core、任意 backend/application logger、child logger、direct free-form diagnostic record、非 WARNING record、字符串子类、`bool`、exception 和 stack information。因此一般服务 level 配置为 DEBUG, INFO, WARNING, ERROR, CRITICAL, or an invalid level 时，每个真实 fallback 仍恰好写一条 canonical event；accepted model output 写零条 fallback event。

Logs must not contain API keys, prompts, email or thread content, attachment names or content, provider output, raw exception text, tracebacks, URLs, paths, or customer identifiers.

预期的 provider/validation fallback 路径不得使用 `logger.exception`，不得插值 `raw exception`，也不得设置 `exc_info=True`。自动测试仅使用合成对象并拦截 provider client；Automated verification does not call DeepSeek.
