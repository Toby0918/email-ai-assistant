"""Exact workflow/action hash-lock validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ._canonical import fingerprint, sha256
from .errors import R2CiProvenanceError


_EXPECTED = {
    ".github/workflows/agent_guardrails.yml",
    ".github/workflows/cleanup_agent.yml",
    ".github/workflows/r2_provenance.yml",
}
_USES = re.compile(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)")
_PIN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
_RUNNER = re.compile(r"(?m)^\s*runs-on:\s*([^\s#]+)")


@dataclass(frozen=True, slots=True, repr=False)
class R2WorkflowLockV2:
    workflow_count: int
    action_count: int
    runner_count: int
    lock_fingerprint: str = field(repr=False)

    @classmethod
    def create(cls, *, workflows):
        try:
            normalized, actions, runners = _normalize(workflows)
            state = {
                "workflows": [
                    {"path_fingerprint": sha256(path.encode("utf-8")),
                     "byte_sha256": sha256(content)}
                    for path, content in normalized
                ],
                "actions": sorted(actions),
                "runners": sorted(runners),
            }
            return cls(len(normalized), len(actions), len(runners),
                       fingerprint("r2-workflow-action-lock-v2", state))
        except R2CiProvenanceError:
            raise
        except Exception:
            raise R2CiProvenanceError() from None


def _normalize(workflows):
    if type(workflows) is not tuple or len(workflows) != len(_EXPECTED):
        raise R2CiProvenanceError()
    if any(type(item) is not tuple or len(item) != 2 for item in workflows):
        raise R2CiProvenanceError()
    normalized = tuple(sorted(workflows))
    if {path for path, _content in normalized} != _EXPECTED:
        raise R2CiProvenanceError()
    actions, runners = [], []
    for _path, content in normalized:
        if type(content) is not bytes or not 1 <= len(content) <= 262_144:
            raise R2CiProvenanceError()
        text = content.decode("utf-8")
        if "-latest" in text or "continue-on-error: true" in text:
            raise R2CiProvenanceError()
        if "not found; skipping" in text or "if [ -f" in text:
            raise R2CiProvenanceError()
        actions.extend(_USES.findall(text))
        runners.extend(_RUNNER.findall(text))
    if len(actions) < 3 or not runners or any(not _PIN.fullmatch(item) for item in actions):
        raise R2CiProvenanceError()
    return normalized, tuple(actions), tuple(runners)
