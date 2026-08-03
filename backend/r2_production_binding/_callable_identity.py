"""Path-independent behavior identity for reviewed production callables."""

from __future__ import annotations

import dis
import hashlib
import marshal
import types

from .errors import ProductionBindingError
from ._frame_primitives import frame, text_frame
from ._module_identity import function_dependency_frame
from ._semantic_identity import deep_value_frame, type_frame, value_frame
from ._static_code import require_static_code as _require_static_code
from ._traversal import SemanticTraversal, cached_frame, remember_frame
from .vocabulary import ProductionCommandV2


def production_callable_fingerprint_v2(command, callback):
    """Return the closed behavior identity for one fixed command."""
    try:
        if type(command) is not ProductionCommandV2 or not callable(callback):
            raise ProductionBindingError()
        if isinstance(callback, types.MethodType):
            raise ProductionBindingError()
        if not isinstance(callback, types.FunctionType) or callback.__closure__:
            raise ProductionBindingError()
        body = b"\0".join((
            b"r2-production-callable-v2",
            command.value.encode("ascii"),
            _function_frame(callback, SemanticTraversal(), 0),
            _parameter_contract_frame(command, SemanticTraversal()),
        ))
        return hashlib.sha256(body).hexdigest()
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None


def _function_frame(function, seen, depth, enforce_static=True, traverse_globals=True):
    if depth > 128:
        raise ProductionBindingError()
    identity = (function.__module__, function.__qualname__)
    marker = ("function", id(function), enforce_static, traverse_globals)
    cached = cached_frame(seen, marker)
    if cached is not None:
        return cached
    if marker in seen:
        return frame(b"function-reference", text_frame(identity))
    seen.add(marker)
    try:
        seen.attribute_names.update(
            item.argval
            for code in _nested_codes(function.__code__)
            for item in dis.get_instructions(code)
            if item.opname in {"LOAD_ATTR", "LOAD_METHOD"}
        )
        _record_module_attributes(function, seen)
        if traverse_globals and enforce_static is not None:
            _require_static_code(
                function.__code__,
                function.__globals__,
                allow_internal_attributes=not enforce_static,
            )
        if traverse_globals:
            if enforce_static is None:
                nested_frame = _unrestricted_function_frame
            else:
                nested_frame = (_function_frame if enforce_static
                                else _semantic_function_frame)
            globals_body, builtins_body = _global_frames(
                function, seen, depth, nested_frame)
        else:
            nested_frame = _surface_function_frame
            globals_body, builtins_body = [], []
        value_framer = deep_value_frame if traverse_globals else value_frame
        body = _function_body_frame(
            function, seen, depth, nested_frame, value_framer,
            globals_body, builtins_body,
        )
        return remember_frame(seen, marker, frame(b"function", body))
    finally:
        seen.remove(marker)


def _function_body_frame(
    function, seen, depth, nested_frame, value_framer,
    globals_body, builtins_body,
):
    identity = (function.__module__, function.__qualname__, function.__name__)
    return b"".join((
        text_frame(identity),
        frame(b"doc", value_framer(
            function.__doc__, seen, depth + 1, nested_frame
        )),
        frame(b"annotations", _mapping_frame(
            function.__annotations__, seen, depth + 1,
            nested_frame, value_framer,
        )),
        frame(b"code", marshal.dumps(_normalized_code(function.__code__))),
        frame(b"defaults", value_framer(
            function.__defaults__, seen, depth + 1, nested_frame
        )),
        frame(b"kwdefaults", _keyword_defaults_frame(
            function.__kwdefaults__, seen, depth + 1,
            nested_frame, value_framer,
        )),
        frame(b"closure", _closure_frame(
            function, seen, depth + 1, nested_frame, value_framer
        )),
        frame(b"globals", b"".join(globals_body)),
        frame(b"builtins", b"".join(builtins_body)),
        frame(b"function-state", _mapping_frame(
            function.__dict__, seen, depth + 1,
            nested_frame, value_framer,
        )),
    ))


def _semantic_function_frame(
    function, seen, depth, enforce_static=False, traverse_globals=True
):
    return _function_frame(function, seen, depth, False, traverse_globals)


def _unrestricted_function_frame(
    function, seen, depth, enforce_static=None, traverse_globals=True
):
    return _function_frame(function, seen, depth, None, traverse_globals)


def _surface_function_frame(
    function, seen, depth, enforce_static=False, traverse_globals=False
):
    return _function_frame(function, seen, depth, enforce_static, False)


def _parameter_function_frame(
    function, seen, depth, enforce_static=None, traverse_globals=True
):
    return function_dependency_frame(
        function, seen, depth, _function_frame,
        value_frame, frame, text_frame, traverse_globals,
    )


def _global_frames(function, seen, depth, function_frame):
    builtins = function.__builtins__
    if type(builtins) is not dict:
        raise ProductionBindingError()
    names = {
        item.argval
        for code in _nested_codes(function.__code__)
        for item in dis.get_instructions(code)
        if item.opname == "LOAD_GLOBAL"
    }
    globals_body, builtins_body = [], []
    for name in sorted(names):
        if name in function.__globals__ and name != "__builtins__":
            target, output = function.__globals__[name], globals_body
        elif name in builtins:
            target, output = builtins[name], builtins_body
        else:
            raise ProductionBindingError()
        target_frame = deep_value_frame(
            target, seen, depth + 1, function_frame)
        output.append(frame(name.encode("utf-8"), target_frame))
    return globals_body, builtins_body


def _record_module_attributes(function, seen):
    missing = object()
    for code in _nested_codes(function.__code__):
        instructions = tuple(dis.get_instructions(code))
        for index, instruction in enumerate(instructions):
            if instruction.opname != "LOAD_GLOBAL":
                continue
            target = function.__globals__.get(instruction.argval, missing)
            if target is missing and type(function.__builtins__) is dict:
                target = function.__builtins__.get(instruction.argval, missing)
            for following in instructions[index + 1:]:
                if (
                    following.opname not in {"LOAD_ATTR", "LOAD_METHOD"}
                    or not isinstance(target, types.ModuleType)
                ):
                    break
                seen.module_attributes.setdefault(id(target), set()).add(
                    following.argval
                )
                target = vars(target).get(following.argval, missing)


def _normalized_code(code):
    constants = tuple(
        _normalized_code(value) if isinstance(value, types.CodeType) else value
        for value in code.co_consts
    )
    return code.replace(co_consts=constants, co_filename="", co_firstlineno=0)


def _nested_codes(code):
    return (code, *(
        nested
        for value in code.co_consts if isinstance(value, types.CodeType)
        for nested in _nested_codes(value)
    ))


def _keyword_defaults_frame(
    values, seen, depth, function_frame, value_framer=deep_value_frame
):
    if values is None:
        return frame(b"none", b"")
    return _mapping_frame(
        values, seen, depth, function_frame, value_framer)


def _closure_frame(
    function, seen, depth, function_frame, value_framer=deep_value_frame
):
    closure = function.__closure__
    if closure is None:
        return frame(b"none", b"")
    try:
        values = tuple(cell.cell_contents for cell in closure)
    except ValueError:
        raise ProductionBindingError() from None
    return frame(b"cells", b"".join(
        frame(str(index).encode("ascii"), value_framer(
            value, seen, depth + 1, function_frame
        ))
        for index, value in enumerate(values)
    ))


def _mapping_frame(
    values, seen, depth, function_frame, value_framer=deep_value_frame
):
    if type(values) is not dict or any(type(name) is not str for name in values):
        raise ProductionBindingError()
    return frame(b"mapping", b"".join(
        frame(name.encode("utf-8"), value_framer(
            values[name], seen, depth + 1, function_frame
        ))
        for name in sorted(values)
    ))


def _parameter_contract_frame(command, seen):
    from .binding import ApprovedCutoverBindingV2
    from .claim import DurableAuthorityClaimV2
    parameter_types = [ApprovedCutoverBindingV2, DurableAuthorityClaimV2]
    if command in {
        ProductionCommandV2.EXECUTE,
        ProductionCommandV2.RESUME,
        ProductionCommandV2.ROLLBACK,
    }:
        parameter_types.extend((str, str, str))
    return frame(b"parameter-types", b"".join(
        type_frame(item, seen, 0, _parameter_function_frame, True)
        for item in parameter_types
    ))
