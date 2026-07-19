"""Pure behavior tests for current-message visible-resource classification."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = (
    ROOT
    / "frontend"
    / "browser_extension"
    / "content"
    / "exmail_visible_resource_classifier.js"
)


class BrowserExtensionVisibleResourceClassifierTests(unittest.TestCase):
    def run_node_case(self, case_name: str) -> None:
        self.assertTrue(CLASSIFIER.exists(), "visible-resource classifier is missing")
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__CLASSIFIER_PATH__, "utf8");
            const root = {};
            vm.runInNewContext(source, { window: root }, {
              filename: "exmail_visible_resource_classifier.js",
            });
            const api = root.EmailAssistantExmailVisibleResourceClassifier;
            if (!api || typeof api.classifyVisibleResource !== "function") {
              throw new Error("classifier API is unavailable");
            }

            const baseInline = Object.freeze({
              candidateKind: "inline_image",
              resourceType: "image",
              visible: true,
              currentMessageOwned: true,
              approvedUrl: true,
              ambiguousOwnership: false,
              quotedHistory: false,
              afterSignatureBoundary: false,
              repeated: false,
              width: 1280,
              height: 960,
              visualHint: "product packaging inspection photo",
              signatureContext: false,
              contactSignalCount: 0,
            });

            function classify(overrides = {}) {
              return api.classifyVisibleResource({ ...baseInline, ...overrides });
            }
            function expect(expected, overrides = {}) {
              const actual = classify(overrides);
              if (actual !== expected) {
                throw new Error(`expected ${expected}, got ${String(actual)}`);
              }
              if (typeof actual !== "string") {
                throw new Error("classification must be one internal enum string");
              }
            }

            const cases = {
              large_current_body_product_photo_is_included: () => {
                expect("inline_business_image", {
                  sourceUrl: "https://exmail.qq.com/cgi-bin/viewfile?opaque=private",
                  originalFilename: "customer-product-photo.jpg",
                  domSelector: "#private-message img:nth-child(7)",
                  credentials: "include",
                });
              },
              visible_attachment_control_is_included: () => {
                expect("visible_attachment", {
                  candidateKind: "attachment",
                  resourceType: "pdf",
                  verifiedAttachmentControl: true,
                  width: 0,
                  height: 0,
                  visualHint: "",
                });
              },
              deferred_legacy_attachment_type_is_an_internal_fact: () => {
                expect("visible_attachment", {
                  candidateKind: "attachment",
                  resourceType: "",
                  verifiedAttachmentControl: true,
                  deferredTypeValidation: true,
                  width: 160,
                  height: 24,
                  visualHint: "",
                });
                expect("rejected", {
                  candidateKind: "attachment",
                  resourceType: "",
                  verifiedAttachmentControl: true,
                  deferredTypeValidation: false,
                  width: 160,
                  height: 24,
                  visualHint: "",
                });
              },
              portrait_contact_logo_signature_is_rejected: () => {
                expect("rejected", {
                  width: 180,
                  height: 180,
                  visualHint: "staff portrait avatar beside contact logo",
                  signatureContext: true,
                  contactSignalCount: 3,
                });
              },
              corporate_wordmark_signature_is_rejected: () => {
                expect("rejected", {
                  width: 720,
                  height: 140,
                  visualHint: "corporate brand wordmark logo",
                });
              },
              contact_address_banner_signature_is_rejected: () => {
                expect("rejected", {
                  width: 900,
                  height: 150,
                  visualHint: "company contact address banner",
                  signatureContext: true,
                  contactSignalCount: 4,
                });
              },
              media_after_signature_boundary_is_rejected: () => {
                expect("rejected", { afterSignatureBoundary: true });
              },
              quoted_history_media_is_rejected: () => {
                expect("rejected", { quotedHistory: true });
              },
              repeated_image_is_rejected: () => {
                expect("rejected", { repeated: true });
              },
              logo_is_rejected: () => {
                expect("rejected", { visualHint: "supplier logo" });
              },
              avatar_is_rejected: () => {
                expect("rejected", { width: 256, height: 256, visualHint: "profile avatar" });
              },
              icon_is_rejected: () => {
                expect("rejected", { width: 96, height: 96, visualHint: "social icon" });
              },
              tracking_pixel_is_rejected: () => {
                expect("rejected", { width: 1, height: 1, visualHint: "tracking pixel" });
              },
              hidden_media_is_rejected: () => {
                expect("rejected", { visible: false });
              },
              external_source_is_rejected: () => {
                expect("rejected", { approvedUrl: false });
              },
              ambiguous_ownership_is_rejected: () => {
                expect("rejected", { ambiguousOwnership: true });
              },
              small_unlabelled_inline_image_is_rejected: () => {
                expect("rejected", { width: 200, height: 120, visualHint: "" });
              },
            };

            cases[__CASE_NAME__]();
            """
        )
        script = script.replace("__CLASSIFIER_PATH__", json.dumps(str(CLASSIFIER)))
        script = script.replace("__CASE_NAME__", json.dumps(case_name))
        result = subprocess.run(
            ["node", "-"],
            input=script,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_large_current_body_product_photo_is_included(self) -> None:
        self.run_node_case("large_current_body_product_photo_is_included")

    def test_visible_attachment_control_is_included(self) -> None:
        self.run_node_case("visible_attachment_control_is_included")

    def test_deferred_legacy_attachment_type_is_an_internal_fact(self) -> None:
        self.run_node_case("deferred_legacy_attachment_type_is_an_internal_fact")

    def test_portrait_contact_logo_signature_is_rejected(self) -> None:
        self.run_node_case("portrait_contact_logo_signature_is_rejected")

    def test_corporate_wordmark_signature_is_rejected(self) -> None:
        self.run_node_case("corporate_wordmark_signature_is_rejected")

    def test_contact_address_banner_signature_is_rejected(self) -> None:
        self.run_node_case("contact_address_banner_signature_is_rejected")

    def test_media_after_signature_boundary_is_rejected(self) -> None:
        self.run_node_case("media_after_signature_boundary_is_rejected")

    def test_quoted_history_media_is_rejected(self) -> None:
        self.run_node_case("quoted_history_media_is_rejected")

    def test_repeated_image_is_rejected(self) -> None:
        self.run_node_case("repeated_image_is_rejected")

    def test_logo_is_rejected(self) -> None:
        self.run_node_case("logo_is_rejected")

    def test_avatar_is_rejected(self) -> None:
        self.run_node_case("avatar_is_rejected")

    def test_icon_is_rejected(self) -> None:
        self.run_node_case("icon_is_rejected")

    def test_tracking_pixel_is_rejected(self) -> None:
        self.run_node_case("tracking_pixel_is_rejected")

    def test_hidden_media_is_rejected(self) -> None:
        self.run_node_case("hidden_media_is_rejected")

    def test_external_source_is_rejected(self) -> None:
        self.run_node_case("external_source_is_rejected")

    def test_ambiguous_ownership_is_rejected(self) -> None:
        self.run_node_case("ambiguous_ownership_is_rejected")

    def test_small_unlabelled_inline_image_is_rejected(self) -> None:
        self.run_node_case("small_unlabelled_inline_image_is_rejected")


if __name__ == "__main__":
    unittest.main()
