"""Fresh-process probe proving transaction bootstrap state cannot unlock."""

from __future__ import annotations

import sys

from backend.r2_transaction_process.production_v2 import main


class _PoisonBootstrap:
    def __getattribute__(self, name):
        raise AssertionError(f"bootstrap inspected {name}")


if __name__ == "__main__":
    raise SystemExit(
        main(argv=tuple(sys.argv[1:]), bootstrap=_PoisonBootstrap())
    )
