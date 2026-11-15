"""Selection admissibility against a canonical proof, without subset extraction."""

from typing import get_args

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1 import SOURCE_PROOF_SCHEMA_V1
from app.application.worldData.sourceVersioning.proof.atomIndex import SourceProofAtomIndex
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.sourceVersioning._proofValueRules import invalid_selection_order_positions
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
        bound = bind_field(_INDICES)
        element_type = get_args(bound.model.model_fields[bound.field].annotation)[0]
        element_validator: TypeAdapter[int] = TypeAdapter(element_type)
        usable: list[int] = []
        usable_positions: list[int] = []
        invalid_positions: set[int] = set()
        for position, index in enumerate(indices):
            try:
                value = element_validator.validate_python(index, strict=True)
            except ValidationError:
                invalid_positions.add(position)
            else:
                usable.append(value)
                usable_positions.append(position)
        invalid_positions.update(usable_positions[position] for position in
                                 invalid_selection_order_positions(tuple(usable)))
        for position in sorted(invalid_positions):
            errors.add(SourceFieldIssue(code=SourceFieldCode.INVALID_SELECTION,
                path=path.field(_INDICES).item(position).freeze(),
                message="selection indices must be non-negative integers, unique and increasing"))
        fingerprint = content_digest(CanonicalCodec(SOURCE_PROOF_SCHEMA_V1).encode(proof)).hex()
        if selection.proof_fingerprint != fingerprint:
            errors.add(SourceLogicIssue(code=SourceLogicCode.SELECTION_PROOF_MISMATCH,
                group_index=selection_index, use_index=None, source=None, artifact=None))
        atom_count = len(self._atoms.enumerate(proof))
        if any(index >= atom_count for index in usable):
            errors.add(SourceLogicIssue(code=SourceLogicCode.SELECTION_OUT_OF_RANGE,
                group_index=selection_index, use_index=None, source=None, artifact=None))
        return errors.snapshot()
