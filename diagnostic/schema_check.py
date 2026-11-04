"""A small JSON Schema checker for the evaluation contracts. No dependencies.

`load_schema` inlines every $ref (local "#/..." or "<file>.schema.json#/..."), so any
sub-schema can be checked on its own. The checker supports the keywords
evaluation/schemas/*.json use: type (name or list), const, enum, required, properties,
additionalProperties (bool or schema), items, maxItems, uniqueItems, minimum,
maximum, minLength, maxLength, pattern. Anything else (format, $schema, ...) is
ignored, which is why tests also cross-check against the `jsonschema` package when
it is installed.

    errors = validate(instance, schema)      # [] when valid
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Union

from .paths import EVAL_ROOT

SCHEMA_DIR = EVAL_ROOT / "schemas"


def _read(file_name: str) -> Dict[str, Any]:
    return json.loads((SCHEMA_DIR / file_name).read_text(encoding="utf-8"))


def _inline_refs(node: Any, root: Dict[str, Any]) -> Any:
    """Replace each {"$ref": ...} with the schema it points to."""
    if isinstance(node, list):
        return [_inline_refs(value, root) for value in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        file_name, _, pointer = node["$ref"].partition("#")
        target_root = _read(file_name) if file_name else root
        target: Any = target_root
        for key in filter(None, pointer.split("/")):
            target = target[key]
        return _inline_refs(target, target_root)
    return {key: _inline_refs(value, root) for key, value in node.items()}


def load_schema(name: str) -> Dict[str, Any]:
    """Load evaluation/schemas/<name>.schema.json with every $ref inlined."""
    schema = _read(f"{name}.schema.json")
    return _inline_refs(schema, schema)


def _is_type(value: Any, name: str) -> bool:
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "string":
        return isinstance(value, str)
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    return True


def validate(instance: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    errors: List[str] = []
    wanted: Union[str, List[str], None] = schema.get("type")
    if wanted is not None:
        names = [wanted] if isinstance(wanted, str) else list(wanted)
        if not any(_is_type(instance, n) for n in names):
            return [f"{path}: expected {'/'.join(names)}, got {type(instance).__name__}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: {instance!r} is not {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} is below the minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} is above the maximum {schema['maximum']}")
    if isinstance(instance, str):
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']} characters")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match {schema['pattern']}")
    if isinstance(instance, list):
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in instance}) < len(instance):
            errors.append(f"{path}: items are not unique")
        for index, value in enumerate(instance):
            if "items" in schema:
                errors += validate(value, schema["items"], f"{path}[{index}]")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required field {key!r}")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                errors += validate(value, properties[key], f"{path}.{key}")
            elif extra is False:
                errors.append(f"{path}: unexpected field {key!r}")
            elif isinstance(extra, dict):
                errors += validate(value, extra, f"{path}.{key}")
    return errors


def validate_tool_output(tool: str, output: Dict[str, Any]) -> List[str]:
    """Check a tool's `output` object against evaluation/schemas/<tool>.schema.json."""
    return validate(output, load_schema(tool)["properties"]["output"], "output")


def validate_tool_input(tool: str, tool_input: Dict[str, Any]) -> List[str]:
    return validate(tool_input, load_schema(tool)["properties"]["input"], "input")


def validate_event_row(row: Dict[str, Any]) -> List[str]:
    return validate(row, load_schema("event_log"), "row")
