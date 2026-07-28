"""Fixed path roles accepted by the Issue #55 ACL adapter."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True, repr=False)
class AclRolePaths:
    source_tree: Path
    parent: Path
    finance: Path
    project_container: Path
    runtimes: Path
    local_data: Path
    runtime_temp: Path
    logs: Path
    artifacts: Path
    worktrees: Path
    config: Path
    operator_private: Path
