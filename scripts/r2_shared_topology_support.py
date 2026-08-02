"""One physical synthetic topology consumed by the #74-#81 binders."""

from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from backend.cutover_contracts import CutoverProfileV1
from backend.cutover_host_mutation.acl_contracts import AclCompatibilityPolicyV1
from backend.cutover_host_mutation.windows_acl import _current_operator_sid_fingerprint
from backend.cutover_repository_transaction.synthetic_scope import (
    _bind_test_sandbox_transaction,
    _review_test_sandbox,
)
from backend.r2_config_publication import ConfigFaultSelectorV1, ManagedConfigSelectionV1
from backend.r2_config_publication.testing import bind_test_config_transaction
from backend.r2_crx_publication import CrxFaultSelectorV1
from backend.r2_crx_publication.testing import bind_test_crx_transaction
from backend.r2_database_publication import (
    DatabaseFaultSelectorV1,
    QuiescencePrerequisitesV1,
)
from backend.r2_database_publication.testing import (
    bind_test_database_transaction,
    bind_test_legacy_service_controller,
)
from backend.r2_main_publication import MainPublicationSelectorV1
from backend.r2_main_publication.testing import bind_test_main_publication
from backend.r2_main_publication.windows_dacl import capture_tree
from backend.r2_repository_manifest import ManifestSelectorV1
from backend.r2_repository_manifest.testing import bind_test_manifest_transaction
from backend.r2_runtime_publication import RuntimeFaultSelectorV1
from backend.r2_runtime_publication.testing import bind_test_runtime_transaction
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.cutover_managed_activation_fixtures import build_runtime_scenario
from tests.cutover_repository_transaction_fixtures import (
    OBSERVED_AT,
    authorization_for,
    profile_for_review,
)
from tests.r2_main_publication_fixture import build_main_publication_scenario
from tests.r2_repository_manifest_fixture import build_manifest_repository_scenario


@dataclass(slots=True)
class SharedExecutedTopology:
    root: Path
    container: Path
    runtime_executable: Path
    database_path: Path
    config_path: Path
    receipts: tuple[object, ...]
    quiescence_receipt_fingerprint: str
    quiescence_prerequisites_fingerprint: str
    execution_order: tuple[str, ...]


def execute_shared_publications(
    sandbox: Path, prerequisites: QuiescencePrerequisitesV1
) -> SharedExecutedTopology:
    if type(prerequisites) is not QuiescencePrerequisitesV1:
        raise ValueError("R2_SHARED_QUIESCENCE_PREREQUISITES_INVALID")
    root = sandbox / "issue56-synthetic-full-topology"
    root.mkdir()
    database_source = root / "legacy-analysis.sqlite3"
    _prepare_database_source(database_source)
    transactions = []
    database_transaction = _database_transaction(
        root, root / "Container", database_source, prerequisites, transactions
    )
    stopped = database_transaction.quiesce()
    order = ["quiescence:committed"]
    source = None
    try:
        main_scenario = build_main_publication_scenario(shared_root=root)
        main = _main(main_scenario)
        order.append("main:committed")
        repository = _repository(sandbox, root, main_scenario.container)
        order.append("repository:committed")
        container = root / "Container"
        carried = container / "main" / "ManagedMainRootV1"
        if (
            capture_tree(carried).items[0].observation.identity_fingerprint
            != main.main_identity_fingerprint
        ):
            raise RuntimeError("R2_SHARED_MAIN_IDENTITY_NOT_CARRIED")
        source = build_runtime_scenario(sandbox)
        database = database_transaction.execute(DatabaseFaultSelectorV1.none())
        order.append("database:committed")
        runtime, executable = _runtime(
            container, source, stopped.receipt_fingerprint, transactions
        )
        order.append("runtime:committed")
        crx = _crx(
            root, container, source.crx_source,
            stopped.receipt_fingerprint, transactions,
        )
        order.append("crx:committed")
        config = _config(
            root, container, stopped.receipt_fingerprint, transactions
        )
        order.append("config:committed")
        return SharedExecutedTopology(
            root=root,
            container=container,
            runtime_executable=executable,
            database_path=container / "LocalData" / "analysis.sqlite3",
            config_path=container / "Config" / "settings.env",
            receipts=(main, repository, runtime, database, crx, config),
            quiescence_receipt_fingerprint=stopped.receipt_fingerprint,
            quiescence_prerequisites_fingerprint=prerequisites.contract_fingerprint,
            execution_order=tuple(order),
        )
    finally:
        for transaction in transactions:
            transaction.close()
        if source is not None:
            source.close()


def _main(scenario):
    trace = None
    try:
        trace = bind_test_main_publication(scenario, observed_at_epoch=100)
        return trace.execute(MainPublicationSelectorV1.none())
    finally:
        if trace is not None:
            trace.close()
        scenario.close()


def _repository(sandbox, root, container):
    previous = tempfile.tempdir
    tempfile.tempdir = str(sandbox)
    scenario = build_manifest_repository_scenario(
        shared_root=root, shared_source=container
    )
    transaction = None
    try:
        review = _review_test_sandbox(scenario)
        policy = AclCompatibilityPolicyV1.create(
            allowed_descriptor_fingerprints=(opaque_fingerprint(750),),
            maximum_objects=10_000,
        )
        profile = _repository_profile(review, policy)
        scope = _bind_test_sandbox_transaction(
            review=review,
            profile=profile,
            authorization=authorization_for(
                profile, review.operation_fingerprint
            ),
            observed_at_epoch=OBSERVED_AT,
        )
        transaction = bind_test_manifest_transaction(
            scope=scope,
            policy=policy,
            approved_untracked=("approved-note.txt",),
            observed_at_epoch=OBSERVED_AT,
        )
        receipt = transaction.execute(ManifestSelectorV1.none())
        if not transaction.manifest_exact():
            raise RuntimeError("R2_SHARED_MANIFEST_INEXACT")
        return receipt
    finally:
        if transaction is not None:
            transaction.close()
        scenario.close()
        tempfile.tempdir = previous


def _repository_profile(review, policy):
    profile = profile_for_review(
        review, acl_policy_fingerprint=policy.policy_fingerprint
    )
    body = profile.to_mapping()
    body.pop("profile_fingerprint")
    body["operator_fingerprint"] = _current_operator_sid_fingerprint()
    return CutoverProfileV1.create(body)


def _prepare_database_source(path):
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "CREATE TABLE analyses (result_fingerprint TEXT NOT NULL)"
        )


def _database_transaction(root, container, source, prerequisites, transactions):
    state = root / "legacy-service.state"
    state.write_text("running", encoding="ascii")
    target = container / "LocalData" / "analysis.sqlite3"
    transaction = bind_test_database_transaction(
        source=source,
        staging=target.with_name("analysis.sqlite3.prepare"),
        target=target,
        journal=root / "database-publication.journal",
        prerequisites=prerequisites,
        service_controller=bind_test_legacy_service_controller(state),
    )
    transactions.append(transaction)
    return transaction


def _runtime(container, source, quiescence, transactions):
    target = container / "Runtimes" / "managed-runtime"
    transaction = bind_test_runtime_transaction(
        python_source=source.python_source,
        source_manifest=source.python_source_manifest,
        wheelhouse=source.wheelhouse,
        dependency_lock=source.dependency_lock,
        staging=target.with_name("managed-runtime.prepare"),
        target=target,
        journal=container.parent / "runtime-publication.journal",
        quiescence_receipt_fingerprint=quiescence,
    )
    transactions.append(transaction)
    receipt = transaction.execute(RuntimeFaultSelectorV1.none())
    return receipt, target / source.python_source.name


def _crx(root, container, source, quiescence, transactions):
    target = container / "Artifacts" / "email-ai-assistant.crx"
    transaction = bind_test_crx_transaction(
        source=source,
        staging=target.with_name("email-ai-assistant.crx.prepare"),
        target=target,
        journal=root / "crx-publication.journal",
        quiescence_receipt_fingerprint=quiescence,
    )
    transactions.append(transaction)
    return transaction.execute(CrxFaultSelectorV1.none())


def _config(root, container, quiescence, transactions):
    target = container / "Config" / "settings.env"
    transaction = bind_test_config_transaction(
        selection=ManagedConfigSelectionV1.create(
            {
                "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS": [
                    "example.test",
                    "internal.example",
                ],
                "EMAIL_AGENT_LOG_LEVEL": "WARNING",
            }
        ),
        staging=target.with_name("settings.env.prepare"),
        target=target,
        journal=root / "config-publication.journal",
        sqlite_path=container / "LocalData" / "analysis.sqlite3",
        attachment_temp_dir=container / "RuntimeTemp" / "attachments",
        quiescence_receipt_fingerprint=quiescence,
    )
    transactions.append(transaction)
    return transaction.execute(ConfigFaultSelectorV1.none())
