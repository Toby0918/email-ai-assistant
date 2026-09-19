"""Explicit session-only provider selection; never store a key."""
import tkinter as tk
from tkinter import messagebox, ttk

DISCLOSURE = (
    "After you click Analyze, configured remote AI providers may receive locally "
    "deidentified current visible email text and selected current-message images or "
    "files after local screening. Media pixels or document content may contain "
    "identifying information and are not guaranteed to be fully deidentified. "
    "Processing is not local-only, and no zero-retention guarantee is made."
)
PROVIDERS = {"本地规则（不调用 AI）": "disabled", "OpenAI": "openai", "DeepSeek": "deepseek"}


def show_settings(owner, runtime, on_saved):
    dialog = tk.Toplevel(owner)
    dialog.title("AI 设置 · 仅本次运行")
    dialog.transient(owner)
    dialog.resizable(False, False)
    panel = ttk.Frame(dialog, padding=24)
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text="选择分析方式", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w")
    selection = tk.StringVar(value=next(label for label, value in PROVIDERS.items() if value == runtime.provider))
    ttk.Combobox(panel, textvariable=selection, values=list(PROVIDERS), state="readonly", width=43).pack(fill="x", pady=12)
    ttk.Label(panel, text="API Key（仅保留在当前进程内存，退出后需重新输入）").pack(anchor="w")
    key = ttk.Entry(panel, show="●", width=52)
    key.pack(fill="x", pady=8)
    ttk.Label(panel, text="密钥留在本机后端，不写入配置文件。启用远程 AI 后，点击分析会向所选服务发送经筛查的内容。", wraplength=470).pack(anchor="w", pady=8)
    ttk.Label(panel, text=DISCLOSURE, wraplength=470, foreground="#475569").pack(anchor="w", pady=8)
    def save():
        try:
            runtime.configure_provider(PROVIDERS[selection.get()], key.get())
        except (ValueError, RuntimeError):
            messagebox.showerror("设置未保存", "启用远程 AI 时需要填写有效的 API Key。", parent=dialog)
            return
        key.delete(0, "end")
        dialog.destroy()
        on_saved()
    ttk.Button(panel, text="应用到本次运行", command=save).pack(anchor="e", pady=(12, 0))
    dialog.grab_set()
