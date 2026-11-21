"""Closed mock DAG envelopes. Refusals are output values, never NodeError."""
from typing import Never, cast, get_args
from pydantic import BaseModel, ConfigDict, model_validator
from app.application.engine.contracts.nodeContract import NodeContract
from app.dataModel.engine.dag.identity import ContractId, ContractVersion
from app.dataModel.lifecycle.results.errors import LifecycleFieldError, LifecycleLogicError, LifecycleSectionRefused
from tests.lifecycle.support import mixedContracts as m


def _raw_field(value: object, name: str) -> object:
    if isinstance(value, dict):
        return cast(dict[str, object], value).get(name)
    return None


class RequestEnvelope[Q: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    request: Q

    @model_validator(mode="before")
    @classmethod
    def exact_request(cls, value: object) -> object:
        request = value.request if isinstance(value, cls) else _raw_field(value, "request")
        if type(request) is not cls.model_fields["request"].annotation:
            raise ValueError("node input requires the exact named request model")
        return value


class OutputEnvelope[V: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    value: V

    @model_validator(mode="before")
    @classmethod
    def exact_value(cls, value: object) -> object:
        result = value.value if isinstance(value, cls) else _raw_field(value, "value")
        if type(result) not in get_args(cls.model_fields["value"].annotation):
            raise ValueError("node output requires an exact declared result model")
        return value


class CreateNodeInputA(RequestEnvelope[m.CreateRequestA]):
    pass


class CreateNodeOutputA(OutputEnvelope[m.CreateA | LifecycleFieldError | LifecycleLogicError]):
    pass


CREATEA_CONTRACT: NodeContract[CreateNodeInputA, CreateNodeOutputA, Never] = NodeContract(
    CreateNodeInputA, CreateNodeOutputA, ContractId("engine.lifecycle.test_a.prepare_create"), ContractVersion("1"), (), error_types=(),
)


class CreateNodeInputB(RequestEnvelope[m.CreateRequestB]):
    pass


class CreateNodeOutputB(OutputEnvelope[m.CreateB | LifecycleFieldError | LifecycleLogicError]):
    pass


CREATEB_CONTRACT: NodeContract[CreateNodeInputB, CreateNodeOutputB, Never] = NodeContract(
    CreateNodeInputB, CreateNodeOutputB, ContractId("engine.lifecycle.test_b.prepare_create"), ContractVersion("1"), (), error_types=(),
)


class ReplaceNodeInputA(RequestEnvelope[m.ReplaceRequestA]):
    pass


class ReplaceNodeOutputA(OutputEnvelope[m.ReplaceA | LifecycleFieldError | LifecycleLogicError]):
    pass


REPLACEA_CONTRACT: NodeContract[ReplaceNodeInputA, ReplaceNodeOutputA, Never] = NodeContract(
    ReplaceNodeInputA, ReplaceNodeOutputA, ContractId("engine.lifecycle.test_a.prepare_replacement"), ContractVersion("1"), (), error_types=(),
)


class ReplaceNodeInputB(RequestEnvelope[m.ReplaceRequestB]):
    pass


class ReplaceNodeOutputB(OutputEnvelope[m.ReplaceB | LifecycleFieldError | LifecycleLogicError]):
    pass


REPLACEB_CONTRACT: NodeContract[ReplaceNodeInputB, ReplaceNodeOutputB, Never] = NodeContract(
    ReplaceNodeInputB, ReplaceNodeOutputB, ContractId("engine.lifecycle.test_b.prepare_replacement"), ContractVersion("1"), (), error_types=(),
)


class EndNodeInputA(RequestEnvelope[m.EndRequestA]):
    pass


class EndNodeOutputA(OutputEnvelope[m.EndA | LifecycleFieldError | LifecycleLogicError]):
    pass


ENDA_CONTRACT: NodeContract[EndNodeInputA, EndNodeOutputA, Never] = NodeContract(
    EndNodeInputA, EndNodeOutputA, ContractId("engine.lifecycle.test_a.prepare_end"), ContractVersion("1"), (), error_types=(),
)


class EndNodeInputB(RequestEnvelope[m.EndRequestB]):
    pass


class EndNodeOutputB(OutputEnvelope[m.EndB | LifecycleFieldError | LifecycleLogicError]):
    pass


ENDB_CONTRACT: NodeContract[EndNodeInputB, EndNodeOutputB, Never] = NodeContract(
    EndNodeInputB, EndNodeOutputB, ContractId("engine.lifecycle.test_b.prepare_end"), ContractVersion("1"), (), error_types=(),
)


class ReactivateNodeInputA(RequestEnvelope[m.ReactivateRequestA]):
    pass


class ReactivateNodeOutputA(OutputEnvelope[m.ReactivateA | LifecycleFieldError | LifecycleLogicError]):
    pass


REACTIVATEA_CONTRACT: NodeContract[ReactivateNodeInputA, ReactivateNodeOutputA, Never] = NodeContract(
    ReactivateNodeInputA, ReactivateNodeOutputA, ContractId("engine.lifecycle.test_a.prepare_reactivate"), ContractVersion("1"), (), error_types=(),
)


class ReactivateNodeInputB(RequestEnvelope[m.ReactivateRequestB]):
    pass


class ReactivateNodeOutputB(OutputEnvelope[m.ReactivateB | LifecycleFieldError | LifecycleLogicError]):
    pass


REACTIVATEB_CONTRACT: NodeContract[ReactivateNodeInputB, ReactivateNodeOutputB, Never] = NodeContract(
    ReactivateNodeInputB, ReactivateNodeOutputB, ContractId("engine.lifecycle.test_b.prepare_reactivate"), ContractVersion("1"), (), error_types=(),
)


class SectionNodeInputAB(RequestEnvelope[m.PrepareLifecycleSectionAB]):
    pass


class SectionNodeOutputAB(OutputEnvelope[m.LifecycleSectionAB | LifecycleSectionRefused]):
    pass


SECTIONAB_CONTRACT: NodeContract[SectionNodeInputAB, SectionNodeOutputAB, Never] = NodeContract(
    SectionNodeInputAB, SectionNodeOutputAB, ContractId("engine.lifecycle.prepare_section"), ContractVersion("1"), (), error_types=(),
)

