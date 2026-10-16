"""Assembly of the shared write pipeline from existing application dependencies."""
from app.application.templateLibrary.packs.write.writeExecutor import LibraryWriteExecutor
from app.application.templateLibrary.packs.write.writeInspector import LibraryWriteInspector
from app.application.templateLibrary.packs.write.writePlanner import LibraryWritePlanner
from app.application.templateLibrary.packs.write.writePolicy import LibraryWritePolicy
from app.application.templateLibrary.packs.write.writeService import LibraryWriteService


def build_library_write_service(*, db, catalog, adapters, worlds, world_repository, locations=None) -> LibraryWriteService:
    return LibraryWriteService(db=db,
        inspector=LibraryWriteInspector(catalog=catalog, adapters=adapters, worlds=worlds,
                                        locations=locations),
        policy=LibraryWritePolicy(), planner=LibraryWritePlanner(adapters),
        executor=LibraryWriteExecutor(db=db, catalog=catalog, adapters=adapters,
                                     world_repository=world_repository))
