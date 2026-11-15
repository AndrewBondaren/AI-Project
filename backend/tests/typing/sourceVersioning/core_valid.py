"""Internal checker call sites preserve the type of the selected request field."""
from app.application.worldData.sourceVersioning.proof.atomIndex import SourceProofAtomIndex
from app.application.worldData.sourceVersioning.proof.validation.sourceProofCanonicalChecker import SourceProofCanonicalChecker
from app.application.worldData.sourceVersioning.proof.validation.sourceSelectionChecker import SourceSelectionChecker
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelectInput, SourceProofSelection


def check(request: SourceProofSelectInput) -> None:
    proof: FieldRef[SourceProofSelectInput, SourceDurableProof] = FieldRef(
        lambda: SourceProofSelectInput, lambda value: value.proof)
    selection: FieldRef[SourceProofSelectInput, SourceProofSelection] = FieldRef(
        lambda: SourceProofSelectInput, lambda value: value.selection)
    root = CheckedPath.root(SourceProofSelectInput)
    SourceProofCanonicalChecker().check(proof.select(request), path=root.field(proof))
    SourceSelectionChecker(SourceProofAtomIndex()).check(selection.select(request),
        proof=request.proof, path=root.field(selection), selection_index=None)
