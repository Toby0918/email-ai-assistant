"""Exercise the independently started application's public request interface."""
import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from desktop_app.runtime import DesktopRuntime
from desktop_app.attachments import attachment_payload


class DesktopRuntimeTests(unittest.TestCase):
    def test_click_analysis_persists_across_restart_without_old_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"EMAIL_AGENT_LLM_PROVIDER": "openai", "OPENAI_API_KEY": "synthetic-not-used"}):
                runtime = DesktopRuntime(Path(directory), port=0)
                runtime.start()
                try:
                    with urllib.request.urlopen(runtime.url + "/api/health") as response:
                        self.assertTrue(json.load(response)["ok"])
                    self.assertEqual(runtime.provider, "disabled")
                    rejected = runtime.analyze({"subject": "Synthetic", "from": "buyer@example.test", "body_text": "Please confirm delivery."})
                    self.assertEqual(rejected["error"]["code"], "USER_ACTION_REQUIRED")
                    result = runtime.analyze({"subject": "Delivery", "from": "buyer@example.test", "body_text": "Please confirm delivery date for this order.", "user_confirmed": True})
                    self.assertTrue(result["ok"])
                    self.assertTrue(result["analysis"]["reply_draft"]["needs_human_review"])
                    first_id = result["saved_id"]
                finally:
                    runtime.close()
                second = DesktopRuntime(Path(directory), port=0)
                second.start()
                try:
                    result = second.analyze({"subject": "Delivery", "from": "buyer@example.test", "body_text": "Please confirm delivery date for this order.", "user_confirmed": True})
                    self.assertGreater(result["saved_id"], first_id)
                finally:
                    second.close()

    def test_attachment_bytes_require_click_and_limits_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "selected.pdf"
            file.write_bytes(b"%PDF-synthetic")
            with patch.object(Path, "open", side_effect=AssertionError("Read before click")):
                with self.assertRaises(ValueError):
                    attachment_payload((file,), user_confirmed=False)
            self.assertEqual(attachment_payload((file,), user_confirmed=True)[0]["type"], "pdf")
            with self.assertRaises(ValueError):
                attachment_payload((file,) * 6, user_confirmed=True)


if __name__ == "__main__":
    unittest.main()
