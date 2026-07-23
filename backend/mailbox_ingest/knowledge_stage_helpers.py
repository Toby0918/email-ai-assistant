"""Small validation helpers for private knowledge staging."""

from __future__ import annotations


def filenames(attachments: object) -> list[str]:
    result: list[str] = []
    for item in attachments:
        if not isinstance(item, dict):
            raise ValueError
        filename = item.get("filename")
        if isinstance(filename, str) and filename:
            result.append(filename[:500])
    return result


def conversation_bucket(count: int) -> str:
    if count <= 1:
        return "1"
    if count == 2:
        return "2"
    if count <= 5:
        return "3-5"
    return "6-10" if count <= 10 else "11+"


def counterparty_bucket(count: int) -> str:
    if count <= 1:
        return "1"
    if count <= 3:
        return "2-3"
    return "4-10" if count <= 10 else "11+"
