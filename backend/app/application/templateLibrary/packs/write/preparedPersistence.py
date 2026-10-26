"""Strict body-row persistence shared by domain libraries, no policy or upsert."""
from app.application.templateLibrary.packs.errors import LibraryPackConflictError
from app.db.database import _in_transaction


async def persist_body_row(repo, row, *, added):
    if not _in_transaction.get():
        raise RuntimeError("prepared body persistence requires caller UOW")
    current = await repo.get_by_uid(row.template_uid)
    if added:
        if current is not None:
            raise LibraryPackConflictError("new body identity occupied")
        await repo.insert(row)
    else:
        if current is None:
            raise LibraryPackConflictError("replacement body missing")
        await repo.save(row)
    return row
