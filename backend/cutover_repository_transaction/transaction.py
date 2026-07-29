"""Public synthetic-only transaction entry points."""

from __future__ import annotations

from .forward import _run_forward
from .reverse import _run_reverse
from .scope_models import _SyntheticTransactionScope
from .synthetic_scope import _bind_test_sandbox_transaction
from .transaction_types import (
    SyntheticFailureSelectorV1,
)


def run_forward_synthetic_transaction(
    *,
    scope: object,
    failure_selector: object,
    observed_at_epoch: object,
):
    bound = _validated_entry(
        scope, failure_selector, observed_at_epoch, rebind=True
    )
    try:
        return _run_forward(
            scope=bound,
            selector=failure_selector,
            observed_at_epoch=observed_at_epoch,
        )
    except Exception as error:
        _raise_content_free(error)


def run_reverse_synthetic_transaction(
    *,
    scope: object,
    failure_selector: object,
    observed_at_epoch: object,
):
    bound = _validated_entry(
        scope, failure_selector, observed_at_epoch, rebind=False
    )
    try:
        return _run_reverse(
            scope=bound,
            selector=failure_selector,
            observed_at_epoch=observed_at_epoch,
        )
    except Exception as error:
        _raise_content_free(error)


def _validated_entry(scope, selector, observed_at, *, rebind):
    if (
        type(scope) is not _SyntheticTransactionScope
        or type(selector) is not SyntheticFailureSelectorV1
        or type(observed_at) is not int
        or observed_at < 0
        or observed_at >= scope.authorization.expires_at_epoch
    ):
        from .errors import RepositoryTransactionError

        raise RepositoryTransactionError(
            "repository_transaction_scope_invalid"
        ) from None
    if not rebind:
        return scope
    return _bind_test_sandbox_transaction(
        review=scope.review,
        profile=scope.profile,
        authorization=scope.authorization,
        observed_at_epoch=observed_at,
    )


def _raise_content_free(error):
    from .errors import RepositoryTransactionError

    if type(error) is RepositoryTransactionError:
        raise error
    raise RepositoryTransactionError(
        "repository_transaction_failed"
    ) from None
