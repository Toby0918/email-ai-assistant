# Email AI Assistant 桌面版

这是独立重建的 Windows 程序，不依赖旧项目的目录迁移。项目位于 `D:\Projects\email_ai_assistant_rebuild`，应用自身的运行环境、数据、日志、临时文件和构建产物都保存在本目录。

## 启动

双击根目录的 `start.cmd`，或打开 `Program\EmailAssistant\EmailAssistant.exe`。运行成品不需要安装 Python、不需要激活虚拟环境、不需要手动启动后端。整个项目文件夹应一起保留，不要单独移动 exe。

在桌面窗口粘贴当前邮件的主题、发件人和正文，按需选择当前邮件附件，再点击“分析此邮件”。附件选择阶段不读取内容。结果包括处理建议、依据与限制和可编辑回复草稿；审核后勾选确认，再复制草稿到邮箱。程序不会发送、删除或归档邮件。

首次运行默认是本地规则模式，不调用远程 AI。可用“加载示例”验证运行。需要 AI 时，在“AI 设置”选择 OpenAI 或 DeepSeek 并输入自己的 API Key；设置仅在本次进程有效，退出后不保存密钥。启用远程 AI 后，界面在分析前持续展示内容披露。构建与自动化验收不使用真实邮箱或真实模型请求。

DeepSeek 当前采用保守补充模式：AI 可补充摘要、分类等信息，处理建议与草稿仍由本地规则生成，界面会明确说明。自动化测试不调用真实模型；首次人工 DeepSeek 样例已显示 AI 参与和附件数量，但暴露的本地规则误判修复后仍需重新验收业务质量。

## 腾讯企业邮箱扩展

产品扩展 0.2.4 保存在 `frontend\browser_extension`，在已保留的 0.2.3 上增加当前 DeepSeek 文本回退名称的兼容显示。它仍使用 `127.0.0.1:8765`，桌面程序启动时提供兼容后端。需要在 Chrome/Edge 的扩展管理页手动“加载已解压的扩展”并选择此文件夹。桌面程序本身不自动安装扩展或读取浏览器邮件。

桌面粘贴分析可以独立使用；腾讯邮箱页面中的当前邮件提取由浏览器扩展承担。当前没有在真实邮箱中重新验收页面提取。

## 最新稳定依赖基线

2026-09-19 从官方发布源核对后安装。主版本为 Python 3.14.7、SQLite 3.53.4、OpenAI SDK 3.16.2、cryptography 50.0.1、pypdf 6.19.0、python-dotenv 1.2.3。其余直接依赖见 `requirements.txt`，完整实际安装版本含间接依赖和构建工具见 `requirements-resolved.lock`。Tcl/Tk 使用 Python 附带的 9.0.4。

版本来源：[Python 官方稳定版](https://www.python.org/downloads/windows/)、[SQLite 官方下载](https://www.sqlite.org/download.html)、[OpenAI SDK](https://pypi.org/project/openai/)、[PyInstaller](https://pypi.org/project/pyinstaller/)。SQLite 官方 ZIP 的 SHA3-256 已核对，记录见 `docs/sqlite_provenance.json`。Python 可执行文件来自已验证为 Python Software Foundation 有效签名的当前稳定运行时副本，仅在本目录内安装新依赖。

## 目录

| 目录 | 用途 |
| --- | --- |
| `backend`、`desktop_app`、`frontend` | 产品代码、桌面窗口和浏览器扩展 |
| `Runtime\Python3147` | 独立 Python 及已安装依赖 |
| `Program\EmailAssistant` | Windows 程序及其打包依赖 |
| `Data` | 本程序新建的本地分析数据库和请求附件临时目录 |
| `Logs` | 不记录邮件正文或密钥的运行日志 |
| `RuntimeTemp` | 应用和验证临时文件 |
| `Build`、`Cache` | 打包结果、验证报告和下载缓存 |
| `Config` | 预留非敏感配置位置；当前 API Key 不落盘 |
| `docs`、`tests`、`scripts` | 来源记录、验证用例和构建脚本 |

停用的 Python 3.12 试建环境和历史恢复验证目录已由操作者手动删除。`Build\original-requirements-ci-windows.lock` 仅保留原始依赖来源记录，不用于启动或构建。

已核对 35 个安装包，其中 34 个与官方当前稳定版一致。`pydantic-core` 使用当前 Pydantic 2.13.5 明确要求的 2.46.5，而非不兼容的单独最新版 2.49.0；完整结果见 `docs/dependency_versions.json`。该约束通过 `pip check`，不以强行升级破坏可运行性。

## 验证与重建

```powershell
.\Runtime\Python3147\python.exe -B -m unittest discover -s tests
.\scripts\build_windows.ps1
```

打包脚本将临时和缓存位置固定在项目内，并执行打包后的 `--self-test`。机器可读结果写入 `Build\desktop-self-test.json`。该自检覆盖原生窗口、点击分析、人工审核门禁、静态资源、DOCX 子进程解析、附件清理、关闭后重新启动及结果持久化；只使用合成数据。它不证明真实模型的回答质量。

桌面邮件验收要求见 [desktop_mail_acceptance.md](docs/desktop_mail_acceptance.md)。修改邮件或附件后，旧分析、草稿和审核状态立即失效；编辑草稿后需重新勾选审核。运行 `Runtime\Python3147\python.exe -B scripts\create_desktop_acceptance_sample.py` 可生成本地 XLSX 验收样例，配套邮件在 `examples\desktop_acceptance\email.txt`。DeepSeek 使用官方当前名称 `deepseek-flash`；首轮真实样例已观察到 AI 参与，修复版本的业务回答质量仍待复测。

## 已知范围

图片 OCR 依赖可选 Tesseract；没有捆绑 OCR 引擎时会明确降级，不影响正文、PDF 文本、XLSX、DOCX 和规则分析。远程模型调用保持原有隐私与证据校验，失败或输出不安全时回落规则结果。历史邮箱导入、私有知识审批、旧数据库迁移和旧项目的迁移管理流程未接入桌面程序。

XLSX 的“已解析”仅表示已读取受限内容。当前规则能提取明确标签和值，例如 `Quantity | 1200 pcs`，尚不能可靠关联任意多列表头和后续数值行，不能据此宣称理解了整张表格。

若启动提示 8765 端口占用，先退出另一个邮箱助手实例再启动；程序不会结束其他进程。应用数据库保存在本目录，因此复制整个目录也会复制已保存的分析结果。

## 历史资料与旧项目退役

原迁移路线已取消。新目录沿用原仓库的 Git 历史；历史资料提取后，操作者手动完成了约定旧项目、IncidentArchives 和临时验证目录的删除，约定的 13 个路径均已核对不存在。`LegacyArchive` 保留两份 Git bundle 和四份 Windows 当前用户绑定的加密归档，不会自动接入程序，也不上传 Git。加密归档不能视为脱离原 Windows 用户环境仍可解密的便携备份。详细回执在本地 `docs/retirement_20260919/manual_cleanup_completion.json`；回收站内容不在此次检查范围内。
