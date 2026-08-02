"""Content-free source guards for Issue #80."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_independent_audits"


class R2IndependentAuditsLeakageTests(unittest.TestCase):
    def test_package_cannot_reach_private_or_provider_surfaces(self) -> None:
        source = "\n".join(
            item.read_text(encoding="utf-8") for item in PACKAGE.glob("*.py")
        ).lower()
        for forbidden in (
            "mailbox_ingest",
            "private_knowledge",
            "migration_evidence",
            "openai",
            "deepseek",
            "requests",
            "httpx",
            "sqlite3",
            "subprocess",
            "socket",
            "registry",
            "clipboard",
            "credential",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
