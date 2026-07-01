---
last_update: 2026-06-29
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
