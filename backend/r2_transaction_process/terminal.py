"""Transaction-specific Windows TTY input."""

from __future__ import annotations

import os
import sys


class SystemTerminal:
    __slots__ = ()

    def tty_state(self) -> tuple[bool, bool, bool]:
        if os.name != "nt":
            return False, False, False
        return tuple(
            _is_tty(stream)
            for stream in (sys.stdin, sys.stdout, sys.stderr)
        )

    def read_acknowledgement(self) -> str:
        sys.stderr.write("R2_TRANSACTION_ACKNOWLEDGEMENT\n")
        sys.stderr.flush()
        value = sys.stdin.readline(66)
        return value.rstrip("\r\n") if value.endswith(("\r", "\n")) else ""

    def read_hidden_envelope(self, maximum: int) -> str:
        if type(maximum) is not int or not 1 <= maximum <= 65_536:
            return ""
        sys.stderr.write("R2_TRANSACTION_AUTHORIZATION\n")
        sys.stderr.flush()
        value = _hidden_line(maximum)
        sys.stderr.write("\n")
        sys.stderr.flush()
        return value


def _is_tty(stream: object) -> bool:
    try:
        return stream.isatty() is True and stream.fileno() >= 0
    except (AttributeError, OSError, ValueError):
        return False


def _hidden_line(maximum: int) -> str:
    try:
        import msvcrt

        value: list[str] = []
        while len(value) <= maximum:
            character = msvcrt.getwch()
            if character in {"\r", "\n"}:
                return "".join(value)
            if character == "\b" and value:
                value.pop()
            elif character != "\b":
                value.append(character)
        return "".join(value)
    except (EOFError, OSError):
        return ""
