"""Execution faults at the checked section-handler boundary."""


class SectionHandlerContractError(RuntimeError):
    """A returned handler value violates its declared output contract."""
