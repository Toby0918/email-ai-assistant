"""Closed semantic frames for callable globals and exact parameter types."""

from __future__ import annotations

from enum import Enum
import types

from .errors import ProductionBindingError
from ._frame_primitives import (
    builtin_function_frame as _builtin_function_frame,
    descriptor_frame as _descriptor_frame,
    frame,
    json_scanner_state as _json_scanner_state,
    object_state as _object_state,
    scalar_frame as _scalar_frame,
    text_frame,
    type_reference_frame as _type_reference_frame,
)
from ._module_identity import module_frame
from ._traversal import cached_frame, frame_policy, remember_frame
from ._type_identity import type_frame as _build_type_frame

def value_frame(value, seen, depth, function_frame):
    return _value_frame(value, seen, depth, function_frame, False)

def deep_value_frame(value, seen, depth, function_frame):
    return _value_frame(value, seen, depth, function_frame, True)

def behavior_value_frame(value, seen, depth, function_frame):
    return _value_frame(value, seen, depth, function_frame, False, True)

def _value_frame(
    value, seen, depth, function_frame, deep, behavior_methods=False
):
    if depth > 128:
        raise ProductionBindingError()
    scalar = _scalar_frame(value)
    if scalar is not None:
        return scalar
    if type(value) in {tuple, list}:
        return _sequence_frame(
            type(value).__name__.encode(), value, seen, depth,
            function_frame, deep, behavior_methods,
        )
    if type(value) in {set, frozenset}:
        items = sorted(
            _value_frame(
                item, seen, depth + 1, function_frame,
                deep, behavior_methods,
            )
            for item in value
        )
        return frame(type(value).__name__.encode(), b"".join(items))
    if type(value) is dict:
        return _mapping_frame(
            value, seen, depth, function_frame, deep, behavior_methods)
    return _identity_frame(
        value, seen, depth, function_frame, deep, behavior_methods)

def _identity_frame(
    value, seen, depth, function_frame, deep=False, behavior_methods=False
):
    if isinstance(value, Enum):
        return _enum_frame(
            value, seen, depth, function_frame, deep, behavior_methods)
    if isinstance(value, types.FunctionType):
        return function_frame(value, seen, depth + 1)
    if isinstance(value, types.MethodType):
        return frame(
            b"method",
            function_frame(value.__func__, seen, depth + 1)
            + _value_frame(
                value.__self__, seen, depth + 1, function_frame,
                deep, behavior_methods,
            ),
        )
    if isinstance(value, (types.BuiltinFunctionType, types.MethodWrapperType)):
        return _builtin_function_frame(
            value, seen, depth, function_frame, deep,
            behavior_methods, _value_frame,
        )
    return _structured_identity_frame(
        value, seen, depth, function_frame, deep, behavior_methods)


def _enum_frame(value, seen, depth, function_frame, deep, behavior_methods):
    return frame(
        b"enum",
        type_frame(
            type(value), seen, depth + 1, function_frame,
            behavior_methods, deep,
        )
        + _value_frame(
            value.value, seen, depth + 1, function_frame,
            deep, behavior_methods,
        )
        + _mapping_frame(
            vars(value), seen, depth + 1, function_frame,
            deep, behavior_methods,
        ),
    )


def _structured_identity_frame(
    value, seen, depth, function_frame, deep, behavior_methods
):
    scanner = _json_scanner_frame(
        value, seen, depth, function_frame, deep, behavior_methods)
    if scanner is not None:
        return scanner
    if isinstance(value, (classmethod, staticmethod)):
        tag = b"classmethod" if isinstance(value, classmethod) else b"staticmethod"
        item = value.__func__
        return frame(
            tag,
            function_frame(
                item, seen, depth + 1,
                None if deep else False, deep or behavior_methods,
            )
            if isinstance(item, types.FunctionType)
            else _value_frame(
                item, seen, depth + 1, function_frame,
                deep, behavior_methods,
            ),
        )
    if isinstance(value, property):
        return _property_frame(
            value, seen, depth, function_frame,
            deep or behavior_methods,
        )
    if isinstance(value, type):
        return type_frame(
            value, seen, depth + 1, function_frame,
            deep_methods=behavior_methods,
            constructor_globals=deep,
        )
    if isinstance(value, types.ModuleType):
        if not deep and not behavior_methods:
            return frame(
                b"module-reference", text_frame((value.__name__,)))
        return module_frame(
            value, seen, depth + 1, function_frame,
            value_frame,
            deep_value_frame,
            behavior_value_frame,
            frame, text_frame,
        )
    descriptor = _descriptor_frame(value)
    if descriptor is not None:
        return descriptor
    return _object_frame(
        value, seen, depth, function_frame, deep, behavior_methods)


def _json_scanner_frame(
    value, seen, depth, function_frame, deep, behavior_methods,
):
    state = _json_scanner_state(value)
    if state is None:
        return None
    return frame(
        b"json-scanner",
        _value_frame(
            state, seen, depth + 1, function_frame,
            deep, behavior_methods,
        ),
    )

def type_frame(value, seen, depth, function_frame, deep_methods=False,
               constructor_globals=False):
    return _build_type_frame(
        value, seen, depth, function_frame, deep_methods, constructor_globals,
        value_frame=_value_frame, identity_frame=_identity_frame,
        property_frame=_property_frame,
    )

def _object_frame(
    value, seen, depth, function_frame,
    deep=False, behavior_methods=False,
):
    marker = (
        "object", id(value), deep, behavior_methods,
        frame_policy(function_frame),
    )
    cached = cached_frame(seen, marker)
    if cached is not None:
        return cached
    value_type = type(value)
    if marker in seen:
        return frame(b"object-reference", _type_reference_frame(value_type))
    seen.add(marker)
    try:
        complete, state = _object_state(value)
        if (deep or behavior_methods) and not complete:
            raise ProductionBindingError()
        state_frame = (
            frame(b"no-state", b"")
            if state is None
            else _value_frame(
                state, seen, depth, function_frame,
                deep, behavior_methods,
            )
        )
        return remember_frame(
            seen, marker, frame(
                b"object",
                type_frame(
                    value_type, seen, depth + 1, function_frame,
                    deep_methods=behavior_methods,
                    constructor_globals=deep,
                )
                + state_frame,
            ),
        )
    finally:
        seen.remove(marker)

def _property_frame(
    value, seen, depth, function_frame, traverse_globals=False
):
    return frame(
        b"property",
        b"".join(
            frame(b"none", b"")
            if item is None
            else function_frame(
                item, seen, depth + 1,
                None if traverse_globals else False,
                traverse_globals,
            )
            for item in (value.fget, value.fset, value.fdel)
        ),
    )

def _mapping_frame(
    values, seen, depth, function_frame,
    deep=False, behavior_methods=False,
):
    if type(values) is not dict:
        raise ProductionBindingError()
    entries = sorted(
        frame(b"key", _value_frame(
            key, seen, depth + 1, function_frame,
            deep, behavior_methods,
        ))
        + frame(b"value", _value_frame(
            item, seen, depth + 1, function_frame,
            deep, behavior_methods,
        ))
        for key, item in values.items()
    )
    return frame(b"mapping", b"".join(entries))

def _sequence_frame(
    tag, values, seen, depth, function_frame,
    deep=False, behavior_methods=False,
):
    return frame(
        tag,
        b"".join(
            frame(
                str(index).encode("ascii"),
                _value_frame(
                    item, seen, depth + 1, function_frame,
                    deep, behavior_methods,
                ),
            )
            for index, item in enumerate(values)
        ),
    )
