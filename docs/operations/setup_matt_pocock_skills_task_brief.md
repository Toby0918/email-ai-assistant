---
last_update: 2026-07-21
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Setup Matt Pocock Skills Task Brief

## 1. 任务名称

`configure repository metadata for Matt Pocock engineering skills`

## 2. 任务类型

`docs`

## 3. 当前状态

`implemented`

## 4. 任务目标

为工程技能配置仓库级 issue tracker、triage 标签词汇和领域文档读取规则。
配置必须复用本仓库现有 GitHub remote、`AGENTS.md` 和 `docs/decisions/` 布局。
仓库配置只提供项目上下文，不改写 Matt Pocock skills 的 upstream 调用规则。

## 5. 非目标

- 不安装 `gh` CLI 或其他依赖。
- 不修改用户级 Codex 配置或用户目录中的已安装 skill 文件。
- 不把 explicit-only skill 改成 implicit，也不在项目级禁用任何 Matt skill。
- 不创建、修改或关闭 GitHub issue、PR 或标签。
- 不创建空的 `CONTEXT.md`、`CONTEXT-MAP.md` 或重复的 `docs/adr/`。
- 不修改业务代码、API、数据库、Prompt、AI JSON 或邮箱安全边界。
- 不触碰现有 `docs/operations/deployment_notes.md` 和 `frontend/browser_extension.crx` 工作树改动。

## 6. 背景与依据

本任务来自用户明确调用的 `setup-matt-pocock-skills` 技能，并已逐项确认以下选择:

- issue tracker 使用 GitHub Issues。
- triage 使用五个默认标签。
- 领域文档使用 `single-context` 布局，并复用 `docs/decisions/`。

后续只读核验确认，本机 upstream inventory 为 41 个 Matt Pocock skills，另有一个不属于 upstream 的个人符号链接 `netease-uu-booster`。41 个 skills 中，17 个允许隐式调用，24 个按 upstream metadata 保持 explicit-only，项目级禁用数为 0。当前 `.codex/config.toml` 不包含 Matt skill override，只通过 plugin-level 配置禁用 Superpowers；用户级配置和已安装 skill 文件均未修改。项目配置变更必须在新 Codex 会话或重启后才会重新加载。

相关文档:

- `AGENTS.md`
- `docs/operations/project_status_log.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/operations/documentation_rules.md`

## 7. 涉及范围

预计新增或修改:

- `AGENTS.md`
- `docs/agents/issue-tracker.md`
- `docs/agents/triage-labels.md`
- `docs/agents/domain.md`
- `docs/operations/setup_matt_pocock_skills_task_brief.md`
- `docs/operations/project_status_log.md`

## 8. 技术方案

1. 在 `AGENTS.md` 中新增唯一的 `## Agent skills` 区块。
2. 从已批准的 GitHub、默认标签和 domain seed 模板生成仓库级说明。
3. 为新增的 `docs/agents/*.md` 添加符合项目规则的 YAML front matter。
4. 领域文档规则指向现有 `docs/decisions/`，避免创建第二套 ADR 目录。
5. 保留 upstream 的 17 个 implicit 与 24 个 explicit-only 调用边界；项目元数据不承担修改 skill activation metadata 的职责。
6. 生成项目状态日志并运行完整离线验证。

## 9. 数据结构或接口变化

- 数据库变化: 无。
- API 变化: 无。
- AI 输出 JSON 变化: 无。
- Prompt 变化: 无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱数据。
- [x] 不发送、删除、归档或扫描邮件。
- [x] 不读取、保存或暴露 API key、邮箱凭据或 token。
- [x] 不修改 provider、数据流或运行时安全边界。
- [x] 不新增依赖或远程写操作。
- [x] 只处理仓库元数据和文档。

## 11. Prompt Injection 防护

本任务不处理邮件正文、附件、AI 输入或 AI 输出。

## 12. 验收标准

1. `AGENTS.md` 只有一个 `## Agent skills` 区块。
2. `docs/agents/` 包含已批准的三个配置文件。
3. issue tracker 指向 GitHub，且 PR 请求入口保持关闭。
4. triage 标签映射保持五个默认值。
5. domain 规则使用 `single-context` 并指向 `docs/decisions/`。
6. 新增 Markdown 通过 front matter 和静态约束检查。
7. 用户已有工作树改动不被覆盖。
8. 41 个 upstream Matt skills 均未被项目禁用；个人符号链接 `netease-uu-booster` 不计入 inventory。
9. `.codex/config.toml` 只禁用 Superpowers plugin，不修改用户级配置或已安装 skill 文件；配置变化后的实际激活留待新会话或重启验证。

## 13. 测试计划

- 运行 `scripts/generate_project_status.py --output docs/operations/project_status_log.md`。
- 运行 `python -m unittest discover -s tests`。
- 运行 `python scripts/maintenance_scan.py`。
- 运行 `git diff --check`。
- 检查最终 `git status --short` 和本任务 diff。

## 14. 回滚方案

仅撤销本任务新增的三个 `docs/agents/*.md`、任务简报、`AGENTS.md` 的新增区块和状态日志中的本任务更新。不得撤销或覆盖任何任务开始前已存在的工作树改动。

## 15. 需要人工确认的问题

无。用户已批准 GitHub、默认 triage 标签、`single-context` 布局和完整文件草稿。

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md`。
- [x] 已阅读 `docs/operations/project_status_log.md`。
- [x] 已阅读工具、架构和 linter 约束。
- [x] 已阅读任务简报和文档元信息规则。
- [x] 已确认修改文件范围。
- [x] 已确认不会触碰真实邮箱、真实密钥或真实客户数据。

## 17. Remote provider private-context checklist

不适用。本任务不修改 remote provider、private context 或预算。

## 18. Administrator stage-evaluation checklist

不适用。本任务不修改 private-evaluation staging。

## 19. Final dataset build and interactive judge checklist

不适用。本任务不修改 dataset build 或 interactive judge。

## 20. 执行后记录

实际修改文件:

- `AGENTS.md`
- `docs/agents/issue-tracker.md`
- `docs/agents/triage-labels.md`
- `docs/agents/domain.md`
- `docs/operations/setup_matt_pocock_skills_task_brief.md`
- `docs/operations/project_status_log.md`

测试结果:

- Python 3.12.13 状态日志生成成功，active 文档计数从 107 更新为 111。
- 原工作树运行 1518 项测试时，1517 项通过；唯一错误是任务开始前已存在的未跟踪 `frontend/browser_extension.crx` 被前端静态测试当作 UTF-8 文本读取。
- 不修改该用户文件，在隔离临时 clone 中运行同一套 1518 项测试，全部通过。
- 本地 loopback 偶发失败单测随后连续运行 3 次，全部通过。
- `scripts/maintenance_scan.py` 通过，结果为 `No cleanup findings detected.`。
- `git diff --check` 通过。
- 独立只读 Standards 和 Spec 复核均无发现。

未完成事项:

- 本机尚未安装 `gh` CLI。安装和认证属于后续使用 GitHub 技能前的操作，不属于本次仓库配置范围。

后续建议:

- 需要运行会访问 GitHub Issues 的技能前，安装并认证 `gh` CLI。
- 后续可直接编辑 `docs/agents/*.md` 调整配置；只有切换 issue tracker 或从头重建配置时才需要重新运行 setup 技能。
- 修改项目 Codex skill 配置后，新开 Codex 会话或重启 Codex，再核对 17 个 implicit、24 个 explicit-only、0 个 project-disabled 的加载结果。
