"""Fixed read-only Git manifest observations over the bound runner."""

from __future__ import annotations


def tracked_files(runner, repository) -> tuple[str, ...]:
    return _paths(
        runner._run(repository, ("ls-files", "-z", "--cached"))
    )


def untracked_files(runner, repository) -> tuple[str, ...]:
    return _paths(
        runner._run(
            repository,
            ("ls-files", "-z", "--others", "--exclude-standard"),
        )
    )


def ignored_files(runner, repository) -> tuple[str, ...]:
    return _paths(
        runner._run(
            repository,
            (
                "ls-files",
                "-z",
                "--others",
                "--ignored",
                "--exclude-standard",
            ),
        )
    )


def _paths(payload: bytes) -> tuple[str, ...]:
    try:
        values = tuple(
            field.decode("utf-8", "strict")
            for field in payload.split(b"\0")
            if field
        )
    except UnicodeError:
        raise ValueError("repository_manifest_git_observation_invalid") from None
    if len(values) != len(set(value.casefold() for value in values)):
        raise ValueError("repository_manifest_git_observation_invalid")
    return tuple(sorted(values, key=str.casefold))
