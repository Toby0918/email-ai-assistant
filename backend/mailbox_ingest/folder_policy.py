"""Fail-closed folder classification with opaque identifiers."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field


class FolderPolicyError(ValueError):
    def __init__(self, code: str = "folder_policy_invalid") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class RawFolder:
    flags: tuple[str, ...]
    mailbox: str | bytes = field(repr=False)


@dataclass(frozen=True)
class SelectedFolder:
    mailbox: str = field(repr=False)
    role: str
    opaque_folder_id: str

    def __repr__(self) -> str:
        return (
            "SelectedFolder("
            f"role={self.role!r}, opaque_folder_id={self.opaque_folder_id!r})"
        )


_SPECIAL_ROLES = {
    "\\inbox": "inbox",
    "\\sent": "sent",
    "\\sentmail": "sent",
    "\\archive": "archive",
}
_EXCLUDED_FLAGS = {"\\drafts", "\\trash", "\\junk", "\\spam"}
_EXCLUDED_WORDS = {
    "draft", "trash", "junk", "spam", "deleted", "recycle",
    "hr", "human resources", "payroll", "salary", "medical", "health",
    "credential", "password", "security incident", "security incidents",
    "草稿", "垃圾", "已删除", "人事", "薪资", "医疗", "凭据", "安全事件",
}


def select_mail_folders(
    folders: tuple[RawFolder, ...] | list[RawFolder],
    *,
    hmac_key: bytes,
) -> tuple[SelectedFolder, ...]:
    if type(hmac_key) is not bytes or len(hmac_key) < 32:
        raise FolderPolicyError()
    selected: list[SelectedFolder] = []
    seen_mailboxes: set[str] = set()
    seen_special: set[str] = set()
    for raw in folders:
        if not isinstance(raw, RawFolder):
            raise FolderPolicyError()
        mailbox = _decode_mailbox(raw.mailbox)
        normalized = mailbox.casefold()
        if normalized in seen_mailboxes:
            raise FolderPolicyError("folder_duplicate")
        seen_mailboxes.add(normalized)
        flags = {_normalize_flag(flag) for flag in raw.flags}
        roles = {_SPECIAL_ROLES[flag] for flag in flags if flag in _SPECIAL_ROLES}
        excluded_by_flag = bool(flags & _EXCLUDED_FLAGS)
        if roles and excluded_by_flag or len(roles) > 1:
            raise FolderPolicyError("folder_conflict")
        if excluded_by_flag or _is_sensitive_name(normalized):
            continue
        role = next(iter(roles), "business_custom")
        if role != "business_custom":
            if role in seen_special:
                raise FolderPolicyError("folder_duplicate")
            seen_special.add(role)
        opaque = hmac.new(
            hmac_key,
            b"mailbox-folder/v1\0" + mailbox.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        selected.append(SelectedFolder(mailbox, role, opaque))
    if not selected:
        raise FolderPolicyError("no_eligible_folder")
    return tuple(sorted(selected, key=lambda item: (item.role, item.opaque_folder_id)))


def _decode_mailbox(value: str | bytes) -> str:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="strict")
        except UnicodeError:
            raise FolderPolicyError("folder_decode_failed") from None
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        raise FolderPolicyError("folder_decode_failed")
    return value


def _normalize_flag(value: object) -> str:
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        raise FolderPolicyError("folder_flag_invalid")
    return value.casefold()


def _is_sensitive_name(normalized: str) -> bool:
    padded = f" {normalized.replace('/', ' ').replace('_', ' ').replace('-', ' ')} "
    return any(f" {word} " in padded for word in _EXCLUDED_WORDS)


__all__ = [
    "FolderPolicyError",
    "RawFolder",
    "SelectedFolder",
    "select_mail_folders",
]
