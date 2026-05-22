from typing import Awaitable, Callable, TypeVar

from app.api.schemas.imports import ImportError, ImportResult

T = TypeVar("T")


async def import_list(
    rows: list[dict],
    prepare: Callable[[dict], T],
    upsert: Callable[[T], Awaitable[None]],
) -> ImportResult:
    succeeded = 0
    errors: list[ImportError] = []
    for i, row in enumerate(rows):
        try:
            obj = prepare(row)
            await upsert(obj)
            succeeded += 1
        except Exception as e:
            errors.append(ImportError(index=i, message=str(e)))
    return ImportResult(total=len(rows), succeeded=succeeded, failed=len(errors), errors=errors)
