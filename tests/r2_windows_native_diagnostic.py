"""Temporary content-free ordinal probe for the fixed Windows-native suite."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from backend.r2_ci_provenance_v2 import CiProvenanceKindV2, fixed_suite_v2


def _test_cases(value):
    for item in value:
        if isinstance(item, unittest.TestSuite):
            yield from _test_cases(item)
        else:
            yield item


def _failure_category(result, detail: str) -> int:
    if result.failures:
        return 1
    categories = (
        "CutoverHostMutationError",
        "RepositoryTransactionError",
        "ValueError",
        "RuntimeError",
    )
    return next(
        (index for index, value in enumerate(categories, start=2) if value in detail),
        6,
    )


def main() -> int:
    stream = io.StringIO()
    with redirect_stdout(stream), redirect_stderr(stream):
        names = fixed_suite_v2(CiProvenanceKindV2.WINDOWS_NATIVE)
        suite = unittest.defaultTestLoader.loadTestsFromNames(names)
        identifiers = tuple(test.id() for test in _test_cases(suite))
        result = unittest.TextTestRunner(
            stream=stream,
            verbosity=0,
            failfast=True,
        ).run(suite)
    if result.wasSuccessful():
        print(0)
        return 0
    test, detail = (result.failures + result.errors)[0]
    case = getattr(test, "test_case", test)
    try:
        ordinal = identifiers.index(case.id()) + 1
    except ValueError:
        print(250)
        return 0
    category = _failure_category(result, detail)
    print(10 + (ordinal - 1) * 6 + category)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
