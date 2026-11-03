from dataclasses import dataclass

from pydantic import BaseModel

from app.dataModel.engine.dag.identity import ContractId, ContractVersion


@dataclass(frozen=True)
class ContinuationContract[S: BaseModel]:
    contract_id: ContractId
    version: ContractVersion
    state_type: type[S]
