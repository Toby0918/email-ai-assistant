"""Fixed create-only MigrationEvidencePublicationComposition behavior."""

from __future__ import annotations

import tempfile
import threading
import unittest
from unittest import mock

from backend.cutover_composition_contracts import (
    CompositionContractError,
    CompositionStage,
)
from backend.migration_evidence_publication_composition import (
    MigrationEvidencePublicationComposition,
    MigrationEvidencePublicationRolesV1,
)
from tests.cutover_composition_binders import (
    TestOwnedCompositionScopeV1,
    bind_test_publication,
)
from tests.cutover_composition_fixtures import (
    OBSERVED_AT,
    stage_receipt,
    synthetic_context,
)


class MigrationEvidencePublicationCompositionRootTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile, self.sequence, self.binding = synthetic_context()
        self.scope = TestOwnedCompositionScopeV1.create()
        self.addCleanup(self.scope.close)
        self.review = stage_receipt(
            self.binding,
            CompositionStage.EVIDENCE_REVIEW,
            None,
            3,
        )
        self.calls = 0

    def test_exact_confirmed_review_publishes_once_create_only(self) -> None:
        composition = self._composition(
            confirmed=self.review.observation_fingerprint
        )

        published = composition.publish(self.review)

        self.assertIs(
            published.stage,
            CompositionStage.EVIDENCE_PUBLICATION,
        )
        self.assertEqual(
            published.prior_receipt_fingerprint,
            self.review.receipt_fingerprint,
        )
        self.assertEqual(self.calls, 1)
        with self.assertRaisesRegex(
            CompositionContractError,
            "^MIGRATION_EVIDENCE_PUBLICATION_COMPOSITION_REJECTED$",
        ):
            composition.publish(self.review)
        self.assertEqual(self.calls, 1)

    def test_confirmation_receipt_role_and_expiry_drift_fail_closed(self) -> None:
        wrong_confirmation = self._composition(confirmed="f" * 64)
        with self.assertRaisesRegex(
            CompositionContractError,
            "^MIGRATION_EVIDENCE_PUBLICATION_COMPOSITION_REJECTED$",
        ):
            wrong_confirmation.publish(self.review)
        self.assertEqual(self.calls, 0)

        with self.assertRaisesRegex(
            CompositionContractError,
            "^MIGRATION_EVIDENCE_PUBLICATION_COMPOSITION_REJECTED$",
        ):
            self._composition(confirmed=None)

        with self.assertRaisesRegex(
            CompositionContractError,
            "^MIGRATION_EVIDENCE_PUBLICATION_COMPOSITION_REJECTED$",
        ):
            bind_test_publication(
                scope=self.scope,
                binding=self.binding,
                authorization_sequence=self.sequence,
                roles={"publish": self._publish},
                confirmed_review_fingerprint=(
                    self.review.observation_fingerprint
                ),
                observed_at_epoch=OBSERVED_AT,
            )

        composition = self._composition(
            confirmed=self.review.observation_fingerprint
        )
        wrong = stage_receipt(
            self.binding,
            CompositionStage.HOST_BASELINE,
            None,
            2,
        )
        with self.assertRaisesRegex(
            CompositionContractError,
            "^MIGRATION_EVIDENCE_PUBLICATION_COMPOSITION_REJECTED$",
        ):
            composition.publish(wrong)
        self.assertEqual(self.calls, 0)

        _profile, expired, binding = synthetic_context(
            expires_at_epoch=OBSERVED_AT + 1
        )
        with self.assertRaisesRegex(
            CompositionContractError,
            "^MIGRATION_EVIDENCE_PUBLICATION_COMPOSITION_REJECTED$",
        ):
            bind_test_publication(
                scope=self.scope,
                binding=binding,
                authorization_sequence=expired,
                roles=MigrationEvidencePublicationRolesV1(
                    binding_fingerprint=binding.binding_fingerprint,
                    publish_confirmed_review=self._publish
                ),
                confirmed_review_fingerprint=(
                    self.review.observation_fingerprint
                ),
                observed_at_epoch=OBSERVED_AT + 1,
            )

    def test_public_constructor_is_locked(self) -> None:
        with self.assertRaises(TypeError):
            MigrationEvidencePublicationComposition()

    def test_bound_role_cannot_outlive_test_owned_scope(self) -> None:
        composition = self._composition(
            confirmed=self.review.observation_fingerprint
        )
        self.scope.close()

        with self.assertRaisesRegex(
            CompositionContractError,
            "^MIGRATION_EVIDENCE_PUBLICATION_COMPOSITION_REJECTED$",
        ):
            composition.publish(self.review)
        self.assertEqual(self.calls, 0)

    def test_scope_close_failure_is_irreversibly_inactive(self) -> None:
        child = tempfile.TemporaryDirectory()
        self.scope.own_temporary_directory(child)
        original_cleanup = tempfile.TemporaryDirectory.cleanup

        def fail_child(owner):
            if owner is child:
                raise OSError("synthetic cleanup failure")
            return original_cleanup(owner)

        try:
            with mock.patch.object(
                tempfile.TemporaryDirectory,
                "cleanup",
                fail_child,
            ), self.assertRaisesRegex(
                CompositionContractError,
                "^TEST_COMPOSITION_SCOPE_INVALID$",
            ):
                self.scope.close()
            with self.assertRaisesRegex(
                CompositionContractError,
                "^TEST_COMPOSITION_SCOPE_INVALID$",
            ):
                self.scope.require_active()
        finally:
            child.cleanup()

    def test_concurrent_close_blocks_role_before_fixture_callback(self) -> None:
        child = tempfile.TemporaryDirectory()
        self.scope.own_temporary_directory(child)
        composition = self._composition(
            confirmed=self.review.observation_fingerprint
        )
        cleanup_started = threading.Event()
        allow_cleanup = threading.Event()
        close_errors = []
        original_cleanup = tempfile.TemporaryDirectory.cleanup

        def block_child(owner):
            if owner is child:
                cleanup_started.set()
                if not allow_cleanup.wait(timeout=5):
                    raise RuntimeError("synthetic cleanup wait timeout")
            return original_cleanup(owner)

        def close_scope():
            try:
                self.scope.close()
            except Exception as error:
                close_errors.append(error)

        with mock.patch.object(
            tempfile.TemporaryDirectory,
            "cleanup",
            block_child,
        ):
            closing = threading.Thread(target=close_scope)
            closing.start()
            self.assertTrue(cleanup_started.wait(timeout=5))
            with self.assertRaisesRegex(
                CompositionContractError,
                "^MIGRATION_EVIDENCE_PUBLICATION_COMPOSITION_REJECTED$",
            ):
                composition.publish(self.review)
            self.assertEqual(self.calls, 0)
            allow_cleanup.set()
            closing.join(timeout=5)

        self.assertFalse(closing.is_alive())
        self.assertEqual(close_errors, [])

    def _composition(self, *, confirmed):
        return bind_test_publication(
            scope=self.scope,
            binding=self.binding,
            authorization_sequence=self.sequence,
            roles=MigrationEvidencePublicationRolesV1(
                binding_fingerprint=self.binding.binding_fingerprint,
                publish_confirmed_review=self._publish
            ),
            confirmed_review_fingerprint=confirmed,
            observed_at_epoch=OBSERVED_AT,
        )

    def _publish(self, review):
        self.calls += 1
        return stage_receipt(
            self.binding,
            CompositionStage.EVIDENCE_PUBLICATION,
            review,
            4,
        )


if __name__ == "__main__":
    unittest.main()
