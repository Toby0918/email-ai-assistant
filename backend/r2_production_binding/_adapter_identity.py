"""Path-independent source identity for reviewed production adapter types."""

from __future__ import annotations

import hashlib
import inspect
import marshal
import sys
import types

from .errors import ProductionBindingError
from .vocabulary import (
    ProductionCommandV2,
    authority_domain_for_command_v2,
)


def production_adapter_fingerprint_v1(command, adapter_type):
    """Commit one command and domain to an exact adapter type implementation."""
    try:
        if type(command) is not ProductionCommandV2 or type(adapter_type) is not type:
            raise ProductionBindingError()
        module = sys.modules.get(adapter_type.__module__)
        if module is None or vars(module).get(adapter_type.__name__) is not adapter_type:
            raise ProductionBindingError()
        source = inspect.getsource(module).encode("utf-8")
        domain = authority_domain_for_command_v2(command)
        surface_digest = _adapter_type_surface_digest_v1(adapter_type)
        body = b"\0".join(
            (
                b"r2-production-adapter-v1",
                command.value.encode("ascii"),
                domain.value.encode("ascii"),
                adapter_type.__module__.encode("utf-8"),
                adapter_type.__qualname__.encode("utf-8"),
                hashlib.sha256(source).digest(),
                surface_digest,
            )
        )
        return hashlib.sha256(body).hexdigest()
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None


def _snapshot_adapter_type_surface_v1(adapter_type):
    try:
        _adapter_type_surface_v1(adapter_type)
        namespace = vars(adapter_type)
        return tuple((name, namespace[name]) for name in sorted(namespace))
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None


def _require_adapter_type_surface_v1(adapter_type, expected):
    try:
        observed = _snapshot_adapter_type_surface_v1(adapter_type)
        if type(expected) is not tuple or len(observed) != len(expected):
            raise ProductionBindingError()
        for current, bound in zip(observed, expected, strict=True):
            if (
                type(bound) is not tuple
                or len(bound) != 2
                or type(bound[0]) is not str
                or current[0] != bound[0]
                or current[1] is not bound[1]
            ):
                raise ProductionBindingError()
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None


def _adapter_type_surface_digest_v1(adapter_type):
    try:
        return hashlib.sha256(_adapter_type_surface_v1(adapter_type)).digest()
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None


def _adapter_type_surface_v1(adapter_type):
    if type(adapter_type) is not type or adapter_type.__bases__ != (object,):
        raise ProductionBindingError()
    namespace = vars(adapter_type)
    members = tuple(
        _adapter_member_frame_v1(adapter_type, name, namespace[name])
        for name in sorted(namespace)
    )
    return _frame_v1(b"adapter-type-surface-v1", *members)


def _adapter_member_frame_v1(adapter_type, name, value):
    if type(name) is not str:
        raise ProductionBindingError()
    encoded_name = name.encode("utf-8")
    if type(value) is types.FunctionType:
        return _frame_v1(
            b"function-member",
            encoded_name,
            _function_frame_v1(adapter_type, name, value),
        )
    if type(value) is classmethod:
        return _frame_v1(
            b"classmethod-member",
            encoded_name,
            _function_frame_v1(adapter_type, name, value.__func__),
        )
    if type(value) is staticmethod:
        return _frame_v1(
            b"staticmethod-member",
            encoded_name,
            _function_frame_v1(adapter_type, name, value.__func__),
        )
    if type(value) in (types.MemberDescriptorType, types.GetSetDescriptorType):
        if value.__objclass__ is not adapter_type or value.__name__ != name:
            raise ProductionBindingError()
        return _frame_v1(b"slot-member", encoded_name)
    return _frame_v1(b"value-member", encoded_name, _stable_value_frame_v1(value))


def _function_frame_v1(adapter_type, name, function):
    if (
        function.__module__ != adapter_type.__module__
        or function.__qualname__ != f"{adapter_type.__qualname__}.{name}"
        or function.__closure__ is not None
    ):
        raise ProductionBindingError()
    normalized = _normalized_code_v1(function.__code__)
    return _frame_v1(
        b"function-surface-v1",
        function.__name__.encode("utf-8"),
        function.__qualname__.encode("utf-8"),
        function.__module__.encode("utf-8"),
        marshal.dumps(normalized),
        _stable_value_frame_v1(function.__defaults__),
        _stable_value_frame_v1(function.__kwdefaults__),
        _stable_value_frame_v1(function.__annotations__),
        _stable_value_frame_v1(function.__dict__),
        _stable_value_frame_v1(getattr(function, "__type_params__", ())),
    )


def _normalized_code_v1(code):
    if type(code) is not types.CodeType:
        raise ProductionBindingError()
    constants = tuple(
        _normalized_code_v1(value) if type(value) is types.CodeType else value
        for value in code.co_consts
    )
    return code.replace(
        co_consts=constants,
        co_filename="",
        co_firstlineno=1,
    )


def _stable_value_frame_v1(value):
    if value is None:
        return b"none"
    if type(value) is bool:
        return b"bool:1" if value else b"bool:0"
    if type(value) is int:
        return _frame_v1(b"int", str(value).encode("ascii"))
    if type(value) is str:
        return _frame_v1(b"str", value.encode("utf-8"))
    if type(value) is bytes:
        return _frame_v1(b"bytes", value)
    if type(value) is tuple:
        return _frame_v1(
            b"tuple",
            *(_stable_value_frame_v1(item) for item in value),
        )
    if type(value) is dict and all(type(key) is str for key in value):
        items = tuple(
            _frame_v1(
                b"item",
                key.encode("utf-8"),
                _stable_value_frame_v1(value[key]),
            )
            for key in sorted(value)
        )
        return _frame_v1(b"dict", *items)
    raise ProductionBindingError()


def _frame_v1(tag, *parts):
    if type(tag) is not bytes or any(type(part) is not bytes for part in parts):
        raise ProductionBindingError()
    framed = bytearray(tag)
    for part in parts:
        framed.extend(len(part).to_bytes(8, "big"))
        framed.extend(part)
    return bytes(framed)
