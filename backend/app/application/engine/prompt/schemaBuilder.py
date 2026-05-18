import copy


def build_strict_schema(node_schemas: dict[str, dict]) -> dict:
    """
    Combines per-node Pydantic schemas into a single OpenAI strict-mode schema.

    Handles:
    - Inlining all $ref / $defs (strict mode requires no references)
    - Adding additionalProperties: false to every object
    - Moving all properties to required (strict mode requires all fields listed)
    """
    properties = {
        node_id: _inline_schema(copy.deepcopy(schema))
        for node_id, schema in node_schemas.items()
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
        "additionalProperties": False,
    }


def _inline_schema(schema: dict) -> dict:
    defs = schema.pop("$defs", {})
    resolved = _resolve_refs(schema, defs)
    return _enforce_strict(resolved)


def _resolve_refs(obj, defs: dict):
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref_name = obj["$ref"].split("/")[-1]
            return _resolve_refs(copy.deepcopy(defs[ref_name]), defs)
        return {k: _resolve_refs(v, defs) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(item, defs) for item in obj]
    return obj


def _enforce_strict(obj):
    if isinstance(obj, dict):
        processed = {k: _enforce_strict(v) for k, v in obj.items()}
        if processed.get("type") == "object" and "properties" in processed:
            processed.setdefault("additionalProperties", False)
            processed["required"] = list(processed["properties"].keys())
            for prop in processed["properties"].values():
                prop.pop("default", None)
        return processed
    if isinstance(obj, list):
        return [_enforce_strict(item) for item in obj]
    return obj
