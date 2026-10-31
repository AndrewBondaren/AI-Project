"""Repair transport for failed sections in the existing conversation."""

from dataclasses import dataclass

from pydantic import BaseModel, TypeAdapter

from app.application.engine.repair.repairMode import RepairMode
from app.application.engine.runtime.prompt.pojo.llmPayload import LLMPayload
from app.application.engine.runtime.repair.pojo.nodeFailureContext import NodeFailureContext


@dataclass(frozen=True, kw_only=True)
class LLMRepairPayload(LLMPayload):
    errors: tuple[NodeFailureContext[BaseModel], ...]
    mode: RepairMode = RepairMode.MAXIMUM

    def __post_init__(self) -> None:
        super().__post_init__()
        TypeAdapter(RepairMode).validate_python(self.mode, strict=True)
        # Tuples of native validation contexts are transient, not resume snapshots.
        self._validate_errors(self.errors)

    def _validate_errors(self, errors: object) -> None:
        if not isinstance(errors, tuple) or not errors:
            raise ValueError("repair requires a nonempty tuple of failures")
        if tuple(error.identity.node_id for error in self.errors) != tuple(section.node_id for section in self.sections):
            raise ValueError("repair failures must match ordered sections exactly")
        contexts = {(error.identity.execution_id, error.pass_number, error.repair_attempt) for error in self.errors}
        if len(contexts) != 1:
            raise ValueError("repair failures have mixed execution/pass/repair attempt")
        for error, section in zip(self.errors, self.sections, strict=True):
            error.__post_init__()
            if error.output_type is not section.output_type:
                raise TypeError("repair Output schema does not match prepared section")
            if section.node_id in ("type", "errors"):
                raise ValueError("repair node ID collides with reserved transport key")

    def to_user_dict(self) -> dict[str, object]:
        errors = [error.to_dict() for error in self.errors]
        if self.mode == RepairMode.ECONOMY:
            return {"type": "repair", "errors": errors}
        return {**super().to_user_dict(), "type": "repair", "errors": errors}

    def to_dict(self) -> dict[str, object]:
        payload = self.to_user_dict()
        if self.mode == RepairMode.MAXIMUM:
            payload["dsl"] = self.global_dsl
        return payload
