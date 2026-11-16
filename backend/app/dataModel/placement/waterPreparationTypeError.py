"""Field cause with source context for authored water geometry."""
from pydantic import BaseModel

from app.dataModel.fields.checkedPath import CheckedPath, CheckedPathError
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.waterPreparationCode import WaterPreparationCode
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class WaterPreparationTypeError(FieldPathError[WaterPreparationCode]):
    source_uid: EntityUid

    def diagnostic_path(self) -> tuple[str | int, ...]:
        return ("authored_geometry", self.source_uid, *self.path.projection())

    @classmethod
    def at(cls, model: type[BaseModel], loc: tuple[str | int, ...], message: str, *,
           source_uid: EntityUid, code: WaterPreparationCode) -> "WaterPreparationTypeError":
        path = CheckedPath.from_pydantic_loc(model, loc)
        if path is None:
            raise CheckedPathError(f"{model.__name__} has no field at {loc!r}")
        return cls(code=code, message=message, path=path, source_uid=source_uid)
