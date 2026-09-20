"""Exercise the native window against its real local service, without providers."""
import tempfile
import threading
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop_app.runtime import DesktopRuntime
from desktop_app.window import DesktopWindow


class DesktopWindowTests(unittest.TestCase):
    def setUp(self):
        project = Path(__file__).resolve().parents[1]
        (project / "RuntimeTemp").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=project / "RuntimeTemp")
        self.addCleanup(self.temp.cleanup)
        self.runtime = DesktopRuntime(Path(self.temp.name), port=0)
        self.runtime.start()
        self.addCleanup(self.runtime.close)
        self.root = tk.Tk()
        self.root.withdraw()
        self.window = DesktopWindow(self.root, self.runtime)
        self.addCleanup(self.destroy_window)
        self.window.load_sample()
        self.root.update()

    def destroy_window(self):
        self.wait_for_analysis()
        self.window.close()

    def wait_for_analysis(self):
        deadline = time.monotonic() + 15
        while self.window.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.root.update()
        self.assertFalse(self.window.busy, "Local analysis did not finish")

    def analyze_sample(self):
        self.window.analyze_button.invoke()
        self.wait_for_analysis()
        self.assertIsNotNone(self.window.completed_analysis)
        self.assertTrue(self.window.draft.get("1.0", "end-1c").strip())

    def test_changing_email_invalidates_reviewed_draft(self):
        self.analyze_sample()
        self.window.reviewed.set(True)
        self.window.fields["subject"].set("A different order")
        with patch.object(self.root, "clipboard_clear") as clear, patch.object(self.root, "clipboard_append") as append:
            self.window.copy_button.invoke()
        clear.assert_not_called()
        append.assert_not_called()
        self.assertIsNone(self.window.completed_analysis)
        self.assertFalse(self.window.reviewed.get())
        self.assertEqual(self.window.draft.get("1.0", "end-1c"), "")

    def test_body_edit_before_event_delivery_blocks_copy(self):
        self.analyze_sample()
        self.window.reviewed.set(True)
        self.window.body.insert("end", " Updated order quantity: 900 pcs.")
        with patch.object(self.root, "clipboard_append") as append:
            self.window.copy_draft()
        append.assert_not_called()
        self.assertIsNone(self.window.completed_analysis)

    def test_late_result_is_discarded_after_input_changes(self):
        original_analyze = self.runtime.analyze
        release = threading.Event()

        def delayed_response(payload):
            if not release.wait(10):
                raise TimeoutError("Test did not release local service request")
            return original_analyze(payload)

        with patch.object(self.runtime, "analyze", side_effect=delayed_response):
            try:
                self.window.analyze_button.invoke()
                self.window.fields["subject"].set("A different order")
                # Even changing back cannot restore the former review/result.
                self.window.fields["subject"].set("Delivery date confirmation")
            finally:
                release.set()
            self.wait_for_analysis()
        self.assertIsNone(self.window.completed_analysis)
        self.assertEqual(self.window.draft.get("1.0", "end-1c"), "")
        self.assertIn("已丢弃旧结果", self.window.status.get())
        self.analyze_sample()

    def test_selected_xlsx_analysis_review_edit_copy_and_clear(self):
        from openpyxl import Workbook
        workbook = Workbook()
        workbook.active.append(["Product", "Synthetic faucet"])
        workbook.active.append(["Quantity", "1200 pcs"])
        workbook.active.append(["Delivery", "Not confirmed; verify before replying"])
        attachment = Path(self.temp.name) / "synthetic-order.xlsx"
        workbook.save(attachment)
        workbook.close()
        with patch("desktop_app.window.filedialog.askopenfilenames", return_value=(str(attachment),)):
            self.window.select_files()
        self.analyze_sample()
        insights = self.window.completed_analysis["attachment_insights"]
        self.assertEqual(len(insights), 1)
        self.assertEqual(insights[0]["status"], "parsed")
        self.assertIn("1200", str(insights))
        self.assertFalse(list((Path(self.temp.name) / "attachment_temp").glob("*")))
        self.window.reviewed.set(True)
        self.window.draft.insert("end", "\nI will verify the production schedule first.")
        with patch.object(self.root, "clipboard_append") as append:
            self.window.copy_draft()
        append.assert_not_called()
        self.root.update()
        self.assertFalse(self.window.reviewed.get())
        expected_draft = self.window.draft.get("1.0", "end-1c").strip()
        self.window.reviewed.set(True)
        with patch.object(self.root, "clipboard_clear") as clear, patch.object(self.root, "clipboard_append") as append:
            self.window.copy_button.invoke()
        clear.assert_called_once_with()
        append.assert_called_once_with(expected_draft)
        self.window.clear_files()
        self.assertFalse(self.window.reviewed.get())
        self.assertIsNone(self.window.completed_analysis)

    def test_selecting_another_attachment_invalidates_previous_analysis(self):
        self.analyze_sample()
        self.window.reviewed.set(True)
        with patch("desktop_app.window.filedialog.askopenfilenames", return_value=(str(Path(self.temp.name) / "new.pdf"),)):
            self.window.select_files()
        self.assertIsNone(self.window.completed_analysis)
        self.assertFalse(self.window.reviewed.get())
        self.assertEqual(self.window.draft.get("1.0", "end-1c"), "")

    def test_clipboard_failure_has_safe_status_and_keeps_draft(self):
        self.analyze_sample()
        self.window.reviewed.set(True)
        draft = self.window.draft.get("1.0", "end-1c")
        with patch.object(self.root, "clipboard_clear", side_effect=tk.TclError("private diagnostic")):
            self.window.copy_draft()
        self.assertIn("复制失败", self.window.status.get())
        self.assertNotIn("private diagnostic", self.window.status.get())
        self.assertEqual(self.window.draft.get("1.0", "end-1c"), draft)


if __name__ == "__main__":
    unittest.main()
