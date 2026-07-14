"""Bounded S-expression syntax parser used by BODYSTRUCTURE handling."""

from __future__ import annotations

MAX_SOURCE_BYTES = 65_536
MAX_TOKENS = 4_096
MAX_NODES = 8_192
MAX_DEPTH = 32
MAX_STRING_LENGTH = 1_024


class BodyStructureError(ValueError):
    """A representation-safe parser error."""

    def __init__(self, code: str = "bodystructure_invalid") -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"BodyStructureError(code={self.code!r})"


class _Tokenizer:
    def __init__(self, source: str) -> None:
        if not isinstance(source, str):
            raise BodyStructureError()
        try:
            encoded = source.encode("utf-8", errors="strict")
        except UnicodeError:
            raise BodyStructureError() from None
        if not encoded or len(encoded) > MAX_SOURCE_BYTES or "{" in source:
            raise BodyStructureError()
        self.source = source
        self.offset = 0
        self.count = 0

    def next(self) -> tuple[str, object] | None:
        source = self.source
        while self.offset < len(source) and source[self.offset].isspace():
            self.offset += 1
        if self.offset >= len(source):
            return None
        start = self.offset
        character = source[self.offset]
        if character in "()":
            self.offset += 1
            return self._emit(character, character)
        if character == '"':
            self.offset += 1
            value: list[str] = []
            while self.offset < len(source):
                current = source[self.offset]
                self.offset += 1
                if current == '"':
                    text = "".join(value)
                    if len(text) > MAX_STRING_LENGTH:
                        raise BodyStructureError()
                    return self._emit("string", text)
                if current == "\\":
                    if self.offset >= len(source):
                        raise BodyStructureError()
                    current = source[self.offset]
                    self.offset += 1
                if ord(current) < 32 and current not in "\t":
                    raise BodyStructureError()
                value.append(current)
            raise BodyStructureError()
        while self.offset < len(source):
            current = source[self.offset]
            if current.isspace() or current in "()":
                break
            if ord(current) < 33 or ord(current) > 126:
                raise BodyStructureError()
            self.offset += 1
        if self.offset == start:
            raise BodyStructureError()
        atom = source[start:self.offset]
        if len(atom) > MAX_STRING_LENGTH:
            raise BodyStructureError()
        if atom.upper() == "NIL":
            value: object = None
        elif atom.isdigit():
            value = int(atom)
        else:
            value = atom
        return self._emit("atom", value)

    def _emit(self, kind: str, value: object) -> tuple[str, object]:
        self.count += 1
        if self.count > MAX_TOKENS:
            raise BodyStructureError()
        return kind, value


class _Parser:
    def __init__(self, source: str) -> None:
        self.tokens = _Tokenizer(source)
        self.lookahead = self.tokens.next()
        self.nodes = 0

    def parse(self) -> object:
        value = self._value(0)
        if self.lookahead is not None:
            raise BodyStructureError()
        return value

    def _value(self, depth: int) -> object:
        if depth > MAX_DEPTH or self.lookahead is None:
            raise BodyStructureError()
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise BodyStructureError()
        kind, value = self.lookahead
        if kind != "(":
            if kind == ")":
                raise BodyStructureError()
            self.lookahead = self.tokens.next()
            return value
        self.lookahead = self.tokens.next()
        result: list[object] = []
        while self.lookahead is not None and self.lookahead[0] != ")":
            result.append(self._value(depth + 1))
        if self.lookahead is None:
            raise BodyStructureError()
        self.lookahead = self.tokens.next()
        return result


def parse_sexpression(source: str) -> object:
    return _Parser(source).parse()


__all__ = ["BodyStructureError", "MAX_STRING_LENGTH", "parse_sexpression"]
