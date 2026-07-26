"""Closed public enumerations for canonical cutover receipts."""

from enum import Enum


class ReceiptType(str, Enum):
    PREFLIGHT = "PreflightReceiptV1"
    EVIDENCE = "EvidenceReceiptV1"
    ACL = "AclReceiptV1"
    REPOSITORY = "RepositoryReceiptV1"
    WORKTREE = "WorktreeReceiptV1"
    RUNTIME = "RuntimeReceiptV1"
    DATABASE = "DatabaseReceiptV1"
    ARTIFACT = "ArtifactReceiptV1"
    CONFIG = "ConfigReceiptV1"
    ACTIVATION = "ActivationReceiptV1"
    ROLLBACK = "RollbackReceiptV1"
    INCIDENT_STOP = "IncidentStopReceiptV1"


class ReceiptStatus(str, Enum):
    PREFLIGHT_ACCEPTED = "PREFLIGHT_ACCEPTED"
    PREFLIGHT_REJECTED = "PREFLIGHT_REJECTED"
    SAFE_ABORT = "SAFE_ABORT"
    EVIDENCE_ACCEPTED = "EVIDENCE_ACCEPTED"
    EVIDENCE_REJECTED = "EVIDENCE_REJECTED"
    ACL_ACCEPTED = "ACL_ACCEPTED"
    ACL_REJECTED = "ACL_REJECTED"
    REPOSITORY_ACCEPTED = "REPOSITORY_ACCEPTED"
    REPOSITORY_REJECTED = "REPOSITORY_REJECTED"
    WORKTREE_ACCEPTED = "WORKTREE_ACCEPTED"
    WORKTREE_REJECTED = "WORKTREE_REJECTED"
    RUNTIME_ACCEPTED = "RUNTIME_ACCEPTED"
    RUNTIME_REJECTED = "RUNTIME_REJECTED"
    DATABASE_ACCEPTED = "DATABASE_ACCEPTED"
    DATABASE_REJECTED = "DATABASE_REJECTED"
    ARTIFACT_ACCEPTED = "ARTIFACT_ACCEPTED"
    ARTIFACT_REJECTED = "ARTIFACT_REJECTED"
    CONFIG_ACCEPTED = "CONFIG_ACCEPTED"
    CONFIG_REJECTED = "CONFIG_REJECTED"
    ACTIVATION_ACCEPTED = "ACTIVATION_ACCEPTED"
    ACTIVATION_REJECTED = "ACTIVATION_REJECTED"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    CUTOVER_SUCCEEDED = "CUTOVER_SUCCEEDED"
    ROLLBACK_ACCEPTED = "ROLLBACK_ACCEPTED"
    ROLLBACK_REJECTED = "ROLLBACK_REJECTED"
    INCIDENT_STOP = "INCIDENT_STOP"


class ReceiptOperation(str, Enum):
    REAL_PREFLIGHT = "real_preflight"
    EVIDENCE_PUBLICATION = "evidence_publication"
    CUTOVER_EXECUTION = "cutover_execution"
    RECOVERY = "recovery"


class ReceiptProducer(str, Enum):
    REAL_PREFLIGHT = "real_preflight_composition"
    EVIDENCE_PUBLICATION = "evidence_publication_composition"
    CUTOVER_TRANSACTION = "cutover_transaction_composition"


class ReceiptSubjectRole(str, Enum):
    OPERATION = "operation"
    EVIDENCE_PACKAGE = "evidence_package"
    ACL_POLICY = "acl_policy"
    REPOSITORY_ROOT = "repository_root"
    WORKTREE_ROSTER = "worktree_roster"
    RUNTIME = "runtime"
    DATABASE = "database"
    BROWSER_EXTENSION = "browser_extension"
    CONFIG = "config"
    SERVICE = "service"
    ROLLBACK = "rollback"


class ReceiptInputRole(str, Enum):
    PROFILE = "profile"
    AUTHORIZATION = "authorization"
    POLICY = "policy"
    REVIEW = "review"
    PRIOR_RECEIPT = "prior_receipt"
    SOURCE_OBSERVATION = "source_observation"
    ARTIFACT = "artifact"
    CONFIG = "config"
    JOURNAL = "journal"
