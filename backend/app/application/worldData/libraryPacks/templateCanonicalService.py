"""Atomic attach of the declared structure/building/plot graph (TZ packs §6)."""
from pathlib import Path

from app.application.canonicalLibrary import ensure_canonical
from app.application.worldData.libraryPacks.templateCanonicalPersistence import (
    TemplateCanonicalContext, template_canonical_spec,
)
from app.application.worldData.libraryPacks.templateCanonicalSource import (
    SOURCE_ROOT, load_canonical_template_graph,
)


class TemplateCanonicalService:
    def __init__(self, *, db, catalog, source_root: Path = SOURCE_ROOT):
        self._db, self._catalog, self._root = db, catalog, source_root

    async def ensure(self):
        graph = load_canonical_template_graph(self._root)
        results = {}
        # Own the main-connection UOW before domain locks, including concurrent reads.
        # No positive fullness cache: check body + membership on every call.
        async with self._db.transaction_if_needed():
            for pack in graph:
                context = TemplateCanonicalContext(self._db, self._catalog, pack)
                results[pack.kind] = await ensure_canonical(template_canonical_spec(pack), context)
        return results
