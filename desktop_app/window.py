"""Native input, analysis and human-reviewed draft window."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .attachments import attachment_payload
from .presentation import advice_text, details_text
from .settings import DISCLOSURE, show_settings


class DesktopWindow:
    def __init__(self, root: tk.Tk, runtime):
        self.root, self.runtime = root, runtime
        self.paths = ()
        self.busy = False
        self.completed_analysis = None
        self._closed = False
        self._messages = queue.Queue()
        root.title("Email AI Assistant · 桌面版")
        root.geometry("1180x820")
        root.minsize(900, 650)
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TLabel", font=("Microsoft YaHei UI", 10))
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=6)
        shell = ttk.Frame(root, padding=18)
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x")
        ttk.Label(header, text="邮件处理助手", font=("Microsoft YaHei UI", 19, "bold")).pack(side="left")
        self.settings_button = ttk.Button(header, text="AI 设置", command=self.settings)
        self.settings_button.pack(side="right")
        self.mode = tk.StringVar()
        ttk.Label(shell, textvariable=self.mode, foreground="#475569").pack(anchor="w", pady=(8, 12))
        self.refresh_mode()
        columns = ttk.Panedwindow(shell, orient="horizontal")
        columns.pack(fill="both", expand=True)
        left, right = ttk.Frame(columns, padding=(0, 0, 15, 0)), ttk.Frame(columns)
        columns.add(left, weight=1)
        columns.add(right, weight=2)
        self._build_input(left)
        self._build_output(right)
        self.notice = ttk.Label(shell, text="内容仅在点击分析后处理。分析结果保存在本机；原始附件按请求临时处理。", wraplength=1080, foreground="#475569")
        self.notice.pack(fill="x", pady=(12, 4))
        self.status = tk.StringVar(value="就绪。可粘贴当前邮件，或加载示例验证运行。")
        ttk.Label(shell, textvariable=self.status, wraplength=1080).pack(fill="x")
        self._poll_id = root.after(80, self.poll)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_input(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="当前邮件", font=("Microsoft YaHei UI", 12, "bold")).pack(side="left")
        ttk.Button(top, text="加载示例", command=self.load_sample).pack(side="right")
        self.fields = {}
        for name, label in (("subject", "主题"), ("from", "发件人"), ("to", "收件人（可选）")):
            ttk.Label(parent, text=label).pack(anchor="w", pady=(6, 3))
            value = tk.StringVar()
            ttk.Entry(parent, textvariable=value).pack(fill="x")
            self.fields[name] = value
        ttk.Label(parent, text="正文 / 当前可见会话").pack(anchor="w", pady=(10, 3))
        self.body = scrolledtext.ScrolledText(parent, wrap="word", height=12, font=("Microsoft YaHei UI", 10), undo=True)
        self.body.pack(fill="both", expand=True)
        attachment_row = ttk.Frame(parent)
        attachment_row.pack(fill="x", pady=8)
        ttk.Button(attachment_row, text="选择当前邮件附件", command=self.select_files).pack(side="left")
        ttk.Button(attachment_row, text="清空", command=self.clear_files).pack(side="right")
        self.file_label = tk.StringVar(value="未选择附件 · 最多 5 个，单个 10 MiB，总计 25 MiB")
        ttk.Label(parent, textvariable=self.file_label, wraplength=350).pack(anchor="w")
        self.analyze_button = ttk.Button(parent, text="分析此邮件", command=self.analyze)
        self.analyze_button.pack(fill="x", pady=(14, 0))

    def _build_output(self, parent):
        ttk.Label(parent, text="分析与回复", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(0, 12))
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)
        advice, draft, details = (ttk.Frame(notebook, padding=10) for _ in range(3))
        notebook.add(advice, text="处理建议")
        notebook.add(draft, text="回复草稿")
        notebook.add(details, text="依据与限制")
        self.advice = self._text(advice, editable=False)
        self.draft_subject = tk.StringVar(value="尚未生成草稿")
        ttk.Label(draft, textvariable=self.draft_subject, wraplength=600).pack(anchor="w", pady=(0, 8))
        self.draft = self._text(draft, editable=True)
        self.reviewed = tk.BooleanVar(value=False)
        ttk.Checkbutton(draft, text="我已审核并修改草稿，确认可以复制", variable=self.reviewed).pack(anchor="w", pady=8)
        self.copy_button = ttk.Button(draft, text="复制已审核草稿", command=self.copy_draft)
        self.copy_button.pack(anchor="e")
        self.draft.bind("<<Modified>>", self._draft_changed)
        self.details = self._text(details, editable=False)

    @staticmethod
    def _text(parent, *, editable):
        widget = scrolledtext.ScrolledText(parent, wrap="word", font=("Microsoft YaHei UI", 10), height=12)
        widget.pack(fill="both", expand=True)
        if not editable:
            widget.configure(state="disabled")
        return widget

    @staticmethod
    def set_text(widget, value, *, editable=False):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        if not editable:
            widget.configure(state="disabled")

    def load_sample(self):
        if self.busy:
            return
        for key, value in {"subject": "Delivery date confirmation", "from": "buyer@example.test", "to": "sales@example.test"}.items():
            self.fields[key].set(value)
        self.set_text(self.body, "Please confirm delivery date for this order. Please check the production schedule before replying.", editable=True)
        self.clear_files()

    def select_files(self):
        if self.busy:
            return
        selected = filedialog.askopenfilenames(parent=self.root, title="选择当前邮件的附件", filetypes=[("受支持的附件", "*.pdf *.xlsx *.docx *.png *.jpg *.jpeg *.webp")])
        if selected:
            self.paths = tuple(Path(path) for path in selected)
            self.file_label.set("；".join(path.name for path in self.paths))

    def clear_files(self):
        if not self.busy:
            self.paths = ()
            self.file_label.set("未选择附件 · 最多 5 个，单个 10 MiB，总计 25 MiB")

    def analyze(self):
        if self.busy:
            return
        payload = {key: value.get().strip() for key, value in self.fields.items()}
        payload["body_text"] = self.body.get("1.0", "end-1c").strip()
        if not payload["subject"] or not payload["from"] or not payload["body_text"]:
            self.status.set("请填写主题、发件人和正文。")
            return
        payload["to"] = [value.strip() for value in payload["to"].split(",") if value.strip()]
        payload["user_confirmed"] = True
        self.completed_analysis = None
        self.set_text(self.advice, "正在分析当前输入…")
        self.set_text(self.details, "")
        self.set_text(self.draft, "", editable=True)
        self.draft_subject.set("正在生成草稿")
        self.reviewed.set(False)
        self.busy = True
        self.analyze_button.configure(state="disabled")
        self.settings_button.configure(state="disabled")
        self.status.set("正在处理本次点击提交的内容，请稍候…")
        threading.Thread(target=self._worker, args=(payload, self.paths), daemon=True).start()

    def _worker(self, payload, paths):
        try:
            payload["attachment_files"] = attachment_payload(paths, user_confirmed=True)
            response = self.runtime.analyze(payload)
        except (ValueError, OSError):
            response = {"ok": False, "error": {"code": "LOCAL_INPUT_OR_SERVICE_ERROR"}}
        except Exception:
            response = {"ok": False, "error": {"code": "LOCAL_ANALYSIS_ERROR"}}
        self._messages.put(response)

    def poll(self):
        try:
            response = self._messages.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.analyze_button.configure(state="normal")
            self.settings_button.configure(state="normal")
            if response.get("ok"):
                result = response["analysis"]
                self.completed_analysis = result
                self.set_text(self.advice, advice_text(result))
                self.set_text(self.details, details_text(result))
                draft = result.get("reply_draft", {})
                self.draft_subject.set(draft.get("subject", "回复草稿"))
                self.set_text(self.draft, draft.get("body", ""), editable=True)
                self.reviewed.set(False)
                engine = result.get("analysis_engine", "unknown")
                self.status.set(f"分析完成 · {engine} · 请检查依据并人工审核回复。")
            else:
                self.set_text(self.advice, "未完成分析。请检查输入、附件大小和服务状态后重试。")
                self.draft_subject.set("尚未生成草稿")
                self.status.set("分析未完成；没有可复制的新草稿。")
        if not self._closed:
            self._poll_id = self.root.after(80, self.poll)

    def _draft_changed(self, _event=None):
        if self.draft.edit_modified():
            self.reviewed.set(False)
            self.draft.edit_modified(False)

    def copy_draft(self):
        text = self.draft.get("1.0", "end-1c").strip()
        if not text or not self.reviewed.get():
            self.status.set("请先审核草稿，并勾选确认后再复制。")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set("已复制已审核草稿；请在邮箱中自行确认和发送。")

    def settings(self):
        if not self.busy:
            show_settings(self.root, self.runtime, self.refresh_mode)

    def refresh_mode(self):
        provider = self.runtime.provider
        self.mode.set("本地规则模式 · 不调用远程 AI" if provider == "disabled" else f"远程 AI：{provider} · 仅本次运行启用")
        if hasattr(self, "notice"):
            self.notice.configure(text=DISCLOSURE if provider != "disabled" else "内容仅在点击分析后处理。分析结果保存在本机；原始附件按请求临时处理。")

    def close(self):
        if self.busy:
            self.status.set("正在完成当前分析，请等待结果返回后关闭。")
            return
        self._closed = True
        self.root.after_cancel(self._poll_id)
        self.root.destroy()
