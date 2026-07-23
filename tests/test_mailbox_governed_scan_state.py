"""Capacity contracts for governed-scan encrypted checkpoints."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.mailbox_ingest.control_store import EncryptedControlStore
from backend.mailbox_ingest.governed_scan_state import advance_scan_state
from backend.mailbox_ingest.scan import ScanError


_OUTCOME_LIMIT = 20_000


def _state(outcome_count: int) -> dict[str, object]:
    folder_id = "f" * 64
    return {
        "schema_version": 3,
        "scope": "a" * 64,
        "fingerprint": "b" * 64,
        "policy": "c" * 64,
        "window_start": "2024-01-01T00:00:00+00:00",
        "window_end": "2026-01-01T00:00:00+00:00",
        "counts": {
            "processed": 0,
            "excluded_automated": 0,
            "excluded_non_sales": 0,
            "excluded_forwards": 0,
            "sensitive": 0,
            "ambiguous": 0,
            "supported_attachments": 0,
            "unsupported_attachments": 0,
        },
        "outcomes": {
            f"{index:064x}": ["non_sales", 256, 0]
            for index in range(outcome_count)
        },
        "folders": {
            folder_id: {
                "uidvalidity": 1,
                "cursor": 0,
                "processed_count": 0,
            }
        },
    }


class GovernedScanStateCapacityTests(unittest.TestCase):
    def test_maximum_checkpoint_fits_production_control_envelope(self) -> None:
        state = _state(_OUTCOME_LIMIT)
        with tempfile.TemporaryDirectory() as directory:
            with EncryptedControlStore(
                Path(directory),
                vault_id="00000000-0000-4000-8000-000000000001",
                master_key=b"K" * 32,
            ) as control:
                control.write("scan-state", state)
                restored = control.read("scan-state")

        self.assertEqual(len(restored["outcomes"]), _OUTCOME_LIMIT)

    def test_new_token_past_capacity_fails_before_checkpoint_mutation(self) -> None:
        state = _state(_OUTCOME_LIMIT)
        folder = state["folders"]["f" * 64]
        before = dict(folder)

        with self.assertRaisesRegex(ScanError, "scan_state_capacity_exceeded"):
            advance_scan_state(
                state,
                folder,
                1,
                "automated",
                0,
                0,
                "f" * 63 + "e",
            )

        self.assertEqual(folder, before)
        self.assertNotIn("f" * 63 + "e", state["outcomes"])


if __name__ == "__main__":
    unittest.main()
