"""Fail-closed bytecode policy for reviewed production callables."""

from __future__ import annotations

import dis
import types

from .errors import ProductionBindingError
from ._module_identity import _module_is_explicitly_mounted


_FORBIDDEN_NAMES = frozenset({
    "__builtins__", "__dict__", "__getattribute__", "__setattr__",
    "__delattr__", "__subclasses__", "_getframe", "currentframe",
    "f_globals", "f_locals", "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr", "eval", "exec", "compile",
    "__import__", "importlib", "import_module", "reload", "find_spec",
    "module_from_spec", "exec_module", "modules", "breakpoint", "input",
    "__package__", "__loader__", "__spec__", "__file__", "__cached__",
    "__path__", "__globals__",
})
_FORBIDDEN_OPCODES = frozenset({
    "IMPORT_STAR", "LOAD_BUILD_CLASS", "LOAD_NAME", "STORE_NAME",
    "DELETE_NAME", "STORE_GLOBAL", "DELETE_GLOBAL", "IMPORT_NAME",
    "IMPORT_FROM",
})


def require_static_code(code, global_values, *, allow_internal_attributes=False):
    forbidden_names = _FORBIDDEN_NAMES
    if allow_internal_attributes:
        forbidden_names -= {"__getattribute__", "__setattr__", "__delattr__"}
    if set(code.co_names) & forbidden_names or any(
        type(value) is str and value in forbidden_names
        for value in code.co_consts
    ):
        raise ProductionBindingError()
    instructions = tuple(dis.get_instructions(code))
    if any(item.opname in _FORBIDDEN_OPCODES for item in instructions):
        raise ProductionBindingError()
    _reject_imported_nested_module_access(instructions, global_values)
    for item, following in zip(instructions, instructions[1:]):
        if (
            item.opname == "LOAD_GLOBAL"
            and following.opname in {"LOAD_ATTR", "LOAD_METHOD"}
            and isinstance(global_values.get(item.argval), types.FunctionType)
        ):
            raise ProductionBindingError()
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            require_static_code(
                value,
                global_values,
                allow_internal_attributes=allow_internal_attributes,
            )


def _reject_imported_nested_module_access(instructions, global_values):
    missing = object()
    for index, instruction in enumerate(instructions):
        if instruction.opname != "LOAD_GLOBAL":
            continue
        target = global_values.get(instruction.argval, missing)
        if not isinstance(target, types.ModuleType):
            continue
        for following in instructions[index + 1:]:
            if following.opname not in {"LOAD_ATTR", "LOAD_METHOD"}:
                break
            target = vars(target).get(following.argval, missing)
            if target is missing:
                break
            if isinstance(target, types.ModuleType):
                if not _module_is_explicitly_mounted(target):
                    raise ProductionBindingError()
                continue
            break
