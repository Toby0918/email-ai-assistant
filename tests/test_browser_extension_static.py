"""Static tests for the Tencent Exmail browser extension prototype."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
EXTENSION = FRONTEND / "browser_extension"
REMOTE_PROCESSING_NOTICE = (
    "After you click Analyze, configured remote AI providers may receive locally deidentified "
    "current visible email text and selected current-message images or files after local "
    "screening. Media pixels or document content may contain identifying information and are not "
    "guaranteed to be fully deidentified. Processing is not local-only, and no zero-retention "
    "guarantee is made."
)


def all_frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in FRONTEND.rglob("*")
        if path.is_file()
    )


class BrowserExtensionStaticTests(unittest.TestCase):
    def test_popup_manual_attachment_picker_is_collapsed_bounded_and_loaded_before_popup(self) -> None:
        page = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        expected_accept = (
            ".png,.jpg,.jpeg,.gif,.webp,.bmp,.tif,.tiff,.pdf,.xlsx,.docx,"
            "image/png,image/jpeg,image/gif,image/webp,image/bmp,image/tiff,application/pdf,"
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        self.assertIn('<details class="manual-attachment-picker">', page)
        self.assertNotIn('<details class="manual-attachment-picker" open', page)
        self.assertIn('id="manual-attachment-files"', page)
        self.assertIn('type="file"', page)
        self.assertIn("multiple", page)
        self.assertIn(f'accept="{expected_accept}"', page)
        self.assertLess(
            page.index('src="shared/manual_attachment_files.js"'),
            page.index('src="popup.js"'),
        )

    def test_popup_shows_remote_processing_notice_before_analyze_click(self) -> None:
        page = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        script = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn('id="remote-processing-notice"', page)
        self.assertIn(REMOTE_PROCESSING_NOTICE, page)
        self.assertLess(
            page.index('id="remote-processing-notice"'),
            page.index('id="analyze-button"'),
        )
        notice_start = page.index('<p id="remote-processing-notice"')
        notice_tag = page[notice_start : page.index(">", notice_start)]
        self.assertNotIn("hidden", notice_tag)
        self.assertNotIn("aria-hidden", notice_tag)
        self.assertNotIn("remote-processing-notice", script)

    def test_frontend_never_contains_deepseek_key_or_direct_endpoint(self) -> None:
        source = all_frontend_source()

        self.assertNotIn("DEEPSEEK_API_KEY", source)
        self.assertNotIn("api.deepseek.com", source)

    def test_tencent_exmail_route_decision_is_documented(self) -> None:
        adr = (ROOT / "docs" / "decisions" / "adr_0002_frontend_route.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "product" / "roadmap.md").read_text(encoding="utf-8")
        scope = (ROOT / "docs" / "product" / "feature_scope.md").read_text(encoding="utf-8")

        self.assertIn("Tencent Exmail", adr)
        self.assertIn("Chrome / Edge browser extension", adr)
        self.assertIn("exmail.qq.com", adr)
        self.assertIn("current opened Tencent Exmail message", adr)
        self.assertIn("user-selected email content", adr)
        self.assertIn("not arbitrary webpage analysis", adr)
        self.assertIn("after the explicit analyze click", adr)
        self.assertIn("Tencent Exmail", roadmap)
        self.assertIn("Tencent Exmail", scope)

    def test_active_docs_keep_selected_text_fallback_email_scoped(self) -> None:
        docs = [
            ROOT / "docs" / "decisions" / "adr_0002_frontend_route.md",
            ROOT / "docs" / "superpowers" / "specs" / "2026-07-02-tencent-exmail-browser-extension-design.md",
            ROOT / "docs" / "superpowers" / "plans" / "2026-07-02-tencent-exmail-browser-extension.md",
        ]
        required = [
            "user-selected email content",
            "currently opened Tencent Exmail message",
            "not arbitrary webpage analysis",
            "not background page scraping",
            "Open a Tencent Exmail message or select email body text from that opened message first",
        ]
        forbidden = [
            "selected page text",
            "selected text on any web page",
            "fallback when no opened email is detected",
            "No opened email or selected text found",
            "Open one email or select visible email body content first",
        ]

        for path in docs:
            text = path.read_text(encoding="utf-8")
            for marker in required:
                with self.subTest(path=path.name, marker=marker):
                    self.assertIn(marker, text)
            for marker in forbidden:
                with self.subTest(path=path.name, marker=marker):
                    self.assertNotIn(marker, text)

    def test_implementation_plan_uses_narrow_fallback_wording(self) -> None:
        plan = (
            ROOT
            / "docs"
            / "superpowers"
            / "plans"
            / "2026-07-02-tencent-exmail-browser-extension.md"
        ).read_text(encoding="utf-8")

        self.assertNotIn("当前打开邮件或用户选中的文本", plan)
        self.assertNotIn("Open one email or select email text first", plan)
        self.assertIn(
            "Open a Tencent Exmail message or select email body text from that opened message first",
            plan,
        )

    def test_exmail_superpowers_docs_use_allowed_source_type(self) -> None:
        docs = [
            ROOT / "docs" / "superpowers" / "specs" / "2026-07-02-tencent-exmail-browser-extension-design.md",
            ROOT / "docs" / "superpowers" / "plans" / "2026-07-02-tencent-exmail-browser-extension.md",
        ]

        for path in docs:
            text = path.read_text(encoding="utf-8")
            front_matter = text.split("---", 2)[1]
            with self.subTest(path=path.name):
                self.assertIn("source_type: operation_guide", front_matter)
                self.assertNotIn("source_type: design_spec", front_matter)
                self.assertNotIn("source_type: implementation_plan", front_matter)

    def test_browser_extension_files_exist(self) -> None:
        expected = [
            "manifest.json",
            "background.js",
            "popup.html",
            "popup.css",
            "popup.js",
            "content/exmail_visible_context.js",
            "content/exmail_visible_resource_classifier.js",
            "content/current_message_collector.js",
            "content/exmail_adapter.js",
            "shared/api_client.js",
            "shared/render_analysis.js",
        ]

        for relative in expected:
            with self.subTest(relative=relative):
                self.assertTrue((EXTENSION / relative).exists())

    def test_visible_context_is_exactly_scoped_and_revalidated(self) -> None:
        path = EXTENSION / "content" / "exmail_visible_context.js"
        self.assertTrue(path.exists())
        script = path.read_text(encoding="utf-8")
        adapter = (EXTENSION / "content" / "exmail_adapter.js").read_text(encoding="utf-8")
        manifest = (EXTENSION / "manifest.json").read_text(encoding="utf-8")

        self.assertIn("resolveVerifiedDocumentContext", script)
        self.assertIn("revalidateVerifiedDocumentContext", script)
        self.assertIn('"mainFrame"', script)
        self.assertIn("contextToken", script)
        self.assertIn("resolveVerifiedDocumentContext", adapter)
        self.assertIn("revalidateVerifiedDocumentContext", adapter)
        self.assertNotIn("collectAccessibleDocuments", adapter)
        self.assertNotIn("visitWindow", adapter)
        self.assertNotIn("all_frames", manifest)

    def test_api_client_calls_only_local_backend(self) -> None:
        script = (EXTENSION / "shared" / "api_client.js").read_text(encoding="utf-8")

        self.assertIn("http://127.0.0.1:8765/api/analyze-current-email", script)
        self.assertIn("fetch(", script)
        self.assertIn('"Content-Type": "application/json"', script)
        self.assertIn("user_confirmed: true", script)
        self.assertIn('attachments: projectItems(email.attachments, ["filename", "size", "type"])', script)
        self.assertIn("thread_segments: projectItems(email.thread_segments", script)
        self.assertIn("attachment_files: projectItems(email.attachment_files", script)
        self.assertNotIn("api.openai.com", script)
        self.assertNotIn("OPENAI_API_KEY", script)
        self.assertNotIn("process.env", script)

    def test_renderer_displays_existing_analysis_schema(self) -> None:
        page = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        script = (EXTENSION / "shared" / "render_analysis.js").read_text(encoding="utf-8")

        self.assertIn('id="engine"', page)
        self.assertIn("renderAnalysis", script)
        self.assertIn("clearAnalysis", script)
        self.assertIn("analysis.analysis_engine", script)
        self.assertIn("analysis.decision_brief", script)
        self.assertIn("analysis.priority", script)
        self.assertIn("analysis.summary", script)
        self.assertIn("analysis.category", script)
        self.assertIn("analysis.risk_flags", script)
        self.assertIn("analysis.suggested_actions", script)
        self.assertIn("renderDraft(fields, analysis.reply_draft)", script)
        self.assertIn("draft.body", script)
        self.assertIn('id="attachments"', page)
        self.assertIn('id="decision-brief"', page)
        self.assertIn("renderDecisionBrief", script)
        self.assertIn("formatAttachments", script)
        self.assertIn("new_product_development", script)

        for private_field in (
            "runtime_cards", "private_context", "knowledge_cards",
            "placeholder_mapping", "card_id", "snapshot_id", "vault_id", "<EMAIL_",
        ):
            with self.subTest(private_field=private_field):
                self.assertNotIn(private_field, script)

    def test_popup_styles_long_analysis_output(self) -> None:
        page = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        styles = "\n".join((
            (EXTENSION / "popup.css").read_text(encoding="utf-8"),
            (EXTENSION / "shared" / "analysis_components.css").read_text(encoding="utf-8"),
        ))

        self.assertIn('class="analysis-surface"', page)
        self.assertIn('class="analysis-list-field"', page)
        self.assertIn(".analysis-list", styles)
        self.assertIn(".analysis-list__item", styles)
        self.assertIn("overflow-wrap: anywhere", styles)
        self.assertIn("max-height", styles)
        self.assertNotIn("overflow-y: auto", styles)

    def test_copy_draft_button_stays_with_draft_area(self) -> None:
        page = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        styles = (EXTENSION / "popup.css").read_text(encoding="utf-8")

        self.assertIn('class="draft-section"', page)
        self.assertIn('class="draft-header"', page)
        self.assertLess(page.index('id="copy-draft-button"'), page.index('id="draft"'))
        self.assertIn(".popup-shell", styles)
        self.assertIn("display: flex", styles)
        self.assertIn("flex-direction: column", styles)
        self.assertIn(".result-section", styles)
        self.assertLess(page.index('id="work-must-check"'), page.index('class="draft-section"'))
        self.assertNotIn("overflow: hidden", styles)
        self.assertNotIn("flex: 0 0 auto", styles)

    def test_roadmap_records_next_extension_phases(self) -> None:
        roadmap = (ROOT / "docs" / "product" / "roadmap.md").read_text(encoding="utf-8")

        self.assertIn("阶段 2.1：辅助窗口体验修复", roadmap)
        self.assertIn("阶段 2.2：已实现的分析质量增强", roadmap)
        self.assertIn("阶段 2.3：附件辅助分析", roadmap)
        self.assertIn("阶段 2.4：可安装原型", roadmap)

    def test_exmail_adapter_extracts_only_after_popup_message(self) -> None:
        script = (EXTENSION / "content" / "exmail_adapter.js").read_text(encoding="utf-8")

        self.assertIn("chrome.runtime.onMessage.addListener", script)
        self.assertIn('MESSAGE_TYPE = "EXTRACT_CURRENT_EMAIL"', script)
        self.assertIn(".then(sendResponse)", script)
        self.assertIn("return true;", script)
        self.assertNotIn("setInterval(", script)
        self.assertNotIn("MutationObserver", script)

    def test_exmail_adapter_scopes_selected_text_to_message_context(self) -> None:
        script = (EXTENSION / "content" / "exmail_adapter.js").read_text(encoding="utf-8")

        self.assertIn("hasMessageContext", script)
        self.assertIn("isReadMessageDocument", script)
        self.assertIn("hasSubjectContext", script)
        self.assertIn("hasHeaderContext", script)
        self.assertIn("findKnownBodyElement", script)
        self.assertIn("getSelectedEmailContent", script)
        self.assertIn("selectionBelongsToMessage", script)
        self.assertIn("findBodyElement", script)
        self.assertIn("findAttachments", script)
        self.assertIn("attachments", script)
        self.assertIn("view.getSelection", script)
        self.assertIn("selected_text", script)
        self.assertIn('source: "dom"', script)
        self.assertNotIn("dom_fallback", script)
        self.assertIn(
            "Open a Tencent Exmail message or select email body text from that opened message first",
            script,
        )
        self.assertIn("not arbitrary webpage analysis", script)
        self.assertNotIn("selected page text", script)
        self.assertNotIn("selected text on any web page", script)
        self.assertNotIn("[role='main']", script)
        self.assertNotIn("firstText(doc, BODY_SELECTORS) ||", script)
        self.assertIn(
            "findBodyElement(doc, allowDocumentBodyFallback, suppliedBodyElement)",
            script,
        )
        self.assertIn(
            "if (!isReadMessageDocument(doc))",
            script,
        )
        self.assertIn("allowDocumentBodyFallback", script)
        self.assertIn("isLikelyExcludedUiElement", script)

    def test_exmail_adapter_does_not_log_email_body(self) -> None:
        script = (EXTENSION / "content" / "exmail_adapter.js").read_text(encoding="utf-8")

        self.assertNotIn("console.log", script)

    def test_resource_trust_has_no_extension_only_dom_markers(self) -> None:
        source = "\n".join(
            (EXTENSION / "content" / filename).read_text(encoding="utf-8")
            for filename in ("exmail_adapter.js", "current_message_collector.js")
        )

        for marker in (
            "data-email-current-message-container",
            "data-email-host-resource-controls",
            "data-email-host-attachment",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)

    def test_visible_resource_bounds_and_url_allowlist_remain_exact(self) -> None:
        collector = (
            EXTENSION / "content" / "current_message_collector.js"
        ).read_text(encoding="utf-8")

        self.assertIn("const MAX_RESOURCE_COUNT = 5;", collector)
        self.assertIn("const MAX_RESOURCE_CANDIDATES = 20;", collector)
        self.assertIn("const MAX_RESOURCE_BYTES = 10 * 1024 * 1024;", collector)
        self.assertIn("const MAX_TOTAL_RESOURCE_BYTES = 25 * 1024 * 1024;", collector)
        self.assertIn("const MAX_OVERALL_RESOURCE_TIMEOUT_MS = 20000;", collector)
        self.assertIn(
            '["/cgi-bin/download", "/cgi-bin/viewfile"]',
            collector,
        )
        self.assertIn('resolved.protocol !== "https:"', collector)
        self.assertIn("resolved.username || resolved.password", collector)

    def test_resource_discovery_is_iterative_and_bounded_before_fetch(self) -> None:
        adapter = (EXTENSION / "content" / "exmail_adapter.js").read_text(encoding="utf-8")

        self.assertIn("const MAX_RESOURCE_PHASE_MS = 20000;", adapter)
        self.assertIn("const MAX_RESOURCE_DISCOVERY_NODES = 200;", adapter)
        self.assertIn("const MAX_RESOURCE_DISCOVERY_DEPTH = 20;", adapter)
        self.assertIn("boundedResourceCandidates", adapter)
        self.assertIn("overallDeadline: resourceDeadline", adapter)
        self.assertNotIn(
            ".flatMap((subtree) => [subtree, ...descendantElements(subtree)])",
            adapter,
        )

    def test_popup_requests_current_email_after_user_click(self) -> None:
        script = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn('document.querySelector("#analyze-button").addEventListener("click"', script)
        self.assertIn("chrome.tabs.query", script)
        self.assertIn("chrome.tabs.sendMessage", script)
        self.assertIn("EXTRACT_CURRENT_EMAIL", script)
        self.assertIn("EmailAssistantApi.analyzeCurrentEmail", script)
        self.assertIn("EmailAssistantRender.renderAnalysis", script)
        self.assertIn("EmailAssistantRender.renderAttachments", script)

    def test_popup_handles_copy_draft(self) -> None:
        script = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn('document.querySelector("#copy-draft-button").addEventListener("click"', script)
        self.assertIn("navigator.clipboard.writeText", script)
        self.assertIn("No draft to copy", script)
        self.assertIn("Copy failed", script)

    def test_popup_has_user_facing_error_states(self) -> None:
        script = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn("Open a Tencent Exmail tab first", script)
        self.assertIn("Open a Tencent Exmail message or select email body text from that opened message first", script)
        self.assertIn("Local analysis service unavailable", script)
        self.assertIn("safeAnalysisErrorStatus", script)
        self.assertIn("分析未完成，请重试。", script)
        self.assertNotIn("data.error.message", script)
        self.assertIn('if (!data.analysis || typeof data.analysis !== "object")', script)
        self.assertIn("Invalid analysis response", script)

    def test_background_opens_persistent_side_panel_on_action_click(self) -> None:
        script = (EXTENSION / "background.js").read_text(encoding="utf-8")

        self.assertIn("chrome.sidePanel.setPanelBehavior", script)
        self.assertIn("openPanelOnActionClick: true", script)
        self.assertIn("chrome.runtime.onInstalled.addListener", script)
        forbidden = [
            "chrome.action.onClicked",
            "chrome.tabs",
            "chrome.scripting",
            "chrome.cookies",
            "chrome.storage",
            "fetch(",
            "XMLHttpRequest",
            "sendMail",
            "archiveMessage",
            "deleteMessage",
            "trashMessage",
            "messages.trash",
            "messages.modify",
            "moveMessage",
            "forwardMessage",
        ]
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, script)

    def test_historical_task_briefs_attribute_observations_to_prior_user_feedback(self) -> None:
        expectations = {
            "browser_extension_side_panel_task_brief.md": [
                "Prior user-reported Tencent Exmail trial feedback indicated",
            ],
            "popup_readability_and_next_phase_task_brief.md": [
                "Prior user-provided Tencent Exmail trial feedback indicated",
                "Follow-up user-provided feedback also indicated",
            ],
            "decision_brief_analysis_task_brief.md": [
                "用户此前提供的 Tencent Exmail 试用反馈指出",
            ],
        }

        for filename, required_phrases in expectations.items():
            text = (ROOT / "docs" / "operations" / filename).read_text(encoding="utf-8")
            for phrase in required_phrases:
                with self.subTest(filename=filename, phrase=phrase):
                    self.assertIn(phrase, text)

    def test_historical_task_briefs_avoid_direct_manual_validation_claims(self) -> None:
        briefs = [
            ROOT / "docs" / "operations" / "browser_extension_side_panel_task_brief.md",
            ROOT / "docs" / "operations" / "popup_readability_and_next_phase_task_brief.md",
            ROOT / "docs" / "operations" / "decision_brief_analysis_task_brief.md",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in briefs)

        for unsupported_claim in (
            "Manual Tencent Exmail testing showed",
            "A follow-up manual test also showed",
            "真实 Tencent Exmail 测试中",
        ):
            with self.subTest(unsupported_claim=unsupported_claim):
                self.assertNotIn(unsupported_claim, combined)

    def test_side_panel_docs_describe_persistent_behavior(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        setup = (ROOT / "docs" / "operations" / "setup_checklist.md").read_text(encoding="utf-8")
        testing = (ROOT / "docs" / "operations" / "testing_checklist.md").read_text(encoding="utf-8")

        self.assertIn("persistent side panel", readme)
        self.assertIn("clicking outside the assistant does not close it", readme)
        self.assertIn("persistent side panel", setup)
        self.assertIn("side panel remains open", testing)

    def test_browser_extension_has_no_secret_or_openai_markers(self) -> None:
        forbidden = [
            "OPENAI_API_KEY",
            "api.openai.com",
            "/v1/responses",
            "/v1/chat/completions",
            "new OpenAI",
            "process.env",
            ".env",
            "sk-",
        ]

        for path in EXTENSION.rglob("*"):
            if path.is_dir() or path.suffix not in {".js", ".html", ".json", ".css"}:
                continue
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=path.relative_to(ROOT), marker=marker):
                    self.assertNotIn(marker, text)

    def test_browser_extension_has_no_high_risk_mailbox_actions(self) -> None:
        forbidden = [
            "sendMail",
            "gmail.users.messages.send",
            "archiveMessage",
            "deleteMessage",
            "trashMessage",
            "messages.trash",
        ]

        for path in EXTENSION.rglob("*.js"):
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=path.relative_to(ROOT), marker=marker):
                    self.assertNotIn(marker, text)

    def test_readme_documents_browser_extension_usage(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("frontend/browser_extension", readme)
        self.assertIn("exmail.qq.com", readme)
        self.assertIn("Load unpacked", readme)
        self.assertIn("start_local_service.cmd", readme)
        self.assertNotIn("浏览器扩展路线，需要后续单独确认", readme)

    def test_operations_docs_document_extension_setup_and_testing(self) -> None:
        setup = (ROOT / "docs" / "operations" / "setup_checklist.md").read_text(encoding="utf-8")
        testing = (ROOT / "docs" / "operations" / "testing_checklist.md").read_text(encoding="utf-8")
        structure = (ROOT / "docs" / "operations" / "project_structure.md").read_text(encoding="utf-8")

        self.assertIn("frontend/browser_extension", setup)
        self.assertIn("Load unpacked", setup)
        self.assertIn("Tencent Exmail", testing)
        self.assertIn("message-scoped selected-text fallback", testing)
        self.assertIn("frontend/browser_extension", structure)
        self.assertNotIn("当前正式邮箱前端路线尚未选择", structure)

    def test_tencent_exmail_task_brief_exists(self) -> None:
        brief = ROOT / "docs" / "operations" / "tencent_exmail_browser_extension_task_brief.md"

        self.assertTrue(brief.exists())
        text = brief.read_text(encoding="utf-8")
        self.assertIn("Tencent Exmail", text)
        self.assertIn("https://exmail.qq.com/*", text)
        self.assertIn("http://127.0.0.1:8765/api/analyze-current-email", text)
        self.assertIn("Selected-text fallback", text)
        self.assertIn("No browser storage of real email bodies", text)
        self.assertIn("python -m unittest discover -s tests", text)
        self.assertIn("scripts/maintenance_scan.py", text)
        self.assertIn("No automatic send", text)
        self.assertIn("No mailbox account integration", text)

    def test_project_status_log_reflects_selected_extension_route(self) -> None:
        status_log = (ROOT / "docs" / "operations" / "project_status_log.md").read_text(encoding="utf-8")

        self.assertIn("Tencent Exmail Chrome / Edge 浏览器扩展", status_log)
        self.assertNotIn("单独确认下一阶段正式邮箱前端路线", status_log)


if __name__ == "__main__":
    unittest.main()
