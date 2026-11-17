"""Chunk input evidence checks without payload admission or state transitions."""

from typing import TypeVar

from pydantic import BaseModel

from app.application.worldData.pack.preparation.errors import valid_preparation_field, preparation_field_value
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldPack.preparation.errors import PackPreparationDiagnostic, PackPreparationIssueCode
from app.dataModel.worldPack.preparation.operations import PackWildernessChunkWrite
from app.dataModel.worldPack.preparation.parts import PackWildernessChunkPartInput
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataInputEvidence, PackMetadataValueInputSelector, PackMetadataInputField
from app.application.worldData.pack.preparation.metadataProjection import metadata_input_fingerprint
from app.dataModel.worldPack.meta.worldPackManifest import ChunkRefineRole

from app.application.worldData.pack.preparation.errors import _issue

RootT = TypeVar("RootT", bound=BaseModel)
ItemT = TypeVar("ItemT", bound=PackWildernessChunkWrite)


class MetadataEvidenceValidator:
    def check(
        self, model: type[ItemT], item: object, world: str | None, path: CheckedPath[RootT, ItemT],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        part = preparation_field_value(item, FieldRef(lambda: model, lambda value: value.part))
        inputs = FieldRef(lambda: model, lambda value: value.metadata_inputs)
        raw_inputs = preparation_field_value(item, inputs)
        address = valid_preparation_field(part, FieldRef(lambda: PackWildernessChunkPartInput, lambda value: value.address))
        role_field: FieldRef[PackWildernessChunkWrite, ChunkRefineRole | None] = FieldRef(lambda: PackWildernessChunkWrite, lambda value: value.refine_role)
        role = valid_preparation_field(item, role_field)
        role_valid = role is not None or preparation_field_value(item, role_field) is None
        present: set[PackMetadataInputField] = set()
        selectors_valid = True
        for index, evidence in enumerate(raw_inputs if isinstance(raw_inputs, tuple) else ()):
            evidence_path = path.field(inputs).item(index)
            selector_field = FieldRef(lambda: PackMetadataInputEvidence, lambda value: value.input)
            selector = valid_preparation_field(evidence, selector_field)
            usage_field = FieldRef(lambda: PackMetadataInputEvidence, lambda value: value.source_usage)
            usage = preparation_field_value(evidence, usage_field)
            world_field = FieldRef(lambda: SourceProofInput, lambda value: value.world_uid)
            usage_world = valid_preparation_field(usage, world_field)
            if world is not None and usage_world is not None and world != usage_world:
                _issue(errors, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                       evidence_path.field(usage_field).field(world_field), "input usage belongs to another world")
            if selector is None:
                selectors_valid = False
                continue
            if not isinstance(selector, PackMetadataValueInputSelector) or selector.field not in (
                    PackMetadataInputField.ADDRESS, PackMetadataInputField.REFINE_ROLE):
                _issue(errors, PackPreparationIssueCode.METADATA_INPUT_MISMATCH, evidence_path.field(selector_field), "unsupported chunk input selector")
                continue
            if selector.field in present:
                _issue(errors, PackPreparationIssueCode.METADATA_INPUT_MISMATCH, evidence_path.field(selector_field), "duplicate input selector")
            present.add(selector.field)
            fingerprint_field = FieldRef(lambda: PackMetadataInputEvidence, lambda value: value.value_fingerprint)
            fingerprint = valid_preparation_field(evidence, fingerprint_field)
            selected = address if selector.field is PackMetadataInputField.ADDRESS else role
            available = address is not None if selector.field is PackMetadataInputField.ADDRESS else role_valid
            if available and fingerprint is not None and fingerprint != metadata_input_fingerprint(selector, selected):
                _issue(errors, PackPreparationIssueCode.METADATA_INPUT_MISMATCH, evidence_path.field(fingerprint_field), "input fingerprint differs from selected value")
        if isinstance(raw_inputs, tuple) and selectors_valid and present != {PackMetadataInputField.ADDRESS, PackMetadataInputField.REFINE_ROLE}:
            _issue(errors, PackPreparationIssueCode.METADATA_INPUT_MISMATCH, path.field(inputs), "missing required chunk input evidence")
