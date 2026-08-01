"""Fresh-console synthetic evidence publication child."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from backend.r2_evidence_process import EvidenceProcessStatus
from backend.r2_evidence_process.terminal import SystemTerminal
from tests.r2_evidence_process_fixture import create_synthetic_process


def main() -> int:
    calls = 0
    owned = None
    root = Path.cwd()
    if (root / ".r2-full-topology-sandbox").is_file():
        target = root / "published.evidence"
    else:
        owned = tempfile.TemporaryDirectory(prefix="r2-evidence-worker-")
        target = Path(owned.name) / "published.evidence"
    try:

        def publish() -> int:
            nonlocal calls
            calls += 1
            with target.open("xb") as stream:
                stream.write(b"SYNTHETIC_R2_EVIDENCE\n")
            return 1

        process = create_synthetic_process(publish)
        result = process.run(
            argv=tuple(sys.argv[1:]), terminal=SystemTerminal()
        )
        valid = (
            result.status is EvidenceProcessStatus.PUBLISHED
            and result.counts() == (1, 0, 1)
            and process.publication_acquisitions == 1
            and calls == 1
            and target.read_bytes() == b"SYNTHETIC_R2_EVIDENCE\n"
        )
        sys.stdout.write(
            f"{result.status.value} accepted={result.accepted} "
            f"rejected={result.rejected} published={result.published}\n"
        )
        sys.stdout.flush()
        return 0 if valid else 5
    finally:
        if owned is not None:
            owned.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
