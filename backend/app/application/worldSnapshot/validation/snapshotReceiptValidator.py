"""Pure input association and provenance checks before receipt accumulation."""
from collections.abc import Mapping
from pydantic import ValidationError
from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.context import SnapshotApplyContext
from app.application.worldSnapshot.errors import SnapshotReceiptContractError
from app.application.worldSnapshot.validation.receiptFacts import ReceiptFactsAdmission, check_receipt_index
from app.application.worldSnapshot.validation.receiptProvenance import (
    collect_pinned_base_issues, collect_receipt_provenance, patch_matches_operation,
)
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldSnapshot.diagnostics.receiptContract import (
    ReceiptChangedPatchNotInInput, ReceiptContractIssue, ReceiptSectionMismatch,
)
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef
from app.dataModel.worldSnapshot.metadata.envelope import SnapshotEnvelope
from app.dataModel.worldSnapshot.metadata.metadataIssues import (
    SnapshotMetadataCode, SnapshotMetadataFieldIssue, SnapshotMetadataRelationIssue,
)


class SnapshotReceiptValidator:
    def validate(self, section: DomainSection, receipt: SectionApplyReceipt,
                                  context: SnapshotApplyContext, bases: Mapping[SnapshotRef, SnapshotEnvelope],
                                  *, section_index: int) -> None:
        check_receipt_index(section_index)
        base_issues = collect_pinned_base_issues(context.validation, bases)
        if base_issues:
            raise PublicationInfrastructureError(base_issues)
        facts = ReceiptFactsAdmission.admit(receipt, section_index=section_index)
        errors: ValidatorAggregationHelper[ReceiptContractIssue] = ValidatorAggregationHelper(
            (ReceiptSectionMismatch, ReceiptChangedPatchNotInInput, SnapshotMetadataFieldIssue, SnapshotMetadataRelationIssue))
        for issue in facts.structural_issues:
            errors.add(issue)
        if facts.section_key is not None and facts.section_key != section.header.key:
            errors.add(ReceiptSectionMismatch(section_index=section_index, expected_section_key=section.header.key,
                                              actual_section_key=facts.section_key))
        inputs = frozenset(patch.header.ref for patch in section.patches)
        for item in facts.changed:
            if item.ref not in inputs:
                errors.add(ReceiptChangedPatchNotInInput(section_index=section_index, section_key=section.header.key,
                                                        changed_index=item.index, patch_ref=item.ref))
        for item in facts.changed:
            if not patch_matches_operation(item.ref, context.validation.operation_id):
                errors.add(SnapshotMetadataRelationIssue(code=SnapshotMetadataCode.FOREIGN_OPERATION,
                    location="receipts", address=(section_index, "changed", item.index, "operation_id"),
                    message="patch belongs to another operation"))
        for issue in collect_receipt_provenance(facts, context, bases):
            errors.add(issue)
        if facts.validated is None:
            # Retain the model failure as cause; facts retain all independent diagnostics.
            try:
                SectionApplyReceipt.model_validate(receipt, strict=True)
            except ValidationError as cause:
                raise SnapshotReceiptContractError(errors.snapshot()) from cause
        errors.raise_if_any(SnapshotReceiptContractError)
