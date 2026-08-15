"""Code-fixed Issue #39 Windows paths; no caller selection exists."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True, repr=False)
class _Issue39FixedLayoutV1:
    projects: Path = field(repr=False)
    source: Path = field(repr=False)
    legacy: Path = field(repr=False)
    container: Path = field(repr=False)
    failed: Path = field(repr=False)
    main: Path = field(repr=False)
    runtimes: Path = field(repr=False)
    local_data: Path = field(repr=False)
    runtime_temp: Path = field(repr=False)
    logs: Path = field(repr=False)
    artifacts: Path = field(repr=False)
    worktrees: Path = field(repr=False)
    config: Path = field(repr=False)
    operator_private: Path = field(repr=False)
    runtime_stage: Path = field(repr=False)
    runtime_target: Path = field(repr=False)
    database_stage: Path = field(repr=False)
    database_target: Path = field(repr=False)
    database_authority_target: Path = field(repr=False)
    crx_stage: Path = field(repr=False)
    crx_target: Path = field(repr=False)
    config_stage: Path = field(repr=False)
    config_target: Path = field(repr=False)


def fixed_layout_v1():
    projects = Path(r"D:\Projects")
    container = projects / "email_ai_assistant"
    runtimes = container / "Runtimes"
    local_data = container / "LocalData"
    artifacts = container / "Artifacts"
    config = container / "Config"
    return _Issue39FixedLayoutV1(
        projects=projects,
        source=container,
        legacy=projects / "LegacySourceAnchorV1",
        container=container,
        failed=projects / "FailedContainerV1",
        main=container / "main",
        runtimes=runtimes,
        local_data=local_data,
        runtime_temp=container / "RuntimeTemp",
        logs=container / "Logs",
        artifacts=artifacts,
        worktrees=container / "Worktrees",
        config=config,
        operator_private=container / "OperatorPrivate",
        runtime_stage=runtimes / "venv.prepare",
        runtime_target=runtimes / "venv",
        database_stage=local_data / ".database-init-authority-v1.prepare",
        database_target=local_data / "email_agent.sqlite3",
        database_authority_target=local_data / ".database-init-authority-v1",
        crx_stage=artifacts / "email-ai-assistant.crx.prepare",
        crx_target=artifacts / "email-ai-assistant.crx",
        config_stage=config / "settings.env.prepare",
        config_target=config / "settings.env",
    )
