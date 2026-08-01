"""Evidence-specific Windows TTY and hidden-input adapter."""

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
        sys.stderr.write("R2_EVIDENCE_ACKNOWLEDGEMENT\n")
        sys.stderr.flush()
        value = sys.stdin.readline(66)
        if not value.endswith(("\n", "\r")):
            return ""
        return value.rstrip("\r\n")

    def read_hidden_envelope(self, maximum: int) -> str:
        if type(maximum) is not int or not 1 <= maximum <= 65_536:
            return ""
        sys.stderr.write("R2_EVIDENCE_AUTHORIZATION\n")
        sys.stderr.flush()
        value = _read_hidden(maximum)
        sys.stderr.write("\n")
        sys.stderr.flush()
        return value


def _is_tty(stream: object) -> bool:
    try:
        return stream.isatty() is True and stream.fileno() >= 0
    except (AttributeError, OSError, ValueError):
        return False


def _read_hidden(maximum: int) -> str:
    try:
        import msvcrt

        characters: list[str] = []
        while len(characters) <= maximum:
            character = msvcrt.getwch()
            if character in {"\r", "\n"}:
                return "".join(characters)
            if character == "\b":
                if characters:
                    characters.pop()
            else:
                characters.append(character)
        return "".join(characters)
    except (EOFError, OSError):
        return ""
