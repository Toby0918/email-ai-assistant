"""Fixed one-shot CLI for historical Solo Maintainer Closure evidence rollover."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if sys.flags.isolated and str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.r2_closure_evidence_rollover import (  # noqa: E402
    ClosureEvidenceRollover,
    ClosureEvidenceRolloverError,
    RolloverErrorCode,
)
from backend.r2_solo_maintainer_closure._canonical import canonical_json  # noqa: E402


VERBS = ("run",)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in VERBS:
        return _failure(RolloverErrorCode.INVALID)
    try:
        rollover = ClosureEvidenceRollover()
        candidate = rollover.prepare()
        sys.stderr.write(candidate.to_canonical_json().decode("ascii") + "\n")
        sys.stderr.flush()
        receipt = rollover.execute(candidate.candidate_fingerprint)
        sys.stdout.write(receipt.to_canonical_json().decode("ascii") + "\n")
        return 0
    except ClosureEvidenceRolloverError as exc:
        return _failure(exc.code)
    except Exception:
        return _failure(RolloverErrorCode.INVALID)


def _failure(code: RolloverErrorCode) -> int:
    try:
        payload = canonical_json({"status": code.value}).decode("ascii")
    except Exception:
        payload = '{"status":"R2_CLOSURE_EVIDENCE_ROLLOVER_INVALID"}'
    sys.stdout.write(payload + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
