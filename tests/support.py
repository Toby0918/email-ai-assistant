"""Shared helpers for repository guardrail tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_script_module(script: Path, module_name: str) -> ModuleType:
    # Load command-line scripts without requiring them to be packaged modules.
    spec = importlib.util.spec_from_file_location(module_name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {script.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def failure_message(what: str, fix: str, doc: str) -> str:
    return f"❌ 什么错：{what}\n✅ 怎么改：{fix}\n📖 去哪里看：{doc}"
