---
last_update: 2026-07-21
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue tracker: GitHub

本仓库的 issue 和 PRD 记录在 GitHub Issues 中。所有操作使用 `gh` CLI。

当前前置条件: 本机尚未安装 `gh` CLI。本次配置不会安装依赖、创建 issue 或执行任何远程写操作。

## 操作约定

- 创建 issue: `gh issue create --title "..." --body "..."`
- 读取 issue: `gh issue view <number> --comments --json number,title,body,labels,comments`
- 列出 issue: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`
- 评论: `gh issue comment <number> --body "..."`
- 添加或移除标签: `gh issue edit <number> --add-label "..."` 或 `gh issue edit <number> --remove-label "..."`
- 关闭: `gh issue close <number> --comment "..."`
- 多行正文应通过 PowerShell here-string 或临时正文文件安全传入 `--body`。

在当前 clone 中运行时，由 `git remote -v` 推断目标仓库。

## Pull requests 作为 triage 请求入口

**PRs as a request surface: no.**

如果以后将该值改为 `yes`，PR 将使用与 issue 相同的标签和状态:

- 读取 PR: `gh pr view <number> --comments` 和 `gh pr diff <number>`
- 列出外部 PR: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`
- 只保留 `authorAssociation` 为 `CONTRIBUTOR`、`FIRST_TIME_CONTRIBUTOR` 或 `NONE` 的 PR
- 评论、修改标签或关闭: 使用 `gh pr comment`、`gh pr edit` 和 `gh pr close`

GitHub 的 issue 与 PR 共用编号空间。遇到 `#42` 时，先运行 `gh pr view 42`，失败后再运行 `gh issue view 42`。

## 技能要求发布到 issue tracker 时

创建一个 GitHub issue。

## 技能要求读取相关 ticket 时

运行 `gh issue view <number> --comments`。

## Wayfinding 操作

`/wayfinder` 使用一个 map issue 和若干 child issue:

- Map: 使用 `gh issue create --label wayfinder:map` 创建单个 issue，正文保存 Notes、Decisions-so-far 和 Fog。
- Child ticket: 优先通过 GitHub sub-issues endpoint 的 `gh api` 调用把 child 关联到 map。sub-issue 不可用时，将 child 加入 map 的任务列表，并在 child 顶部写入 `Part of #<map>`。
- Child 标签: 使用 `wayfinder:<type>`，其中 type 为 `research`、`prototype`、`grilling` 或 `task`。
- Blocking: 优先使用 GitHub 原生 issue dependencies。通过 `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>` 添加依赖，其中 `<blocker-db-id>` 必须来自 `gh api repos/<owner>/<repo>/issues/<n> --jq .id`，不能使用 `#number` 或 `node_id`。原生依赖不可用时，在 child 顶部写入 `Blocked by: #<n>, #<n>`。
- Frontier: 列出 map 的开放 child，排除 `issue_dependencies_summary.blocked_by > 0`、fallback `Blocked by` 中仍有开放 issue 或已有 assignee 的 child，再按 map 顺序选择第一个。
- Claim: 运行 `gh issue edit <n> --add-assignee @me`，这是 session 的第一次写操作。
- Resolve: 依次运行 `gh issue comment <n> --body "<answer>"` 和 `gh issue close <n>`，再把 gist 与链接形式的 context pointer 追加到 map 的 Decisions-so-far。
