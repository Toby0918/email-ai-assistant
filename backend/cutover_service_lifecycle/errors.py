"""Fixed content-free errors for the Issue #58 lifecycle."""


class ServiceLifecycleError(Exception):
    """Reject invalid lifecycle evidence without host details."""
