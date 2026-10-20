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


TYPES = {"object", "array", "string", "boolean", "null", "number", "integer"}
#: Keywords whose value is one subschema, a list of them, or a name -> subschema map.
_ONE = {"additionalProperties", "items", "if", "then", "else"}
_LIST = {"anyOf", "allOf"}
_MAP = {"properties", "$defs"}


def _is_type(value: Any, name: str) -> bool:
    if name not in TYPES:
        raise UnsupportedKeyword(f"type {name!r}")
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
    # "integer": 2020-12, a number with no fractional part (2.0 is an integer)
    return isinstance(value, int) or (isinstance(value, float) and value.is_integer())


def _same(a: Any, b: Any) -> bool:
    """JSON equality, recursively: a boolean equals only a boolean (Python has True == 1), also inside
    arrays and objects."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list | dict) or isinstance(b, list | dict):
        return False
    return bool(a == b)


class Checker:
    def __init__(self, schema: dict[str, Any]) -> None:
        self.root = schema
        self._walk(schema, "#")  # refuse anything this checker cannot evaluate, wherever it is

    def _walk(self, schema: Any, path: str, boolean_ok: bool = False) -> None:
        """Every subschema is one this checker can evaluate: implemented keywords, known type names,
        every $ref resolvable to a schema object, well-formed properties/$defs/anyOf/allOf, and a
        boolean subschema only where _check handles one (additionalProperties).

        Checked once over the whole schema, so a branch a value never visits (an anyOf alternative
        after a match, an else when then is taken, an unreferenced $defs entry, the schema of an
        absent property) is refused as well."""
        if isinstance(schema, bool):
            if not boolean_ok:
                raise UnsupportedKeyword(f"{path}: a boolean subschema (only additionalProperties may be one)")
            return
        if not isinstance(schema, dict):
            raise UnsupportedKeyword(f"{path}: a schema must be an object")
        unknown = set(schema) - SUPPORTED
        if unknown:
            raise UnsupportedKeyword(f"{sorted(unknown)} at {path}")
        if "type" in schema:
            names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if bad := [n for n in names if n not in TYPES]:
                raise UnsupportedKeyword(f"type {bad} at {path}")
        if "$ref" in schema:
            self._resolve(schema["$ref"])
        for key in _ONE & set(schema):
            self._walk(schema[key], f"{path}/{key}", boolean_ok=key == "additionalProperties")
        for key in _LIST & set(schema):
            if not isinstance(schema[key], list):
                raise UnsupportedKeyword(f"{path}/{key}: must be a list of schemas")
            for n, sub in enumerate(schema[key]):
                self._walk(sub, f"{path}/{key}/{n}")
        for key in _MAP & set(schema):
            if not isinstance(schema[key], dict):
                raise UnsupportedKeyword(f"{path}/{key}: must map names to schemas")
            for name, sub in schema[key].items():
                self._walk(sub, f"{path}/{key}/{name}")

    def errors(self, value: Any) -> list[str]:
        return self._check(value, self.root, "$")

    def _resolve(self, ref: str) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise UnsupportedKeyword(f"$ref {ref!r} (only local #/... references)")
        node: Any = self.root
        for part in ref[2:].split("/"):
            if not isinstance(node, dict) or part not in node:
                raise UnsupportedKeyword(f"$ref {ref!r} does not resolve")
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
