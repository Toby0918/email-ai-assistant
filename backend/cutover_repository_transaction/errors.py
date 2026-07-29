"""Fixed failures for the repository transaction boundary."""


class RepositoryTransactionError(Exception):
    """Content-free repository transaction failure."""

    def __repr__(self) -> str:
        return "RepositoryTransactionError()"
