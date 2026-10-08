from datetime import datetime
from typing import Awaitable, Callable, TypeVar
from inspect import signature

from app.application.importResult import ImportError, ImportResult

T = TypeVar("T")


def prepare_import_row(model: type[T], row: dict) -> T:
    """Validate constructor shape before persistence, without changing wire types.

    DB dataclass annotations are storage metadata; wire POJOs own field types.
    In particular some legacy registry columns accept list wire in dict columns.
    """
    try:
        signature(model).bind(**row)
    except TypeError as exc:
        raise ValueError(str(exc)) from exc
    return model(**row)


def with_default_created_at(row: dict) -> dict:
    """DB audit field — optional on wire; default to server local time if omitted."""
    if row.get("created_at"):
        return row
    return {**row, "created_at": datetime.now().isoformat(timespec="seconds")}


async def import_list(
    rows: list[dict],
    prepare: Callable[[dict], T],
    upsert: Callable[[T], Awaitable[None]],
    id_key: str = "",
) -> ImportResult:
    succeeded = 0
    errors: list[ImportError] = []
    for i, row in enumerate(rows):
        try:
            obj = prepare(row)
            await upsert(obj)
            succeeded += 1
        except Exception as e:
            entity_id = row.get(id_key) if id_key else None
            errors.append(ImportError(index=i, message=str(e), entity_id=entity_id))
    return ImportResult(total=len(rows), succeeded=succeeded, failed=len(errors), errors=errors)
