"""Selection admissibility against a canonical proof, without subset extraction."""

from pydantic import BaseModel

from app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1 import SOURCE_PROOF_SCHEMA_V1
from app.application.worldData.sourceVersioning.proof.atomIndex import SourceProofAtomIndex
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceErrors import SourceFieldCode, SourceFieldIssue, SourceLogicCode, SourceLogicIssue
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.encoding.canonicalCodec import CanonicalCodec, content_digest

_INDICES: FieldRef[SourceProofSelection, tuple[int, ...]] = FieldRef(
    lambda: SourceProofSelection, lambda selection: selection.dependency_indices)


class SourceSelectionChecker:
    def __init__(self, atoms: SourceProofAtomIndex) -> None:
        self._atoms = atoms

    def check[RootT: BaseModel](self, selection: SourceProofSelection, *,
                               proof: SourceDurableProof,
                               path: CheckedPath[RootT, SourceProofSelection],
                               selection_index: int | None,
                               ) -> tuple[SourceFieldIssue | SourceLogicIssue, ...]:
        if selection_index is not None and (type(selection_index) is not int or selection_index < 0):
            raise ValueError("selection index must be a non-negative integer")
        indices = _INDICES.select(selection)
        if type(indices) is not tuple:
            raise TypeError("selection indices must be a tuple")
        errors = ValidatorAggregationHelper[SourceFieldIssue | SourceLogicIssue]((SourceFieldIssue, SourceLogicIssue))
        previous: int | None = None
        seen: set[int] = set()
        usable: list[int] = []
        for position, index in enumerate(indices):
            valid_int = type(index) is int and index >= 0
            if not valid_int or index in seen or (previous is not None and index <= previous):
                errors.add(SourceFieldIssue(code=SourceFieldCode.INVALID_SELECTION,
                    path=path.field(_INDICES).item(position).freeze(),
                    message="selection indices must be non-negative integers, unique and increasing"))
            if valid_int:
                usable.append(index)
                seen.add(index)
                previous = index
        fingerprint = content_digest(CanonicalCodec(SOURCE_PROOF_SCHEMA_V1).encode(proof)).hex()
        if selection.proof_fingerprint != fingerprint:
            errors.add(SourceLogicIssue(code=SourceLogicCode.SELECTION_PROOF_MISMATCH,
                group_index=selection_index, use_index=None, source=None, artifact=None))
        atom_count = len(self._atoms.enumerate(proof))
        for index in usable:
            if index >= atom_count:
                errors.add(SourceLogicIssue(code=SourceLogicCode.SELECTION_OUT_OF_RANGE,
                    group_index=selection_index, use_index=None, source=None, artifact=None))
        return errors.snapshot()
