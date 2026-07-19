# Email AI Assistant

企业邮箱 AI 辅助窗口项目。用户打开一封企业邮件后，辅助窗口识别当前邮件，并在用户点击“分析此邮件”后生成摘要、优先级、分类、风险点、建议动作和回复草稿。

本项目不是批量邮件读取、批量邮箱扫描或报表自动化工具。

## 第一阶段边界（当前仍适用）

支持：

- 用户点击按钮后分析当前打开的一封邮件。
- 清洗邮件正文并生成结构化分析结果。
- 在用户点击后，受限传输并解析当前邮件页面可见的图片、PDF、XLSX 和 DOCX 附件，并重建可见会话线程。
- 展示摘要、优先级、分类、风险点、建议动作和回复草稿。
- 将分析结果保存到本地 SQLite，用于调试、回看和功能验证。

不支持：

- 浏览器扩展和正常后端不接入真实邮箱账号或遍历邮箱；唯一例外是书面授权、管理员手动运行、与正常服务隔离的只读 IMAP 导入 CLI。
- 不自动发送、删除或归档邮件。
- 不自动扫描邮箱或批量分析所有邮件。
- 不把 OpenAI API key、邮箱凭据、OAuth token 或服务端密钥放入前端。
- 不自动代表用户承诺价格、交期、付款、合同或法律事项。

## 当前发布状态

- Current unpacked extension version: `0.2.3`.
- 当前远程分析路线为 one OpenAI multimodal primary call、最多 one eligible DeepSeek text-only fallback、deterministic rules last；all providers disabled by default。
- Task 9 synthetic provider and current-clicked Tencent smokes are complete；这些有界测试不授权后续新的真实邮箱操作。
- Task 5 real current-message attachment smoke remains pending，新的自动附件获取路径仍是 not live-tested，并需要 fresh explicit authorization。

详细状态、预算与媒体边界见 `docs/operations/project_status_log.md` 和 `docs/decisions/0007-multimodal-current-email-analysis.md`。

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
- `cryptography==49.0.0`

SQLite 使用运行时版本 3.50.4，不通过 `requirements.txt` 安装。

## 本地配置

复制 `.env.example` 为本地 `.env`，只配置后端本地分析服务需要的变量。`.env` 不得提交。

```powershell
Copy-Item .env.example .env
```

OpenAI 和 DeepSeek API key 只能放在后端本地环境或受控部署环境中，不能写入前端、浏览器扩展、Add-in 页面或 docs。

第二阶段本地默认值如下；变量均只由 Python 后端读取：

| 变量 | 默认值 | 用途 |
|---|---|---|
| `EMAIL_AGENT_LLM_PROVIDER` | `disabled` | 默认不调用模型；可显式设置为 `openai`、`deepseek` 或 `ollama` |
| `EMAIL_AGENT_OPENAI_MODEL` | `gpt-5.6-sol` | OpenAI 多模态主模型；仅允许固定模型和官方端点 |
| `EMAIL_AGENT_OPENAI_TIMEOUT_SECONDS` | `35` | OpenAI 单次调用上限 |
| `EMAIL_AGENT_TEXT_FALLBACK_PROVIDER` | `disabled` | 仅显式设为 `deepseek` 时允许一次合格的文本回退 |
| `EMAIL_AGENT_DEEPSEEK_MODEL` | `deepseek-v4-flash` | DeepSeek 直连或文本回退模型；也允许 `deepseek-v4-pro` |
| `EMAIL_AGENT_DEEPSEEK_TIMEOUT_SECONDS` | `10` | DeepSeek 单次调用上限 |
| `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE` | `conservative` | DeepSeek 默认保守输出模式 |
| `EMAIL_AGENT_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | 后端本地 Ollama 地址 |
| `EMAIL_AGENT_OLLAMA_MODEL` | `qwen3.6:latest` | 启用 Ollama 时的模型；可改为 `gemma4` |
| `EMAIL_AGENT_OLLAMA_TIMEOUT_SECONDS` | `30` | 本地模型超时秒数 |
| `EMAIL_AGENT_ATTACHMENT_TEMP_DIR` | `outputs/attachment_temp` | 后端受控临时附件目录 |
| `EMAIL_AGENT_ATTACHMENT_RETENTION_HOURS` | `24` | 仅用于崩溃后孤儿文件清理；正常请求结束时立即删除临时文件 |
| `EMAIL_AGENT_ATTACHMENT_MAX_FILES` | `5` | 单次请求最多附件数 |
| `EMAIL_AGENT_ATTACHMENT_MAX_FILE_BYTES` | `10485760` | 单文件上限（10 MiB） |
| `EMAIL_AGENT_ATTACHMENT_MAX_TOTAL_BYTES` | `26214400` | 单次请求总上限（25 MiB） |
| `EMAIL_AGENT_PRIVATE_KNOWLEDGE_ENABLED` | `false` | 仅显式 `true` 时在服务启动阶段尝试加载已批准知识快照 |
| `EMAIL_AGENT_PRIVATE_KNOWLEDGE_AUTHORITY_ROOT` | 空 | 项目和 OneDrive 外的私有 authority 绝对路径；不会进入公开输出 |
| `EMAIL_AGENT_PRIVATE_KNOWLEDGE_SNAPSHOT_PATH` | 空 | 项目和 OneDrive 外的 `.pksnap` 绝对路径；不会进入公开输出 |

图片 OCR 使用可选的 Tesseract 可执行程序。在本地规则路径中，Tesseract 缺失或 OCR 失败会安全降级；显式启用 OpenAI 多模态路线后，经本地筛查的当前邮件正文、业务图片和受支持文件可按点击前披露发送给远程模型。

After you click Analyze, configured remote AI providers may receive locally deidentified current visible email text and selected current-message images or files after local screening. Media pixels or document content may contain identifying information and are not guaranteed to be fully deidentified. Processing is not local-only, and no zero-retention guarantee is made.

## 本地调试运行

第一版使用本地调试页面验证“点击分析当前邮件”的辅助窗口体验，不接入真实邮箱账号。

推荐使用服务管理脚本：

```powershell
python scripts/manage_local_service.py start
python scripts/manage_local_service.py status
python scripts/manage_local_service.py restart
python scripts/manage_local_service.py stop
```

`start` 会在启动进程前执行一次过期附件清理；`restart` 会在停止和重新启动序列前执行一次，且不会通过嵌套 `start` 重复清理。成功输出只包含删除计数和服务状态。清理失败时命令返回通用可操作错误，不启动或重启服务，也不输出附件名、内容、私有 URL、cookie、token、OCR 文本或异常中的私有路径。请求处理时的既有清理仍保留；项目没有后台邮箱轮询器或常驻清理调度器。

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

可选私有知识默认为关闭。只有三个 `EMAIL_AGENT_PRIVATE_KNOWLEDGE_*` 配置同时满足
安全门时，启动入口才会通过当前 Windows 用户范围 DPAPI 一次性打开 authority
key envelope、验证并解密只读 snapshot，然后把不可变的已批准知识卡保存在内存。
missing、expired、tampered、路径或 DPAPI 失败均静默返回空知识集，普通规则分析继续
工作。请求处理期间没有 snapshot/DPAPI/filesystem access，也没有 reload、polling、
hot update 或公开状态接口；修改配置或发布新 snapshot 后必须重启服务。

本地服务仅允许绑定 `localhost` 或字面 IPv4 loopback（`127.0.0.0/8`）；不要使用 `0.0.0.0`、LAN/公网地址、DNS alias 或 IPv6。分析 POST 必须使用匹配实际端口的 loopback `Host` 和 `Content-Type: application/json`（可选 `charset=utf-8`）。

页面只会在点击 `Analyze` 后调用本地后端接口。`EMAIL_AGENT_LLM_PROVIDER=disabled` 时使用本地规则分析器。OpenAI 主路线出现合格失败、显式配置 DeepSeek 且共享预算至少剩余 12 秒时，符合条件时先尝试一次 DeepSeek 文本回退；该回退被禁用、不合格、预算不足、失败或不安全时才返回规则结果。直接启用 DeepSeek 或 Ollama 的路线在缺少有效配置、超时或未通过安全校验时同样返回可校验的安全规则结果。

## Tencent Exmail browser extension prototype

Second-stage prototype files live in `frontend/browser_extension`.

Current unpacked extension version: `0.2.3`.

Local use:

1. Start the backend with `start_local_service.cmd` or `python scripts/manage_local_service.py start`.
2. Open Chrome or Edge extension management.
3. Choose `Load unpacked`.
4. Select the `frontend/browser_extension` folder.
5. Confirm version `0.2.3`. After pulling or copying a new build, click `Reload` on the extension card before testing.
6. Open Tencent Exmail Web at `https://exmail.qq.com/`.
7. Click the extension icon to open the persistent side panel.
8. Open one email, then click the side panel's `Analyze current email` button.

The assistant runs in a persistent side panel, so clicking outside the assistant does not close it. The extension calls only the local backend. It does not store API keys, connect to a mailbox account, scan the mailbox, or automatically send/delete/archive email.

Health and troubleshooting:

- Run `python scripts/manage_local_service.py status`; a healthy managed service reports `running`, its PID, and the loopback URL only.
- Or request `GET http://127.0.0.1:8765/api/health` and expect HTTP 200.
- If startup reports attachment cleanup failure, verify `EMAIL_AGENT_ATTACHMENT_TEMP_DIR` and local directory permissions, then retry. The command intentionally omits the failing path.
- If the extension cannot reach the backend, confirm port `8765`, restart the local service, then reload extension version `0.2.3`.
- If image text is unavailable, install the Tesseract executable for optional OCR or accept the safe metadata-only degradation.

Automated tests and synthetic fixtures cover the phase-two attachment/thread flow and lifecycle behavior. Task 9 synthetic provider and current-clicked Tencent smokes are complete for their approved bounded checks. Task 5 real current-message attachment smoke remains pending: the new automatic attachment acquisition path is not live-tested and requires fresh explicit authorization. A previous smoke does not authorize mailbox navigation, scanning, sending, or another live provider call.

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

## 主要实现目录

当前主要目录：

- `backend/email_agent/`：邮件清洗、AI 调用、JSON 校验、SQLite 持久化、本地 API。
- `frontend/local_debug_page/`：只用于验证“点击分析当前邮件”的辅助窗口体验。
- `tests/`：持续维护可执行约束和业务测试。

第二阶段已选择 Tencent Exmail Chrome / Edge 浏览器扩展原型，位于 `frontend/browser_extension`。Outlook Add-in 和 Google Workspace Add-on 路线仍需后续单独确认。
