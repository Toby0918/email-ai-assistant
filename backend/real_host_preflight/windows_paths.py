"""Strict local DOS path rules with no Win32 alias normalization."""

from pathlib import Path


_RESERVED_DEVICE_NAMES = frozenset(
    {
        "aux",
        "clock$",
        "con",
        "nul",
        "prn",
        *(f"com{index}" for index in range(1, 10)),
        *(f"lpt{index}" for index in range(1, 10)),
    }
)
_FORBIDDEN_NAME_CHARACTERS = frozenset('<>:"/\\|?*')


def is_absolute_local_path(path: object) -> bool:
    return (
        type(path) is type(Path())
        and path.is_absolute()
        and len(path.drive) == 2
        and path.drive[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        and path.drive[1:] == ":"
        and all(_valid_component(part) for part in path.parts[1:])
    )


def path_components(path: Path) -> tuple[Path, ...]:
    current = Path(path.anchor)
    components = [current]
    for part in path.parts[1:]:
        current /= part
        components.append(current)
    return tuple(components)


def expected_final_path(path: Path) -> str:
    return "\\\\?\\" + str(path)


def _valid_component(part: str) -> bool:
    base = part.split(".", 1)[0].casefold()
    return (
        bool(part)
        and part not in {".", ".."}
        and not part.endswith((" ", "."))
        and base not in _RESERVED_DEVICE_NAMES
        and all(
            ord(character) >= 32
            and character not in _FORBIDDEN_NAME_CHARACTERS
            for character in part
        )
    )
