from __future__ import annotations

from typing import Any

import cattrs

converter = cattrs.Converter()

def strip_empty_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Remove None, empty strings, lists, and dicts from serialized output."""
    clean = {}
    for k, v in d.items():
        if v in (None, "", [], {}):
            continue
        if isinstance(v, dict):
            v = strip_empty_dict(v)
            if not v:
                continue
        clean[k] = v
    return clean

converter.register_unstructure_hook(dict, strip_empty_dict)
