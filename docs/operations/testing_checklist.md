---
last_update: 2026-07-11
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 测试检查清单

## 必测场景

- 普通客户询盘。
- 空正文邮件。
- HTML 邮件正文。
- 含引用历史的邮件。
- 含付款、合同或交期风险的邮件。
- 含 prompt injection 文本的邮件。
- AI 返回不可解析 JSON。
- 后端服务不可用。
- Cleanup Agent 只读扫描报告生成。
- 项目状态日志可以生成并反映当前阶段。
- 后端最小骨架不违反架构依赖方向。
- 脱敏 golden 样例集覆盖主要邮件类型。
- 本地规则分析器输出与 golden 样例预期保持一致。
- `start` 在启动进程前恰好清理一次过期附件，且新鲜附件保留。
- `restart` 在 stop/start 序列前恰好清理一次，不通过嵌套 `start` 重复清理。
- 附件清理失败返回通用可操作错误，不停止或启动服务，也不暴露文件名、内容、私有 URL、cookie、token、OCR 文本或私有路径。
- `status` 和 `/api/health` 不读取或显示附件内容。

## Tencent Exmail extension checks

- Click the extension icon and verify the side panel remains open after clicking or scrolling inside Tencent Exmail.
- Open one Tencent Exmail message and click `Analyze current email`.
- Verify one current-email payload is sent after the click.
- Verify message-scoped selected-text fallback works only for user-selected email content in the currently opened Tencent Exmail message.
- Verify local backend unavailable state is readable.
- Verify the extension does not send, delete, archive, move, or reply to mail.
- Confirm unpacked extension version `0.2.2`, and click `Reload` after updating its files.
- Verify only image, PDF, XLSX, and DOCX resources visibly associated with the opened message are eligible after the click.
- Verify the configured bounds: 5 files, 10 MiB per file, and 25 MiB total.
- If Tesseract is unavailable, verify image OCR degrades to metadata-only while email-body/rule analysis continues.

## 安全检查

- 前端没有 API key。
- `.env` 未被提交。
- 日志不包含真实邮件和密钥。
- 回复草稿不会自动发送。
- 用户未点击按钮时不会触发分析。
- Cleanup Agent 不自动删除文件、不修改 Prompt、不放宽约束。
- 生命周期清理只在请求处理和本地服务 start/restart 路径运行，不存在后台邮箱轮询器或常驻调度器。

## 质量要求

- 新增业务代码必须配套测试。
- 涉及 AI 输出解析和邮件清洗的逻辑必须覆盖异常输入。
- 非小型任务完成后，必须更新项目状态日志，再运行完整测试和维护扫描。
- 修改邮件分类、优先级、风险点或建议动作规则时，必须运行 `tests/test_golden_email_analysis.py`。

## Repeatable phase-two release checklist

在项目根目录按顺序运行：

```powershell
python scripts/generate_project_status.py --output docs/operations/project_status_log.md
python -m unittest discover -s tests
python -B scripts/maintenance_scan.py
node --check frontend/browser_extension/content/current_message_collector.js
node --check frontend/browser_extension/content/exmail_adapter.js
node --check frontend/browser_extension/shared/api_client.js
node --check frontend/browser_extension/shared/render_analysis.js
node --check frontend/browser_extension/popup.js
node --check frontend/browser_extension/background.js
node --check frontend/local_debug_page/app.js
python -c "import json, pathlib; json.loads(pathlib.Path('frontend/browser_extension/manifest.json').read_text(encoding='utf-8')); print('manifest json: OK')"
python -m unittest tests.test_browser_extension_manifest tests.test_architecture_constraints tests.test_static_linter_constraints
git diff --cached --check
git diff --cached --name-status
```

通过条件：完整 Python suite 无失败；maintenance scan 无 findings；全部 Node 和 manifest 检查退出 0；文档/front-matter guards 通过；staged snapshot 只包含本次生命周期、文档、状态和计划收尾范围，且不包含 `.env`、数据库、日志、真实邮件、密钥或 token。

## Validation status

- 自动化单元测试、约束检查、JavaScript 语法检查和合成附件/线程样例属于本仓库内可执行验证。
- 真实 Tencent Exmail 邮件 smoke test **未在本任务执行**。它仍是用户在单独授权、确认最小范围并准备测试邮件后的外部验证项；不得把自动化或合成结果描述为真实邮箱验证。


