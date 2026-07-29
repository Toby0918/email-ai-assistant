"""Closed role and status enumerations for Issue #55."""

from enum import Enum


class AclRole(str, Enum):
    SOURCE_TREE = "source_tree"
    PARENT = "parent"
    FINANCE = "finance"
    PROJECT_CONTAINER = "project_container"
    RUNTIMES = "runtimes"
    LOCAL_DATA = "local_data"
    RUNTIME_TEMP = "runtime_temp"
    LOGS = "logs"
    ARTIFACTS = "artifacts"
    WORKTREES = "worktrees"
    CONFIG = "config"
    OPERATOR_PRIVATE = "operator_private"


class AclReceiptStatus(str, Enum):
    ACCEPTED = "ACL_ACCEPTED"
    REJECTED = "ACL_REJECTED"


class AclFailureCode(str, Enum):
    NONE = "NONE"
    AUTHORIZATION_REJECTED = "ACL_AUTHORIZATION_REJECTED"
    COMPATIBILITY_REJECTED = "ACL_COMPATIBILITY_REJECTED"
    DESCRIPTOR_INVALID = "ACL_DESCRIPTOR_INVALID"
    IDENTITY_CHANGED = "ACL_IDENTITY_CHANGED"
    INHERITANCE_REJECTED = "ACL_INHERITANCE_REJECTED"
    JOURNAL_INTENT_REQUIRED = "ACL_JOURNAL_INTENT_REQUIRED"
    POLICY_REJECTED = "ACL_POLICY_REJECTED"
    SCOPE_INVALID = "ACL_SCOPE_INVALID"
    INTERNAL_ERROR = "ACL_INTERNAL_ERROR"


class FilesystemMutationKind(str, Enum):
    CREATE_DIRECTORY = "create_directory"
    PUBLISH_FILE = "publish_file"
    MOVE_OBJECT = "move_object"
