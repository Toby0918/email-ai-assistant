"""The exact four capabilities available to ManagedActivationPhase."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .receipts import (
    ConfigPublicationReceiptV1,
    CrxPublicationReceiptV1,
    ManagedRuntimeReceiptV1,
    StoppedDatabaseCopyReceiptV1,
)


@dataclass(frozen=True, slots=True, repr=False)
class RuntimePublicationAdapter:
    publish_runtime: Callable[[], ManagedRuntimeReceiptV1] = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class DatabasePublicationAdapter:
    copy_stopped_database: Callable[
        [], StoppedDatabaseCopyReceiptV1
    ] = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class ArtifactPublicationAdapter:
    publish_crx: Callable[[], CrxPublicationReceiptV1] = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class ConfigPublicationAdapter:
    publish_config: Callable[[], ConfigPublicationReceiptV1] = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class ManagedActivationAdapters:
    runtime: RuntimePublicationAdapter = field(repr=False)
    database: DatabasePublicationAdapter = field(repr=False)
    artifact: ArtifactPublicationAdapter = field(repr=False)
    config: ConfigPublicationAdapter = field(repr=False)


def has_exact_adapter_bundle(value: object) -> bool:
    return (
        type(value) is ManagedActivationAdapters
        and type(value.runtime) is RuntimePublicationAdapter
        and type(value.database) is DatabasePublicationAdapter
        and type(value.artifact) is ArtifactPublicationAdapter
        and type(value.config) is ConfigPublicationAdapter
        and callable(value.runtime.publish_runtime)
        and callable(value.database.copy_stopped_database)
        and callable(value.artifact.publish_crx)
        and callable(value.config.publish_config)
    )
