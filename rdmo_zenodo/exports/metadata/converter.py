from __future__ import annotations

from typing import Any, get_args, get_origin

import attr
import cattrs

from rdmo_zenodo.exports.metadata.invenio import Language, ResourceType
from rdmo_zenodo.exports.metadata.zenodo import Community, Grant

converter = cattrs.Converter()

_EMPTY = (None, "", [], {})


def strip_empty(value: Any) -> Any:
    if isinstance(value, dict):
        # Clean nested first, then drop empty keys.
        cleaned = {k: strip_empty(v) for k, v in value.items()}
        return {k: v for k, v in cleaned.items() if v not in _EMPTY}
    if isinstance(value, list):
        # Clean nested first, then drop empty items.
        cleaned = [strip_empty(v) for v in value]
        return [v for v in cleaned if v not in _EMPTY]
    return value


def unstructure_attrs_and_strip(inst: Any) -> Any:
    cls = type(inst)
    # Use attr.fields to walk declared attrs fields
    data = {f.name: converter.unstructure(getattr(inst, f.name)) for f in attr.fields(cls)}
    return strip_empty(data)


# Apply to ALL attrs-based classes (top-level and nested).
# Using attr.has as the predicate means: “if this is an @attrs class, use the hook”.
converter.register_unstructure_hook_factory(
    attr.has,
    lambda _cls: unstructure_attrs_and_strip,
)

def register_from_string_hook(converter, cls):
    converter.register_structure_hook(
        cls,
        lambda v, _: cls.from_string(v) if isinstance(v, str) else cls(**v)
    )

for simple_cls in (Language, ResourceType, Grant, Community):
    register_from_string_hook(converter, simple_cls)

def make_list_hook(inner_cls):
    def _hook(value: Any, _: Any):
        if isinstance(value, str):
            return [inner_cls.from_string(value)]
        if isinstance(value, dict):
            return [inner_cls(**value)]
        if isinstance(value, list):
            return [inner_cls.from_string(v) if isinstance(v, str) else inner_cls(**v) for v in value]
        raise TypeError(f"Cannot structure {value!r} as list[{inner_cls.__name__}]")
    return _hook

def make_list_pred(inner_cls):
    return lambda tp: get_origin(tp) is list and get_args(tp) == (inner_cls,)

for simple_cls in (Language, Grant, Community):
    converter.register_structure_hook_func(
        make_list_pred(simple_cls),
        make_list_hook(simple_cls),
    )
