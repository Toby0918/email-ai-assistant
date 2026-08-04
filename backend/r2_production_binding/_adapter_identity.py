"""Path-independent source identity for reviewed production adapter types."""

from __future__ import annotations

import hashlib
import inspect
import sys

from .errors import ProductionBindingError
from .vocabulary import (
    ProductionCommandV2,
    authority_domain_for_command_v2,
)


def production_adapter_fingerprint_v1(command, adapter_type):
    """Commit one command and domain to an exact adapter type implementation."""
    try:
        if type(command) is not ProductionCommandV2 or type(adapter_type) is not type:
            raise ProductionBindingError()
        module = sys.modules.get(adapter_type.__module__)
        if module is None or vars(module).get(adapter_type.__name__) is not adapter_type:
            raise ProductionBindingError()
        source = inspect.getsource(module).encode("utf-8")
        domain = authority_domain_for_command_v2(command)
        body = b"\0".join(
            (
                b"r2-production-adapter-v1",
                command.value.encode("ascii"),
                domain.value.encode("ascii"),
                adapter_type.__module__.encode("utf-8"),
                adapter_type.__qualname__.encode("utf-8"),
                hashlib.sha256(source).digest(),
            )
        )
        return hashlib.sha256(body).hexdigest()
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None
