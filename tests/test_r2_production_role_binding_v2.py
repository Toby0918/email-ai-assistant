"""Reviewed callable-code binding for all three production process roots."""

import io
import itertools
import json
import math
import operator
import random
import re
import struct
import types
import unittest
import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from importlib.machinery import ModuleSpec

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.r2_evidence_process import EvidenceProductionRoleV2
from backend.r2_final_master_closure import FinalMasterBindingV1
from backend.r2_preflight_process import PreflightProductionRolesV2
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    OperatorRoleV2,
    ProductionBindingError,
    ProductionCommandV2,
    ProductionRoleV2,
    PublicKeyRoleV2,
    command_production_role_v2,
    production_callable_fingerprint_v2,
)
from backend.r2_transaction_process import TransactionProductionRolesV2
import backend.r2_production_binding.binding as binding_module


def _preflight_callback(binding, claim):
    return binding, claim


def _evidence_callback(binding, claim):
    return binding, claim


def _transaction_callback(binding, claim, head, transition, plan):
    return binding, claim, head, transition, plan


_CALLBACK_MODE = "safe"
_DYNAMIC_MODE = "safe"


def _global_callback(binding, claim):
    return _CALLBACK_MODE


def _default_callback(binding, claim, mode="safe"):
    return mode


def _replacement_callback(binding, claim):
    return "unsafe"


def _dynamic_global_callback(binding, claim):
    return globals()["_DYNAMIC_MODE"]


def _nested_dynamic_global_callback(binding, claim):
    def lookup():
        return globals()["_DYNAMIC_MODE"]

    return lookup()


def _import_callback(binding, claim):
    import r2_probe_dynamic_import

    return r2_probe_dynamic_import.mode


def _helper_callback(binding, claim):
    return binding, claim


_helper_callback.mode = "safe"


def _attribute_callback(binding, claim):
    return _helper_callback.mode


def _module_attribute_callback(binding, claim):
    return math.ceil(1.5)


_LOCALE_PATTERN = re.compile(b"[a-z]", re.LOCALE)


def _locale_pattern_callback(binding, claim):
    return bool(_LOCALE_PATTERN.match(b"a"))


class _ReviewedMode:
    value = "safe"


def _class_attribute_callback(binding, claim):
    return _ReviewedMode.value


def _module_alias_attribute_callback(binding, claim):
    dependency = math
    return dependency.ceil(1.5)


def _class_alias_attribute_callback(binding, claim):
    dependency = _ReviewedMode
    return dependency.value


class _AlternateMode:
    value = "alternate"


def _conditional_attribute_callback(binding, claim):
    dependency = _ReviewedMode if binding else _AlternateMode
    return dependency.value


def _choose_reviewed_mode():
    return _ReviewedMode


def _helper_return_attribute_callback(binding, claim):
    return _choose_reviewed_mode().value


def _container_attribute_callback(binding, claim):
    dependency = (_ReviewedMode,)[0]
    return dependency.value


def _binding_method_callback(binding, claim):
    return binding.to_mapping()


_CONSTRUCTOR_MODE = "safe"


class _Result:
    def __new__(cls):
        instance = super().__new__(cls)
        instance.mode = _CONSTRUCTOR_MODE
        return instance


def _constructor_callback(binding, claim):
    return _Result()


def _replacement_result_new(cls):
    return object.__new__(cls)


_METHOD_MODE = "safe"


class _MethodResult:
    def value(self):
        return _METHOD_MODE


def _method_callback(binding, claim):
    return _MethodResult().value()


_OBJECT_METHOD_MODE = "safe"


class _ObjectService:
    def value(self):
        return _OBJECT_METHOD_MODE


_OBJECT_SERVICE = _ObjectService()


def _object_method_callback(binding, claim):
    return _OBJECT_SERVICE.value()


class _ObservedDictDescriptor:
    def __init__(self):
        self.calls = 0

    def __get__(self, instance, owner):
        self.calls += 1
        return {"hidden": "unsafe"}


_OBSERVED_DICT_DESCRIPTOR = _ObservedDictDescriptor()


class _CustomDictState:
    __dict__ = _OBSERVED_DICT_DESCRIPTOR
    value = "safe"


_CUSTOM_DICT_STATE = _CustomDictState()


def _custom_dict_descriptor_callback(binding, claim):
    return _CUSTOM_DICT_STATE.value


_SPOOF_META_COUNTS = {"calls": 0}


class _SpoofIdentityMeta(type):
    def __getattribute__(cls, name):
        if name in {
            "__dict__", "__mro__", "__module__", "__qualname__", "__name__",
        }:
            _SPOOF_META_COUNTS["calls"] += 1
            if name == "__dict__":
                return {}
            if name == "__mro__":
                return (cls, object)
            if name == "__module__":
                return "reviewed.spoofed"
            return "Spoofed"
        return type.__getattribute__(cls, name)


class _SpoofIdentityState(metaclass=_SpoofIdentityMeta):
    MODE = "safe"


def _spoof_identity_callback(binding, claim):
    return _SpoofIdentityState.MODE


_CROSS_METHOD_MODULE = types.ModuleType("reviewed_cross_method")
exec(
    "MODE = 'safe'\n"
    "def instance(self): return MODE\n"
    "def static(): return MODE\n"
    "def class_value(cls): return MODE",
    _CROSS_METHOD_MODULE.__dict__,
)


class _CrossModuleService:
    instance = _CROSS_METHOD_MODULE.instance
    static = staticmethod(_CROSS_METHOD_MODULE.static)
    class_value = classmethod(_CROSS_METHOD_MODULE.class_value)


_CROSS_MODULE_SERVICE = _CrossModuleService()


def _cross_instance_callback(binding, claim):
    return _CROSS_MODULE_SERVICE.instance()


def _cross_static_callback(binding, claim):
    return _CrossModuleService.static()


def _cross_class_callback(binding, claim):
    return _CrossModuleService.class_value()


_BOUND_RECEIVER_MODE = "safe"


class _BoundWorker:
    def run(self):
        return _BOUND_RECEIVER_MODE


class _BoundService:
    def __init__(self):
        self.worker = _BoundWorker()

    def run(self):
        return self.worker.run()


_BOUND_HANDLER = _BoundService().run


def _bound_method_callback(binding, claim):
    return _BOUND_HANDLER()


_CUSTOM_META_MODULE = types.ModuleType("reviewed_custom_meta_method")
exec(
    "MODE = 'safe'\n"
    "class Meta(type): pass\n"
    "def run(self): return MODE",
    _CUSTOM_META_MODULE.__dict__,
)


class _CustomMetaService(metaclass=_CUSTOM_META_MODULE.Meta):
    pass


_CustomMetaService.run = _CUSTOM_META_MODULE.run
_CUSTOM_META_SERVICE = _CustomMetaService()


def _custom_meta_method_callback(binding, claim):
    return _CUSTOM_META_SERVICE.run()


_ENUM_METHOD_MODE = "safe"


class _BehaviorMode(Enum):
    ACTIVE = "active"

    def __init__(self, value):
        self.state = "safe"

    def run(self):
        return _ENUM_METHOD_MODE

    def state_value(self):
        return self.state


_ENUM_HANDLER = _BehaviorMode.ACTIVE


def _enum_member_callback(binding, claim):
    return _ENUM_HANDLER.run()


def _enum_member_state_callback(binding, claim):
    return _ENUM_HANDLER.state_value()


_STATIC_DESCRIPTOR_MODE = "safe"


def _static_descriptor_target():
    return _STATIC_DESCRIPTOR_MODE


_STATIC_HANDLER = staticmethod(_static_descriptor_target)


def _static_descriptor_callback(binding, claim):
    return _STATIC_HANDLER()


_PROPERTY_DESCRIPTOR_MODE = "safe"


class _PropertyReceiver:
    pass


def _property_descriptor_target(receiver):
    return _PROPERTY_DESCRIPTOR_MODE


_PROPERTY_RECEIVER = _PropertyReceiver()
_PROPERTY_HANDLER = property(_property_descriptor_target)


def _property_descriptor_callback(binding, claim):
    return _PROPERTY_HANDLER.fget(_PROPERTY_RECEIVER)


class _SlottedService:
    __slots__ = ("mode",)

    def __init__(self):
        self.mode = "safe"

    def run(self):
        return self.mode


_SLOTTED_SERVICE = _SlottedService()


def _slotted_service_callback(binding, claim):
    return _SLOTTED_SERVICE.run()


_BUILTIN_RECEIVER = {"value": "safe"}
_BUILTIN_HANDLER = _BUILTIN_RECEIVER.get


def _builtin_bound_method_callback(binding, claim):
    return _BUILTIN_HANDLER("value")


class _SlotBase:
    __slots__ = ("mode",)


class _ShadowSlotService(_SlotBase):
    __slots__ = ("mode",)

    def run(self):
        return _SlotBase.mode.__get__(self)


_SHADOW_SLOT_SERVICE = _ShadowSlotService()
_SlotBase.mode.__set__(_SHADOW_SLOT_SERVICE, "safe")
_ShadowSlotService.mode.__set__(_SHADOW_SLOT_SERVICE, "shadow")


def _shadow_slot_callback(binding, claim):
    return _SHADOW_SLOT_SERVICE.run()


_METHOD_WRAPPER_RECEIVER = ["safe"]
_METHOD_WRAPPER_HANDLER = _METHOD_WRAPPER_RECEIVER.__iter__


def _method_wrapper_callback(binding, claim):
    return next(_METHOD_WRAPPER_HANDLER())


_OPAQUE_STREAM = io.StringIO("safe")
_OPAQUE_ITERATOR = iter(["safe"])
_OPAQUE_RANDOM = random.Random(1)
_OPAQUE_COUNTER = itertools.count(10)


def _opaque_stream_callback(binding, claim):
    return _OPAQUE_STREAM.getvalue()


def _opaque_iterator_callback(binding, claim):
    return next(_OPAQUE_ITERATOR)


def _opaque_random_callback(binding, claim):
    return _OPAQUE_RANDOM.random()


def _opaque_counter_callback(binding, claim):
    return next(_OPAQUE_COUNTER)


class _AlternateEncoder(json.JSONEncoder):
    pass


def _json_callback(binding, claim):
    return json.dumps({"safe": True})


_EXTERNAL_IMPL = types.ModuleType("reviewed_external_impl")
_EXTERNAL_IMPL.__spec__ = ModuleSpec("reviewed_external_impl", None)
exec(
    "MODE = 'safe'\n"
    "class Service:\n"
    "    def run(self):\n"
    "        return MODE\n"
    "def action():\n"
    "    return MODE\n",
    _EXTERNAL_IMPL.__dict__,
)
_EXTERNAL_API = types.ModuleType("reviewed_external_api")
_EXTERNAL_API.__spec__ = ModuleSpec("reviewed_external_api", None)
_EXTERNAL_API.SINGLETON = _EXTERNAL_IMPL.Service()
_EXTERNAL_API.TYPE_BOX = (_EXTERNAL_IMPL.Service,)


def _external_singleton_callback(binding, claim):
    return _EXTERNAL_API.SINGLETON.run()


def _external_container_type_callback(binding, claim):
    return _EXTERNAL_API.TYPE_BOX[0]().run()


def _external_exported_function_callback(binding, claim):
    return _EXTERNAL_FUNCTION_API.ACTION()


_EXTERNAL_FUNCTION_IMPL = types.ModuleType("reviewed_function_impl")
_EXTERNAL_FUNCTION_IMPL.__spec__ = ModuleSpec("reviewed_function_impl", None)
exec(
    "MODE = 'safe'\n"
    "def action():\n"
    "    return MODE\n",
    _EXTERNAL_FUNCTION_IMPL.__dict__,
)
_EXTERNAL_FUNCTION_API = types.ModuleType("reviewed_function_api")
_EXTERNAL_FUNCTION_API.__spec__ = ModuleSpec("reviewed_function_api", None)
_EXTERNAL_FUNCTION_API.ACTION = _EXTERNAL_FUNCTION_IMPL.action


_EXTERNAL_NAMESPACE_DEP = types.ModuleType("reviewed_namespace_dep")
_EXTERNAL_NAMESPACE_DEP.__spec__ = ModuleSpec(
    "reviewed_namespace_dep", object())
_EXTERNAL_NAMESPACE_DEP.MODE = "safe"
_EXTERNAL_NAMESPACE_API = types.ModuleType("reviewed_namespace_api")
_EXTERNAL_NAMESPACE_API.__spec__ = ModuleSpec(
    "reviewed_namespace_api", object())
_EXTERNAL_NAMESPACE_API.DEP = _EXTERNAL_NAMESPACE_DEP
exec(
    "def action():\n"
    "    return DEP.MODE\n",
    _EXTERNAL_NAMESPACE_API.__dict__,
)


def _external_namespace_function_callback(binding, claim):
    return _EXTERNAL_NAMESPACE_API.action()


_EXTERNAL_STATE_DEP = types.ModuleType("reviewed_state_dep")
_EXTERNAL_STATE_DEP.__spec__ = ModuleSpec("reviewed_state_dep", None)
exec("def action():\n    return 'safe'\n", _EXTERNAL_STATE_DEP.__dict__)
_EXTERNAL_STATE_IMPL = types.ModuleType("reviewed_state_impl")
_EXTERNAL_STATE_IMPL.__spec__ = ModuleSpec("reviewed_state_impl", None)
exec(
    "class Service:\n"
    "    def __init__(self, dep):\n"
    "        self.dep = dep\n"
    "    def run(self):\n"
    "        return self.dep.action()\n",
    _EXTERNAL_STATE_IMPL.__dict__,
)
_EXTERNAL_STATE_API = types.ModuleType("reviewed_state_api")
_EXTERNAL_STATE_API.__spec__ = ModuleSpec("reviewed_state_api", None)
_EXTERNAL_STATE_API.SINGLETON = _EXTERNAL_STATE_IMPL.Service(
    _EXTERNAL_STATE_DEP)


def _external_state_module_callback(binding, claim):
    return _EXTERNAL_STATE_API.SINGLETON.run()


_EXTERNAL_META_HELPER = types.ModuleType("reviewed_meta_helper")
_EXTERNAL_META_HELPER.__spec__ = ModuleSpec("reviewed_meta_helper", None)
exec(
    "MODE = 'safe'\n"
    "def helper():\n"
    "    return MODE\n",
    _EXTERNAL_META_HELPER.__dict__,
)
_EXTERNAL_META_IMPL = types.ModuleType("reviewed_meta_impl")
_EXTERNAL_META_IMPL.__spec__ = ModuleSpec("reviewed_meta_impl", None)
_EXTERNAL_META_IMPL.HELPER = _EXTERNAL_META_HELPER
exec(
    "class Meta(type):\n"
    "    def __call__(cls):\n"
    "        return HELPER.helper()\n"
    "class Service(metaclass=Meta):\n"
    "    pass\n",
    _EXTERNAL_META_IMPL.__dict__,
)
_EXTERNAL_META_API = types.ModuleType("reviewed_meta_api")
_EXTERNAL_META_API.__spec__ = ModuleSpec("reviewed_meta_api", None)
_EXTERNAL_META_API.Service = _EXTERNAL_META_IMPL.Service


def _external_metaclass_callback(binding, claim):
    return _EXTERNAL_META_API.Service()


_EXTERNAL_BASE = types.ModuleType("reviewed_external_base")
_EXTERNAL_BASE.__spec__ = ModuleSpec("reviewed_external_base", None)
exec(
    "MODE = 'safe'\n"
    "class Base:\n"
    "    def run(self):\n"
    "        return MODE\n",
    _EXTERNAL_BASE.__dict__,
)
_EXTERNAL_DERIVED = types.ModuleType("reviewed_external_derived")
_EXTERNAL_DERIVED.__spec__ = ModuleSpec("reviewed_external_derived", None)
_EXTERNAL_DERIVED.Base = _EXTERNAL_BASE.Base
exec("class Service(Base):\n    pass\n", _EXTERNAL_DERIVED.__dict__)
_EXTERNAL_DERIVED_API = types.ModuleType("reviewed_derived_api")
_EXTERNAL_DERIVED_API.__spec__ = ModuleSpec("reviewed_derived_api", None)
_EXTERNAL_DERIVED_API.Service = _EXTERNAL_DERIVED.Service


def _external_inherited_method_callback(binding, claim):
    return _EXTERNAL_DERIVED_API.Service().run()


_EXTERNAL_UNUSED_IMPL = types.ModuleType("reviewed_unused_impl")
_EXTERNAL_UNUSED_IMPL.__spec__ = ModuleSpec("reviewed_unused_impl", None)
exec(
    "MODE = 'one'\n"
    "def helper():\n"
    "    return MODE\n"
    "def run():\n"
    "    return 'safe'\n"
    "run.unused = helper\n",
    _EXTERNAL_UNUSED_IMPL.__dict__,
)
_EXTERNAL_UNUSED_API = types.ModuleType("reviewed_unused_api")
_EXTERNAL_UNUSED_API.__spec__ = ModuleSpec("reviewed_unused_api", None)
_EXTERNAL_UNUSED_API.RUN = _EXTERNAL_UNUSED_IMPL.run


def _external_unused_implicit_callback(binding, claim):
    return _EXTERNAL_UNUSED_API.RUN()


_DYNAMIC_NAMESPACE = types.ModuleType("reviewed_dynamic_namespace")
_DYNAMIC_NAMESPACE.__spec__ = ModuleSpec("reviewed_dynamic_namespace", None)
_DYNAMIC_NAMESPACE.__getattr__ = lambda name: "unsafe"


def _dynamic_namespace_callback(binding, claim):
    return _DYNAMIC_NAMESPACE.value


class _DynamicModule(types.ModuleType):
    def __getattribute__(self, name):
        if name == "value":
            return "unsafe"
        return super().__getattribute__(name)


_DYNAMIC_MODULE_SUBCLASS = _DynamicModule("reviewed_dynamic_subclass")
_DYNAMIC_MODULE_SUBCLASS.__spec__ = ModuleSpec(
    "reviewed_dynamic_subclass", None)


def _dynamic_module_subclass_callback(binding, claim):
    return _DYNAMIC_MODULE_SUBCLASS.value


_CLASS_STATE_BASE = types.ModuleType("reviewed_class_state_base")
_CLASS_STATE_BASE.__spec__ = ModuleSpec("reviewed_class_state_base", None)
exec(
    "MODE = 'one'\n"
    "class Base:\n"
    "    def act(self):\n"
    "        return MODE\n",
    _CLASS_STATE_BASE.__dict__,
)
_CLASS_STATE_IMPL = types.ModuleType("reviewed_class_state_impl")
_CLASS_STATE_IMPL.__spec__ = ModuleSpec("reviewed_class_state_impl", None)
_CLASS_STATE_IMPL.Base = _CLASS_STATE_BASE.Base
exec("class Derived(Base):\n    pass\n", _CLASS_STATE_IMPL.__dict__)
_CLASS_STATE_API = types.ModuleType("reviewed_class_state_api")
_CLASS_STATE_API.__spec__ = ModuleSpec("reviewed_class_state_api", None)
_CLASS_STATE_API.Derived = _CLASS_STATE_IMPL.Derived
exec(
    "class Carrier:\n"
    "    agent = Derived()\n"
    "    def run(self):\n"
    "        return self.agent.act()\n",
    _CLASS_STATE_API.__dict__,
)
del _CLASS_STATE_API.Derived


def _class_state_object_callback(binding, claim):
    return _CLASS_STATE_API.Carrier().run()


_OWNED_EXTERNAL_BRIDGE = types.ModuleType(
    "backend.reviewed_owned_external_bridge")
_OWNED_EXTERNAL_BRIDGE.EXTERNAL = _EXTERNAL_UNUSED_API
exec(
    "def go():\n"
    "    return EXTERNAL.RUN()\n",
    _OWNED_EXTERNAL_BRIDGE.__dict__,
)


def _owned_external_unused_callback(binding, claim):
    return _OWNED_EXTERNAL_BRIDGE.go()


_META_STATE_API = types.ModuleType("reviewed_meta_state_api")
_META_STATE_API.__spec__ = ModuleSpec("reviewed_meta_state_api", None)
exec(
    "class Meta(type):\n"
    "    config = 'one'\n"
    "    def __call__(cls):\n"
    "        return type(cls).config\n"
    "class Factory(metaclass=Meta):\n"
    "    pass\n",
    _META_STATE_API.__dict__,
)
_META_STATE_TYPE = _META_STATE_API.Meta
del _META_STATE_API.Meta


def _metaclass_state_callback(binding, claim):
    return _META_STATE_API.Factory()


_ANNOTATION_STATE_API = types.ModuleType("reviewed_annotation_state_api")
_ANNOTATION_STATE_API.__spec__ = ModuleSpec(
    "reviewed_annotation_state_api", None)
exec(
    "class Service:\n"
    "    marker: str\n"
    "    @classmethod\n"
    "    def run(cls):\n"
    "        return cls.__annotations__['marker']\n",
    _ANNOTATION_STATE_API.__dict__,
)


def _annotation_state_callback(binding, claim):
    return _ANNOTATION_STATE_API.Service.run()


_NAME_STATE_API = types.ModuleType("reviewed_name_state_api")
_NAME_STATE_API.__spec__ = ModuleSpec("reviewed_name_state_api", None)
exec(
    "class Service:\n"
    "    @classmethod\n"
    "    def run(cls):\n"
    "        return cls.__name__\n",
    _NAME_STATE_API.__dict__,
)


def _name_state_callback(binding, claim):
    return _NAME_STATE_API.Service.run()


@dataclass
class _DataclassMetadataState:
    value: str = "one"

    @classmethod
    def current_default(cls):
        return cls.__dataclass_fields__["value"].default


def _dataclass_metadata_callback(binding, claim):
    return _DataclassMetadataState.current_default()


class _ObservedMetadata(Mapping):
    def __init__(self):
        self.calls = 0

    def __getitem__(self, key):
        self.calls += 1
        return "one"

    def __iter__(self):
        self.calls += 1
        return iter(("scope",))

    def __len__(self):
        self.calls += 1
        return 1


_NAN_VALUE = struct.unpack(">d", bytes.fromhex("7ff8000000000001"))[0]
_SLICE_VALUE = slice(None, 1, None)


def _nan_payload_callback(binding, claim):
    return struct.pack(">d", _NAN_VALUE).hex()


def _slice_type_callback(binding, claim):
    return isinstance(_SLICE_VALUE.stop, str)


_COMPLEX_API = types.ModuleType("reviewed_complex_api")
_COMPLEX_API.__spec__ = ModuleSpec("reviewed_complex_api", None)
_COMPLEX_API.VALUE = 1 + 2j


def _complex_value_callback(binding, claim):
    return _COMPLEX_API.VALUE


_SPOOF_BASE = types.ModuleType("reviewed_spoof_base")
_SPOOF_BASE.__spec__ = ModuleSpec("reviewed_spoof_base", None)
exec(
    "MODE = 'one'\n"
    "class Base:\n"
    "    def run(self):\n"
    "        return MODE\n",
    _SPOOF_BASE.__dict__,
)
_SPOOF_API = types.ModuleType("reviewed_spoof_api")
_SPOOF_API.__spec__ = ModuleSpec("reviewed_spoof_api", None)
_SPOOF_API.Base = _SPOOF_BASE.Base
exec("class Service(Base):\n    pass\n", _SPOOF_API.__dict__)
_SPOOF_API.Service.__module__ = "builtins"
del _SPOOF_API.Base


def _spoofed_builtin_callback(binding, claim):
    return _SPOOF_API.Service().run()


_NESTED_VALUE_MODULE = types.ModuleType("reviewed_nested_value")
_NESTED_VALUE_MODULE.__spec__ = ModuleSpec("reviewed_nested_value", None)
_NESTED_VALUE_MODULE.VALUE = "one"
_NESTED_VALUE_API = types.ModuleType("reviewed_nested_value_api")
_NESTED_VALUE_API.__spec__ = ModuleSpec("reviewed_nested_value_api", None)
_NESTED_VALUE_API.sub = _NESTED_VALUE_MODULE


def _nested_module_value_callback(binding, claim):
    return _NESTED_VALUE_API.sub.VALUE


_MODULE_DUNDER_API = types.ModuleType("reviewed_module_dunder_api")
_MODULE_DUNDER_API.__spec__ = ModuleSpec("reviewed_module_dunder_api", None)
_MODULE_DUNDER_API.__package__ = "one"


def _module_dunder_callback(binding, claim):
    return _MODULE_DUNDER_API.__package__


_MODULE_DOC_API = types.ModuleType("reviewed_module_doc_api", "one")
_MODULE_DOC_API.__spec__ = ModuleSpec("reviewed_module_doc_api", None)


def _module_doc_callback(binding, claim):
    return _MODULE_DOC_API.__doc__


_MOUNT_POLICY_HELPER = types.ModuleType("reviewed_mount_policy_helper")
_MOUNT_POLICY_HELPER.__spec__ = ModuleSpec(
    "reviewed_mount_policy_helper", None)
_MOUNT_POLICY_HELPER.MODE = "one"
_MOUNT_POLICY_MODULE = types.ModuleType("reviewed_mount_policy")
_MOUNT_POLICY_MODULE.HELPER = _MOUNT_POLICY_HELPER
exec(
    "class Service:\n"
    "    def run(self): return HELPER.MODE\n"
    "singleton = Service()\n",
    _MOUNT_POLICY_MODULE.__dict__,
)
_MOUNT_POLICY_API = types.ModuleType("reviewed_mount_policy_api")
_MOUNT_POLICY_API.__spec__ = ModuleSpec("reviewed_mount_policy_api", None)
_MOUNT_POLICY_API.mount = _MOUNT_POLICY_MODULE


def _mounted_singleton_callback(binding, claim):
    return _MOUNT_POLICY_API.mount.singleton.run()


_IMPORTED_VALUE_MODULE = types.ModuleType("reviewed_imported_value")
_IMPORTED_VALUE_MODULE.__spec__ = ModuleSpec(
    "reviewed_imported_value", object())
_IMPORTED_VALUE_MODULE.VALUE = "one"
_IMPORTED_VALUE_API = types.ModuleType("reviewed_imported_value_api")
_IMPORTED_VALUE_API.__spec__ = ModuleSpec(
    "reviewed_imported_value_api", None)
_IMPORTED_VALUE_API.cache = _IMPORTED_VALUE_MODULE


def _imported_nested_value_callback(binding, claim):
    return _IMPORTED_VALUE_API.cache.VALUE


def _return_first_module(values):
    return values[0]


def _imported_nested_alias_helper_container_callback(binding, claim):
    local = _IMPORTED_VALUE_API
    return _return_first_module((local,)).cache.VALUE


_DEFAULT_FUNCTION_MODE = "one"


def _default_function_helper():
    return _DEFAULT_FUNCTION_MODE


_default_function_helper.__annotations__["marker"] = "one"


def _default_function_globals_callback(
    binding, claim, helper=_default_function_helper,
):
    return helper.__globals__["_DEFAULT_FUNCTION_MODE"]


def _attrgetter_function_globals_callback(
    binding, claim, helper=_default_function_helper,
):
    return operator.attrgetter("__globals__")(helper)[
        "_DEFAULT_FUNCTION_MODE"]


def _default_function_annotations_callback(
    binding, claim, helper=_default_function_helper,
):
    return helper.__annotations__["marker"]


_EXTERNAL_HELPER = types.ModuleType("reviewed_external_helper")
_EXTERNAL_HELPER.__spec__ = ModuleSpec("reviewed_external_helper", None)
exec(
    "MODE = 'safe'\n"
    "def helper():\n"
    "    return MODE\n",
    _EXTERNAL_HELPER.__dict__,
)
_EXTERNAL_NESTED = types.ModuleType("reviewed_external_nested")
_EXTERNAL_NESTED.__spec__ = ModuleSpec("reviewed_external_nested", None)
_EXTERNAL_NESTED.HELPER = _EXTERNAL_HELPER
exec(
    "class Outer:\n"
    "    class Inner:\n"
    "        def run(self):\n"
    "            return HELPER.helper()\n",
    _EXTERNAL_NESTED.__dict__,
)


def _external_nested_type_callback(binding, claim):
    return _EXTERNAL_NESTED.Outer.Inner().run()


class _ClassState:
    value = "safe"


class _ClassWithObjectConstant:
    state = _ClassState()


def _class_object_constant_callback(binding, claim):
    return _ClassWithObjectConstant.state.value


_METACLASS_MODE = "safe"


class _ResultMeta(type):
    def __call__(cls):
        return _METACLASS_MODE


class _MetaResult(metaclass=_ResultMeta):
    pass


def _metaclass_constructor_callback(binding, claim):
    return _MetaResult()


def _nested_module_action():
    return _nested_module_helper()


_NESTED_MODULE_MODE = "safe"


def _nested_module_helper():
    return _NESTED_MODULE_MODE


_NESTED_MODULE_B = types.ModuleType("reviewed_nested_module_b")
_NESTED_MODULE_B.action = _nested_module_action


def _nested_module_run():
    return _NESTED_MODULE_B.action()


_NESTED_MODULE_A = types.ModuleType("reviewed_nested_module_a")
_NESTED_MODULE_A.run = _nested_module_run


def _nested_module_callback(binding, claim):
    return _NESTED_MODULE_A.run()


_OWNED_MODULE_B = types.ModuleType("reviewed_owned_module_b")
exec("def action(): return 'safe'", _OWNED_MODULE_B.__dict__)
_OWNED_MODULE_A = types.ModuleType("reviewed_owned_module_a")
_OWNED_MODULE_A.dependency = _OWNED_MODULE_B
exec("def run(): return dependency.action()", _OWNED_MODULE_A.__dict__)


def _owned_module_callback(binding, claim):
    return _OWNED_MODULE_A.run()


_CROSS_ROOT_MODULE_C = types.ModuleType("reviewed_root_c")
exec("MODE = 'safe'\ndef action(): return MODE", _CROSS_ROOT_MODULE_C.__dict__)
_CROSS_ROOT_MODULE_B = types.ModuleType("reviewed_root_b")
_CROSS_ROOT_MODULE_B.action = _CROSS_ROOT_MODULE_C.action
exec("def run(): return action()", _CROSS_ROOT_MODULE_B.__dict__)
_CROSS_ROOT_MODULE_A = types.ModuleType("reviewed_root_a")
_CROSS_ROOT_MODULE_A.run = _CROSS_ROOT_MODULE_B.run


def _cross_root_module_callback(binding, claim):
    return _CROSS_ROOT_MODULE_A.run()


_DEFAULT_MODULE = types.ModuleType("reviewed_default_module")
exec(
    "MODE = 'safe'\n"
    "def helper(): return MODE\n"
    "def run(callback=helper): return callback()",
    _DEFAULT_MODULE.__dict__,
)
del _DEFAULT_MODULE.__dict__["helper"]


def _module_default_callback(binding, claim):
    return _DEFAULT_MODULE.run()


class _StatefulCallback:
    def callback(self, binding, claim):
        return binding, claim


class R2ProductionRoleBindingV2Tests(unittest.TestCase):
    def test_all_three_roots_bind_callback_code_to_reviewed_role_fingerprints(self):
        callbacks = {
            command: _preflight_callback
            for command in tuple(ProductionCommandV2)[:6]
        }
        binding = _binding({
            command: callback for command, callback in callbacks.items()
        })
        roles = PreflightProductionRolesV2.create(
            binding=binding,
            **{command.value: callback for command, callback in callbacks.items()},
        )
        for command in callbacks:
            self.assertEqual(
                roles.select(command).implementation_fingerprint,
                dict(binding.production_role_fingerprints)[
                    command_production_role_v2(command)
                ],
            )

        evidence_binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _evidence_callback
        })
        self.assertIsInstance(
            EvidenceProductionRoleV2.create(
                binding=evidence_binding,
                publish_reviewed_evidence=_evidence_callback,
            ),
            EvidenceProductionRoleV2,
        )

        transaction_callbacks = {
            command: _transaction_callback
            for command in (
                ProductionCommandV2.EXECUTE,
                ProductionCommandV2.RESUME,
                ProductionCommandV2.ROLLBACK,
            )
        }
        transaction_binding = _binding(transaction_callbacks)
        self.assertIsInstance(
            TransactionProductionRolesV2.create(
                binding=transaction_binding,
                execute=_transaction_callback,
                resume=_transaction_callback,
                rollback=_transaction_callback,
            ),
            TransactionProductionRolesV2,
        )

    def test_wrong_or_closure_callable_is_rejected_before_it_can_be_invoked(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _evidence_callback
        })
        calls = []

        def injected(binding, claim):
            calls.append(1)
            return binding, claim

        with self.assertRaisesRegex(
            ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
        ):
            EvidenceProductionRoleV2.create(
                binding=binding, publish_reviewed_evidence=injected
            )
        self.assertEqual(calls, [])
        with self.assertRaises(TypeError):
            EvidenceProductionRoleV2(_evidence_callback)

    def test_bound_method_is_rejected_instead_of_ignoring_instance_state(self):
        with self.assertRaisesRegex(
            ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
        ):
            production_callable_fingerprint_v2(
                ProductionCommandV2.EVIDENCE_PUBLICATION,
                _StatefulCallback().callback,
            )

    def test_dynamic_namespace_access_is_rejected_recursively(self):
        for callback in (
            _dynamic_global_callback,
            _nested_dynamic_global_callback,
            _import_callback,
            _attribute_callback,
        ):
            with self.subTest(callback=callback.__name__), self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                production_callable_fingerprint_v2(
                    ProductionCommandV2.EVIDENCE_PUBLICATION, callback
                )

    def test_default_global_and_code_drift_are_rechecked_before_invocation(self):
        global _CALLBACK_MODE
        cases = (
            (_default_callback, lambda: setattr(
                _default_callback, "__defaults__", ("unsafe",)
            )),
            (_global_callback, lambda: globals().__setitem__("_CALLBACK_MODE", "unsafe")),
            (_evidence_callback, lambda: setattr(
                _evidence_callback, "__code__", _replacement_callback.__code__
            )),
        )
        original_defaults = _default_callback.__defaults__
        original_mode = _CALLBACK_MODE
        original_code = _evidence_callback.__code__
        try:
            for callback, mutate in cases:
                binding = _binding({
                    ProductionCommandV2.EVIDENCE_PUBLICATION: callback
                })
                role = EvidenceProductionRoleV2.create(
                    binding=binding, publish_reviewed_evidence=callback
                )
                mutate()
                with self.assertRaisesRegex(
                    ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
                ):
                    role.publish_reviewed_evidence(None, None)
                _default_callback.__defaults__ = original_defaults
                _CALLBACK_MODE = original_mode
                _evidence_callback.__code__ = original_code
        finally:
            _default_callback.__defaults__ = original_defaults
            _CALLBACK_MODE = original_mode
            _evidence_callback.__code__ = original_code

    def test_module_attribute_drift_changes_identity_and_blocks_invocation(self):
        original = math.ceil
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _module_attribute_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_module_attribute_callback
        )
        try:
            math.ceil = lambda value: 999
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(None, None)
        finally:
            math.ceil = original

    def test_locale_dependent_regex_is_rejected(self):
        with self.assertRaisesRegex(
            ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
        ):
            production_callable_fingerprint_v2(
                ProductionCommandV2.EVIDENCE_PUBLICATION,
                _locale_pattern_callback,
            )

    def test_class_attribute_drift_changes_identity_and_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _class_attribute_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_class_attribute_callback
        )
        try:
            _ReviewedMode.value = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(None, None)
        finally:
            _ReviewedMode.value = "safe"

    def test_alias_branch_helper_and_container_flows_bind_dependency_drift(self):
        cases = (
            (_module_alias_attribute_callback, "math"),
            (_class_alias_attribute_callback, "class"),
            (_conditional_attribute_callback, "class"),
            (_helper_return_attribute_callback, "class"),
            (_container_attribute_callback, "class"),
        )
        original_ceil = math.ceil
        try:
            for callback, dependency in cases:
                binding = _binding({
                    ProductionCommandV2.EVIDENCE_PUBLICATION: callback
                })
                role = EvidenceProductionRoleV2.create(
                    binding=binding, publish_reviewed_evidence=callback
                )
                if dependency == "math":
                    math.ceil = lambda value: 999
                else:
                    _ReviewedMode.value = "unsafe"
                with self.subTest(callback=callback.__name__), self.assertRaisesRegex(
                    ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
                ):
                    role.publish_reviewed_evidence(binding, None)
                math.ceil = original_ceil
                _ReviewedMode.value = "safe"
        finally:
            math.ceil = original_ceil
            _ReviewedMode.value = "safe"

    def test_exact_parameter_method_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _binding_method_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_binding_method_callback
        )
        original = ApprovedCutoverBindingV2.to_mapping
        try:
            ApprovedCutoverBindingV2.to_mapping = lambda self: {"unsafe": True}
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            ApprovedCutoverBindingV2.to_mapping = original

    def test_exact_parameter_method_global_dependency_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _binding_method_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_binding_method_callback
        )
        original = binding_module._SCALAR_FIELDS
        try:
            binding_module._SCALAR_FIELDS = ()
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            binding_module._SCALAR_FIELDS = original

    def test_global_type_constructor_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _constructor_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_constructor_callback
        )
        original = _Result.__new__
        try:
            _Result.__new__ = _replacement_result_new
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _Result.__new__ = original

    def test_global_type_constructor_dependency_drift_blocks_invocation(self):
        global _CONSTRUCTOR_MODE
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _constructor_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_constructor_callback
        )
        original = _CONSTRUCTOR_MODE
        try:
            _CONSTRUCTOR_MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _CONSTRUCTOR_MODE = original

    def test_global_type_method_dependency_drift_blocks_invocation(self):
        global _METHOD_MODE
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _method_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_method_callback
        )
        original = _METHOD_MODE
        try:
            _METHOD_MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _METHOD_MODE = original

    def test_global_object_method_dependency_drift_blocks_invocation(self):
        global _OBJECT_METHOD_MODE
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _object_method_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_object_method_callback
        )
        original = _OBJECT_METHOD_MODE
        try:
            _OBJECT_METHOD_MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _OBJECT_METHOD_MODE = original

    def test_custom_dict_descriptor_is_rejected_without_execution(self):
        _OBSERVED_DICT_DESCRIPTOR.calls = 0
        with self.assertRaisesRegex(
            ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
        ):
            production_callable_fingerprint_v2(
                ProductionCommandV2.EVIDENCE_PUBLICATION,
                _custom_dict_descriptor_callback,
            )
        self.assertEqual(_OBSERVED_DICT_DESCRIPTOR.calls, 0)

    def test_metaclass_identity_spoof_is_bypassed_and_real_drift_blocks(self):
        _SPOOF_META_COUNTS["calls"] = 0
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _spoof_identity_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_spoof_identity_callback,
        )
        try:
            _SpoofIdentityState.MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
            self.assertEqual(_SPOOF_META_COUNTS["calls"], 0)
        finally:
            _SpoofIdentityState.MODE = "safe"

    def test_cross_module_method_dependency_drift_blocks_invocation(self):
        callbacks = (
            _cross_instance_callback,
            _cross_static_callback,
            _cross_class_callback,
        )
        try:
            for callback in callbacks:
                _CROSS_METHOD_MODULE.MODE = "safe"
                binding = _binding({
                    ProductionCommandV2.EVIDENCE_PUBLICATION: callback
                })
                role = EvidenceProductionRoleV2.create(
                    binding=binding, publish_reviewed_evidence=callback
                )
                _CROSS_METHOD_MODULE.MODE = "unsafe"
                with self.subTest(
                    callback=callback.__name__
                ), self.assertRaisesRegex(
                    ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
                ):
                    role.publish_reviewed_evidence(binding, None)
        finally:
            _CROSS_METHOD_MODULE.MODE = "safe"

    def test_bound_method_receiver_dependency_drift_blocks_invocation(self):
        global _BOUND_RECEIVER_MODE
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _bound_method_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_bound_method_callback
        )
        original = _BOUND_RECEIVER_MODE
        try:
            _BOUND_RECEIVER_MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _BOUND_RECEIVER_MODE = original

    def test_custom_metaclass_explicit_method_dependency_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _custom_meta_method_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_custom_meta_method_callback,
        )
        try:
            _CUSTOM_META_MODULE.MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _CUSTOM_META_MODULE.MODE = "safe"

    def test_enum_member_method_dependency_drift_blocks_invocation(self):
        global _ENUM_METHOD_MODE
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _enum_member_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_enum_member_callback
        )
        original = _ENUM_METHOD_MODE
        try:
            _ENUM_METHOD_MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _ENUM_METHOD_MODE = original

    def test_enum_member_state_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _enum_member_state_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_enum_member_state_callback,
        )
        try:
            _ENUM_HANDLER.state = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _ENUM_HANDLER.state = "safe"

    def test_static_descriptor_dependency_drift_blocks_invocation(self):
        global _STATIC_DESCRIPTOR_MODE
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _static_descriptor_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_static_descriptor_callback,
        )
        original = _STATIC_DESCRIPTOR_MODE
        try:
            _STATIC_DESCRIPTOR_MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _STATIC_DESCRIPTOR_MODE = original

    def test_property_descriptor_dependency_drift_blocks_invocation(self):
        global _PROPERTY_DESCRIPTOR_MODE
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _property_descriptor_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_property_descriptor_callback,
        )
        original = _PROPERTY_DESCRIPTOR_MODE
        try:
            _PROPERTY_DESCRIPTOR_MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _PROPERTY_DESCRIPTOR_MODE = original

    def test_slotted_object_state_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _slotted_service_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_slotted_service_callback
        )
        try:
            _SLOTTED_SERVICE.mode = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _SLOTTED_SERVICE.mode = "safe"

    def test_builtin_bound_receiver_state_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _builtin_bound_method_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_builtin_bound_method_callback,
        )
        try:
            _BUILTIN_RECEIVER["value"] = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _BUILTIN_RECEIVER["value"] = "safe"

    def test_shadowed_base_slot_state_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _shadow_slot_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_shadow_slot_callback
        )
        try:
            _SlotBase.mode.__set__(_SHADOW_SLOT_SERVICE, "unsafe")
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _SlotBase.mode.__set__(_SHADOW_SLOT_SERVICE, "safe")

    def test_method_wrapper_receiver_state_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _method_wrapper_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_method_wrapper_callback
        )
        try:
            _METHOD_WRAPPER_RECEIVER[0] = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _METHOD_WRAPPER_RECEIVER[0] = "safe"

    def test_opaque_native_state_is_rejected(self):
        callbacks = (
            _opaque_stream_callback,
            _opaque_iterator_callback,
            _opaque_random_callback,
            _opaque_counter_callback,
        )
        for callback in callbacks:
            with self.subTest(callback=callback.__name__), self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                production_callable_fingerprint_v2(
                    ProductionCommandV2.EVIDENCE_PUBLICATION, callback
                )

    def test_json_encoder_and_default_encoder_drift_block_invocation(self):
        original_encoder = json.__dict__["JSONEncoder"]
        original_default = json.__dict__["_default_encoder"]
        try:
            for name, replacement in (
                ("JSONEncoder", _AlternateEncoder),
                ("_default_encoder", _AlternateEncoder()),
            ):
                binding = _binding({
                    ProductionCommandV2.EVIDENCE_PUBLICATION: _json_callback
                })
                role = EvidenceProductionRoleV2.create(
                    binding=binding, publish_reviewed_evidence=_json_callback
                )
                json.__dict__[name] = replacement
                with self.subTest(name=name), self.assertRaisesRegex(
                    ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
                ):
                    role.publish_reviewed_evidence(binding, None)
                json.__dict__["JSONEncoder"] = original_encoder
                json.__dict__["_default_encoder"] = original_default
        finally:
            json.__dict__["JSONEncoder"] = original_encoder
            json.__dict__["_default_encoder"] = original_default

    def test_json_encoder_helper_global_drift_blocks_invocation(self):
        import json.encoder as encoder_module

        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _json_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_json_callback
        )
        original = encoder_module.encode_basestring_ascii
        try:
            encoder_module.encode_basestring_ascii = lambda value: '"evil"'
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            encoder_module.encode_basestring_ascii = original

    def test_external_singleton_method_global_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _external_singleton_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_external_singleton_callback,
        )
        try:
            _EXTERNAL_IMPL.MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _EXTERNAL_IMPL.MODE = "safe"

    def test_external_container_type_global_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _external_container_type_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_external_container_type_callback,
        )
        try:
            _EXTERNAL_IMPL.MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _EXTERNAL_IMPL.MODE = "safe"

    def test_external_exported_function_global_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _external_exported_function_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_external_exported_function_callback,
        )
        try:
            _EXTERNAL_FUNCTION_IMPL.MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _EXTERNAL_FUNCTION_IMPL.MODE = "safe"

    def test_external_namespace_function_global_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _external_namespace_function_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_external_namespace_function_callback,
        )
        try:
            _EXTERNAL_NAMESPACE_DEP.MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _EXTERNAL_NAMESPACE_DEP.MODE = "safe"

    def test_external_object_state_module_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _external_state_module_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_external_state_module_callback,
        )
        try:
            exec(
                "def action():\n    return 'unsafe'\n",
                _EXTERNAL_STATE_DEP.__dict__,
            )
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            exec(
                "def action():\n    return 'safe'\n",
                _EXTERNAL_STATE_DEP.__dict__,
            )

    def test_external_metaclass_global_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _external_metaclass_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_external_metaclass_callback,
        )
        try:
            _EXTERNAL_META_HELPER.MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _EXTERNAL_META_HELPER.MODE = "safe"

    def test_external_inherited_method_global_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _external_inherited_method_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_external_inherited_method_callback,
        )
        try:
            _EXTERNAL_BASE.MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _EXTERNAL_BASE.MODE = "safe"

    def test_external_unused_implicit_global_does_not_change_identity(self):
        before = production_callable_fingerprint_v2(
            ProductionCommandV2.EVIDENCE_PUBLICATION,
            _external_unused_implicit_callback,
        )
        try:
            _EXTERNAL_UNUSED_IMPL.MODE = "two"
            after = production_callable_fingerprint_v2(
                ProductionCommandV2.EVIDENCE_PUBLICATION,
                _external_unused_implicit_callback,
            )
            self.assertEqual(after, before)
            self.assertEqual(
                _external_unused_implicit_callback(None, None), "safe")
        finally:
            _EXTERNAL_UNUSED_IMPL.MODE = "one"

    def test_dynamic_module_namespaces_are_rejected(self):
        callbacks = (
            _dynamic_namespace_callback,
            _dynamic_module_subclass_callback,
        )
        for callback in callbacks:
            with self.subTest(callback=callback.__name__), self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                production_callable_fingerprint_v2(
                    ProductionCommandV2.EVIDENCE_PUBLICATION, callback
                )

    def test_external_class_state_object_global_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _class_state_object_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_class_state_object_callback,
        )
        try:
            _CLASS_STATE_BASE.MODE = "two"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _CLASS_STATE_BASE.MODE = "one"

    def test_owned_external_unused_implicit_global_is_stable(self):
        before = production_callable_fingerprint_v2(
            ProductionCommandV2.EVIDENCE_PUBLICATION,
            _owned_external_unused_callback,
        )
        try:
            _EXTERNAL_UNUSED_IMPL.MODE = "two"
            after = production_callable_fingerprint_v2(
                ProductionCommandV2.EVIDENCE_PUBLICATION,
                _owned_external_unused_callback,
            )
            self.assertEqual(after, before)
            self.assertEqual(_owned_external_unused_callback(None, None), "safe")
        finally:
            _EXTERNAL_UNUSED_IMPL.MODE = "one"

    def test_external_metaclass_state_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _metaclass_state_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_metaclass_state_callback,
        )
        try:
            _META_STATE_TYPE.config = "two"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _META_STATE_TYPE.config = "one"

    def test_external_annotation_state_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _annotation_state_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_annotation_state_callback,
        )
        try:
            _ANNOTATION_STATE_API.Service.__annotations__["marker"] = int
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _ANNOTATION_STATE_API.Service.__annotations__["marker"] = str

    def test_external_type_name_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _name_state_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_name_state_callback
        )
        try:
            _NAME_STATE_API.Service.__name__ = "Changed"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _NAME_STATE_API.Service.__name__ = "Service"

    def test_dataclass_field_default_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _dataclass_metadata_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_dataclass_metadata_callback,
        )
        field = _DataclassMetadataState.__dataclass_fields__["value"]
        try:
            field.default = "two"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            field.default = "one"

    def test_nan_payload_drift_blocks_invocation(self):
        global _NAN_VALUE
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _nan_payload_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_nan_payload_callback
        )
        try:
            _NAN_VALUE = struct.unpack(
                ">d", bytes.fromhex("7ff8000000000002"))[0]
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _NAN_VALUE = struct.unpack(
                ">d", bytes.fromhex("7ff8000000000001"))[0]

    def test_slice_member_type_drift_blocks_invocation(self):
        global _SLICE_VALUE
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _slice_type_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_slice_type_callback
        )
        try:
            _SLICE_VALUE = slice(None, "1", None)
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _SLICE_VALUE = slice(None, 1, None)

    def test_external_complex_value_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _complex_value_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_complex_value_callback
        )
        try:
            _COMPLEX_API.VALUE = 3 + 4j
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _COMPLEX_API.VALUE = 1 + 2j

    def test_spoofed_builtin_type_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _spoofed_builtin_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_spoofed_builtin_callback
        )
        try:
            _SPOOF_BASE.MODE = "two"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _SPOOF_BASE.MODE = "one"

    def test_nested_module_value_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _nested_module_value_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_nested_module_value_callback,
        )
        try:
            _NESTED_VALUE_MODULE.VALUE = "two"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _NESTED_VALUE_MODULE.VALUE = "one"

    def test_unbound_module_dunder_access_is_rejected(self):
        with self.assertRaisesRegex(
            ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
        ):
            production_callable_fingerprint_v2(
                ProductionCommandV2.EVIDENCE_PUBLICATION,
                _module_dunder_callback,
            )

    def test_module_doc_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _module_doc_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_module_doc_callback,
        )
        try:
            _MODULE_DOC_API.__doc__ = "two"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _MODULE_DOC_API.__doc__ = "one"

    def test_loaderless_mounted_singleton_behavior_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _mounted_singleton_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_mounted_singleton_callback,
        )
        try:
            _MOUNT_POLICY_HELPER.MODE = "two"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _MOUNT_POLICY_HELPER.MODE = "one"

    def test_imported_nested_module_attribute_access_is_rejected(self):
        with self.assertRaisesRegex(
            ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
        ):
            production_callable_fingerprint_v2(
                ProductionCommandV2.EVIDENCE_PUBLICATION,
                _imported_nested_value_callback,
            )

    def test_loaderful_nested_module_alias_helper_container_drift_is_rejected(self):
        with self.assertRaisesRegex(
            ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
        ):
            production_callable_fingerprint_v2(
                ProductionCommandV2.EVIDENCE_PUBLICATION,
                _imported_nested_alias_helper_container_callback,
            )

    def test_default_function_globals_access_is_rejected(self):
        with self.assertRaisesRegex(
            ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
        ):
            production_callable_fingerprint_v2(
                ProductionCommandV2.EVIDENCE_PUBLICATION,
                _default_function_globals_callback,
            )

    def test_attrgetter_function_globals_access_is_rejected(self):
        with self.assertRaisesRegex(
            ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
        ):
            production_callable_fingerprint_v2(
                ProductionCommandV2.EVIDENCE_PUBLICATION,
                _attrgetter_function_globals_callback,
            )

    def test_default_function_annotation_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _default_function_annotations_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_default_function_annotations_callback,
        )
        try:
            _default_function_helper.__annotations__["marker"] = "two"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _default_function_helper.__annotations__["marker"] = "one"

    def test_dataclass_field_subclass_is_rejected(self):
        field = _DataclassMetadataState.__dataclass_fields__["value"]

        class ExtendedField(dataclasses.Field):
            __slots__ = ("extra",)

        extended = ExtendedField(
            field.default, field.default_factory, field.init, field.repr,
            field.hash, field.compare, field.metadata, field.kw_only,
        )
        extended.name = field.name
        extended.type = field.type
        extended._field_type = field._field_type
        extended.extra = "one"
        try:
            _DataclassMetadataState.__dataclass_fields__["value"] = extended
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                production_callable_fingerprint_v2(
                    ProductionCommandV2.EVIDENCE_PUBLICATION,
                    _dataclass_metadata_callback,
                )
        finally:
            _DataclassMetadataState.__dataclass_fields__["value"] = field

    def test_custom_dataclass_metadata_is_rejected_without_iteration(self):
        field = _DataclassMetadataState.__dataclass_fields__["value"]
        original = field.metadata
        observed = _ObservedMetadata()
        try:
            field.metadata = observed
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                production_callable_fingerprint_v2(
                    ProductionCommandV2.EVIDENCE_PUBLICATION,
                    _dataclass_metadata_callback,
                )
            self.assertEqual(observed.calls, 0)
        finally:
            field.metadata = original

    def test_unknown_dataclass_field_kind_is_rejected(self):
        field = _DataclassMetadataState.__dataclass_fields__["value"]
        original = field._field_type
        try:
            field._field_type = object()
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                production_callable_fingerprint_v2(
                    ProductionCommandV2.EVIDENCE_PUBLICATION,
                    _dataclass_metadata_callback,
                )
        finally:
            field._field_type = original

    def test_external_nested_type_global_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _external_nested_type_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_external_nested_type_callback,
        )
        try:
            _EXTERNAL_HELPER.MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _EXTERNAL_HELPER.MODE = "safe"

    def test_class_object_constant_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _class_object_constant_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_class_object_constant_callback,
        )
        try:
            _ClassWithObjectConstant.state.value = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _ClassWithObjectConstant.state.value = "safe"

    def test_custom_metaclass_constructor_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _metaclass_constructor_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_metaclass_constructor_callback,
        )
        original = _ResultMeta.__call__
        try:
            _ResultMeta.__call__ = lambda cls: "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _ResultMeta.__call__ = original

    def test_custom_metaclass_dependency_drift_blocks_invocation(self):
        global _METACLASS_MODE
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _metaclass_constructor_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_metaclass_constructor_callback,
        )
        original = _METACLASS_MODE
        try:
            _METACLASS_MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _METACLASS_MODE = original

    def test_nested_module_dependency_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _nested_module_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_nested_module_callback
        )
        original = _NESTED_MODULE_B.action
        try:
            _NESTED_MODULE_B.action = lambda: "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _NESTED_MODULE_B.action = original

    def test_nested_module_helper_dependency_drift_blocks_invocation(self):
        global _NESTED_MODULE_MODE
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _nested_module_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_nested_module_callback
        )
        original = _NESTED_MODULE_MODE
        try:
            _NESTED_MODULE_MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _NESTED_MODULE_MODE = original

    def test_module_owned_cross_module_dependency_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _owned_module_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_owned_module_callback
        )
        original = _OWNED_MODULE_B.action
        try:
            exec("def action(): return 'unsafe'", _OWNED_MODULE_B.__dict__)
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _OWNED_MODULE_B.action = original

    def test_cross_root_helper_dependency_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION:
                _cross_root_module_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding,
            publish_reviewed_evidence=_cross_root_module_callback,
        )
        original = _CROSS_ROOT_MODULE_C.MODE
        try:
            _CROSS_ROOT_MODULE_C.MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _CROSS_ROOT_MODULE_C.MODE = original

    def test_module_callable_default_dependency_drift_blocks_invocation(self):
        binding = _binding({
            ProductionCommandV2.EVIDENCE_PUBLICATION: _module_default_callback
        })
        role = EvidenceProductionRoleV2.create(
            binding=binding, publish_reviewed_evidence=_module_default_callback
        )
        original = _DEFAULT_MODULE.MODE
        try:
            _DEFAULT_MODULE.MODE = "unsafe"
            with self.assertRaisesRegex(
                ProductionBindingError, "R2_PRODUCTION_BINDING_INVALID"
            ):
                role.publish_reviewed_evidence(binding, None)
        finally:
            _DEFAULT_MODULE.MODE = original


def _binding(callbacks):
    final = FinalMasterBindingV1.create(
        final_commit_oid="a" * 40,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )
    keys = {role: Ed25519PrivateKey.generate().public_key().public_bytes_raw()
            for role in PublicKeyRoleV2}
    role_values = {
        role: f"{index + 100:064x}" for index, role in enumerate(ProductionRoleV2)
    }
    for command, callback in callbacks.items():
        role_values[command_production_role_v2(command)] = (
            production_callable_fingerprint_v2(command, callback)
        )
    return ApprovedCutoverBindingV2.create(
        final_master_binding=final,
        operation_fingerprint="f" * 64,
        operator_role_fingerprints={
            role: f"{index + 10:064x}" for index, role in enumerate(OperatorRoleV2)
        },
        verification_public_keys=keys,
        production_role_fingerprints=role_values,
    )


if __name__ == "__main__":
    unittest.main()
