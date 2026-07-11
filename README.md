# Email AI Assistant

企业邮箱 AI 辅助窗口项目。第一阶段目标是在用户打开一封企业邮件后，由辅助窗口识别当前邮件，并在用户点击“分析此邮件”后生成摘要、优先级、分类、风险点、建议动作和回复草稿。

本项目不是批量邮件读取、批量邮箱扫描或报表自动化工具。

## 第一阶段边界

支持：

- 用户点击按钮后分析当前打开的一封邮件。
- 清洗邮件正文并生成结构化分析结果。
- 展示摘要、优先级、分类、风险点、建议动作和回复草稿。
- 将分析结果保存到本地 SQLite，用于调试、回看和功能验证。

不支持：

- 不接入真实邮箱账号或读取真实邮箱数据。
- 不自动发送、删除或归档邮件。
- 不自动扫描邮箱或批量分析所有邮件。
- 不把 OpenAI API key、邮箱凭据、OAuth token 或服务端密钥放入前端。
- 不自动代表用户承诺价格、交期、付款、合同或法律事项。

## 快速入口

- 项目规则入口：`AGENTS.md`
- Agent 项目进度日志：`docs/operations/project_status_log.md`
- 文档入口：`docs/README.md`
- 项目结构：`docs/operations/project_structure.md`
- 工具约束：`docs/constraints/tooling_constraints.md`
- 架构约束：`docs/constraints/architecture_constraints.md`
- 静态检查：`docs/constraints/linter_constraints.md`
- CI 护栏：`docs/constraints/ci_guardrails.md`
- 后台清理 Agent：`docs/operations/cleanup_agent.md`
- Codex 清理自动化：`docs/operations/cleanup_agent_codex.md`

## 技术基线

后端使用 Python 3.12.13。依赖版本锁定在 `requirements.txt`：

- `beautifulsoup4==4.15.0`
- `openpyxl==3.1.5`
- `openai==2.45.0`
- `python-dotenv==1.2.2`
- `pypdf==6.14.2`
- `python-docx==1.2.0`
- `Pillow==12.3.0`
- `pytesseract==0.3.13`

SQLite 使用运行时版本 3.50.4，不通过 `requirements.txt` 安装。

## 本地配置

复制 `.env.example` 为本地 `.env`，只配置后端本地分析服务需要的变量。`.env` 不得提交。

```powershell
Copy-Item .env.example .env
```

OpenAI API key 只能放在后端本地环境或受控部署环境中，不能写入前端、浏览器扩展、Add-in 页面或 docs。

## 本地调试运行

第一版使用本地调试页面验证“点击分析当前邮件”的辅助窗口体验，不接入真实邮箱账号。

推荐使用服务管理脚本：

```powershell
python scripts/manage_local_service.py start
python scripts/manage_local_service.py status
python scripts/manage_local_service.py restart
python scripts/manage_local_service.py stop
```

Windows 可直接双击这些快捷脚本：

```text
start_local_service.cmd
status_local_service.cmd
restart_local_service.cmd
stop_local_service.cmd
```

也可以前台直接运行旧入口：

```powershell
python scripts/run_local_debug.py
```

启动后打开：

```text
http://127.0.0.1:8765
```

页面只会在点击 `Analyze` 后调用本地后端接口。未配置 OpenAI API key 时，后端使用本地规则分析器返回可校验结果。

## Tencent Exmail browser extension prototype

Second-stage prototype files live in `frontend/browser_extension`.

Local use:

1. Start the backend with `start_local_service.cmd` or `python scripts/manage_local_service.py start`.
2. Open Chrome or Edge extension management.
3. Choose `Load unpacked`.
4. Select the `frontend/browser_extension` folder.
5. Open Tencent Exmail Web at `https://exmail.qq.com/`.
6. Open one email, then click the extension's `Analyze current email` button.

The extension calls only the local backend. It does not store API keys, connect to a mailbox account, scan the mailbox, or automatically send/delete/archive email.

## 可执行检查

使用项目自带的约束测试检查文档元信息、敏感文件、架构边界、静态规则和机械规则：

```powershell
python -m unittest discover -s tests
```

如果系统 PATH 中没有 `python`，使用项目虚拟环境或 Codex bundled Python 运行同一命令。

## Agent 项目进度日志

项目进度日志不是普通开发日志，而是 Agent 接手任务前的上下文入口。它记录当前阶段、已建立护栏、关键文件状态、下一步建议和不可触碰边界。

更新日志：

```powershell
python scripts/generate_project_status.py --output docs/operations/project_status_log.md
```

## 后台清理扫描

每周定时扫描优先由 Codex 自动化任务 `Weekly Cleanup Agent` 执行，规范见 `docs/operations/cleanup_agent_codex.md`，任务 Prompt 源文件见 `docs/operations/codex_cleanup_task.md`。如保留 `.github/workflows/cleanup_agent.yml`，它只作为可选报告通道或 CI 补充。

该 Agent 只读扫描并生成报告，不会自动删除文件、修改 Prompt、放宽约束或合并代码。

本地运行：

```powershell
python scripts/maintenance_scan.py --output outputs/cleanup_report.md
```

## GitHub 上传前检查

上传或推送前请先运行：

```powershell
python -m unittest discover -s tests
python scripts/maintenance_scan.py
git status --short --ignored
```

确认不要提交 `.env`、真实邮件数据、SQLite 数据库、日志、`outputs/`、`.venv/`、`.idea/`、API key、邮箱凭据或 token。首次推送需要先创建 GitHub 仓库并添加远程地址，例如：

```powershell
git remote add origin https://github.com/<your-account>/<your-repo>.git
git push -u origin master
```

## 第一阶段开发方向

建议先落地：

- `backend/email_agent/`：邮件清洗、AI 调用、JSON 校验、SQLite 持久化、本地 API。
- `frontend/local_debug_page/`：只用于验证“点击分析当前邮件”的辅助窗口体验。
- `tests/`：持续维护可执行约束和业务测试。

第二阶段已选择 Tencent Exmail Chrome / Edge 浏览器扩展原型，位于 `frontend/browser_extension`。Outlook Add-in 和 Google Workspace Add-on 路线仍需后续单独确认。
