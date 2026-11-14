"""Pure value relations; no coverage, lease admission or live hold checks."""
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder, PinHolder, VerifiedArtifactRef
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.publication.preparationSourceAuthority import PreparationSourceBinding, PinnedManifestSourceOrigin
from app.dataModel.publication.preparationSourceBindingIssue import (
    PreparationSourceBindingFieldCode as Code, PreparationSourceBindingFieldIssue as Issue,
)
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofReadInput
from app.dataModel.worldPack.read.pinnedManifest import ManifestPinRead
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper


class PreparationSourceBindingValidator:
    def validate(self, value: PreparationSourceBinding) -> tuple[Issue, ...]:
        value = PreparationSourceBinding.model_validate(value, strict=True)
        errors = ValidatorAggregationHelper((Issue,))
        root = CheckedPath.root(PreparationSourceBinding)
        request = FieldRef(lambda: PreparationSourceBinding, lambda v: v.request)
        origin = FieldRef(lambda: PreparationSourceBinding, lambda v: v.origin)
        world = FieldRef(lambda: SourceProofReadInput, lambda v: v.world_uid)
        pin = FieldRef(lambda: PinnedManifestSourceOrigin, lambda v: v.pin)
        pin_world = FieldRef(lambda: ManifestPinRead, lambda v: v.world_uid)
        if world.select(request.select(value)) != value.target.world_uid:
            errors.add(Issue(code=Code.WORLD_MISMATCH, path=root.field(request).field(world).freeze(),
                             message="Request world differs from target world"))
        if pin_world.select(pin.select(origin.select(value))) != value.target.world_uid:
            errors.add(Issue(code=Code.WORLD_MISMATCH,
                             path=root.field(origin).field(pin).field(pin_world).freeze(),
                             message="Origin pin world differs from target world"))
        sources = FieldRef(lambda: PreparationSourceBinding, lambda v: v.sources)
        ref = FieldRef(lambda: VerifiedArtifactRef, lambda v: v.ref)
        holder = FieldRef(lambda: VerifiedArtifactRef, lambda v: v.holder)
        seen: set[ArtifactRef] = set()
        for index, source in enumerate(sources.select(value)):
            path = root.field(sources).item(index)
            current = ref.select(source)
            if current in seen:
                errors.add(Issue(code=Code.DUPLICATE_SOURCE, path=path.field(ref).freeze(),
                                 message="Full artifact reference occurs more than once"))
            seen.add(current)
            actual = holder.select(source)
            valid = (isinstance(actual, PinHolder) and actual.pin_id == value.origin.pin.pin_id
                     if current == value.origin.manifest else
                     isinstance(actual, ArtifactRetentionHolder) and actual.artifact == value.origin.manifest)
            if not valid:
                errors.add(Issue(code=Code.INVALID_SOURCE_HOLDER, path=path.field(holder).freeze(),
                                 message="Holder does not match the pinned origin"))
        return errors.snapshot()
