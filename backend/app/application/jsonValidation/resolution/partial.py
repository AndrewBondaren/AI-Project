"""Compile Pydantic schemas for partial updates and atomic field writes."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ValidationError
from pydantic_core import SchemaSerializer, SchemaValidator, core_schema

from app.application.jsonValidation.resolution.diagnostics import ResolveContext, reject_unresolved
from app.application.jsonValidation.resolution.wireIssues import pydantic_issues
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue


def _model_fields_schema(schema: dict, definitions: list[dict]) -> dict:
    while schema["type"] != "model-fields":
        if schema["type"] == "definition-ref":
            schema = next(item for item in definitions if item.get("ref") == schema["schema_ref"])
        else:
            schema = schema["schema"]
    return schema


def _patch_fields(schema: dict, definitions: list[dict], *, validate_by_alias: bool) -> dict:
    fields = {}
    for name, info in schema["fields"].items():
        options = {}
        if "validation_alias" in info:
            options["validation_alias"] = info["validation_alias"]
        fields[name] = core_schema.typed_dict_field(
            _patch_field_schema(info["schema"], definitions), required=False, **options)
    return core_schema.typed_dict_schema(fields,
        extra_behavior=schema.get("extra_behavior", "ignore"),
        config={"validate_by_alias": validate_by_alias, "validate_by_name": True})


def _contains_patch_model(schema: dict) -> bool:
    if schema["type"] in ("model", "definition-ref"):
        return True
    if "schema" in schema:
        return _contains_patch_model(schema["schema"])
    if schema["type"] in ("union", "tagged-union"):
        choices = schema["choices"]
        return any(_contains_patch_model(c[0] if isinstance(c, tuple) else c)
                   for c in (choices.values() if isinstance(choices, dict) else choices))
    return False


def _patch_field_schema(schema: dict, definitions: list[dict]) -> dict:
    kind = schema["type"]
    if kind == "default":
        return _patch_field_schema(schema["schema"], definitions)
    if kind == "model" and not schema.get("root_model"):
        fields = dict(_model_fields_schema(schema, definitions))
        fields["extra_behavior"] = schema.get("config", {}).get("extra_fields_behavior", "ignore")
        return _patch_fields(fields, definitions, validate_by_alias=schema.get("config", {}).get("validate_by_alias", True))
    if kind == "definition-ref":
        target = next(item for item in definitions if item.get("ref") == schema["schema_ref"])
        return _patch_field_schema(target, definitions)
    if kind in ("nullable", "function-before"):
        return {**schema, "schema": _patch_field_schema(schema["schema"], definitions)}
    if kind in ("function-after", "function-wrap") and _contains_patch_model(schema):
        # These validators consume complete POJOs; run them after merge.
        return _patch_field_schema(schema["schema"], definitions)
    if kind == "tagged-union" and _contains_patch_model(schema):
        patched = {**schema, "choices": {k: _patch_field_schema(v, definitions)
                                        for k, v in schema["choices"].items()}}
        discriminator = schema["discriminator"]
        def validate(value, handler):
            if isinstance(value, dict) and isinstance(discriminator, str) and discriminator not in value:
                # The existing object's tag is available only after merge. Keep
                # every authored key, then validate against that selected branch.
                return dict(value)
            return handler(value)
        return core_schema.no_info_wrap_validator_function(validate, patched)
    if kind == "union" and _contains_patch_model(schema):
        def validate(value, handler):
            if isinstance(value, dict):
                return dict(value)  # branch selection belongs to merged validation
            return handler(value)
        return core_schema.no_info_wrap_validator_function(validate, schema)
    # Collections contain complete rows, so retain their full original schemas.
    return schema


@lru_cache
def _patch_validator(model_cls: type[BaseModel]) -> SchemaValidator:
    """Validate supplied fields; union patches without tags await merged validation.

    Before field validators are retained. Validators consuming complete nested
    POJOs and model invariants run on the full merged object, without patch defaults.
    """
    schema = model_cls.__pydantic_core_schema__
    definitions = schema.get("definitions", []) if schema["type"] == "definitions" else []
    fields = dict(_model_fields_schema(schema, definitions))
    fields["extra_behavior"] = model_cls.model_config.get("extra", "ignore")
    patch_schema = _patch_fields(fields, definitions, validate_by_alias=model_cls.model_config.get("validate_by_alias", True))
    if definitions:
        patch_schema = core_schema.definitions_schema(patch_schema, definitions)
    return SchemaValidator(patch_schema)


@lru_cache
def _field_codec(model_cls: type[BaseModel], name: str) -> tuple[SchemaValidator, SchemaSerializer]:
    """Reuse the complete field schema, including nested model validators.

    Unlike patch validation, an authored column is an atomic value.
    Model-level invariants of the containing POJO need resolve_model instead.
    """
    schema = model_cls.__pydantic_core_schema__
    definitions = schema.get("definitions", []) if schema["type"] == "definitions" else []
    field_schema = core_schema.typed_dict_schema({
        name: core_schema.typed_dict_field(
            _model_fields_schema(schema, definitions)["fields"][name]["schema"], required=False),
    })
    if definitions:
        field_schema = core_schema.definitions_schema(field_schema, definitions)
    config = dict(model_cls.model_config)
    return SchemaValidator(field_schema, config=config), SchemaSerializer(field_schema, config=config)


def resolve_model_field(model_cls: type[BaseModel], name: str, raw: Any,
                        *, ctx: ResolveContext) -> Any:
    """Validate one independent, complete POJO field and return its JSON wire."""
    validator, serializer = _field_codec(model_cls, name)
    try:
        value = validator.validate_python({name: raw}, by_name=True, by_alias=True)
    except ValidationError as exc:
        reject_unresolved(ctx, pydantic_issues(ctx, model_cls, exc, raw={name: raw}))
    return serializer.to_python(value, mode="json")[name]


def resolve_patch(model_cls: type[BaseModel], raw: dict[str, Any], *, ctx: ResolveContext) -> dict[str, Any]:
    """Validate supplied fields only; a patch is deliberately not a full POJO."""
    if not isinstance(raw, dict):
        reject_unresolved(ctx, [WireShapeIssue(code=JsonValidationCode.EXPECTED_OBJECT,
                                               location=ctx.location, message="expected object")])
    try:
        return _patch_validator(model_cls).validate_python(raw, by_name=True)
    except ValidationError as exc:
        reject_unresolved(ctx, pydantic_issues(ctx, model_cls, exc, raw=raw))
