"""Managed resource and reviewed extension rehearsal tests."""

from __future__ import annotations

from dataclasses import fields, replace
import unittest

from backend.runtime_activation_rehearsal import (
    FAILED_RESULT,
    ManagedActivationAdapters,
    rehearse_managed_runtime_activation,
)
from backend.runtime_activation_rehearsal.adapters import (
    ArtifactDestinationEvidence,
    ArtifactPublicationEvidence,
    ArtifactSourceEvidence,
    FilesystemAdapter,
    ManagedLayoutEvidence,
    ManagedResourceEvidence,
    ReviewedArtifactEvidence,
)
from backend.runtime_activation_rehearsal.policy import (
    ManagedResourceRole,
    ManagedZone,
)
from tests.test_runtime_activation_rehearsal_runtime import _layout
from tests.test_runtime_activation_rehearsal_sqlite import _database_bundle


class RuntimeActivationRehearsalManagedZoneTests(unittest.TestCase):
    def test_operational_resources_use_exact_managed_zones(self) -> None:
        layout = _layout()
        expected_parents = {
            ManagedResourceRole.ATTACHMENT_TEMP: ManagedZone.RUNTIME_TEMP,
            ManagedResourceRole.SERVICE_LOG: ManagedZone.LOGS,
            ManagedResourceRole.PID_STATE: ManagedZone.LOGS,
            ManagedResourceRole.NON_SECRET_CONFIG: ManagedZone.CONFIG,
            ManagedResourceRole.BROWSER_EXTENSION: ManagedZone.ARTIFACTS,
        }
        zone_identities = {
            zone.role: zone.identity for zone in layout.zones
        }

        self.assertEqual(
            {resource.role for resource in layout.resources},
            set(expected_parents),
        )
        for resource in layout.resources:
            self.assertEqual(
                resource.parent_identity,
                zone_identities[expected_parents[resource.role]],
            )

    def test_wrong_resource_zone_or_secret_observation_fails_early(
        self,
    ) -> None:
        layout = _layout()
        first_resource = replace(
            layout.resources[0],
            parent_identity="zone-local_data",
        )
        cases = {
            "wrong_parent": replace(
                layout,
                resources=(first_resource,) + layout.resources[1:],
            ),
            "resource_reparse": replace(
                layout,
                resources=(
                    replace(
                        layout.resources[0],
                        has_reparse_component=True,
                    ),
                )
                + layout.resources[1:],
            ),
            "config_values": replace(
                layout,
                config_values_observed=True,
            ),
            "signing_material": replace(
                layout,
                signing_material_observed=True,
            ),
            "boolean_schema": replace(
                layout,
                schema_version=True,
            ),
        }
        for name, invalid_layout in cases.items():
            with self.subTest(name=name):
                events: list[str] = []
                adapters = _artifact_bundle(
                    events=events,
                    layout=invalid_layout,
                )

                result = rehearse_managed_runtime_activation(
                    adapters=adapters
                )

                self.assertEqual(result, FAILED_RESULT)
                self.assertEqual(events, ["filesystem.layout"])

    def test_review_precedes_create_only_artifact_publication(
        self,
    ) -> None:
        events: list[str] = []
        adapters = _artifact_bundle(events=events)

        result = rehearse_managed_runtime_activation(adapters=adapters)

        self.assertEqual(result, FAILED_RESULT)
        artifact_events = [
            event for event in events if "artifact" in event
        ]
        self.assertEqual(
            artifact_events,
            [
                "filesystem.artifact_source",
                "probe.artifact_review",
                "filesystem.artifact_publish",
                "filesystem.artifact_destination",
                "probe.artifact_destination",
                "filesystem.artifact_source",
            ],
        )
        self.assertIn("lifecycle.start", events)

    def test_artifact_mismatch_or_existing_target_fails_before_start(
        self,
    ) -> None:
        cases = {
            "source_reparse": (
                {"has_reparse_component": True},
                {},
                {},
                {},
                {},
            ),
            "source_boolean_schema": (
                {"schema_version": True},
                {},
                {},
                {},
                {},
            ),
            "review_hash": (
                {},
                {"sha256": "2" * 64},
                {},
                {},
                {},
            ),
            "boolean_sizes": (
                {"size_bytes": 1},
                {"size_bytes": True},
                {},
                {"size_bytes": True},
                {},
            ),
            "existing_target": (
                {},
                {},
                {"target_was_absent": False},
                {},
                {},
            ),
            "not_create_only": (
                {},
                {},
                {"create_only": False},
                {},
                {},
            ),
            "destination_hash": (
                {},
                {},
                {},
                {"sha256": "3" * 64},
                {},
            ),
            "probe_drift": (
                {},
                {},
                {},
                {},
                {"identity": "artifact-racer"},
            ),
        }
        for name, changes in cases.items():
            with self.subTest(name=name):
                events: list[str] = []
                adapters = _artifact_bundle(
                    events=events,
                    source_changes=changes[0],
                    review_changes=changes[1],
                    publication_changes=changes[2],
                    destination_changes=changes[3],
                    destination_probe_changes=changes[4],
                )

                result = rehearse_managed_runtime_activation(
                    adapters=adapters
                )

                self.assertEqual(result, FAILED_RESULT)
                self.assertNotIn("lifecycle.start", events)

    def test_source_race_fails_and_adapter_has_no_signing_capability(
        self,
    ) -> None:
        events: list[str] = []
        adapters = _artifact_bundle(
            events=events,
            source_after_changes={"sha256": "4" * 64},
        )

        result = rehearse_managed_runtime_activation(adapters=adapters)

        self.assertEqual(result, FAILED_RESULT)
        self.assertNotIn("lifecycle.start", events)
        capability_names = {
            field.name.lower() for field in fields(FilesystemAdapter)
        }
        for forbidden in ("sign", "pem", "key", "cert"):
            self.assertFalse(
                any(forbidden in name for name in capability_names)
            )


def _artifact_bundle(
    *,
    events: list[str],
    layout: ManagedLayoutEvidence | None = None,
    source_changes: dict[str, object] | None = None,
    review_changes: dict[str, object] | None = None,
    publication_changes: dict[str, object] | None = None,
    destination_changes: dict[str, object] | None = None,
    destination_probe_changes: dict[str, object] | None = None,
    source_after_changes: dict[str, object] | None = None,
) -> ManagedActivationAdapters:
    base = _database_bundle(events=events)
    selected_layout = layout or _layout()
    source_before = replace(
        _artifact_source(),
        **(source_changes or {}),
    )
    source_after = replace(
        source_before,
        **(source_after_changes or {}),
    )
    review = replace(_artifact_review(), **(review_changes or {}))
    publication = replace(
        _artifact_publication(),
        **(publication_changes or {}),
    )
    destination = replace(
        _artifact_destination(),
        **(destination_changes or {}),
    )
    destination_probe = replace(
        destination,
        **(destination_probe_changes or {}),
    )
    source_calls = 0

    def observe_layout() -> ManagedLayoutEvidence:
        events.append("filesystem.layout")
        return selected_layout

    def observe_source() -> ArtifactSourceEvidence:
        nonlocal source_calls
        events.append("filesystem.artifact_source")
        source_calls += 1
        return source_before if source_calls == 1 else source_after

    def reviewed_artifact() -> ReviewedArtifactEvidence:
        events.append("probe.artifact_review")
        return review

    def publish_artifact(
        approved: ReviewedArtifactEvidence,
    ) -> ArtifactPublicationEvidence:
        events.append("filesystem.artifact_publish")
        if approved != review:
            raise AssertionError("unreviewed artifact")
        return publication

    def observe_destination() -> ArtifactDestinationEvidence:
        events.append("filesystem.artifact_destination")
        return destination

    def probe_destination() -> ArtifactDestinationEvidence:
        events.append("probe.artifact_destination")
        return destination_probe

    def start(*args: object) -> object:
        events.append("lifecycle.start")
        raise RuntimeError("service boundary")

    return replace(
        base,
        filesystem=FilesystemAdapter(
            observe_layout=observe_layout,
            observe_artifact_source=observe_source,
            publish_artifact=publish_artifact,
            observe_artifact_destination=observe_destination,
        ),
        lifecycle=replace(base.lifecycle, start=start),
        probe=replace(
            base.probe,
            reviewed_artifact=reviewed_artifact,
            observe_artifact_destination=probe_destination,
        ),
    )


def _artifact_source() -> ArtifactSourceEvidence:
    return ArtifactSourceEvidence(
        schema_version=1,
        present=True,
        identity="artifact-source",
        parent_identity="synthetic-review-source",
        size_bytes=2048,
        sha256="1" * 64,
        canonical=True,
        has_reparse_component=False,
    )


def _artifact_review() -> ReviewedArtifactEvidence:
    return ReviewedArtifactEvidence(
        schema_version=1,
        approved=True,
        artifact_kind="browser_extension",
        source_identity="artifact-source",
        size_bytes=2048,
        sha256="1" * 64,
    )


def _artifact_publication() -> ArtifactPublicationEvidence:
    return ArtifactPublicationEvidence(
        schema_version=1,
        created=True,
        create_only=True,
        target_was_absent=True,
        source_identity="artifact-source",
        destination_identity="artifact-destination",
        source_sha256="1" * 64,
        destination_sha256="1" * 64,
        destination_parent_identity="resource-browser_extension",
        source_preserved=True,
        parent_has_reparse_component=False,
    )


def _artifact_destination() -> ArtifactDestinationEvidence:
    return ArtifactDestinationEvidence(
        schema_version=1,
        present=True,
        identity="artifact-destination",
        parent_identity="resource-browser_extension",
        size_bytes=2048,
        sha256="1" * 64,
        canonical=True,
        has_reparse_component=False,
    )


if __name__ == "__main__":
    unittest.main()
