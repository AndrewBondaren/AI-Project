"""Pure value relations; no coverage, lease admission or live hold checks."""
from typing import cast
from pydantic import BaseModel, TypeAdapter, ValidationError
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder, PinHolder, VerifiedArtifactRef
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.publication.preparationSourceAuthority import PreparationSourceBinding, PinnedManifestSourceOrigin
from app.dataModel.publication.preparationSourceBindingIssue import (
    PreparationSourceBindingFieldCode as Code, PreparationSourceBindingFieldIssue as Issue,
    PreparationSourceBindingShapeIssue as ShapeIssue, PreparationSourceBindingIssue,
)
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofReadInput
from app.dataModel.worldPack.read.pinnedManifest import ManifestPinRead
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper


def _raw[M: BaseModel, T](value: object, field: FieldRef[M, T]) -> object:
    name = bind_field(field).field
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _valid[M: BaseModel, T](value: object, field: FieldRef[M, T]) -> T | None:
    bound = bind_field(field)
    try:
        return cast(T, TypeAdapter(bound.model.model_fields[bound.field].rebuild_annotation()).validate_python(
            _raw(value, field), strict=True))
    except ValidationError:
        return None  # The whole-value structural pass owns these diagnostics.


class PreparationSourceBindingValidator:
    def validate(self, value: PreparationSourceBinding) -> tuple[PreparationSourceBindingIssue, ...]:
        errors = ValidatorAggregationHelper[PreparationSourceBindingIssue]((Issue, ShapeIssue))
        try:
            PreparationSourceBinding.model_validate(value, strict=True)
        except ValidationError as failure:
            for detail in failure.errors(include_url=False, include_input=False):
                loc = detail["loc"]
                path = CheckedPath.from_pydantic_loc(PreparationSourceBinding, loc)
                message = f"{detail['type']}: {detail['msg']}"
                if path is None:
                    errors.add(ShapeIssue(code=Code.INVALID_SHAPE, location=loc, message=message))
                else:
                    errors.add(Issue(code=Code.INVALID_SHAPE, path=path, message=message))
        root = CheckedPath.root(PreparationSourceBinding)
        request = FieldRef(lambda: PreparationSourceBinding, lambda v: v.request)
        origin = FieldRef(lambda: PreparationSourceBinding, lambda v: v.origin)
        world = FieldRef(lambda: SourceProofReadInput, lambda v: v.world_uid)
        pin = FieldRef(lambda: PinnedManifestSourceOrigin, lambda v: v.pin)
        pin_world = FieldRef(lambda: ManifestPinRead, lambda v: v.world_uid)
        target = FieldRef(lambda: PreparationSourceBinding, lambda v: v.target)
        target_world = FieldRef(lambda: OperationLeaseRef, lambda v: v.world_uid)
        expected = _valid(_raw(value, target), target_world)
        actual_world = _valid(_raw(value, request), world)
        origin_value = _raw(value, origin)
        pin_value = _raw(origin_value, pin)
        actual_pin_world = _valid(pin_value, pin_world)
        if expected is not None and actual_world is not None and actual_world != expected:
            errors.add(Issue(code=Code.WORLD_MISMATCH, path=root.field(request).field(world).freeze(),
                             message="Request world differs from target world"))
        if expected is not None and actual_pin_world is not None and actual_pin_world != expected:
            errors.add(Issue(code=Code.WORLD_MISMATCH,
                             path=root.field(origin).field(pin).field(pin_world).freeze(),
                             message="Origin pin world differs from target world"))
        sources = FieldRef(lambda: PreparationSourceBinding, lambda v: v.sources)
        ref = FieldRef(lambda: VerifiedArtifactRef, lambda v: v.ref)
        holder = FieldRef(lambda: VerifiedArtifactRef, lambda v: v.holder)
        manifest = _valid(origin_value, FieldRef(lambda: PinnedManifestSourceOrigin, lambda v: v.manifest))
        pin_id = _valid(pin_value, FieldRef(lambda: ManifestPinRead, lambda v: v.pin_id))
        seen: set[ArtifactRef] = set()
        raw_sources = _raw(value, sources)
        for index, source in enumerate(raw_sources if isinstance(raw_sources, tuple) else ()):
            path = root.field(sources).item(index)
            current = _valid(source, ref)
            if current is None:
                continue
            if current in seen:
                errors.add(Issue(code=Code.DUPLICATE_SOURCE, path=path.field(ref).freeze(),
                                 message="Full artifact reference occurs more than once"))
            seen.add(current)
            actual = _valid(source, holder)
            if actual is None or manifest is None:
                continue
            if current == manifest and pin_id is None:
                continue
            valid = (isinstance(actual, PinHolder) and actual.pin_id == pin_id
                     if current == manifest else
                     isinstance(actual, ArtifactRetentionHolder) and actual.artifact == manifest)
            if not valid:
                errors.add(Issue(code=Code.INVALID_SOURCE_HOLDER, path=path.field(holder).freeze(),
                                 message="Holder does not match the pinned origin"))
        return errors.snapshot()
