"""In-memory artifact preparation envelopes."""

from typing import Annotated
from copy import deepcopy

from pydantic import BaseModel, ConfigDict, GetCoreSchemaHandler, ValidatorFunctionWrapHandler
from pydantic_core import CoreSchema, core_schema
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.staging.contentValidation import require_unchanged_content, validate_content_instance


def _content(value: object, handler: ValidatorFunctionWrapHandler, expected: object) -> object:
    if isinstance(value, (bytes, BaseModel)):
        if type(value) is not expected:
            raise ValueError("content must have the exact declared concrete type")
        validate_content_instance(value)
        require_unchanged_content(value, handler(deepcopy(value)))
        return value
    # Keep Pydantic's native JSON mode (not Python revalidation of decoded lists).
    checked = handler(deepcopy(value))
    validate_content_instance(checked)
    return checked


class ArtifactInstanceSchema:
    """Validated Python instance preservation with native strict JSON parsing."""
    @classmethod
    def __get_pydantic_core_schema__(cls, source: object, handler: GetCoreSchemaHandler) -> CoreSchema:
        schema = handler(source)

        def python_content(value: object, inner: ValidatorFunctionWrapHandler) -> object:
            return _content(value, inner, source)

        def json_content(value: bytes | BaseModel) -> bytes | BaseModel:
            validate_content_instance(value)
            return value

        return core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_after_validator_function(json_content, schema),
            python_schema=core_schema.no_info_wrap_validator_function(python_content, schema),
        )


class ArtifactPrepareStageInputBase(BaseModel):
    """Named diagnostic schema; concrete payload admission belongs to its specialization."""
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="never")
    content: bytes | BaseModel


class ArtifactPrepareStageInput[C: bytes | BaseModel](ArtifactPrepareStageInputBase):
    content: Annotated[C, ArtifactInstanceSchema]


class PreparedArtifactBase(BaseModel):
    """Named schema for fields addressed by staging diagnostics."""
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="never")
    content: bytes | BaseModel
    descriptor: ArtifactRef


class PreparedArtifact[C: bytes | BaseModel](PreparedArtifactBase):
    content: Annotated[C, ArtifactInstanceSchema]
