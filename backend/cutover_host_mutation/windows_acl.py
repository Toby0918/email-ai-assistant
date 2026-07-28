"""Stable internal import facade for the Issue #55 ACL adapter."""

from .acl_paths import AclRolePaths as _AclRolePaths
from .windows_acl_adapter import WindowsAclAdapter
from .windows_acl_factory import (
    create_test_windows_acl_adapter as _create_test_windows_acl_adapter,
    current_operator_fingerprint as _current_operator_sid_fingerprint,
)

__all__ = ["WindowsAclAdapter"]
