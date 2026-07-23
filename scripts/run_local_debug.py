"""Run the local first-version assistant server."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.email_agent.config import (
    build_standalone_verification_config,
    load_config,
)
from backend.email_agent.logging_config import configure_logging
from backend.email_agent.server import run_server, validate_local_server_host
from backend.private_knowledge.runtime_bootstrap import load_configured_runtime_cards
from backend.project_layout import (
    OperationalLayout,
    RepositoryPlacement,
    StandaloneStateKind,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database", default=None)
    parser.add_argument("--standalone-state-root", default=None)
    return parser.parse_args()


def _run_configured(args: argparse.Namespace, host: str) -> None:
    config = load_config()
    configure_logging(
        config.log_level,
        log_file=ROOT / "outputs" / "local_debug_service.log",
    )
    runtime_cards = load_configured_runtime_cards(
        enabled=config.private_knowledge_enabled,
        authority_root=config.private_knowledge_authority_root,
        snapshot_path=config.private_knowledge_snapshot_path,
        project_root=ROOT,
    )
    run_server(
        host=host,
        port=args.port,
        database_path=args.database,
        config=config,
        runtime_cards=runtime_cards,
    )


def _run_standalone(args: argparse.Namespace, host: str) -> None:
    if args.database is not None:
        raise ValueError("standalone database path is derived from state root")
    placement = RepositoryPlacement.standalone(
        repository_root=ROOT,
        state_root=Path(args.standalone_state_root),
        state_kind=StandaloneStateKind.TEMPORARY,
    )
    layout = OperationalLayout.for_placement(placement)
    database_path = layout.data_root / "email_agent.sqlite3"
    config = build_standalone_verification_config(
        sqlite_path=database_path,
        attachment_temp_dir=layout.temporary_root / "attachment_temp",
    )
    configure_logging(
        config.log_level,
        log_file=layout.log_root / "local_debug_service.log",
    )
    run_server(
        host=host,
        port=args.port,
        database_path=str(database_path),
        config=config,
        runtime_cards=(),
    )


def main() -> int:
    args = parse_args()
    host = validate_local_server_host(args.host)
    if args.standalone_state_root is not None:
        _run_standalone(args, host)
    else:
        _run_configured(args, host)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
