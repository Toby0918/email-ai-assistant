"""Nominal evidence bootstrap cannot unlock Issue #110 production."""

from .production_v2 import dormant_evidence_production_v2


def execute_evidence_main_v2(argv, bootstrap):
    """Ignore all supplied state and preserve unconditional dormancy."""

    return dormant_evidence_production_v2(argv=None)
