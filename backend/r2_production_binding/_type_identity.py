"""Executable type surfaces for production callable identity."""

from __future__ import annotations

import dataclasses
from enum import Enum
import types

from .errors import ProductionBindingError
from ._frame_primitives import (
    descriptor_frame,
    frame,
    is_builtin_type,
    same_module_family,
    text_frame,
    traverse_method_globals,
    type_identity,
    type_mro,
    type_namespace,
    type_reference_frame,
)
from ._traversal import cached_frame, frame_policy, remember_frame


_IGNORED_CLASS_NAMES = frozenset({
    "__dataclass_fields__", "__dict__", "__module__", "__weakref__",
})


def type_frame(
    value, seen, depth, function_frame, deep_methods=False,
    constructor_globals=False, *, value_frame, identity_frame, property_frame,
):
    identity = type_identity(value)
    if is_builtin_type(value):
        return frame(b"builtin-type", text_frame(identity))
    if depth > 128:
        raise ProductionBindingError()
    marker = (
        "type", id(value), deep_methods, constructor_globals,
        frame_policy(function_frame),
    )
    cached = cached_frame(seen, marker)
    if cached is not None:
        return cached
    if marker in seen:
        return frame(b"type-reference", text_frame(identity))
    seen.add(marker)
    try:
        body = _owner_frames(
            value, seen, depth, function_frame, deep_methods,
            constructor_globals, value_frame, identity_frame, property_frame,
        )
        body += _type_tail(
            value, seen, depth, function_frame,
            deep_methods, constructor_globals,
            value_frame, identity_frame, property_frame,
        )
        return remember_frame(
            seen, marker,
            frame(b"type", text_frame(identity) + b"".join(body)),
        )
    finally:
        seen.remove(marker)


def _owner_frames(
    value, seen, depth, function_frame, deep_methods, constructor_globals,
    value_frame, identity_frame, property_frame,
):
    body = [_dataclass_fields_frame(
        value, seen, depth, function_frame, deep_methods,
        constructor_globals, value_frame,
    )]
    for owner in type_mro(value):
        if is_builtin_type(owner):
            continue
        owner_body = []
        for name, item in sorted(type_namespace(owner).items()):
            item_frame = _class_item_frame(
                owner, name, item, seen, depth + 1, function_frame,
                deep_methods,
                constructor_globals and same_module_family(owner, value),
                value_frame, identity_frame, property_frame,
            )
            if item_frame is not None:
                owner_body.append(frame(name.encode("utf-8"), item_frame))
        body.append(frame(
            b"mro-owner",
            type_reference_frame(owner) + b"".join(owner_body),
        ))
    return body


def _dataclass_fields_frame(
    value, seen, depth, function_frame, deep_methods,
    constructor_globals, value_frame,
):
    fields = type_namespace(value).get("__dataclass_fields__")
    if type(fields) is not dict:
        return frame(b"dataclass-fields", b"")
    body = []
    for name, field_value in sorted(fields.items()):
        if type(field_value) is not dataclasses.Field:
            raise ProductionBindingError()
        items = []
        for item_name, item in _dataclass_field_items(field_value):
            item_frame = _dataclass_field_value_frame(
                item_name, item, seen, depth, function_frame,
                deep_methods, constructor_globals, value_frame,
            )
            items.append(frame(item_name.encode("utf-8"), item_frame))
        body.append(frame(name.encode("utf-8"), b"".join(items)))
    return frame(b"dataclass-fields", b"".join(body))


def _dataclass_field_items(field_value):
    names = (
        "name", "type", "default", "default_factory", "repr", "hash",
        "init", "compare", "metadata", "kw_only", "_field_type", "doc",
    )
    return tuple(
        (name, getattr(field_value, name))
        for name in names if hasattr(field_value, name)
    )


def _dataclass_field_value_frame(
    name, value, seen, depth, function_frame,
    deep_methods, constructor_globals, value_frame,
):
    if value is dataclasses.MISSING:
        return frame(b"dataclass-missing", b"")
    if name == "metadata":
        if value is not dataclasses._EMPTY_METADATA:
            raise ProductionBindingError()
        return frame(b"dataclass-empty-metadata", b"")
    if name == "_field_type":
        return frame(
            b"dataclass-field-kind",
            text_frame((_dataclass_field_kind(value),)),
        )
    return value_frame(
        value, seen, depth + 1, function_frame,
        constructor_globals, deep_methods,
    )


def _dataclass_field_kind(value):
    kinds = (
        (dataclasses._FIELD, "field"),
        (dataclasses._FIELD_CLASSVAR, "classvar"),
        (dataclasses._FIELD_INITVAR, "initvar"),
    )
    for sentinel, label in kinds:
        if value is sentinel:
            return label
    raise ProductionBindingError()


def _type_tail(
    value, seen, depth, function_frame, deep_methods, constructor_globals,
    value_frame, identity_frame, property_frame,
):
    meta_frame = _metaclass_frame(
        type(value), seen, depth + 1, function_frame,
        deep_methods or (
            constructor_globals and same_module_family(type(value), value)
        ),
        value_frame, identity_frame, property_frame,
    )
    bases_frame = frame(
        b"mro",
        b"".join(type_reference_frame(owner) for owner in type_mro(value)),
    )
    return [meta_frame, bases_frame]


def _class_item_frame(
    owner, name, item, seen, depth, function_frame,
    deep_methods, constructor_globals,
    value_frame, identity_frame, property_frame,
):
    if name in _IGNORED_CLASS_NAMES:
        return None
    traverse = deep_methods or constructor_globals
    if isinstance(item, types.FunctionType):
        relaxed = (type(type_namespace(owner).get("__dataclass_fields__")) is dict
                   and name in {"__setattr__", "__delattr__"})
        traverse = traverse_method_globals(item, owner, traverse)
        return function_frame(
            item, seen, depth + 1,
            None if traverse else not relaxed, traverse,
        )
    if isinstance(item, (classmethod, staticmethod)):
        return _wrapped_method_frame(
            owner, item, seen, depth, function_frame,
            deep_methods, constructor_globals, value_frame,
        )
    if isinstance(item, property):
        return property_frame(
            item, seen, depth, function_frame, traverse)
    if isinstance(item, type):
        return type_frame(
            item, seen, depth + 1, function_frame,
            deep_methods=deep_methods,
            constructor_globals=constructor_globals,
            value_frame=value_frame, identity_frame=identity_frame,
            property_frame=property_frame,
        )
    if isinstance(item, Enum):
        return identity_frame(
            item, seen, depth + 1, function_frame,
            constructor_globals, deep_methods,
        )
    descriptor = descriptor_frame(item)
    if descriptor is not None:
        return descriptor
    return value_frame(
        item, seen, depth + 1, function_frame,
        constructor_globals, deep_methods,
    )


def _wrapped_method_frame(
    owner, item, seen, depth, function_frame,
    deep_methods, constructor_globals, value_frame,
):
    tag = b"classmethod" if isinstance(item, classmethod) else b"staticmethod"
    target = item.__func__
    traverse = deep_methods or constructor_globals
    traverse = traverse_method_globals(target, owner, traverse)
    target_frame = (
        function_frame(
            target, seen, depth + 1,
            None if traverse else False, traverse,
        )
        if isinstance(target, types.FunctionType)
        else value_frame(
            target, seen, depth + 1, function_frame,
            constructor_globals, deep_methods,
        )
    )
    return frame(tag, target_frame)


def _metaclass_frame(
    value, seen, depth, function_frame, constructor_globals,
    value_frame, identity_frame, property_frame,
):
    if is_builtin_type(value):
        return type_reference_frame(value)
    body = _owner_frames(
        value, seen, depth, function_frame,
        constructor_globals, constructor_globals,
        value_frame, identity_frame, property_frame,
    )
    return frame(
        b"metaclass", type_reference_frame(value) + b"".join(body))
