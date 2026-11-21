"""One immutable current-result binding for publication storage and replay."""
from dataclasses import dataclass
from typing import get_args, get_origin, Annotated, Literal, TypeVar, Any, TypeAliasType
from enum import Enum
from dataclasses import is_dataclass, fields
from pydantic import BaseModel

from pydantic import TypeAdapter

from app.application.encoding.boundedCanonicalDecode import validate_decode_limits
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord, OperationCancelled
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind
from app.dataModel.patch.values import FormatVersion
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.publication import PackActivationResult, GameplayStarted
from app.encoding.canonicalCodec import CanonicalCodec


@dataclass(frozen=True)
class PublicationResultBinding[R: SnapshotApplyResult]:
    result_model: type[R]
    snapshot_format_version: FormatVersion
    manifest: CanonicalSchemaManifest
    record_model: type[OperationRecord[R]]
    limits: DecodeLimits

    def __post_init__(self) -> None:
        validate_decode_limits(self.limits)
        TypeAdapter(FormatVersion).validate_python(self.snapshot_format_version, strict=True)
        if self.snapshot_format_version != 1:
            raise ValueError("unsupported current snapshot outcome format")
        if (not isinstance(self.result_model, type)
                or not issubclass(self.result_model, SnapshotApplyResult)
                or self.result_model is SnapshotApplyResult):
            raise TypeError("current result must be a concrete Snapshot result")
        if not isinstance(self.record_model, type) or not issubclass(self.record_model, OperationRecord):
            raise TypeError("expected concrete OperationRecord model")
        expected = {self.result_model, PackActivationResult, GameplayStarted, OperationCancelled, type(None)}
        if set(get_args(self.record_model.model_fields["terminal"].annotation)) != expected:
            raise ValueError("record terminal differs from current result binding")
        CanonicalCodec(self.manifest)
        for model in expected - {type(None)}:
            entries = [entry for entry in self.manifest.entries if entry.python_type is model]
            if len(entries) != 1 or entries[0].kind is not CanonicalTypeKind.RECORD:
                raise ValueError("terminal root must have one canonical record binding")
        root = next(entry.type_id for entry in self.manifest.entries if entry.python_type is self.result_model)
        if root == 20124:
            raise ValueError("old Snapshot root cannot be the current result")
        registered = {entry.python_type for entry in self.manifest.entries}
        visited = set()

        def check(annotation):
            if annotation is Any or isinstance(annotation, TypeVar):
                raise TypeError("terminal schema must be closed")
            if isinstance(annotation, TypeAliasType):
                check(annotation.__value__)
                return
            origin = get_origin(annotation)
            if isinstance(origin, type) and issubclass(origin, str) and not issubclass(origin, Enum):
                return  # Nominal scalar parameters are not serialized records.
            if origin is Literal:
                for value in get_args(annotation):
                    if isinstance(value, Enum):
                        check(type(value))
                return
            if origin is Annotated:
                check(get_args(annotation)[0])
                return
            if origin is not None:
                for child in get_args(annotation):
                    if child is not Ellipsis:
                        check(child)
                return
            if not isinstance(annotation, type) or annotation in visited:
                return
            visited.add(annotation)
            if issubclass(annotation, (BaseModel, Enum)) or is_dataclass(annotation):
                if annotation not in registered:
                    raise ValueError(f"unregistered terminal schema type: {annotation.__module__}.{annotation.__qualname__}")
                if issubclass(annotation, BaseModel):
                    for field in annotation.model_fields.values():
                        check(field.annotation)
                elif is_dataclass(annotation):
                    from typing import get_type_hints
                    hints = get_type_hints(annotation, include_extras=True)
                    for field in fields(annotation):
                        check(hints[field.name])

        for model in expected - {type(None)}:
            check(model)
