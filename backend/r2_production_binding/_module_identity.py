"""Semantic module frames limited to executable global dependencies."""

from __future__ import annotations

import dis
import types

from .errors import ProductionBindingError
from ._traversal import cached_frame, frame_policy, remember_frame


def module_frame(
    value, seen, depth, function_frame, namespace_value_frame,
    dependency_value_frame, external_namespace_value_frame,
    frame, text_frame, force_external=False,
):
    _require_static_module(value)
    identity = (value.__name__,)
    marker = _module_marker(
        value, function_frame, namespace_value_frame,
        dependency_value_frame, external_namespace_value_frame, force_external,
    )
    cached = cached_frame(seen, marker)
    if cached is not None:
        return cached
    if marker in seen:
        return frame(b"module-reference", text_frame(identity))
    if depth > 128:
        raise ProductionBindingError()
    seen.add(marker)
    try:
        dependency_frame = _dependency_function_frame(
            function_frame, dependency_value_frame, frame, text_frame)
        external_function_frame = _dependency_function_frame(
            function_frame, dependency_value_frame, frame, text_frame,
            namespace_value_frame,
        )
        owned = _module_owns_behavior(value) and not force_external
        namespace_function_frame = dependency_frame if owned else (
            _surface_function_frame(function_frame))
        item_value_frame = (
            namespace_value_frame if owned else external_namespace_value_frame)
        item_function_frame = (namespace_function_frame if owned
                               else external_function_frame)
        body = _module_body(
            value, seen, depth, function_frame, namespace_value_frame,
            item_value_frame, dependency_value_frame,
            external_namespace_value_frame, item_function_frame,
            frame, text_frame, owned,
        )
        return remember_frame(
            seen, marker,
            frame(b"module", text_frame(identity) + b"".join(body)),
        )
    finally:
        seen.remove(marker)


def _module_body(
    value, seen, depth, function_frame, namespace_value_frame,
    item_value_frame, dependency_value_frame, external_namespace_value_frame,
    item_function_frame, frame, text_frame, owned,
):
    body = [frame(
        b"__doc__",
        item_value_frame(
            vars(value).get("__doc__"), seen, depth + 1, item_function_frame,
        ),
    )]
    for name, item in sorted(vars(value).items()):
        if name.startswith("__"):
            continue
        item_frame = _module_item_frame(
            value, name, item, seen, depth, function_frame,
            namespace_value_frame, item_value_frame,
            dependency_value_frame, external_namespace_value_frame,
            item_function_frame, frame, text_frame, owned,
        )
        body.append(frame(name.encode("utf-8"), item_frame))
    return body


def _require_static_module(value):
    if type(value) is not types.ModuleType or "__getattr__" in vars(value):
        raise ProductionBindingError()


def function_dependency_frame(
    function, seen, depth, function_frame, value_frame, frame, text_frame,
    traverse_dependencies=True, owned_globals=None,
    implicit_value_frame=None,
):
    if not traverse_dependencies:
        return function_frame(function, seen, depth + 1, False, False)
    marker = _dep_marker(
        function, owned_globals, function_frame, value_frame, implicit_value_frame)
    cached = cached_frame(seen, marker)
    if cached is not None:
        return cached
    if marker in seen:
        return function_frame(function, seen, depth + 1, False, False)
    if depth > 128:
        raise ProductionBindingError()
    surface = function_frame(function, seen, depth + 1, False, False)
    seen.add(marker)
    dependency_frame = _dependency_function_frame(
        function_frame, value_frame, frame, text_frame,
        implicit_value_frame,
    )
    try:
        implicit_function_frame = (
            dependency_frame if implicit_value_frame is None
            else _surface_function_frame(function_frame)
        )
        implicit = _implicit_dependency_frame(
            function, seen, depth, implicit_function_frame,
            implicit_value_frame or value_frame, frame,
        )
        dependencies = _global_dependency_frames(
            function, seen, depth, function_frame, value_frame,
            dependency_frame, owned_globals, frame,
        )
        body = surface + implicit + frame(
            b"dependencies", b"".join(dependencies))
        return remember_frame(
            seen, marker, frame(b"module-function", body))
    finally:
        seen.remove(marker)


def _global_dependency_frames(
    function, seen, depth, function_frame, value_frame,
    dependency_frame, owned_globals, frame,
):
    dependencies = []
    for name in _loaded_global_names(function.__code__):
        if name in function.__globals__ and name != "__builtins__":
            target = function.__globals__[name]
        elif type(function.__builtins__) is dict and name in function.__builtins__:
            target = function.__builtins__[name]
        else:
            raise ProductionBindingError()
        if (owned_globals is not None
                and isinstance(target, types.FunctionType)
                and target.__globals__ is owned_globals):
            target_frame = function_frame(
                target, seen, depth + 1, False, False)
        else:
            target_frame = _dependency_value_frame(
                target, seen, depth + 1, dependency_frame, value_frame)
        dependencies.append(frame(name.encode("utf-8"), target_frame))
    return dependencies


def _dep_marker(
    function, owned_globals, function_frame, value_frame, implicit_value_frame
):
    return (
        "dependency-function", id(function), id(owned_globals),
        frame_policy(function_frame), frame_policy(value_frame),
        frame_policy(implicit_value_frame or value_frame),
    )


def _dependency_function_frame(
    function_frame, value_frame, frame, text_frame, implicit_value_frame=None
):
    base_function_frame = getattr(
        function_frame, "_semantic_dependency_base", function_frame)

    def dependency(function, seen, depth, enforce_static=False, traverse_globals=True):
        return function_dependency_frame(
            function, seen, depth, base_function_frame,
            value_frame, frame, text_frame, traverse_globals,
            implicit_value_frame=implicit_value_frame,
        )

    dependency._semantic_policy = (
        "dependency", frame_policy(base_function_frame),
        frame_policy(value_frame),
        frame_policy(implicit_value_frame or value_frame),
    )
    dependency._semantic_dependency_base = base_function_frame
    dependency._semantic_dependency = True
    return dependency


def _surface_function_frame(function_frame):
    if getattr(function_frame, "_semantic_surface", False):
        return function_frame

    def surface(function, seen, depth, enforce_static=False, traverse_globals=False):
        return function_frame(function, seen, depth, False, False)

    surface._semantic_policy = ("surface", frame_policy(function_frame))
    surface._semantic_surface = True
    return surface


def _module_item_frame(
    owner, name, item, seen, depth, function_frame, shallow_value_frame,
    namespace_value_frame,
    dependency_value_frame, external_namespace_value_frame,
    namespace_function_frame, frame, text_frame, owned,
):
    if isinstance(item, types.ModuleType):
        if _module_is_explicitly_mounted(item):
            return module_frame(
                item, seen, depth + 1, namespace_function_frame,
                shallow_value_frame, dependency_value_frame,
                external_namespace_value_frame, frame, text_frame, True,
            )
        if name in seen.attribute_names:
            raise ProductionBindingError()
        return frame(b"module-reference", text_frame((item.__name__,)))
    if not isinstance(item, types.FunctionType):
        return namespace_value_frame(
            item, seen, depth + 1, namespace_function_frame)
    if not owned:
        return namespace_function_frame(
            item, seen, depth + 1, False,
            item.__globals__ is not vars(owner)
            or name in seen.module_attributes.get(id(owner), ()),
        )
    return function_dependency_frame(
        item, seen, depth + 1, function_frame,
        dependency_value_frame, frame, text_frame,
        owned_globals=(vars(owner) if item.__globals__ is vars(owner) else None),
    )


def _module_owns_behavior(value):
    return value.__name__.startswith("backend.") or value.__spec__ is None


def _module_is_explicitly_mounted(value):
    spec = value.__spec__
    return spec is None or spec.loader is None


def _module_marker(
    value, function_frame, namespace_value_frame, dependency_value_frame,
    external_namespace_value_frame, force_external,
):
    return (
        "module", id(value), frame_policy(function_frame),
        frame_policy(namespace_value_frame),
        frame_policy(dependency_value_frame),
        frame_policy(external_namespace_value_frame),
        force_external,
    )


def _dependency_value_frame(value, seen, depth, function_frame, value_frame):
    if isinstance(value, type):
        from ._semantic_identity import type_frame
        return type_frame(
            value, seen, depth, function_frame,
            constructor_globals=True,
        )
    return value_frame(value, seen, depth, function_frame)


def _implicit_dependency_frame(
    function, seen, depth, function_frame, value_frame, frame
):
    try:
        closure = () if function.__closure__ is None else tuple(
            cell.cell_contents for cell in function.__closure__)
    except ValueError:
        raise ProductionBindingError() from None
    values = (
        function.__defaults__, function.__kwdefaults__,
        closure, function.__dict__,
    )
    return frame(b"implicit-dependencies", b"".join(
        value_frame(value, seen, depth + 1, function_frame)
        for value in values
    ))


def _loaded_global_names(code):
    names = {
        item.argval
        for item in dis.get_instructions(code)
        if item.opname == "LOAD_GLOBAL"
    }
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            names.update(_loaded_global_names(value))
    return tuple(sorted(names))
