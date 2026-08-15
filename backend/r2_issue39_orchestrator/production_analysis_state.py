"""Capability-free synthetic request and exact persisted-result observation."""

from __future__ import annotations

import hashlib
import json
import sqlite3


SUBJECT = "Synthetic delivery question"
SENDER = "buyer@example.test"


def synthetic_analysis_payload():
    return {
        "user_confirmed": True,
        "subject": SUBJECT,
        "from": SENDER,
        "to": ["sales@example.test"],
        "body_text": "Can you confirm a synthetic delivery window?",
    }


def matching_analysis(path, *, allow_absent=False):
    uri = path.resolve(strict=True).as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True, timeout=0)
    try:
        connection.execute("PRAGMA query_only = ON")
        rows = connection.execute(
            "SELECT id, analysis_json FROM email_analysis "
            "WHERE subject=? AND sender=? ORDER BY id",
            (SUBJECT, SENDER),
        ).fetchall()
    finally:
        connection.close()
    if not rows and allow_absent:
        return None
    if len(rows) != 1 or type(rows[0][0]) is not int or rows[0][0] <= 0:
        raise ValueError("R2_ISSUE39_VALIDATION_ROW_INVALID")
    analysis = json.loads(rows[0][1], object_pairs_hook=_strict_pairs)
    engine = analysis.get("analysis_engine")
    if type(engine) is not dict or engine.get("source") != "rule_fallback":
        raise ValueError("R2_ISSUE39_VALIDATION_ROW_INVALID")
    return {
        "matching_rows": 1,
        "saved_id": rows[0][0],
        "result_fingerprint": hashlib.sha256(
            json.dumps(
                analysis, ensure_ascii=True, allow_nan=False, sort_keys=True,
                separators=(",", ":"),
            ).encode("ascii")
        ).hexdigest(),
    }


def _strict_pairs(pairs):
    value = {}
    for name, item in pairs:
        if name in value:
            raise ValueError("R2_ISSUE39_VALIDATION_ROW_INVALID")
        value[name] = item
    return value
