"""Nominal transaction bootstrap cannot unlock Issue #110 production."""

from .production_v2 import dormant_transaction_production_v2


def execute_transaction_main_v2(argv, bootstrap):
    """Ignore all supplied state and preserve unconditional dormancy."""

    return dormant_transaction_production_v2(argv=None)
