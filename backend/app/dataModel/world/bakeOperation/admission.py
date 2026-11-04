from dataclasses import dataclass

from app.dataModel.world.bakeOperation.record import BakeOwner


@dataclass(frozen=True)
class Started:
    operation_ref: str
    owner_token: BakeOwner


@dataclass(frozen=True)
class Joined:
    operation_ref: str


@dataclass(frozen=True)
class BakeConflict:
    active_operation_ref: str


type BakeAdmission = Started | Joined | BakeConflict
