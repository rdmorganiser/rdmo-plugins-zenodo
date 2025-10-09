from __future__ import annotations

from typing import Any

import attr
import cattrs

from rdmo_zenodo.exports.metadata.invenio import Language, ResourceType, Rights, Role

# Single shared converter instance
converter = cattrs.Converter()

_EMPTY = (None, "", [], {})


def _strip_empty(value: Any) -> Any:
    """Recursively drop None, '', [], {} anywhere in the structure."""
    if isinstance(value, dict):
        # Clean nested first, then drop empty keys.
        cleaned = {k: _strip_empty(v) for k, v in value.items()}
        return {k: v for k, v in cleaned.items() if v not in _EMPTY}
    if isinstance(value, list):
        # Clean nested first, then drop empty items.
        cleaned = [_strip_empty(v) for v in value]
        return [v for v in cleaned if v not in _EMPTY]
    return value


def _unstructure_attrs_and_strip(inst: Any) -> Any:
    """
    Unstructure one attrs instance:
    - Recursively unstructure every field via the converter (important!)
    - Strip empties from the resulting dict
    """
    cls = type(inst)
    # Use attr.fields to walk declared attrs fields
    data = {f.name: converter.unstructure(getattr(inst, f.name)) for f in attr.fields(cls)}
    return _strip_empty(data)


# Apply to ALL attrs-based classes (top-level and nested).
# Using attr.has as the predicate means: “if this is an @attrs class, use the hook”.
converter.register_unstructure_hook_factory(
    attr.has,
    lambda _cls: _unstructure_attrs_and_strip,
)

def make_simple_id_hook(cls):
    def _hook(value: Any, _: type) -> Any:
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls(id=value)
        if isinstance(value, dict):
            return cls(**value)
        raise TypeError(f"Cannot structure {value!r} as {cls.__name__}")
    return _hook

for simple_cls in (ResourceType, Language, Role, Rights):
    converter.register_structure_hook(simple_cls, make_simple_id_hook(simple_cls))
