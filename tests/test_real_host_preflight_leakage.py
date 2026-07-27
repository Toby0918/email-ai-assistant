"""Content-free receipt, failure, stdout, stderr, and log guards."""

from __future__ import annotations

import contextlib
import io
import logging
import unittest

from backend.real_host_preflight import (
    CurrentTopologyCallbacks,
    run_current_topology_preflight,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.real_host_preflight_fixtures import (
    OBSERVED_AT,
    sandbox_authorization,
    topology_callbacks,
    valid_profile,
)


SENSITIVE_TOKENS = (
    r"D:\PrivateName\customer",
    "S-1-5-21-123456789",
    "(A;;FA;;;SY)",
    "private-account",
    "refs/heads/secret-customer",
    "EXCEPTION_SENTINEL",
    "MoveFile secret command",
)
FORBIDDEN_RECEIPT_KEYS = {
    "account",
    "command",
    "exception",
    "file_id",
    "git_name",
    "message",
    "path",
    "sddl",
    "sid",
}


class RealHostPreflightLeakageTests(unittest.TestCase):
    def test_success_receipt_contains_only_closed_content_free_values(
        self,
    ) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        receipt = run_current_topology_preflight(
            profile=profile,
            authorization=sandbox_authorization(
                profile,
                operation_fingerprint=operation,
            ),
            operation_fingerprint=operation,
            policy_fingerprint=opaque_fingerprint(407),
            observed_at_epoch=OBSERVED_AT,
            callbacks=topology_callbacks([]),
        )

        mapping = receipt.to_mapping()
        rendered = (
            receipt.to_canonical_json().decode("utf-8")
            + repr(receipt)
            + str(receipt)
        )
        self.assertTrue(
            FORBIDDEN_RECEIPT_KEYS.isdisjoint(_all_keys(mapping))
        )
        for token in SENSITIVE_TOKENS:
            self.assertNotIn(token, rendered)

    def test_callback_exception_is_collapsed_without_output_or_logs(
        self,
    ) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        sentinel = " ".join(SENSITIVE_TOKENS)

        def hostile_reader() -> object:
            raise RuntimeError(sentinel)

        safe = topology_callbacks([])
        callbacks = CurrentTopologyCallbacks(
            source_root=hostile_reader,
            target_parent=safe.target_parent,
            finance_root=safe.finance_root,
            target_absence=safe.target_absence,
            git=safe.git,
            acl=safe.acl,
            volume=safe.volume,
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        log_output = io.StringIO()
        handler = logging.StreamHandler(log_output)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        try:
            with (
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
                self.assertRaisesRegex(
                    ValueError,
                    "^REAL_HOST_TOPOLOGY_REJECTED$",
                ) as raised,
            ):
                run_current_topology_preflight(
                    profile=profile,
                    authorization=sandbox_authorization(
                        profile,
                        operation_fingerprint=operation,
                    ),
                    operation_fingerprint=operation,
                    policy_fingerprint=opaque_fingerprint(407),
                    observed_at_epoch=OBSERVED_AT,
                    callbacks=callbacks,
                )
        finally:
            root_logger.removeHandler(handler)
        rendered = (
            str(raised.exception)
            + repr(raised.exception)
            + stdout.getvalue()
            + stderr.getvalue()
            + log_output.getvalue()
        )
        for token in SENSITIVE_TOKENS:
            self.assertNotIn(token, rendered)


def _all_keys(value: object) -> set[str]:
    if type(value) is dict:
        result = set(value)
        for item in value.values():
            result.update(_all_keys(item))
        return result
    if type(value) is list:
        result: set[str] = set()
        for item in value:
            result.update(_all_keys(item))
        return result
    return set()


if __name__ == "__main__":
    unittest.main()
