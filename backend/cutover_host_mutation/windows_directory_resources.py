"""Lifetime-bound handles for a guarded new Container."""

from __future__ import annotations

from threading import Lock

from .windows_handles import _NativeWindowsFailure


class GuardedDirectoryHandles:
    __slots__ = ("_api", "_handles", "_lock")

    def __init__(
        self,
        api,
        *,
        root_handle: int,
        marker_handle: int,
        parent_handle: int,
        target_handle: int,
    ) -> None:
        self._api = api
        self._handles = (
            root_handle,
            marker_handle,
            parent_handle,
            target_handle,
        )
        self._lock = Lock()

    def snapshot(self) -> tuple[int, int, int, int]:
        with self._lock:
            if self._handles is None:
                raise LookupError("guarded handles unavailable")
            return self._handles

    def close(self) -> None:
        with self._lock:
            handles = self._handles
            self._handles = None
        if handles is None:
            return
        failed = False
        for handle in reversed(handles):
            try:
                self._api.close(handle)
            except _NativeWindowsFailure:
                failed = True
        if failed:
            raise _NativeWindowsFailure()

    def close_silently(self) -> None:
        try:
            self.close()
        except _NativeWindowsFailure:
            return
