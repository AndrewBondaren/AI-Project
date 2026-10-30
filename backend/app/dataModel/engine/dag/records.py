"""Immutable published values and read evidence. SoT: tz_engine_node_context §§6–7."""

from typing import Annotated, Generic, Self, TypeVar, cast

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

from app.dataModel.engine.dag.identity import (
    ContractIdValue,
    ContractVersionValue,
    DomainRevisionValue,
    ExecutionIdentity,
    NodeIdValue,
)
from app.dataModel.validation.immutableValue import validate_immutable


O = TypeVar("O", bound=BaseModel)


class DependencyRead(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    producer: NodeIdValue
    contract_id: ContractIdValue
    contract_version: ContractVersionValue
    required: bool
    result: ExecutionIdentity | None

    @model_validator(mode="after")
    def check_producer(self) -> Self:
        if self.result is not None and self.result.node_id != self.producer:
            raise ValueError("read result must belong to its declared producer")
        return self


class DomainReadEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    domain: Annotated[str, StringConstraints(min_length=1, pattern=r"^\S(?:.*\S)?$")]
    revision: DomainRevisionValue | None


class OutputRecord(BaseModel, Generic[O]):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    identity: ExecutionIdentity
    contract_id: ContractIdValue
    contract_version: ContractVersionValue
    # Publication admits an already validated POJO, preserving its identity even
    # when its class normally revalidates/copies model instances.
    output: O
    reads: tuple[DependencyRead, ...] = ()
    domain_reads: tuple[DomainReadEvidence, ...] = ()

    @field_validator("output", mode="plain")
    @classmethod
    def admit_existing_output(cls, value: object) -> O:
        output_type = cls.model_fields["output"].annotation
        if isinstance(output_type, TypeVar):
            output_type = output_type.__bound__
        if not isinstance(output_type, type) or not issubclass(output_type, BaseModel):
            raise ValueError("OutputRecord requires a POJO output contract")
        if not isinstance(value, output_type):
            raise ValueError("output must be an instance of the declared POJO contract")
        # Checked generic cast at the private admission boundary. Field/schema
        # validation belongs to the node boundary; this record must not copy O.
        return cast(O, value)

    @model_validator(mode="after")
    def check_published_record(self) -> Self:
        for read in self.reads:
            if read.required and read.result is None:
                raise ValueError("successful Output cannot have an absent required read")
            if read.result is not None and read.result.execution_id != self.identity.execution_id:
                raise ValueError("dependency read belongs to a different execution")
        validate_immutable(self)
        return self
