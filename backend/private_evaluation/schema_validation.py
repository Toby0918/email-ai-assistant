"""Bounded primitive validators for private evaluation schema values."""

from __future__ import annotations

import re
import uuid
from typing import Any

from backend.private_knowledge.entity_patterns import PATTERNS
from backend.private_knowledge.residual_scanner import scan_residuals

from .errors import PrivateEvaluationError


_UUID_TEXT = re.compile(
    r"(?i)(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}(?![0-9a-f])"
)
_TASK4_PLACEHOLDER_TYPES = frozenset(kind for kind, _pattern in PATTERNS) | {
    "PERSON", "ORGANIZATION",
}
_CANONICAL_PLACEHOLDER = re.compile(r"<([A-Z][A-Z_]*)_([1-9][0-9]*)>")
_ANGLE_TOKEN = re.compile(r"<[^<>\r\n]{0,100}>")
_PLACEHOLDER_FRAGMENT = re.compile(
    r"(?i)(?:<\s*)?[a-z][a-z_]{1,40}[-_]\d{1,12}(?:\s*>)?"
)
_PRIVATE_IDENTIFIER = re.compile(
    r"(?i)(?<!\w)(?:(?:vault|authority|card|message|attachment|source|private)"
    r"[_-](?:id|ref|key|record|locator)|actor(?:[_-](?:id|ref)|[-_:][a-z0-9][a-z0-9-]{2,}))(?!\w)"
)
_RESTORATION_HINT = re.compile(
    r"(?i)(?:restore|recover|replace).{0,30}(?:original|placeholder|mapping|value)"
    r"|(?:恢复|还原|替换).{0,20}(?:原始|占位符|映射|值)"
)
_CJK_TOKEN = re.compile(r"(?<![一-鿿])([一-鿿]{2,3})(?![一-鿿])")
_COMMON_SURNAMES = frozenset(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢邹喻柏窦章苏潘葛范彭郎鲁韦马方余任袁柳唐薛雷贺倪汤殷罗郝安乐傅齐康顾孟黄穆萧姚汪毛米明宋熊舒祝董梁杜席季贾江郭梅林钟徐高夏蔡田胡霍万柯卢房丁邓洪左石崔龚程陆翁耿宁武刘龙叶白蒲古易庄阎连艾向廖段巫乌焦牛关温柴瞿谭蒙乔曾党翟聂赖卓屠牟"
)


def safe_text_tuple(value: object, maximum: int, characters: int) -> tuple[str, ...]:
    return tuple(safe_text(item, characters) for item in list_value(value, maximum))


def enum_tuple(value: object, allowed: frozenset[str], maximum: int) -> tuple[str, ...]:
    result = tuple(enum_value(item, allowed) for item in list_value(value, maximum))
    if len(result) != len(set(result)):
        invalid()
    return result


def safe_text(value: object, maximum: int) -> str:
    text = text_value(value, maximum)
    if (
        "\x00" in text or _UUID_TEXT.search(text)
        or not _evaluation_content_safe(text) or scan_residuals(text)
    ):
        invalid()
    return text


def _evaluation_content_safe(text: str) -> bool:
    for token in _ANGLE_TOKEN.finditer(text):
        parsed = _CANONICAL_PLACEHOLDER.fullmatch(token.group(0))
        if parsed is None or parsed.group(1) not in _TASK4_PLACEHOLDER_TYPES:
            return False
    scrubbed = _CANONICAL_PLACEHOLDER.sub(" ", text)
    if "<" in scrubbed or ">" in scrubbed or _PLACEHOLDER_FRAGMENT.search(scrubbed):
        return False
    if _PRIVATE_IDENTIFIER.search(scrubbed) or _RESTORATION_HINT.search(scrubbed):
        return False
    return not any(
        token.group(1)[0] in _COMMON_SURNAMES for token in _CJK_TOKEN.finditer(scrubbed)
    )


def mapping(value: object, fields: frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        invalid()
    return value


def list_value(value: object, maximum: int) -> list[object]:
    if type(value) is not list or len(value) > maximum:
        invalid()
    return value


def text_value(value: object, maximum: int) -> str:
    if type(value) is not str or not value:
        invalid()
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        invalid()
    if len(encoded) > maximum:
        invalid()
    return value


def enum_value(value: object, allowed: frozenset[str]) -> str:
    if type(value) is not str or value not in allowed:
        invalid()
    return value


def positive_int(value: object) -> int:
    if type(value) is not int or value <= 0:
        invalid()
    return value


def uuid4_value(value: object) -> str:
    if type(value) is not str:
        invalid()
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        invalid()
    if str(parsed) != value or parsed.version != 4:
        invalid()
    return value


def invalid() -> None:
    raise PrivateEvaluationError("dataset_schema_invalid")
