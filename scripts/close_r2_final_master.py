"""Fixed prepare/confirm CLI for Solo Maintainer Closure V1."""

from __future__ import annotations

import ctypes
from pathlib import Path
import sys
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
if sys.flags.isolated and str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.r2_solo_maintainer_closure import (  # noqa: E402
    ClosureErrorCode,
    SoloMaintainerClosure,
    SoloMaintainerClosureError,
)
from backend.r2_solo_maintainer_closure._canonical import canonical_json  # noqa: E402
from backend.r2_solo_maintainer_closure.closure import _console_ceremony  # noqa: E402


VERBS = ("prepare", "confirm")
_MAX_VISIBLE_CHARACTERS = 4_096


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in VERBS:
        return _failure(ClosureErrorCode.INVALID)
    try:
        if sys.argv[1] == "prepare":
            result = SoloMaintainerClosure().prepare()
        else:
            with _console_ceremony() as ceremony:
                closure = SoloMaintainerClosure()
                candidate = closure.prepare()
                ceremony.require_current()
                sys.stderr.write(candidate.to_canonical_json().decode("ascii") + "\n")
                sys.stderr.flush()
                supplied_fingerprint = _read_visible_line(ceremony)
                acknowledgement = _read_visible_line(ceremony)
                ceremony.require_current()
                _require_no_pending_input(ceremony)
                result = closure.confirm(supplied_fingerprint, acknowledgement)
        sys.stdout.write(result.to_canonical_json().decode("ascii") + "\n")
        return 0
    except SoloMaintainerClosureError as exc:
        return _failure(exc.code)
    except Exception:
        return _failure(ClosureErrorCode.INVALID)


def _read_visible_line(ceremony) -> str:
    try:
        reader = getattr(ceremony, "read_console_line", None)
        value = (reader(_MAX_VISIBLE_CHARACTERS + 2) if reader is not None
                 else _read_console_line(ceremony.stdin_handle))
    except Exception:
        raise SoloMaintainerClosureError() from None
    if not value.endswith("\n") or len(value) > _MAX_VISIBLE_CHARACTERS + 1:
        raise SoloMaintainerClosureError()
    value = value[:-1]
    if value.endswith("\r"):
        value = value[:-1]
    if (not value or value != value.strip()
            or any(ord(character) < 32 or 127 <= ord(character) <= 159
                   or unicodedata.category(character) == "Cf" for character in value)):
        raise SoloMaintainerClosureError()
    return value


def _read_console_line(handle: int) -> str:
    buffer = ctypes.create_unicode_buffer(_MAX_VISIBLE_CHARACTERS + 2)
    read = ctypes.c_uint32()
    operation = ctypes.windll.kernel32.ReadConsoleW
    if operation(ctypes.c_void_p(handle), buffer, len(buffer),
                 ctypes.byref(read), None) != 1:
        raise SoloMaintainerClosureError(ClosureErrorCode.TTY_REQUIRED)
    return buffer[:read.value]


def _require_no_pending_input(ceremony) -> None:
    checker = getattr(ceremony, "require_no_pending_input", None)
    if checker is not None:
        checker()
        return
    record, count = ctypes.create_string_buffer(32), ctypes.c_uint32()
    operation = ctypes.windll.kernel32.PeekConsoleInputW
    if operation(ctypes.c_void_p(ceremony.stdin_handle), record, 1,
                 ctypes.byref(count)) != 1 or count.value != 0:
        raise SoloMaintainerClosureError(ClosureErrorCode.TTY_REQUIRED)


def _failure(code: ClosureErrorCode) -> int:
    try:
        payload = canonical_json({"status": code.value}).decode("ascii")
    except Exception:
        payload = '{"status":"R2_SOLO_MAINTAINER_CLOSURE_INVALID"}'
    sys.stdout.write(payload + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
