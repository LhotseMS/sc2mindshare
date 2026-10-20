"""A JSON Schema (2020-12) checker for the keywords schema/mindshare-graph.schema.json uses, standard library
only (CR-018). Any other keyword raises, so the schema can never use something this checker would
silently ignore. The schema file is plain JSON Schema: a full validator (``jsonschema``) reads it the
same way, and can replace this module once a PyPI install is approved (no download in this batch).
"""

from __future__ import annotations

from typing import Any

ANNOTATIONS = {"$schema", "$id", "title", "description"}
SUPPORTED = ANNOTATIONS | {
    "$defs",
    "$ref",
    "type",
    "required",
    "properties",
    "additionalProperties",
    "maxProperties",
    "items",
    "minItems",
    "maxItems",
    "enum",
    "const",
    "anyOf",
    "allOf",
    "if",
    "then",
    "else",
}


class UnsupportedKeyword(ValueError):
    pass


def _is_type(value: Any, name: str) -> bool:
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    if isinstance(value, bool):  # JSON true is never a number
        return False
    if name == "number":
        return isinstance(value, int | float)
    if name == "integer":  # 2020-12: a number with no fractional part (2.0 is an integer)
        return isinstance(value, int) or (isinstance(value, float) and value.is_integer())
    raise UnsupportedKeyword(f"type {name!r}")


def _same(a: Any, b: Any) -> bool:
    """JSON equality: a boolean equals only a boolean (Python has True == 1)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    return bool(a == b)


class Checker:
    def __init__(self, schema: dict[str, Any]) -> None:
        self.root = schema

    def errors(self, value: Any) -> list[str]:
        return self._check(value, self.root, "$")

    def _resolve(self, ref: str) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise UnsupportedKeyword(f"$ref {ref!r} (only local #/... references)")
        node: Any = self.root
        for part in ref[2:].split("/"):
            node = node[part]
        if not isinstance(node, dict):
            raise UnsupportedKeyword(f"$ref {ref!r} does not name a schema object")
        return node

    def _check(self, value: Any, schema: dict[str, Any], path: str) -> list[str]:
        unknown = set(schema) - SUPPORTED
        if unknown:
            raise UnsupportedKeyword(f"{sorted(unknown)} at {path}")
        out: list[str] = []
        if "$ref" in schema:
            out += self._check(value, self._resolve(schema["$ref"]), path)
        if "type" in schema:
            names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_is_type(value, n) for n in names):
                return out + [f"{path}: {value!r:.60} is not of type {schema['type']}"]
        if "enum" in schema and not any(_same(value, e) for e in schema["enum"]):
            out.append(f"{path}: {value!r:.60} is not one of {schema['enum']}")
        if "const" in schema and not _same(value, schema["const"]):
            out.append(f"{path}: {value!r:.60} is not {schema['const']!r}")
        if isinstance(value, dict):
            for key in schema.get("required", []):
                if key not in value:
                    out.append(f"{path}: missing required property {key!r}")
            props = schema.get("properties", {})
            for key, item in value.items():
                if key in props:
                    out += self._check(item, props[key], f"{path}.{key}")
                elif "additionalProperties" in schema:
                    extra = schema["additionalProperties"]
                    if extra is False:
                        out.append(f"{path}: property {key!r} is not allowed")
                    elif isinstance(extra, dict):
                        out += self._check(item, extra, f"{path}.{key}")
            if "maxProperties" in schema and len(value) > schema["maxProperties"]:
                out.append(f"{path}: more than {schema['maxProperties']} properties")
        if isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                out.append(f"{path}: fewer than {schema['minItems']} items")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                out.append(f"{path}: more than {schema['maxItems']} items")
            if "items" in schema:
                for i, item in enumerate(value):
                    out += self._check(item, schema["items"], f"{path}[{i}]")
        if "anyOf" in schema and not any(not self._check(value, s, path) for s in schema["anyOf"]):
            out.append(f"{path}: {value!r:.60} matches none of anyOf")
        for sub in schema.get("allOf", []):
            out += self._check(value, sub, path)
        if "if" in schema:
            branch = "then" if not self._check(value, schema["if"], path) else "else"
            if branch in schema:
                out += self._check(value, schema[branch], path)
        return out
