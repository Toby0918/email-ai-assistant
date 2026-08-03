"""Primitive canonical frames for production callable identity."""

from __future__ import annotations

import builtins
from enum import Enum
import json
import re
import struct
import types

from .errors import ProductionBindingError


_DESCRIPTOR_TYPES = (
    types.BuiltinMethodType,
    types.ClassMethodDescriptorType,
    types.GetSetDescriptorType,
    types.MemberDescriptorType,
    types.MethodDescriptorType,
    types.WrapperDescriptorType,
)
_OPAQUE_NATIVE_MEMBER_TYPES = (
    types.BuiltinFunctionType,
    types.MethodDescriptorType,
    types.WrapperDescriptorType,
)
_JSON_SCANNER_TYPE = type(json.JSONDecoder().scan_once)
_TYPE_DESCRIPTORS = {
    name: type.__dict__[name]
    for name in ("__dict__", "__mro__", "__module__", "__qualname__", "__name__")
}


def frame(tag, value):
    return len(tag).to_bytes(4, "big") + tag + len(value).to_bytes(8, "big") + value


def text_frame(values):
    return b"".join(frame(b"text", value.encode("utf-8")) for value in values)


def scalar_frame(value):
    if value is None:
        return frame(b"none", b"")
    if value is NotImplemented:
        return frame(b"not-implemented", b"")
    if value is Ellipsis:
        return frame(b"ellipsis", b"")
    if type(value) is bool:
        return frame(b"bool", b"1" if value else b"0")
    if type(value) is int:
        return frame(b"int", str(value).encode("ascii"))
    if type(value) is float:
        return frame(b"float", struct.pack(">d", value))
    if type(value) is complex:
        return frame(b"complex", struct.pack(">dd", value.real, value.imag))
    if type(value) is str:
        return frame(b"str", value.encode("utf-8"))
    if type(value) is bytes:
        return frame(b"bytes", value)
    if type(value) is range:
        values = (value.start, value.stop, value.step)
        return frame(b"range", text_frame(tuple(map(str, values))))
    if type(value) is slice:
        values = (value.start, value.stop, value.step)
        items = tuple(scalar_frame(item) for item in values)
        if any(item is None for item in items):
            return None
        return frame(b"slice", b"".join(items))
    if type(value) is re.Pattern:
        if value.flags & re.LOCALE:
            raise ProductionBindingError()
        pattern = scalar_frame(value.pattern)
        if pattern is None:
            return None
        return frame(b"regex", pattern + scalar_frame(value.flags))
    return None


def descriptor_frame(value):
    if not isinstance(value, _DESCRIPTOR_TYPES):
        return None
    return frame(b"descriptor", text_frame((
        type(value).__module__,
        type(value).__qualname__,
        getattr(value, "__name__", ""),
    )))


def json_scanner_state(value):
    if type(value) is not _JSON_SCANNER_TYPE:
        return None
    names = (
        "object_hook", "object_pairs_hook", "parse_constant",
        "parse_float", "parse_int", "strict",
    )
    return tuple(getattr(value, name) for name in names)


def builtin_function_frame(
    value, seen, depth, function_frame, deep, behavior_methods, value_frame,
):
    identity = (getattr(value, "__module__", None) or "", value.__qualname__)
    receiver = getattr(value, "__self__", None)
    receiver_frame = (
        frame(b"module-reference", text_frame((receiver.__name__,)))
        if isinstance(receiver, types.ModuleType)
        else value_frame(
            receiver, seen, depth + 1, function_frame,
            deep, behavior_methods,
        )
    )
    return frame(b"builtin-function", text_frame(identity) + receiver_frame)


def object_state(value):
    dictionary = _instance_dictionary(value)
    slots, complete = [], True
    for owner in type_mro(type(value)):
        if owner is object:
            continue
        if is_builtin_type(owner):
            complete = False
            continue
        namespace = type_namespace(owner)
        if any(
            isinstance(item, _OPAQUE_NATIVE_MEMBER_TYPES)
            for item in namespace.values()
        ):
            complete = False
        for name, descriptor in sorted(namespace.items()):
            if isinstance(descriptor, types.GetSetDescriptorType):
                if name not in {"__dict__", "__weakref__"}:
                    complete = False
                continue
            if (
                not isinstance(descriptor, types.MemberDescriptorType)
                or name in {"__dict__", "__weakref__"}
            ):
                continue
            try:
                item = descriptor.__get__(value, type(value))
            except AttributeError:
                module, qualname, _ = type_identity(owner)
                slots.append((module, qualname, name, False, None))
            else:
                module, qualname, _ = type_identity(owner)
                slots.append((module, qualname, name, True, item))
    if dictionary is None and not slots:
        return complete, None
    return complete, (dictionary, tuple(slots))


def _instance_dictionary(value):
    for owner in type_mro(type(value)):
        namespace = type_namespace(owner)
        if "__dict__" not in namespace:
            continue
        descriptor = namespace["__dict__"]
        if type(descriptor) is not types.GetSetDescriptorType:
            raise ProductionBindingError()
        try:
            return descriptor.__get__(value, type(value))
        except (AttributeError, TypeError):
            return None
    return None


def type_reference_frame(value):
    return frame(b"type-reference", text_frame(type_identity(value)))


def type_identity(value):
    identity = tuple(
        _type_descriptor_value(value, name)
        for name in ("__module__", "__qualname__", "__name__")
    )
    if any(type(item) is not str for item in identity):
        raise ProductionBindingError()
    return identity


def type_mro(value):
    mro = _type_descriptor_value(value, "__mro__")
    if (
        type(mro) is not tuple
        or not mro
        or mro[0] is not value
        or any(not isinstance(owner, type) for owner in mro)
    ):
        raise ProductionBindingError()
    return mro


def type_namespace(value):
    namespace = _type_descriptor_value(value, "__dict__")
    if type(namespace) is not types.MappingProxyType:
        raise ProductionBindingError()
    return namespace


def _type_descriptor_value(value, name):
    if not isinstance(value, type):
        raise ProductionBindingError()
    try:
        return _TYPE_DESCRIPTORS[name].__get__(value, type(value))
    except (AttributeError, TypeError):
        raise ProductionBindingError() from None


def is_builtin_type(value):
    if not isinstance(value, type):
        return False
    _, _, name = type_identity(value)
    return (
        getattr(builtins, name, None) is value
    )


def same_module_family(left, right):
    left_module, _, _ = type_identity(left)
    right_module, _, _ = type_identity(right)
    return left_module.split(".", 1)[0] == right_module.split(".", 1)[0]


def traverse_method_globals(function, owner, requested):
    if not requested:
        return False
    if not issubclass(owner, Enum):
        return True
    source = type_namespace(Enum).get(function.__name__)
    if isinstance(source, (classmethod, staticmethod)):
        source = source.__func__
    return function is not source
