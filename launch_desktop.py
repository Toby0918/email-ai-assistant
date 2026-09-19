"""Windowed executable entry point. All application writes stay in this project."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    from desktop_app.runtime import DesktopRuntime, default_data_root, project_root
    project = project_root()
    for folder in ("RuntimeTemp", "Data", "Logs", "Build"):
        (project / folder).mkdir(exist_ok=True)
    os.environ["TEMP"] = str(project / "RuntimeTemp")
    os.environ["TMP"] = str(project / "RuntimeTemp")
    import tempfile
    tempfile.tempdir = str(project / "RuntimeTemp")
    from backend.email_agent.logging_config import configure_logging
    configure_logging(log_file=project / "Logs" / "application.log")
    if sys.argv[1:] == ["--self-test"]:
        from desktop_app.self_test import run_self_test
        try:
            report = run_self_test(project)
        except Exception:
            report = {"status": "FAIL", "code": "DESKTOP_SELF_TEST_FAILED"}
        (project / "Build" / "desktop-self-test.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 0 if report["status"] == "PASS" else 1
    if sys.argv[1:]:
        return 2
    import tkinter as tk
    from tkinter import messagebox
    from desktop_app.window import DesktopWindow
    root = tk.Tk()
    root.withdraw()
    runtime = DesktopRuntime(default_data_root())
    try:
        runtime.start()
    except Exception:
        messagebox.showerror("无法启动", "本地服务未能启动。请检查项目目录可写，并确认 8765 端口未被其他程序占用。", parent=root)
        root.destroy()
        return 1
    try:
        DesktopWindow(root, runtime)
        root.deiconify()
        root.mainloop()
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
