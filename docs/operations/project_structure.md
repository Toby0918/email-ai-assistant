---
last_update: 2026-07-23
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 项目结构

## 目标

本文档记录项目建议目录结构和各目录职责。`AGENTS.md` 只保留入口说明，项目落地时以本文档作为结构导航。

## 当前结构

```text
email-ai-assistant/
  AGENTS.md
  README.md
  .env.example
  requirements.txt
  .gitignore

  backend/
    current_evidence/
      __init__.py
      artifact_policy.py
      contract.py
      handoff.py
    project_layout/
      __init__.py
      errors.py
      identity.py
      placement.py
      operational.py
      transition.py
    email_agent/
      __init__.py
      config.py
      logging_config.py
      email_cleaner.py
      analyzer.py
      rule_analyzer.py
      llm_client.py
      database.py
      exporter.py
      api.py
      server.py

  frontend/
    local_debug_page/
      index.html
      app.js
      styles.css
    browser_extension/
      manifest.json
      popup.html
      popup.css
      popup.js
      content/
        exmail_adapter.js
      shared/
        api_client.js
        render_analysis.js

  .github/
    workflows/
      agent_guardrails.yml
      cleanup_agent.yml

  docs/
    README.md

    api/
      backend_api_contract.md
      frontend_backend_flow.md
      error_codes.md

    constraints/
      architecture_constraints.md
      tooling_constraints.md
      linter_constraints.md
      ci_guardrails.md
      mechanical_rule_translation.md

    conventions/
      logging.md

    data/
      data_dictionary.md
      database_schema.md
      analysis_result_schema.md
      sample_email_format.md

    decisions/
      adr_0001_project_shape.md
      adr_0002_frontend_route.md
      adr_0003_no_auto_send.md

    knowledge_base/
      email_categories.md
      priority_rules.md
      action_rules.md
      risk_flags.md
      reply_guidelines.md
      business_terms.md
      customer_context_template.md

    operations/
      *_task_brief.md
      setup_checklist.md
      testing_checklist.md
      deployment_notes.md
      troubleshooting.md
      project_status_log.md
      project_status_log_guide.md
      agents_project_status_snippet.md
      cleanup_agent.md
      cleanup_agent_codex.md
      codex_cleanup_task.md
      documentation_rules.md
      project_structure.md
      review_checklist.md
      file_inventory.md

    product/
      product_overview.md
      user_flow.md
      feature_scope.md
      roadmap.md

    prompts/
      analyzer_prompt.md
      reply_draft_prompt.md
      risk_detection_prompt.md
      prompt_version_log.md

    security/
      privacy_rules.md
      api_key_rules.md
      prompt_injection_rules.md
      email_data_handling.md

    templates/
      agent_task_brief_template.md
      cleanup_task_template.md
      code_review_rule_register.md

  tests/
    fixtures/
      sample_emails.json
    test_email_cleaner.py
    test_analyzer.py
    test_analysis_schema.py
    test_api.py
    test_config.py
    test_database.py
    test_frontend_local_debug.py
    test_generate_project_status.py
    test_golden_email_analysis.py
    test_manage_local_service.py
    test_repo_utils.py
    test_rule_analyzer.py
    test_run_local_debug.py
    test_server.py
    test_architecture_constraints.py
    test_static_linter_constraints.py
    test_mechanical_rule_constraints.py
    test_maintenance_scan.py

  scripts/
    repo_utils.py
    maintenance_scan.py
    generate_project_status.py
    manage_local_service.py
    run_local_debug.py

  start_local_service.cmd
  status_local_service.cmd
  restart_local_service.cmd
  stop_local_service.cmd
```

## 第一阶段已落地结构

第一阶段已经落地 `backend/email_agent/`、`frontend/local_debug_page/`、`tests/`、`scripts/` 和结构化 `docs/`。
第二阶段已选择 Tencent Exmail Chrome / Edge 浏览器扩展原型，目录为 `frontend/browser_extension/`。Outlook Add-in 和 Google Workspace Add-on 路线仍属于后续单独确认范围。

```text
email-ai-assistant/
  backend/
    email_agent/
      __init__.py
      config.py
      logging_config.py
      email_cleaner.py
      analyzer.py
      rule_analyzer.py
      llm_client.py
      database.py
      exporter.py
      api.py
      server.py

  frontend/
    local_debug_page/
      index.html
      app.js
      styles.css
    browser_extension/
      manifest.json
      popup.html
      popup.css
      popup.js
      content/
        exmail_adapter.js
      shared/
        api_client.js
        render_analysis.js

  tests/
    fixtures/
      sample_emails.json
    test_*.py

  scripts/
    generate_project_status.py
    maintenance_scan.py
    manage_local_service.py
    repo_utils.py
    run_local_debug.py

  outputs/
```

## 目录职责

- `.github/workflows/`：CI 护栏和可选后台清理报告任务。当前运行架构、静态 linter、机械规则、完整 unittest 和只读 cleanup scan。
- `backend/`：Python 后端代码。负责 placement/layout contracts、邮件正文清洗、AI 调用封装、结构化结果校验、SQLite 持久化、调试导出、本地 API 和本地调试服务。
- `frontend/local_debug_page/`：第一阶段本地辅助窗口调试页面，只在用户点击 `Analyze` 后调用本地后端 API，不接入真实邮箱账号。
- `frontend/browser_extension/`: Chrome / Edge prototype for Tencent Exmail. It contains the Manifest V3 popup, Tencent Exmail content adapter, local API client, and result renderer. It reads only the current opened message after a user click and calls the local backend.
- `frontend/` 其他路线：Outlook Add-in 和 Google Workspace Add-on 属于后续正式邮箱前端路线，需单独确认后再落地。
- `docs/`：结构化知识库、Prompt、业务规则、接口约定、安全规则、约束层、操作指南、Agent 项目进度日志、Codex 自动化规范、模板和技术决策。`docs/` 是项目规则来源，不是附属说明。
- `docs/constraints/`：工具、架构、静态检查、CI 和机械规则约束。
- `docs/conventions/`：日志等代码约定。
- `docs/templates/`：Agent 任务简报和 code review 规则登记模板。
- `tests/`：自动化测试。当前包含业务测试、golden 样例测试、前端静态检查、服务管理脚本测试和可执行约束测试；新增业务代码必须配套测试。
- `tests/fixtures/sample_emails.json`：脱敏 golden 邮件样例，不得存放真实客户邮件全文。
- `scripts/`：维护和本地服务脚本。当前包含只读 cleanup scan、项目状态日志生成器、本地调试服务入口 `scripts/run_local_debug.py` 和服务启停管理 `scripts/manage_local_service.py`，不得自动删除或自动修改业务文件。
- `outputs/`：本地调试输出、SQLite 数据库、pid 文件和临时报表，不得提交到版本库。

## 第一阶段建议

第一阶段当前以本地调试页面完成“用户点击按钮后分析当前邮件”的闭环。第二阶段 Tencent Exmail 浏览器扩展原型已落地；其他正式企业邮箱前端路线应在后续单独确认后再落地。

## Isolated private-analysis structure

下面三个 package 与日常浏览器路径隔离：

```text
backend/mailbox_ingest/
backend/private_knowledge/
backend/private_evaluation/

scripts/manage_mailbox_vault.py
scripts/manage_private_knowledge.py
scripts/evaluate_private_deepseek.py
scripts/repository_leakage_scan.py
```

- `backend/current_evidence/` is a contract-only, write-only ingress boundary.
  `artifact_policy.py` rejects raw headers, private metadata, credentials,
  serialized mappings, Base64-like payloads, and hidden controls without
  returning matched content. `contract.py` validates immutable
  `CurrentClickEvidenceV1` values and
  `submit_current_click_evidence` invokes one injected append callable. The package
  contains no inbox repository, reader, path, key, mailbox, authority, provider,
  scheduler, polling, or reload surface. Issue #10 does not wire it into normal
  runtime; future issue #18 owns that orchestration and storage.

- `backend/mailbox_ingest/` 只可被 `scripts/manage_mailbox_vault.py` 导入，负责
  固定只读 IMAP、授权/fingerprint、外置加密 vault、附件第二遍和恢复封装。
- `backend/private_knowledge/` 负责本地去标识、residual scan、严格知识卡、独立
  authority lifecycle 和签名只读 runtime snapshot；它不读取邮箱或 raw vault。
- `backend/private_knowledge/checked_reader.py` 是 authority envelope 与 snapshot 的
  共享只读 descriptor 边界；它有界读取并在 open 前后核对路径和 parent/target
  identity，不提供 write/replace/delete 接口。
- `backend/private_knowledge/runtime_bootstrap.py` 仅由
  `scripts/run_local_debug.py` 在 logging 配置后、server 启动前调用一次。它 fail closed
  为 immutable empty tuple；请求期、`backend.email_agent`、frontend、health、SQLite
  和后台任务不访问 DPAPI、authority、snapshot 或 loader，也没有 reload/poll/hot update。
- `backend/private_evaluation/` 负责项目外 `.pkeval` 的严格 schema、确定性选择、
  顺序零重试 runner 和 aggregate-only report；只有专用 CLI 可在全部本地门通过后
  lazy-create provider client。
- `backend/private_evaluation/staging_values.py` 保存不依赖 repository/crypto/path 的
  pure `EvaluationStageV1`；`backend/private_evaluation/dataset_builder.py` 只把该严格值
  `EvaluationStageV1` 投影为 fresh UUIDv4 namespace 的 200-case final dataset；
  `repository.py` 的 create-only writer 使用 same operator-supplied 32-byte key，
  但保留 final magic/purpose/nonce separation，以 atomic no-clobber link 发布。
  publication helper 成功返回即 final commit point；代码 never rolls back or unlinks
  the target by pathname，其后仅做不影响成功结果的 best-effort internal-stage cleanup，
  拒绝覆盖/delete competitor 和 path race，且不删除 reviewed stage。
- `backend/private_evaluation/terminal_judge.py` 只接收 `UsefulnessJudgeView`，仅在
  real local TTY 中显示已去标识 input 与 production-gated public output，并读取一次
  pre-key fixed exact-y readiness，拒绝 terminal control/format chars，再逐 case 读取
  exact `y`/`n`。它 no transcript、no file/cache/log surface；外部终端捕获不在程序
  可控制范围内。
- `backend/private_evaluation/staging_contract.py`、`staging.py` 和
  `staging_repository.py` 只支持管理员 `stage-evaluation`：验证 exactly 200 条
  `StageEvaluationSelectionV1` 绑定，并分别核对 authorization `scope_fingerprint`
  与双审清单 `inventory_fingerprint`。handoff 只能调用 mailbox-ingest 的
  evaluation-only source；它在释放 plaintext 前验证 inventory fingerprint，保持
  no evidence accumulation，并在下一条前释放 raw-derived identifiers。随后以 one
  record at a time cleanup 和 hidden interactive base64 key 写入独立 `.pkevalstage`。
  该密文与 `.pkeval` 使用 distinct magic, purpose, and namespace；成功只返回
  `evaluation_stage_complete`，且 no mailbox app password、provider、network、
  SQLite 或 normal-runtime integration。
- `scripts/evaluate_private_deepseek.py` 暴露固定 `build`、`verify` 和 `run`。`build`
  不创建 provider/judge；`run` 只有 explicit `--interactive-judge`、exact confirmation
  和 TTY + fixed readiness gate 通过后才可继续 hidden-key/dataset/provider/client 路径，并保持 20 Flash
  + 180 Flash / 40 Pro、zero retry 和 no automatic production model switch。
- `scripts/repository_leakage_scan.py` 只扫描仓库内明确 scope，并只输出固定 code、
  scope 和 count。它不打开项目外 vault/private dataset，也不自动修改文件。

`backend/email_agent/` 只通过狭窄的已验证 runtime-card seam 使用不可变知识卡；
它只接收启动入口已加载的 tuple，没有 vault、authority、DPAPI、BitLocker、
snapshot filesystem 或 mailbox access。`frontend/` 仍仅在
用户点击后读取当前可见邮件，公开 HTTP/SQLite/renderer schema 没有因为上述
管理员工具而扩大。
