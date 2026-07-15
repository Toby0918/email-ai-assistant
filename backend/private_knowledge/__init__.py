"""Isolated, synthetic-testable private company knowledge primitives."""

from .errors import PrivateKnowledgeError
from .schema import KnowledgeCardV1

__all__ = ["KnowledgeCardV1", "PrivateKnowledgeError"]
