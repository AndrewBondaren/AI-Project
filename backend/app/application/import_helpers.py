from typing import Awaitable, Callable, TypeVar

from app.api.schemas.imports import ImportError, ImportResult

T = TypeVar("T")


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
