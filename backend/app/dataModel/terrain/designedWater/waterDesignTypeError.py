"""Field cause with operation context for water preparation."""
from typing import Literal

from pydantic import BaseModel

from app.dataModel.fields.checkedPath import CheckedPath, CheckedPathError
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class WaterDesignTypeError(FieldPathError[WaterDesignIssueCode]):
    operation: Literal["continental_field", "water_source"]
    source_uid: EntityUid | None = None
    expected_window: PlanRef | None = None
    prefix: tuple[str, ...] = ()

    def diagnostic_path(self) -> tuple[str | int, ...]:
        source = (self.source_uid,) if self.source_uid is not None else ()
        return (self.operation, *source, *self.prefix, *self.path.projection())

    @classmethod
    def at(cls, model: type[BaseModel], loc: tuple[str | int, ...], message: str, *,
           operation: Literal["continental_field", "water_source"], source_uid: EntityUid | None = None,
           prefix: tuple[str, ...] = (), expected_window: PlanRef | None = None) -> "WaterDesignTypeError":
        path = CheckedPath.from_pydantic_loc(model, loc)
        if path is None:
            raise CheckedPathError(f"{model.__name__} has no field at {loc!r}")
        return cls(code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT, message=message, path=path,
                   operation=operation, source_uid=source_uid, prefix=prefix, expected_window=expected_window)
