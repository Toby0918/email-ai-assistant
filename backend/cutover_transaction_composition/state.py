"""Private single-use transaction state."""

from threading import Lock


class SingleActionState:
    __slots__ = ("_claimed", "_lock")

    def __init__(self) -> None:
        self._claimed = False
        self._lock = Lock()

    def claim(self) -> bool:
        with self._lock:
            if self._claimed:
                return False
            self._claimed = True
            return True
