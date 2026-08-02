"""Windows local-TTY adapter with bounded hidden input."""

from __future__ import annotations

import os
import sys


_MAX_ACKNOWLEDGEMENT_CHARS = 64
_ACKNOWLEDGEMENT_PROMPT = "R2_PREFLIGHT_ACKNOWLEDGEMENT\n"
_ENVELOPE_PROMPT = "R2_PREFLIGHT_AUTHORIZATION\n"


class SystemTerminal:
    """Use only the process-owned standard console streams."""

    __slots__ = ()

    def tty_state(self) -> tuple[bool, bool, bool]:
        if os.name != "nt":
            return False, False, False
        return tuple(
            _is_tty(stream)
            for stream in (sys.stdin, sys.stdout, sys.stderr)
        )

    def read_acknowledgement(self) -> str:
        sys.stderr.write(_ACKNOWLEDGEMENT_PROMPT)
        sys.stderr.flush()
        value = sys.stdin.readline(_MAX_ACKNOWLEDGEMENT_CHARS + 2)
        if not value.endswith(("\n", "\r")):
            return ""
        return value.rstrip("\r\n")

    def read_hidden_envelope(self, maximum: int) -> str:
        if type(maximum) is not int or not 1 <= maximum <= 65_536:
            return ""
        sys.stderr.write(_ENVELOPE_PROMPT)
        sys.stderr.flush()
        value = _read_hidden_windows_line(maximum)
        sys.stderr.write("\n")
        sys.stderr.flush()
        return value


def _is_tty(stream: object) -> bool:
    try:
        return stream.isatty() is True and stream.fileno() >= 0
    except (AttributeError, OSError, ValueError):
        return False


def _read_hidden_windows_line(maximum: int) -> str:
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
                continue
            characters.append(character)
        return "".join(characters)
    except (EOFError, OSError):
        return ""
