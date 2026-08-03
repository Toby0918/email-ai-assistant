"""Read-only observation of the exact clean remote final master."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from ._canonical import canonical_json, fingerprint, is_fingerprint
from .binding import FinalMasterBindingV1
from .errors import FinalMasterClosureError


class FrozenMasterStatusV1(str, Enum):
    FROZEN_REMOTE_MASTER_VERIFIED = "FROZEN_REMOTE_MASTER_VERIFIED"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2FrozenRemoteMasterV1:
    observation_type: str
    status: FrozenMasterStatusV1
    binding: FinalMasterBindingV1 = field(repr=False)
    binding_fingerprint: str = field(repr=False)
    remote_ref_fingerprint: str = field(repr=False)
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    source_package_fingerprint: str = field(repr=False)
    runbook_fingerprint: str = field(repr=False)
    workflow_fingerprint: str = field(repr=False)
    exact_match: int
    historical_master_count: int
    dirty_path_count: int
    observation_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("R2FrozenRemoteMasterV1 is created only by the Git adapter")

    def to_mapping(self):
        result = {}
        for name in self.__dataclass_fields__:
            if name == "binding":
                continue
            item = getattr(self, name)
            result[name] = item.value if isinstance(item, Enum) else item
        return result

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def _allocate(binding, body):
    if (
        type(binding) is not FinalMasterBindingV1
        or not is_fingerprint(body.get("remote_ref_fingerprint"))
        or body != {
            "observation_type": "R2FrozenRemoteMasterV1",
            "status": FrozenMasterStatusV1.FROZEN_REMOTE_MASTER_VERIFIED.value,
            "binding_fingerprint": binding.binding_fingerprint,
            "remote_ref_fingerprint": body.get("remote_ref_fingerprint"),
            "final_commit_oid": binding.final_commit_oid,
            "final_tree_oid": binding.final_tree_oid,
            "source_package_fingerprint": binding.source_package_fingerprint,
            "runbook_fingerprint": binding.runbook_fingerprint,
            "workflow_fingerprint": binding.workflow_fingerprint,
            "exact_match": 1,
            "historical_master_count": 0,
            "dirty_path_count": 0,
        }
    ):
        raise FinalMasterClosureError()
    value = object.__new__(R2FrozenRemoteMasterV1)
    object.__setattr__(value, "binding", binding)
    for name, item in body.items():
        object.__setattr__(value, name, FrozenMasterStatusV1(item) if name == "status" else item)
    object.__setattr__(value, "observation_fingerprint",
                       fingerprint("r2-frozen-remote-master-v1", body))
    return value
