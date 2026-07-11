"""Manifest contract tests for the Tencent Exmail browser extension."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "frontend" / "browser_extension"
MANIFEST = EXTENSION / "manifest.json"


class BrowserExtensionManifestTests(unittest.TestCase):
    def load_manifest(self) -> dict[str, object]:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_exists_and_uses_manifest_v3(self) -> None:
        manifest = self.load_manifest()

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["name"], "Email AI Assistant for Tencent Exmail")
        self.assertIn("action", manifest)

    def test_manifest_permissions_are_minimal(self) -> None:
        manifest = self.load_manifest()

        permissions = manifest.get("permissions", [])
        host_permissions = manifest.get("host_permissions", [])

        self.assertEqual(permissions, ["activeTab", "sidePanel"])
        self.assertEqual(
            host_permissions,
            [
                "https://exmail.qq.com/*",
                "http://127.0.0.1:8765/*",
            ],
        )
        self.assertNotIn("<all_urls>", json.dumps(manifest))
        self.assertNotIn("tabs", permissions)
        self.assertNotIn("storage", permissions)

    def test_manifest_uses_persistent_side_panel_instead_of_transient_popup(self) -> None:
        manifest = self.load_manifest()
        action = manifest.get("action", {})
        background = manifest.get("background", {})

        self.assertEqual(action, {"default_title": "Email AI Assistant"})
        self.assertNotIn("default_popup", json.dumps(manifest))
        self.assertEqual(manifest.get("side_panel"), {"default_path": "popup.html"})
        self.assertEqual(background, {"service_worker": "background.js"})

    def test_manifest_registers_exmail_content_adapter(self) -> None:
        manifest = self.load_manifest()
        content_scripts = manifest.get("content_scripts", [])

        self.assertEqual(len(content_scripts), 1)
        script = content_scripts[0]
        self.assertEqual(script["matches"], ["https://exmail.qq.com/*"])
        self.assertEqual(
            script["js"],
            ["content/current_message_collector.js", "content/exmail_adapter.js"],
        )
        self.assertEqual(script["run_at"], "document_idle")


if __name__ == "__main__":
    unittest.main()
