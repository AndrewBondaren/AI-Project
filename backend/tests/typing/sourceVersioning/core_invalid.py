"""Exactly four deliberate errors: wrong path, value, world and request root."""
from app.application.worldData.sourceVersioning.proof.validation.sourceProofCanonicalChecker import SourceProofCanonicalChecker
from app.application.worldData.sourceVersioning.proof.validation.sourceWorldChecker import SourceWorldChecker
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofReadInput
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelectInput, SourceProofSelection


def reject(request: SourceProofSelectInput) -> None:
    selection: FieldRef[SourceProofSelectInput, SourceProofSelection] = FieldRef(
        lambda: SourceProofSelectInput, lambda value: value.selection)
    wrong_path = CheckedPath.root(SourceProofSelectInput).field(selection)
    SourceProofCanonicalChecker().check(request.proof, path=wrong_path)
    proof_path = CheckedPath.root(SourceProofSelectInput).field(FieldRef(
        lambda: SourceProofSelectInput, lambda value: value.proof))
    SourceProofCanonicalChecker().check(request.selection, path=proof_path)
    SourceWorldChecker().check(42, expected="w", group_index=None, use_index=None, source=None)
    wrong_root: CheckedPath[SourceProofReadInput, SourceDurableProof] = CheckedPath.root(SourceProofSelectInput).field(
        FieldRef(lambda: SourceProofSelectInput, lambda value: value.proof))
