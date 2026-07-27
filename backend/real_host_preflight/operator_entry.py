"""Default-locked Issue #53 operator entry before future Issue #39."""

from .contracts_bridge import default_operator_entry


def real_host_preflight_operator_entry():
    """Expose no argument, authorization, callback, path, or command seam."""

    return default_operator_entry()
