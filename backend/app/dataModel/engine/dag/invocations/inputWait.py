from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.dataModel.engine.dag.identity import ContractIdValue, ContractVersionValue, InvocationIdValue, Ordinal, WaitIdValue

type Reference = Annotated[str, StringConstraints(strict=True, min_length=1)]


class InteractionOwner(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    world_uid: Reference
    player_uid: Reference
    session_uid: Reference


class InteractionBinding(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    owner: InteractionOwner
    reference: Reference
    revision: Ordinal
    policy_evidence: Reference


class InputReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    wait_id: WaitIdValue
    request_id: Reference
    revision: Annotated[int, Field(strict=True, gt=0)]


class AcceptedInput(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    payload: str
    receipt: InputReceipt


class SavedWait(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    wait_id: WaitIdValue
    invocation_id: InvocationIdValue
    step_index: Ordinal
    contract_id: ContractIdValue
    version: ContractVersionValue
    binding: InteractionBinding
    intermediate: str
    accepted: AcceptedInput | None = None
