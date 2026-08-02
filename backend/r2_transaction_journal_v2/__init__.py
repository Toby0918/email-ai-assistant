"""Unified R2 journal contracts, beginning with the reviewed genesis."""

from .errors import JournalGenesisError
from .genesis import R2JournalGenesisV2

__all__ = ["JournalGenesisError", "R2JournalGenesisV2"]
