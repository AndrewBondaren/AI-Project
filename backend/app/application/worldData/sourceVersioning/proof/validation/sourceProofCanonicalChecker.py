"""Check persisted ordering without normalizing or encoding an invalid proof."""

from pydantic import BaseModel

from app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1 import SOURCE_PROOF_SCHEMA_V1
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceErrors import SourceFieldCode, SourceFieldIssue
from app.dataModel.sourceVersioning.sourceVersionRef import SourceVersionRef, SourceCollectionVersionRef
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.encoding.canonicalCodec import CanonicalCodec

_USES: FieldRef[SourceDurableProof, tuple[SourceCaptureUsage, ...]] = FieldRef(
    lambda: SourceDurableProof, lambda proof: proof.uses)
_DEPENDENCIES: FieldRef[SourceCaptureUsage, SourceDependencySet] = FieldRef(
    lambda: SourceCaptureUsage, lambda use: use.dependencies)
_OBJECTS: FieldRef[SourceDependencySet, tuple[SourceVersionRef, ...]] = FieldRef(
    lambda: SourceDependencySet, lambda dependencies: dependencies.objects)
_COLLECTIONS: FieldRef[SourceDependencySet, tuple[SourceCollectionVersionRef, ...]] = FieldRef(
    lambda: SourceDependencySet, lambda dependencies: dependencies.collections)


class SourceProofCanonicalChecker:
    def check[RootT: BaseModel](self, proof: SourceDurableProof, *,
                               path: CheckedPath[RootT, SourceDurableProof],
                               ) -> tuple[SourceFieldIssue, ...]:
        if type(proof) is not SourceDurableProof or type(proof.schema_version) is not int or proof.schema_version != 1:
            raise TypeError("expected a Source v1 proof")
        uses = _USES.select(proof)
        if type(uses) is not tuple:
            raise TypeError("proof uses must be a tuple")
        codec = CanonicalCodec(SOURCE_PROOF_SCHEMA_V1)
        errors = ValidatorAggregationHelper[SourceFieldIssue]((SourceFieldIssue,))
        uses_path = path.field(_USES)
        capture_keys = tuple(codec.encode(use.capture) for use in uses)
        if any(left >= right for left, right in zip(capture_keys, capture_keys[1:])):
            errors.add(SourceFieldIssue(code=SourceFieldCode.NON_CANONICAL_PROOF,
                path=uses_path.freeze(), message="capture refs must be unique and canonically ordered"))
        for index, use in enumerate(uses):
            if type(use) is not SourceCaptureUsage or type(use.dependencies) is not SourceDependencySet:
                raise TypeError("expected structurally valid capture usage")
            dependencies = _DEPENDENCIES.select(use)
            dep_path = uses_path.item(index).field(_DEPENDENCIES)
            objects, collections = _OBJECTS.select(dependencies), _COLLECTIONS.select(dependencies)
            if type(objects) is not tuple or type(collections) is not tuple:
                raise TypeError("dependencies must be tuples")
            if not objects and not collections:
                errors.add(SourceFieldIssue(code=SourceFieldCode.NON_CANONICAL_PROOF,
                    path=dep_path.freeze(), message="persisted usage cannot be empty"))
            if not self._canonical(objects, codec):
                errors.add(SourceFieldIssue(code=SourceFieldCode.NON_CANONICAL_PROOF,
                    path=dep_path.field(_OBJECTS).freeze(),
                    message="object refs must have unique identities and canonical order"))
            if not self._canonical(collections, codec):
                errors.add(SourceFieldIssue(code=SourceFieldCode.NON_CANONICAL_PROOF,
                    path=dep_path.field(_COLLECTIONS).freeze(),
                    message="collection refs must have unique identities and canonical order"))
        return errors.snapshot()

    @staticmethod
    def _canonical(refs: tuple[SourceVersionRef, ...] | tuple[SourceCollectionVersionRef, ...],
                   codec: CanonicalCodec) -> bool:
        keys = tuple(codec.encode(ref) for ref in refs)
        identities = tuple(ref.object_id if isinstance(ref, SourceVersionRef) else ref.collection_id for ref in refs)
        return len(set(identities)) == len(identities) and all(
            left < right for left, right in zip(keys, keys[1:]))
