"""Nominal preflight bootstrap cannot unlock Issue #110 production."""

from .production_v2 import dormant_preflight_production_v2


def execute_preflight_main_v2(argv, bootstrap):
    """Ignore all supplied state and preserve unconditional dormancy."""

    return dormant_preflight_production_v2(argv=None)
