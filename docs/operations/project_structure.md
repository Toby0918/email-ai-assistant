---
last_update: 2026-06-30
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
    email_agent/
      __init__.py
      config.py
      logging_config.py
      email_cleaner.py
      analyzer.py
      llm_client.py
      database.py
      exporter.py
      api.py

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
    test_email_cleaner.py
    test_analyzer.py
    test_api.py
    test_architecture_constraints.py
    test_static_linter_constraints.py
    test_mechanical_rule_constraints.py
    test_maintenance_scan.py
    test_generate_project_status.py

  scripts/
    maintenance_scan.py
    generate_project_status.py
```

## 建议实现结构

当前实现代码尚未落地。第一阶段建议按以下结构新增代码：

```text
email-ai-assistant/
  backend/
    email_agent/
      __init__.py
      config.py
      logging_config.py
      email_cleaner.py
      analyzer.py
      llm_client.py
      database.py
      exporter.py
      api.py

  frontend/
    outlook_addin/
      manifest.xml
      taskpane.html
      taskpane.js
      taskpane.css

    google_workspace_addon/
      appsscript.json
      main.js

    browser_extension/
      manifest.json
      content.js
      sidepanel.html
      sidepanel.js
      sidepanel.css

    local_debug_page/
      index.html
      app.js
      style.css

  tests/
    test_email_cleaner.py
    test_analyzer.py
    test_database.py
    test_api.py

  data/
    sample_emails/

  outputs/
```

## 目录职责

- `.github/workflows/`：CI 护栏和可选后台清理报告任务。当前运行架构、静态 linter、机械规则、完整 unittest 和只读 cleanup scan。
- `backend/`：未来 Python 后端代码。负责邮件正文清洗、AI 调用、结构化结果校验、SQLite 持久化、调试导出和本地 API。
- `frontend/`：未来辅助窗口前端。第一阶段只需要选择一种路线，不要求同时实现 Outlook Add-in、Google Workspace Add-on 和浏览器扩展。
- `docs/`：结构化知识库、Prompt、业务规则、接口约定、安全规则、约束层、操作指南、Agent 项目进度日志、Codex 自动化规范、模板和技术决策。`docs/` 是项目规则来源，不是附属说明。
- `docs/constraints/`：工具、架构、静态检查、CI 和机械规则约束。
- `docs/conventions/`：日志等代码约定。
- `docs/templates/`：Agent 任务简报和 code review 规则登记模板。
- `tests/`：自动化测试。当前包含可执行约束测试；新增业务代码必须配套测试。
- `scripts/`：维护脚本。当前包含只读 cleanup scan 和项目状态日志生成器，不得自动删除或自动修改业务文件。
- `data/sample_emails/`：未来脱敏本地测试邮件样本，不得存放真实客户邮件全文。
- `outputs/`：未来本地调试输出和临时报表，不得提交到版本库。

## 第一阶段建议

第一阶段可以先实现 `backend/`、`docs/`、`tests/` 和 `frontend/local_debug_page/`。正式企业邮箱前端路线应在后续单独确认后再落地。
