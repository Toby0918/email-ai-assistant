---
last_update: 2026-07-21
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Matt Pocock Skill Migration Task Brief

## 1. 任务名称

`remove legacy Superpowers artifacts and make Matt Pocock skills the project development workflow`

## 2. 任务类型

`chore`

## 3. 当前状态

`implemented`

## 4. 任务目标

删除项目工作树中的旧 Superpowers 计划、规格和执行记录，修复所有失效的活动文档与测试依赖，并让本机已安装的 41 个 Matt Pocock upstream skills 按其原生触发规则用于本项目后续开发。

这 41 个 skill 不包含个人符号链接 `netease-uu-booster`；其中 17 个允许模型按任务隐式调用，24 个只允许用户显式调用，项目级禁用数为 0。

## 5. 非目标

- 不修改业务代码、API、数据库、Prompt、AI JSON 或邮件处理行为。
- 不读取或操作真实邮箱、provider、vault、private dataset 或浏览器会话。
- 不安装、删除或修改用户目录中的任何 skill bundle 或 plugin 文件。
- 不改变 upstream skill 自带的 implicit/explicit-only 调用规则。
- 不修改用户级 `C:/Users/33506/.codex/config.toml`。
- 不修改或提交 `docs/operations/deployment_notes.md` 和 `frontend/browser_extension.crx`。
- 不提交、推送、发布或合并未经用户另行授权的变更。

## 6. 背景与依据

用户在 2026-07-21 明确要求清理 Superpowers 遗留物，不在当前工作树保留历史设计与计划，并让后续项目开发全面采用 Matt Pocock skills。用户随后批准了“彻底清理 + 规范迁移”的文件级设计。

本机 `C:/Users/33506/.agents/skills` 的只读 inventory 核验结果如下:

- 共发现 42 个目录；`netease-uu-booster` 是指向用户 AppData 的个人符号链接，不计入 upstream inventory。
- 其余 41 个目录均包含 `SKILL.md` 和 `agents/openai.yaml`。
- 17 个 implicit skills: `codebase-design`、`code-review`、`design-an-interface`、`diagnosing-bugs`、`domain-modeling`、`git-guardrails-claude-code`、`grilling`、`migrate-to-shoehorn`、`obsidian-vault`、`prototype`、`qa`、`request-refactor-plan`、`research`、`resolving-merge-conflicts`、`scaffold-exercises`、`setup-pre-commit`、`tdd`。
- 24 个 explicit-only skills: `ask-matt`、`batch-grill-me`、`claude-handoff`、`edit-article`、`grill-me`、`grill-with-docs`、`handoff`、`implement`、`improve-codebase-architecture`、`loop-me`、`setup-matt-pocock-skills`、`setup-ts-deep-modules`、`teach`、`to-questionnaire`、`to-spec`、`to-tickets`、`triage`、`ubiquitous-language`、`wayfinder`、`wizard`、`writing-beats`、`writing-fragments`、`writing-great-skills`、`writing-shape`。
- 项目配置没有禁用任何 Matt skill。`.codex/config.toml` 只通过一个 plugin-level 开关禁用 Superpowers；用户级配置和已安装 skill 文件保持不变。
- 项目配置只会在新 Codex 会话中重新加载；完成配置变更后必须新开会话或重启 Codex 才能验证实际激活状态。

相关文档:

- `AGENTS.md`
- `docs/operations/project_status_log.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/operations/documentation_rules.md`
- `docs/operations/agent_task_brief_rules.md`
- `docs/agents/issue-tracker.md`
- `docs/agents/triage-labels.md`
- `docs/agents/domain.md`

## 7. 涉及范围

预计删除:

- `docs/superpowers/`
- `.superpowers/`
- `docs/operations/project_codex_skill_policy_task_brief.md`

预计新增或修改:

- `.codex/config.toml`
- `.codex/project-skill-policy.toml`
- `AGENTS.md`
- `docs/agents/*.md`
- `docs/decisions/0007-multimodal-current-email-analysis.md`
- `docs/operations/*_task_brief.md` 中仍引用旧执行路径的文件
- `docs/operations/setup_matt_pocock_skills_task_brief.md`
- `docs/operations/project_status_log.md`
- `scripts/generate_project_status.py`
- 与旧文档路径或项目 skill policy 有关的 `tests/`

## 8. 技术方案

1. 删除已跟踪的旧计划、规格、执行 brief/report，以及 `.superpowers/` 下 ignored 本地执行记录。
2. 把仍具约束力的要求指向现有 ADR、约束文档和正式任务简报，不复制旧计划全文。
3. 更新文档契约测试和状态生成器，使它们只依赖当前正式文档。
4. 从项目配置删除所有 Matt skill 禁用覆盖和逐个 Superpowers skill 覆盖；`.codex/config.toml` 最终只保留项目级 Superpowers plugin 禁用开关。
5. 将项目 policy manifest 改为 Matt Pocock primary，记录 41 个 upstream skills、17/24 调用分类、项目禁用数 0，以及全局配置和已安装 skill 文件均未修改。
6. 修复 `docs/agents/*.md` 和 setup task brief 中现有乱码。
7. 增加机械测试，防止旧目录、旧执行指令或 Matt 禁用覆盖重新进入项目。本迁移使用仓库既有任务简报、测试和评审约束执行，不把待删除的 Superpowers 工作流作为执行方法。

## 9. 数据结构或接口变化

- 数据库变化: 无。
- API 变化: 无。
- AI 输出 JSON 变化: 无。
- Prompt 变化: 无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱数据。
- [x] 不自动发送、删除或归档邮件。
- [x] 不读取、保存或暴露 API key、邮箱凭据或 token。
- [x] 不处理邮件正文、附件、AI 输入或 AI 输出。
- [x] 测试只检查本地仓库元数据、文档和配置。
- [x] 用户已有工作树修改保持不变。

## 11. Prompt Injection 防护

不适用。本任务不处理邮件正文、附件、Prompt、模型输入或模型输出。

## 12. 验收标准

1. 工作树中不存在 `docs/superpowers/` 和 `.superpowers/`。
2. 活动代码、测试、生成器和正式文档不再依赖已删除的路径或 Superpowers 执行指令。
3. `.codex/config.toml` 不包含 Matt skill override，并且只用一个 plugin-level 开关禁用 Superpowers。
4. 项目 policy manifest 与已安装的 41 个 Matt Pocock upstream skills 一致，明确记录 17 个 implicit、24 个 explicit-only 和 0 个 project-disabled skill，并排除个人符号链接 `netease-uu-booster`。
5. `AGENTS.md` 明确 Matt Pocock skills 是本项目主要工程工作流。
6. `docs/agents/*.md` 是有效 UTF-8 中文并符合 YAML front matter 规则。
7. 用户级 Codex 配置、已安装 skill 文件和 plugin cache 未被修改。
8. 既有 `deployment_notes.md` 和 `frontend/browser_extension.crx` 保持不变。
9. 针对性测试、完整 unittest、状态生成、维护扫描和泄漏扫描完成并记录结果。
10. 用户级 Codex 配置和已安装 skill 文件没有变化；操作员被明确告知配置变更需要新会话或重启后才能激活。

## 13. 测试计划

- 先增加会因当前遗留路径和 Matt disabled overrides 而失败的 focused tests。
- 使用 Python 3.12.13 `tomllib` 解析项目 TOML 并验证 policy coverage。
- 核对 41 个 upstream inventory、17/24 调用分类、个人符号链接排除项和 0 project-disabled 计数。
- 检查活动仓库路径与引用，不跟随项目外路径，不读取 ignored 邮件或数据库内容。
- 运行与文档路径、状态生成器和静态约束有关的 focused unittest。
- 运行 `python -m unittest discover -s tests`。
- 运行 `scripts/generate_project_status.py --output docs/operations/project_status_log.md`。
- 再次运行完整 unittest。
- 运行 `python scripts/maintenance_scan.py` 和 `python scripts/repository_leakage_scan.py`。
- 运行 `git diff --check` 并复核最终 `git status --short --ignored`。

## 14. 回滚方案

已跟踪旧文件可从任务开始前的 Git revision 恢复。ignored `.superpowers/` 本地记录按用户明确要求不保留，删除后没有 Git 回滚来源。配置或引用迁移失败时，停止在当前任务范围内并恢复本任务改动，不触碰其他工作树修改。

## 15. 需要人工确认的问题

无。用户已确认历史设计与计划不保留，并批准文件级设计。

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md`。
- [x] 已阅读项目状态日志。
- [x] 已阅读 tooling、architecture、linter、文档和任务简报规则。
- [x] 已确认任务目标、非目标和精确删除目录。
- [x] 已确认不会触碰真实邮箱、真实密钥、真实客户数据或远程 provider。
- [x] 已记录并隔离用户已有工作树修改。

## 17. Remote provider private-context checklist

不适用。本任务不改变 remote AI input、runtime knowledge、privacy transformation、provider routing 或 budget。

## 18. Administrator stage-evaluation checklist

不适用。本任务不改变 raw-vault、stage-evaluation 或 private-evaluation handoff。

## 19. Final dataset build and interactive judge checklist

不适用。本任务不改变 dataset build、interactive judge 或 provider execution。

## 20. 执行后记录

实际清理与迁移:

- 删除 `docs/superpowers/` 的 30 个历史文档和 `.superpowers/` 的 66 个执行记录，共 96 个文件、960,851 bytes；其中 47 个为 Git 跟踪文件，49 个为 ignored/local 文件。按用户明确要求，49 个本地文件未保留备份。
- 将活动 ADR、任务简报、文档契约测试和状态生成器改为引用现有 canonical 文档或已验证 commit evidence；不改变业务代码、API、Prompt、provider 或邮箱权限边界。
- `.codex/config.toml` 只保留 Superpowers plugin-level 禁用项；policy manifest 记录 41 个 upstream Matt skills、17 个 implicit、24 个 explicit-only、0 个 project-disabled，并排除个人符号链接 `netease-uu-booster`。
- `AGENTS.md` 与 `docs/agents/` 记录 Matt Pocock primary 工作流、GitHub issue tracker、默认 triage 标签和 single-context domain 约定。
- 用户已有 `docs/operations/deployment_notes.md` 与 `frontend/browser_extension.crx` 的长度和 SHA-256 均保持任务开始时的值；用户级 Codex 配置和已安装 skill 文件未被本任务写入。

验证结果:

- TDD 契约先后捕获 Matt disable overrides、缺失 activation partition、缺失 new-session/exclusion metadata、遗留目录和旧状态日志引用；迁移后 4 项 policy tests 全部 GREEN。
- 迁移相关 9 个模块共 131 项测试全部通过。
- 仓库要求的字面命令 `python -m unittest discover -s tests` 已执行；系统 Python 环境缺少 `openai`、`bs4` 等锁定依赖，运行 1,253 项后出现 36 个 import errors，未向该解释器安装依赖。
- 锁定 Python 3.12.13 运行完整套件，1,522 项全部通过。
- 状态日志生成成功；最终树通过临时 `GIT_INDEX_FILE` 只读模拟，maintenance scan 无发现、repository leakage total 为 0，真实 `.git/index` 哈希前后相同。
- `git diff --check` 通过；两个精确遗留目录均不存在，活动仓库只在本迁移审计记录中保留删除对象名称。
- 新 Codex CLI 进程的 model-visible skill 清单实测包含 17 个 Matt implicit skills、0 个 Superpowers skills。正在执行本任务的既有会话不会热重载，操作员仍应新开会话或重启 Codex 后继续开发。

未完成事项:

- 未提交或推送任何变更；需由用户在复核工作树后决定版本控制操作。
