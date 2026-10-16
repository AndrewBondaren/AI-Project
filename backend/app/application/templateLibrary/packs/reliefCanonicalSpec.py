"""Relief declares no canonical bodies (TZ relief R29, packs §6).

An empty source still participates in the shared per-read attach contract.
It never inspects the FS domain root or turns user packs into defaults.
"""

from app.application.canonicalLibrary import (
    CanonicalAttachPolicy,
    CanonicalLibrarySpec,
    CanonicalScope,
    CanonicalSnapshot,
    CanonicalSourceError,
    SqlCanonicalPersistence,
)
from app.application.templateLibrary.packs.defaults import default_pack_names
from app.db.models.reliefTemplate import ReliefTemplateRow
from app.ids import LibraryKind


class ReliefCanonicalSource:
    async def load(self, context) -> CanonicalSnapshot:
        # Adding defaults requires a validated pack source + membership attach,
        # not silently ignoring a changed trusted declaration.
        if default_pack_names(LibraryKind.RELIEF_TEMPLATES):
            raise CanonicalSourceError("relief canonical source requires an empty default-pack declaration")
        return CanonicalSnapshot()


RELIEF_CANONICAL_SPEC = CanonicalLibrarySpec(
    name=LibraryKind.RELIEF_TEMPLATES.value,
    scope=CanonicalScope.GLOBAL,
    attach_policy=CanonicalAttachPolicy.GLOBAL_FILL_MISSING,
    global_source=ReliefCanonicalSource(),
    global_persistence=SqlCanonicalPersistence(model=ReliefTemplateRow),
)
