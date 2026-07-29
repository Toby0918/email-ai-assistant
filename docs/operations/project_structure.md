---
last_update: 2026-07-27
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
    container_audit/
      __init__.py
      adapters.py
      audit.py
      contract.py
      filesystem_checks.py
      policy.py
      system_checks.py
    migration_evidence/
      __init__.py
      archive_validation.py
      bound_file.py
      checked_io.py
      contract.py
      errors.py
      git_discovery.py
      git_remote.py
      git_runner.py
      manifest.py
      package.py
      path_checks.py
      policy.py
      process_tree.py
      publication.py
      results.py
      review.py
      snapshot.py
      verification.py
      verification_schema.py
      verification_snapshot.py
      verification_values.py
    migration_evidence_publication/
      __init__.py
      canonical.py
      contracts_bridge.py
      creator_bridge.py
      errors.py
      host_baseline_bridge.py
      operator_entry.py
      package_observation.py
      profile_binding.py
      profile_git_binding.py
      publication.py
      publication_receipts.py
      published_scope.py
      receipt_set.py
      receipts.py
      review.py
      review_bridge.py
      selection.py
      selection_state.py
      synthetic_scope.py
      verification_composition.py
    migration_evidence_verifier/
      __init__.py
      bridge.py
      canonical.py
      contracts.py
      package_read.py
      process.py
      process_tree.py
      worker.py
    cutover_contracts/
      __init__.py
      _canonical.py
      authorization.py
      authorization_schema.py
      authorization_validation.py
      errors.py
      operator_entry.py
      profile.py
      profile_schema.py
      receipt.py
      receipt_matrix.py
      receipt_schema.py
      receipt_types.py
    real_host_preflight/
      __init__.py
      audit_bridge.py
      audit_types.py
      authorization_gate.py
      baseline.py
      baseline_bridge.py
      baseline_evidence.py
      callbacks.py
      canonical.py
      collection.py
      composition.py
      contracts.py
      contracts_bridge.py
      errors.py
      evidence.py
      integrity.py
      mutation_gate.py
      operator_entry.py
      profile_snapshot.py
      receipts.py
      sandbox_lease.py
      sandbox_state.py
      sandbox_validation.py
      topology.py
      topology_evidence.py
      windows_api.py
      windows_chain.py
      windows_observation.py
      windows_paths.py
      windows_projection.py
    email_agent/
      __init__.py
      config.py
      managed_runtime.py
      managed_runtime_errors.py
      managed_runtime_validation.py
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
      issue51_cutover_profile_authorization_receipt_task_brief.md
      issue53_windows_real_host_preflight_task_brief.md
      issue54_migration_evidence_publication_task_brief.md
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
      project_container_cutover_contracts.md

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
    cutover_contract_fixtures.py
    test_cutover_authorization_contract.py
    test_cutover_contract_architecture.py
    test_cutover_profile_contract.py
    test_cutover_receipt_contract.py
    real_host_preflight_fixtures.py
    test_real_host_preflight_architecture.py
    test_real_host_preflight_baseline.py
    test_real_host_preflight_composition.py
    test_real_host_preflight_gate.py
    test_real_host_preflight_leakage.py
    test_real_host_preflight_portable.py
    test_real_host_preflight_topology.py
    test_real_host_preflight_windows.py
    test_real_host_preflight_windows_composition.py
    migration_evidence_publication_fixtures.py
    test_migration_evidence_publication_architecture.py
    test_migration_evidence_publication_commit_binding.py
    test_migration_evidence_publication_create_verify.py
    test_migration_evidence_publication_operator.py
    test_migration_evidence_publication_package_observation.py
    test_migration_evidence_publication_receipts.py
    test_migration_evidence_publication_review.py
    test_migration_evidence_verifier_architecture.py
    test_migration_evidence_verifier_process.py

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
      managed_runtime.py
      managed_runtime_errors.py
      managed_runtime_validation.py
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
- `backend/container_audit/`: Issue #34 的纯手工 content-free audit contract；只验证独立 trusted policy 与七个 injected metadata adapters，不含 path/host reader、default adapter、CLI、repair、scheduler 或真实 audit composition。
- `backend/migration_evidence/`: Issue #35 的 offline manual review/create/verify 深模块；只从 exact local refs 与 approved source/tests/docs 创建一个 external create-only package，并独立验证 Git bundle、selection/snapshot/host evidence 和 SHA-256 manifest。Issue #54 将共享纯 archive validation 与 content-free result helpers 从 creator/verifier 中立提取，保持 pre-publication semantic validation，同时让 creator 不再导入 independent verifier。该 package 没有 CLI、default target、normal-runtime consumer、mailbox/provider/private-store 或 migration/cutover capability。
- `backend/migration_evidence_publication/`: Issue #54 的 profile-bound review 与 separately authorized create-only composition。它通过 exact review/create/HostBaseline/contracts bridges 绑定同一 operation、Profile、master、review、selection、Git、host、package/manifest/identity hashes 和 counts，生成 closed review/created/verified receipts，并只在三者完全一致时产生 `MigrationEvidenceReceiptSetV1`。Test-only synthetic binder 把固定 sandbox marker hard-link 到 target parent 并在 claim 时重验同一 regular-file identity，避免 POSIX inode reuse 掩盖 same-path parent replacement；完整 review 仅保留在内存，real entries 在 Issue #39 前保持 locked。
- `backend/migration_evidence_verifier/`: Issue #54 的 physically separate read-only verifier process。固定 sanitized child 通过 bounded descriptor 首次读取 synthetic package，只把该 exact payload 交给 independent verifier，随后要求 target 重读的 identity/bytes 完全一致，并重新计算 package/manifest hashes and counts；它不导入 publication/create capability，也不能 create、write、replace、rename 或删除 package。
- `backend/cutover_host_mutation/`: Issue #55 的 internal fixed-role Windows ACL 与 handle-relative no-clobber primitives。Public `__init__` 仅导出 portable closed contracts；Windows ACL capture/compare/source compatibility、parent-handle-relative `NtCreateFile(FILE_CREATE)` guarded Container、single-use final-DACL apply、exact direct-child zone inheritance、create-only directory/file publication、same-identity move 与 default-locked real constructor 均为 internal seams。Construction DACL 不授予 add-file/add-subdirectory/delete-child 权限，root/marker/parent/target handles 保持打开直到 final DACL linearization；所有 effect 先消费 exact durable Issue #52 INTENT，native tests 只在 caller-owned temporary NTFS sandbox 中运行；normal runtime、scripts、frontend 和 workflows 无 consumer。
- `backend/cutover_repository_transaction/`: Issue #56 的 synthetic-only reversible mixed-topology transaction。它把 exact 8 embedded + 3 external reviewed worktrees、opaque Git admin entries、durable content-free mutation journal、#55 no-replace primitives、scope-bound bounded Git runner、unchanged ContainerAudit filesystem/Git/object/embedded-worktree policy validators、forward/reverse checkpoint recovery 和 locked real constructor 组合在 caller-owned temporary Windows sandbox 内；原 Repository Root 只以 same-volume identity-preserving relocation 成为 `main`，reverse 接受每个完整 forward boundary 与可安全分类的 forward crash gap，先保留已发布的新失败状态再恢复全部原 identity；显式重复 reverse 调用可从每个安全 reverse crash gap 精确续行。无 CLI/HTTP/workflow/normal-runtime consumer、arbitrary path/ref/command、clone/copy/fetch/reset/stash/prune/remove/repair/delete/replace 或 real-host authority。
- `backend/cutover_managed_activation/`: Issue #57 的 synthetic-only create-only publication 深模块。`ManagedActivationPhase` 只组合 Runtime、stopped database、CRX 与 Config 四个窄 adapters；`LockedRuntimeBuilder` 从 complete canonical-tree manifest 绑定的 in-sandbox Python 3.12.13 distribution、complete dependency lock 与 hash-locked offline wheelhouse captured bytes 新建并由新 Runtime 以固定 `-X frozen_modules=on -I -B -S` 自证。完整 approved `Lib/encodings` 从 held source handles 流式生成 bounded deterministic ZIP_STORED `managed-startup.zip`，held `_pth` sentinels 将该 immutable archive 排在 `Lib`/`DLLs` 前，从而封闭 verifier script 接管前的 transient encoding-package 注入。验证脚本只导入 built-in `sys`/`nt`/`_sha2`/`_imp`，先证明 `_imp.is_frozen("codecs")`，再拒绝后续 import；因此 transient `Lib/codecs/__init__.py` 也无法在 hook 前执行。它以 exact Python/SQLite/startup-ZIP/lock/import hashes 和 bounded distribution metadata 证明目标；SQLite binary hashes 与 held approved source entries 交叉验证，目标中临时注入的可遮蔽 Python package 不会执行。CPython source tree 在执行前完成 resource/reparse/ADS 检查，并通过 held write/delete-blocking handles 与 recursive change guard 保持到验证结束；approved source files 从 held handles 流式 create-only 写入 empty Runtime root，mutable source namespace 永不执行；subprocess stdout incrementally bounded，overflow 会终止 child。Immutable scope 保持 root/marker/target-parent handles 并以 parent-handle-relative `NtCreateFile(FILE_CREATE)` 创建目标；streamed CPython baseline 与所有 wheel/lock additions 形成 held exact Runtime tree，拒绝 child reparse/junction、ADS、extra/missing/changed entry。SQLite copier 全程持有 write-blocking source handle 并在最终 target verification 后再次检查 sidecars，CRX source/target 保持到 receipt 与 final reread，Config 只生成 closed-schema non-secret canonical bytes。所有 partial/failed targets 保留，receipts/content-free errors 不含 path/content，real constructors 在 Issue #39 前保持 locked；无 service、repository/worktree、ACL、browser、mailbox/provider/credential/vault/private-data、cleanup/repair/replace 能力或 normal-runtime consumer。
- `backend/cutover_service_lifecycle/`: Issue #58 的 synthetic-only provider-disabled activation、journal-driven rollback 与 legacy recovery 深模块。它只接受 exact injected new/legacy service-role adapters，绑定 Issue #57 receipt set、fresh UUIDv4 nonce、完整 health identity、固定 synthetic request、deterministic-rules/zero-attempt result 与新 `LocalData` 的 exact-one row。已知验证失败进入 `ROLLBACK_REQUIRED`；identity/journal/reparse/provider/safety ambiguity 进入 `INCIDENT_STOP`。rollback 保留 failed/new evidence并恢复 main、Git records 与 11 个 worktrees；legacy recovery 使用独立 disabled Config、不同 nonce、零 legacy analysis write。real constructor 在 Issue #39 前保持 locked。
- `backend/reparenting_rehearsal/`: Issue #36 的 temporary synthetic-only rehearsal 深模块；公开 seam 不接受 path，自建 marker-bound sandbox，复用 exact evidence/audit/layout bridges 演练 existing `.git` reparenting、reviewed worktree repair/recreate、post-state equality 和六个 rollback boundaries。它没有 real workspace、CLI、runtime、browser、workflow、mailbox/provider/vault/private-store/credential/ACL capability。
- `backend/runtime_activation_rehearsal/`: Issue #37 的 pathless synthetic-only activation 深模块；只接受 exact five injected adapters，验证 pinned runtime、从 lock 重建的 Windows venv、`pre_publication` stopped-service create-only SQLite、reviewed-hash extension artifact、Managed writable roles、同一 activation token 绑定的 provider-disabled start/loopback health/一次持久化规则分析/`post_activation` fresh-stop proof 和最终 source preservation。它没有 path、default host adapter、真实 filesystem/SQLite/process/network/provider/mailbox/vault/credential/signing/evidence/cleanup capability，也没有 normal-runtime consumer。
- `backend/cutover_contracts/`: Issue #51 的 pure content-free Cutover Profile、phase-specific authorization 和 canonical receipt 合同层。它只解析、验证和规范化 immutable values；四种 real-host authorization 只能验证外部提供的 canonical values，不能 create、issue 或 mint。`default_operator_entry()` 固定返回 `BLOCKED_NO_APPROVED_COMMAND`。该 package 没有 path、host adapter、filesystem、SQLite、ACL、Git/worktree、runtime、mailbox/provider/vault/private-data、preflight、migration 或 cutover capability，也没有 production consumer。
- `backend/cutover_journal/`: Issue #52 的 pathless synthetic crash-safe journal/state proof。它用 strict canonical hash chain、exact in-memory Windows/Linux barrier traces、per-claim synthetic owner lease、medium operation gate、绑定 exact durable/stable head 且共享 single-use atomic token issuance 的 opaque effect permit、fixed forward/reverse triads、authoritative observed facts、read-only restart inspection 和 explicit authorization-aware resume/rollback 证明状态约束；任何 namespace-published head 在新 append/permit 前必须补齐 stable reread，pending/unbarriered record 不授权 effect，pending direction 必须验证，reverse 只从 committed/applied history LIFO 派生。唯一外部依赖是 exact `contracts_bridge.py`；没有 path/callback/default adapter/CLI/HTTP/host/filesystem/service/ACL/Git/worktree/Runtime/SQLite/provider/mailbox/vault/private-data capability 或 production consumer。
- `backend/real_host_preflight/`: Issue #53 的 physically separate、
  default-locked Windows read-only composition。Portable contracts bind
  opened-handle volume identity, 128-bit file ID, exact object type, parent
  identity, normalized-name fingerprint and reparse metadata；
  `CurrentTopologyPreflight` requires two complete identical observations；
  `PreMutationGate` is fresh UUIDv4-nonce-bound, short-lived,
  operation-bound and single-use；all callback evidence is factory-reconstructed
  and source/parent/finance/target names bind to exact Profile roles；
  `RealHostBaselineCollector` keeps source,
  parent, finance, volume, operator-SID and ACL evidence separate before
  canonical projection。Only `audit_bridge.py`, `baseline_bridge.py`, and
  `contracts_bridge.py` may consume the unchanged ContainerAudit,
  `HostBaseline`, and locked cutover contracts. Final-audit readiness proves
  composability of the unchanged nine-zone policy and exact seven callbacks
  without running an audit or claiming a pass。Windows behavior runs only in
  caller-owned temporary sandboxes through a package-private root/marker
  identity-bound single-use permit; controlled files require exactly one link。
  Receipt, gate, scope and observer trusted state is module-owned; Linux runs
  portable contracts only。The
  operator entry remains `BLOCKED_NO_APPROVED_COMMAND` and the package has no
  service-control、ACL-apply、rename、worktree mutation、Runtime build、
  database copy、artifact、Config、provider、mailbox、vault、private-data or
  production consumer capability。
- `backend/email_agent/managed_runtime.py`: Issue #32 的 Managed launcher adapter；从 exact `main` placement 派生普通 zone，读取 bounded non-secret Config，并返回 provider-disabled resolved config。它不执行真实迁移、container audit、runtime/data/artifact/worktree activation 或 private capability。
- `backend/email_agent/managed_runtime_errors.py` 与 `backend/email_agent/managed_runtime_validation.py`: Managed mode 的固定失败映射、稳定身份检查、可写预检和 bounded settings reader；拆分后仍不向 request handlers 暴露 placement reader。
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
- `outputs/`: 当前 flat compatibility 模式的本地调试输出、SQLite 数据库、pid 文件和临时报表，不得提交到版本库。Managed mode 不使用该目录；其普通状态位于 Project Container 的 approved sibling zones，而 repository tooling 仍停留在 `main`。

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
