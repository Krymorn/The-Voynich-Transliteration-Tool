"""A very small JSON Schema validator with beginner-friendly messages.

If the ``jsonschema`` package is installed it is used (its messages are good).
Otherwise this module validates the subset of JSON Schema that TVTT's own
schemas use: ``type``, ``properties``, ``required``, ``additionalProperties``,
``enum``, ``minimum``/``maximum``, ``items``, ``patternProperties`` and
``anyOf``.

The point is not standards compliance -- it is telling somebody who mistyped
``"enabled": "yes"`` exactly which line of which file to fix.
"""

from __future__ import annotations

import re
from typing import Any

from .errors import ConfigError
from .util import optional_import

_TYPES: dict[str, Any] = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def _typename(value: Any) -> str:
    for name, py in _TYPES.items():
        if name == "integer":
            continue
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, py):
            return name
    return type(value).__name__


def _check(value: Any, schema: dict[str, Any], path: str, errors: list[str]) -> None:
    if not isinstance(schema, dict):
        return

    if "anyOf" in schema:
        collected: list[str] = []
        for sub in schema["anyOf"]:
            probe: list[str] = []
            _check(value, sub, path, probe)
            if not probe:
                return
            collected.extend(probe)
        errors.append(f"{path or 'value'}: does not match any allowed form ({'; '.join(collected[:3])})")
        return

    expected = schema.get("type")
    if expected:
        wanted = expected if isinstance(expected, list) else [expected]
        ok = False
        for w in wanted:
            py = _TYPES.get(w)
            if py is None:
                ok = True
                break
            if w == "boolean":
                ok = isinstance(value, bool)
            elif w in ("number", "integer"):
                ok = isinstance(value, py) and not isinstance(value, bool)
            else:
                ok = isinstance(value, py)
            if ok:
                break
        if not ok:
            errors.append(f"{path or 'value'}: expected {' or '.join(wanted)}, found {_typename(value)} ({value!r})")
            return

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(repr(v) for v in schema["enum"])
        errors.append(f"{path or 'value'}: {value!r} is not one of {allowed}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} is below the minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} is above the maximum {schema['maximum']}")

    if isinstance(value, dict):
        props: dict[str, Any] = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path or 'root'}: missing required key {key!r}")
        patterns = schema.get("patternProperties", {})
        for key, item in value.items():
            sub_path = f"{path}.{key}" if path else key
            if key in props:
                _check(item, props[key], sub_path, errors)
                continue
            matched = False
            for pattern, sub_schema in patterns.items():
                if re.search(pattern, key):
                    _check(item, sub_schema, sub_path, errors)
                    matched = True
                    break
            if matched:
                continue
            extra = schema.get("additionalProperties", True)
            if extra is False:
                near = _closest(key, list(props))
                suffix = f" (did you mean {near!r}?)" if near else ""
                errors.append(f"{path or 'root'}: unknown key {key!r}{suffix}")
            elif isinstance(extra, dict):
                _check(item, extra, sub_path, errors)

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(value):
            _check(item, schema["items"], f"{path}[{i}]", errors)


def _closest(word: str, options: list[str]) -> str | None:
    import difflib

    hits = difflib.get_close_matches(word, options, n=1, cutoff=0.7)
    return hits[0] if hits else None


def validate(instance: Any, schema: dict[str, Any], source: str = "config") -> None:
    """Validate ``instance``; raise :class:`ConfigError` listing every problem."""
    lib = optional_import("jsonschema")
    if lib is not None:
        validator = lib.Draft7Validator(schema)
        problems = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
        if problems:
            lines = [f"  {'.'.join(str(p) for p in e.path) or 'root'}: {e.message}" for e in problems[:20]]
            raise ConfigError(
                f"{source} is not valid:\n" + "\n".join(lines),
                hint=f"Fix the keys listed above in {source}, then run the command again.",
            )
        return

    errors: list[str] = []
    _check(instance, schema, "", errors)
    if errors:
        raise ConfigError(
            f"{source} is not valid:\n" + "\n".join("  " + e for e in errors[:20]),
            hint=f"Fix the keys listed above in {source}, then run the command again.",
        )
