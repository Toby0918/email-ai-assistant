"""Pure governed-sales policy, classification, cleaning, and pairing rules."""
from __future__ import annotations
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from email import policy as email_policy
from email.parser import BytesParser
from email.utils import getaddresses
from typing import Literal, TypeAlias
from .sales_message_primitives import (
    address as _address,
    domain as _domain,
    frame as _frame,
    has_control as _has_control,
    opaque as _opaque,
)
SalesMessageRole: TypeAlias = Literal["customer_request", "sales_reply"]
SalesMessageDecisionStatus: TypeAlias = Literal["candidate", "automated", "non_sales", "forward", "ambiguous"]
_DECISION_STATUSES = {"candidate", "automated", "non_sales", "forward", "ambiguous"}
_POLICY_KEYS = {"schema_version", "company_domain", "salesperson_allowlist"}
_FOLDER_ROLES = {"inbox", "sent", "archive", "business_custom"}
_ID_TOKEN = (r"<[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@"
             r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?>")
_ID = re.compile(_ID_TOKEN + r"\Z")
_ID_LIST = re.compile(_ID_TOKEN + r"(?:\s+" + _ID_TOKEN + r")*\Z")
_ID_FIND = re.compile(_ID_TOKEN)
_QUOTED_BOUNDARY = re.compile(r"(?:-{2,}\s*(?:original|forwarded) message\s*-{2,}|"
    r"on .+ wrote:|在.+写道[:：]|-{2,}\s*(?:原始|转发)邮件\s*-{2,})\Z", re.IGNORECASE)
_SIGNATURE_BOUNDARY = re.compile(
    r"(?:--|(?:best|kind) regards,?|regards,?|sent from my .+|此致)\Z", re.IGNORECASE)
_DISCLAIMER_BOUNDARY = re.compile(r"(?:confidentiality notice(?::.*)?|"
    r"this (?:e-?mail|message).{0,80}confidential.*|本邮件.{0,80}保密.*)\Z", re.IGNORECASE)
_NOTIFICATION_SUBJECT = re.compile(
    r"(?:automatic|automated|system) notification(?:\s*:.*)?\Z", re.IGNORECASE)
_AUTOMATED_LOCALS = {"do-not-reply", "mailer-daemon", "no-reply", "noreply",
                     "notification", "notifications"}
_AUTOMATION_HEADERS = {
    "list-id", "list-unsubscribe", "list-post", "x-auto-response-suppress",
    "x-autoreply", "x-autorespond"}
_QUOTED_HEADER_FLOWS = {
    "from": ("from", "sent", "to", "subject"),
    "发件人": ("发件人", "发送时间", "收件人", "主题")}
_QUOTED_HEADER_OPTIONAL = {"cc", "抄送"}
_MAX_QUOTED_HEADER_LINES = 8
_MAX_HEADER_BYTES, _MAX_BODY_BYTES = 256 * 1024, 4 * 1024 * 1024
class SalesMessagePolicyError(ValueError):
    def __init__(self) -> None:
        self.code = "sales_policy_invalid"
        super().__init__(self.code)
    def __repr__(self) -> str:
        return "SalesMessagePolicyError(code='sales_policy_invalid')"
@dataclass(frozen=True, slots=True, repr=False)
class SalesCorpusPolicy:
    _company_domain: str
    _salesperson_allowlist: tuple[str, ...]
    def fingerprint_material(self) -> bytes:
        canonical = _frame(self._company_domain.encode(), b"\n".join(
            item.encode() for item in self._salesperson_allowlist))
        return hashlib.sha256(b"sales-policy/v1\0" + canonical).digest()
    def __repr__(self) -> str:
        return "SalesCorpusPolicy(<redacted>)"
@dataclass(frozen=True, slots=True, repr=False)
class SalesMessageCandidate:
    role: SalesMessageRole
    trusted_internal_date: datetime
    message_identity: bytes
    reference_identities: tuple[bytes, ...]
    dedupe_material: bytes
    evidence_material: bytes
    quotation_material: bytes
    _learning_text: str
    def learning_projection(self) -> str:
        return self._learning_text
    def __repr__(self) -> str:
        return f"SalesMessageCandidate(role={self.role!r})"
@dataclass(frozen=True, slots=True, repr=False)
class SalesMessagePair:
    request: SalesMessageCandidate
    reply: SalesMessageCandidate
    dedupe_material: bytes
    def __repr__(self) -> str:
        return "SalesMessagePair(<opaque>)"
@dataclass(frozen=True, slots=True, repr=False)
class SalesMessageDecision:
    status: SalesMessageDecisionStatus
    candidate: SalesMessageCandidate | None
    def __post_init__(self) -> None:
        valid_candidate = (
            self.status == "candidate" and isinstance(self.candidate, SalesMessageCandidate)
        ) or (self.status != "candidate" and self.candidate is None)
        if self.status not in _DECISION_STATUSES or not valid_candidate:
            raise ValueError("sales_message_decision_invalid")
    def __repr__(self) -> str:
        return f"SalesMessageDecision(status={self.status!r})"
def parse_sales_corpus_policy(payload: object) -> SalesCorpusPolicy:
    try:
        if (type(payload) is not dict or set(payload) != _POLICY_KEYS
                or type(payload["schema_version"]) is not int or payload["schema_version"] != 1):
            raise ValueError
        domain = _domain(payload["company_domain"])
        raw_allowlist = payload["salesperson_allowlist"]
        if type(raw_allowlist) is not list or not 1 <= len(raw_allowlist) <= 256:
            raise ValueError
        allowlist = tuple(sorted(_address(item) for item in raw_allowlist))
        if (len(allowlist) != len(set(allowlist))
                or any(item.rsplit("@", 1)[1] != domain for item in allowlist)):
            raise ValueError
        return SalesCorpusPolicy(domain, allowlist)
    except (KeyError, TypeError, UnicodeError, ValueError):
        raise SalesMessagePolicyError() from None
def evaluate_sales_message(
    *, policy: SalesCorpusPolicy, raw_header: bytes, raw_body: bytes,
    trusted_internal_date: datetime, folder_role: str, identity_key: bytes,
) -> SalesMessageDecision:
    if not _valid_context(
        policy, raw_header, raw_body, trusted_internal_date, folder_role, identity_key,
    ):
        return SalesMessageDecision("ambiguous", None)
    header = _parse_header(raw_header)
    if header is None:
        return SalesMessageDecision("ambiguous", None)
    sender, recipients, message_id, reference, subject, automated = header
    if automated or _fixed_notification(sender, subject):
        return SalesMessageDecision("automated", None)
    try:
        body = raw_body.decode("utf-8", "strict")
    except UnicodeError:
        return SalesMessageDecision("ambiguous", None)
    if _has_control(body):
        return SalesMessageDecision("ambiguous", None)
    role = _classify(policy, sender, recipients, folder_role)
    if role is None:
        return SalesMessageDecision("non_sales", None)
    learning = _learning_projection(body)
    if not learning:
        return SalesMessageDecision("forward", None)
    recipient_value = "\n".join(sorted(recipients)).encode()
    references = () if reference is None else (reference,)
    raw_material = _frame(
        role.encode(), sender.encode(), recipient_value, message_id.encode(),
        "\n".join(references).encode(), subject.encode(),
        raw_body.replace(b"\r\n", b"\n").replace(b"\r", b"\n"),
    )
    evidence = _frame(role.encode(), sender.encode(), recipient_value,
                      learning.encode("utf-8"))
    candidate = SalesMessageCandidate(
        role, trusted_internal_date,
        _opaque(identity_key, b"message-id", message_id.encode()),
        tuple(_opaque(identity_key, b"message-id", item.encode()) for item in references if role == "sales_reply"),
        _opaque(identity_key, b"raw-message", raw_material),
        _opaque(identity_key, b"learning", evidence),
        _opaque(identity_key, b"quotation", learning.encode("utf-8")), learning,
    )
    return SalesMessageDecision("candidate", candidate)
def parse_sales_message_candidate(
    *, policy: SalesCorpusPolicy, raw_header: bytes, raw_body: bytes,
    trusted_internal_date: datetime, folder_role: str, identity_key: bytes,
) -> SalesMessageCandidate | None:
    return evaluate_sales_message(
        policy=policy, raw_header=raw_header, raw_body=raw_body,
        trusted_internal_date=trusted_internal_date, folder_role=folder_role,
        identity_key=identity_key).candidate
def pair_sales_messages(
    request: SalesMessageCandidate | None,
    reply: SalesMessageCandidate | None,
) -> SalesMessagePair | None:
    if (
        not isinstance(request, SalesMessageCandidate)
        or not isinstance(reply, SalesMessageCandidate)
        or request.role != "customer_request" or reply.role != "sales_reply"
        or reply.trusted_internal_date <= request.trusted_internal_date
        or reply.reference_identities != (request.message_identity,)
    ):
        return None
    material = hashlib.sha256(b"sales-pair/v1\0" + request.evidence_material
                              + reply.evidence_material).digest()
    return SalesMessagePair(request, reply, material)
def _valid_context(
    policy: object, header: object, body: object, when: object,
    role: object, key: object,
) -> bool:
    return (
        isinstance(policy, SalesCorpusPolicy) and type(header) is bytes
        and 0 < len(header) <= _MAX_HEADER_BYTES and type(body) is bytes
        and not any(item < 32 and item not in (9, 10, 13) for item in header)
        and len(body) <= _MAX_BODY_BYTES and isinstance(when, datetime)
        and when.tzinfo is not None and when.utcoffset() is not None
        and role in _FOLDER_ROLES and type(key) is bytes and len(key) == 32
    )
def _parse_header(
    raw: bytes,
) -> tuple[str, tuple[str, ...], str, str | None, str, bool] | None:
    try:
        message = BytesParser(policy=email_policy.default).parsebytes(raw, headersonly=True)
        if (
            message.defects or len(message.items()) > 200
            or any(getattr(value, "defects", ()) for value in message.values())
        ):
            return None
        senders = _addresses(message.get_all("from", []))
        recipients = _addresses(sum((message.get_all(name, [])
            for name in ("to", "cc", "bcc")), []))
        message_ids = _strict_ids(message.get_all("message-id", []), single=True)
        in_reply = _strict_ids(message.get_all("in-reply-to", []),
                               single=True, optional=True)
        references = _strict_ids(message.get_all("references", []), optional=True)
        subjects = message.get_all("subject", [])
        if (
            len(senders) != 1 or not recipients or message_ids is None
            or in_reply is None or references is None or len(subjects) > 1
            or (in_reply and references and in_reply[0] != references[-1])
        ):
            return None
        subject = "" if not subjects else unicodedata.normalize("NFKC", str(subjects[0])).strip()
        if _has_control(subject):
            return None
        reference = in_reply[0] if in_reply else (references[-1] if references else None)
        return senders[0], recipients, message_ids[0], reference, subject, _automated(message)
    except (TypeError, UnicodeError, ValueError):
        return None
def _addresses(values: list[object]) -> tuple[str, ...]:
    result = tuple(_address(address) for _name, address in getaddresses(values))
    if len(result) != len(set(result)) or len(result) > 100:
        raise ValueError
    return result
def _strict_ids(values: list[object], *, single: bool = False,
                optional: bool = False) -> tuple[str, ...] | None:
    if not values:
        return () if optional else None
    if len(values) != 1:
        return None
    text = str(values[0]).strip()
    if not (_ID if single else _ID_LIST).fullmatch(text):
        return None
    try:
        result = tuple(_normalize_message_id(item) for item in _ID_FIND.findall(text))
    except ValueError:
        return None
    return result if len(result) == len(set(result)) and len(result) <= 100 else None
def _normalize_message_id(value: str) -> str:
    inner = value[1:-1]
    local, raw_domain = inner.rsplit("@", 1)
    if (not 1 <= len(inner) <= 254 or local.startswith(".") or local.endswith(".")
            or ".." in local):
        raise ValueError
    return f"<{local}@{_domain(raw_domain)}>"
def _automated(message: object) -> bool:
    auto = [str(item).strip().casefold() for item in message.get_all("auto-submitted", [])]
    precedence = [str(item).strip().casefold() for item in message.get_all("precedence", [])]
    return (
        any(item != "no" for item in auto)
        or any(item in {"bulk", "list", "junk"} for item in precedence)
        or any(message.get_all(name, []) for name in _AUTOMATION_HEADERS)
    )
def _fixed_notification(sender: str, subject: str) -> bool:
    return (sender.rsplit("@", 1)[0] in _AUTOMATED_LOCALS
            or bool(_NOTIFICATION_SUBJECT.fullmatch(subject)))
def _classify(
    policy: SalesCorpusPolicy, sender: str, recipients: tuple[str, ...], role: str,
) -> SalesMessageRole | None:
    sender_domain = sender.rsplit("@", 1)[1]
    recipient_domains = {item.rsplit("@", 1)[1] for item in recipients}
    if sender_domain != policy._company_domain and role != "sent" and policy._company_domain in recipient_domains:
        return "customer_request"
    if (sender in policy._salesperson_allowlist and role == "sent"
            and recipient_domains - {policy._company_domain}):
        return "sales_reply"
    return None
def _learning_projection(body: str) -> str:
    kept: list[str] = []
    lines = tuple(unicodedata.normalize("NFKC", raw_line).strip()
        for raw_line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    for index, line in enumerate(lines):
        if (_quoted_header_boundary(lines, index) or line.startswith(">")
                or _QUOTED_BOUNDARY.fullmatch(line) or _SIGNATURE_BOUNDARY.fullmatch(line)
                or _DISCLAIMER_BOUNDARY.fullmatch(line)):
            break
        if line:
            kept.append(re.sub(r"[\t ]+", " ", line))
    return "\n".join(kept)
def _quoted_header_boundary(lines: tuple[str, ...], start: int) -> bool:
    expected = _QUOTED_HEADER_FLOWS.get(_quoted_header_label(lines[start]))
    if expected is None: return False
    state = 0
    for line in lines[start:start + _MAX_QUOTED_HEADER_LINES]:
        if not line: continue
        label = _quoted_header_label(line)
        if state == len(expected) - 1 and label in _QUOTED_HEADER_OPTIONAL: continue
        if label != expected[state]: return False
        state += 1
        if state == len(expected): return True
    return False
def _quoted_header_label(line: str) -> str | None:
    return line.partition(":")[0].strip().casefold() if ":" in line else None
__all__ = ["SalesCorpusPolicy", "SalesMessageCandidate", "SalesMessageDecision",
    "SalesMessageDecisionStatus", "SalesMessagePair", "SalesMessagePolicyError",
    "SalesMessageRole", "evaluate_sales_message", "pair_sales_messages",
    "parse_sales_corpus_policy", "parse_sales_message_candidate"]
