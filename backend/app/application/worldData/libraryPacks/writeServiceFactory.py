"""Assembly of the shared write pipeline from existing application dependencies."""
from app.application.worldData.libraryPacks.writeExecutor import LibraryWriteExecutor
from app.application.worldData.libraryPacks.writeInspector import LibraryWriteInspector
from app.application.worldData.libraryPacks.writePlanner import LibraryWritePlanner
from app.application.worldData.libraryPacks.writePolicy import LibraryWritePolicy
from app.application.worldData.libraryPacks.writeService import LibraryWriteService


def build_library_write_service(*, db, catalog, adapters, worlds, world_repository) -> LibraryWriteService:
    return LibraryWriteService(db=db,
        inspector=LibraryWriteInspector(catalog=catalog, adapters=adapters, worlds=worlds),
        policy=LibraryWritePolicy(), planner=LibraryWritePlanner(adapters),
        executor=LibraryWriteExecutor(db=db, catalog=catalog, adapters=adapters,
                                     world_repository=world_repository))
