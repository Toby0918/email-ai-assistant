"""Run the local first-version assistant server."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.email_agent.server import run_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    # The local debug server binds to loopback unless the caller opts otherwise.
    run_server(host=args.host, port=args.port, database_path=args.database)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
