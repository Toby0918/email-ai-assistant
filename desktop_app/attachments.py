"""Manual selection carries paths only; read bounded bytes after Analyze."""
from __future__ import annotations

import base64
from pathlib import Path

MAX_FILE = 10 * 1024 * 1024
MAX_TOTAL = 25 * 1024 * 1024
KINDS = {".pdf": "pdf", ".xlsx": "xlsx", ".docx": "docx",
         ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image"}


def attachment_payload(paths: tuple[Path, ...], *, user_confirmed: bool) -> list[dict]:
    if user_confirmed is not True:
        raise ValueError("USER_ACTION_REQUIRED")
    if len(paths) > 5:
        raise ValueError("ATTACHMENT_LIMIT")
    items = []
    total = 0
    for path in paths:
        kind = KINDS.get(path.suffix.lower())
        if kind is None:
            raise ValueError("ATTACHMENT_TYPE_UNSUPPORTED")
        with path.open("rb") as source:
            content = source.read(min(MAX_FILE, MAX_TOTAL - total) + 1)
        total += len(content)
        if len(content) > MAX_FILE or total > MAX_TOTAL:
            raise ValueError("ATTACHMENT_LIMIT")
        items.append({"filename": path.name, "type": kind, "size": len(content),
                      "content_base64": base64.b64encode(content).decode("ascii")})
    return items
