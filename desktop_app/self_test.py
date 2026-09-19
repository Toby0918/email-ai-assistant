"""Offline release smoke through the real window and local service."""
import json
import sqlite3
import sys
import tempfile
import time
import tkinter as tk
import urllib.request
from pathlib import Path

from .runtime import DesktopRuntime
from .window import DesktopWindow


def run_self_test(project: Path) -> dict:
    root = None
    runtime = None
    with tempfile.TemporaryDirectory(prefix="desktop-verification-", dir=project / "RuntimeTemp") as directory:
        try:
            runtime = DesktopRuntime(Path(directory), port=0)
            runtime.start()
            with urllib.request.urlopen(runtime.url + "/api/health") as response:
                assert json.load(response) == {"ok": True, "status": "ok"}
            for path in ("/", "/app.js", "/shared/render_analysis.js"):
                with urllib.request.urlopen(runtime.url + path) as response:
                    assert response.status == 200
                    assert len(response.read()) > 50
            root = tk.Tk()
            root.withdraw()
            window = DesktopWindow(root, runtime)
            window.load_sample()
            window.analyze()
            deadline = time.monotonic() + 15
            while window.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(0.02)
            assert not window.busy
            assert window.completed_analysis is not None
            assert window.completed_analysis["reply_draft"]["needs_human_review"] is True
            assert window.draft.get("1.0", "end-1c").strip()
            assert "处理结论" in window.advice.get("1.0", "end-1c")
            window.copy_draft()
            assert "请先审核" in window.status.get()
            assert runtime.provider == "disabled"
            from docx import Document
            document = Document()
            document.add_paragraph("Material: brass. Finish: chrome. MOQ: 1200 pcs.")
            document_path = Path(directory) / "synthetic-spec.docx"
            document.save(document_path)
            from .attachments import attachment_payload
            attachment_result = runtime.analyze({
                "subject": "Synthetic product specification", "from": "buyer@example.test",
                "body_text": "Please review the attached product specification.", "user_confirmed": True,
                "attachment_files": attachment_payload((document_path,), user_confirmed=True),
            })
            assert attachment_result["ok"]
            insights = attachment_result["analysis"]["attachment_insights"]
            assert len(insights) == 1 and insights[0]["status"] == "parsed"
            assert not list((Path(directory) / "attachment_temp").glob("*"))
            window.close()
            root = None
            runtime.close()
            runtime = DesktopRuntime(Path(directory), port=0)
            runtime.start()
            result = runtime.analyze({"subject": "Second synthetic request", "from": "buyer@example.test",
                                      "body_text": "Please confirm delivery date.", "user_confirmed": True})
            assert result["ok"] and result["saved_id"] >= 2
            # Libraries must survive freezing and upgrading without a provider call.
            from openai import OpenAI
            import openpyxl
            import docx
            import pypdf
            import PIL.Image
            client = OpenAI(api_key="synthetic-not-a-live-key", max_retries=0)
            client.close()
            return {"status": "PASS", "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
                    "native_window": "PASS", "sample_analysis": "PASS", "human_review_gate": "PASS",
                    "static_assets": "PASS", "restart_persistence": "PASS", "dependency_imports": "PASS",
                    "isolated_attachment_worker": "PASS", "attachment_cleanup": "PASS",
                    "provider_calls": 0, "live_mailbox_access": 0}
        finally:
            if root is not None:
                root.destroy()
            if runtime is not None:
                runtime.close()
