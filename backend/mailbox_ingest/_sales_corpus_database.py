"""SQLite connection and exact-schema helpers for the sales corpus."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ._sales_corpus_common import SalesCorpusIndexError


@contextmanager
def connection(path: Path, *, create: bool = False) -> Iterator[sqlite3.Connection]:
    if create:
        selected = sqlite3.connect(path, timeout=5)
    else:
        selected = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=rw", uri=True, timeout=5,
        )
    try:
        selected.execute("PRAGMA foreign_keys=ON")
        selected.execute("BEGIN IMMEDIATE")
        yield selected
        selected.commit()
    except Exception:
        selected.rollback()
        raise
    finally:
        selected.close()


def schema_rows(
    selected: sqlite3.Connection,
) -> tuple[tuple[object, ...], ...]:
    return tuple(selected.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
    ))


def require_schema(
    selected: sqlite3.Connection, schema: tuple[str, ...],
) -> None:
    expected = sqlite3.connect(":memory:")
    try:
        for statement in schema:
            expected.execute(statement)
        expected_rows = schema_rows(expected)
    finally:
        expected.close()
    if (
        schema_rows(selected) != expected_rows
        or selected.execute("PRAGMA user_version").fetchone() != (1,)
    ):
        raise SalesCorpusIndexError("sales_corpus_schema_invalid")


def count(selected: sqlite3.Connection, table: str) -> int:
    if table not in {
        "source_aliases", "pairs", "attachment_blobs", "attachment_bindings",
    }:
        raise SalesCorpusIndexError()
    return selected.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


__all__ = ["connection", "count", "require_schema", "schema_rows"]
