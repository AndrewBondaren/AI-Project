"""Execution faults at the checked section-handler boundary."""
from app.dataModel.patch.validation.admissionReasons import PatchSetAdmissionReason, ADMISSION_REASON_TYPES
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper


class PatchSetAdmissionError(Exception):
    def __init__(self, reasons: tuple[PatchSetAdmissionReason, ...]) -> None:
        collector = ValidatorAggregationHelper[PatchSetAdmissionReason](ADMISSION_REASON_TYPES)
        for reason in reasons:
            collector.add(reason)
        self.reasons = collector.snapshot()
        if not self.reasons:
            raise ValueError("admission failure requires reasons")
        super().__init__("PatchSet admission failed")


class PatchSetValidationClassificationError(RuntimeError):
    """A validation error cannot safely be classified as input diagnostics."""


class SectionHandlerContractError(RuntimeError):
    """A returned handler value violates its declared output contract."""
