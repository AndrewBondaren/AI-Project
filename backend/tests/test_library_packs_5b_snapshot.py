"""Library packs — domain-template-libraries-5b step B3.

``TemplateSnapshotLoader`` at the async boundary: membership-scoped
``EffectiveCatalog`` → prepared typed bodies → immutable
``WorldTemplateSnapshot`` keyed by member ``template_uid``. Same-name
bodies in different packs stay distinct; missing bodies and dangling
declared refs are excluded through the shared diagnostics channel;
``building_catalog_from_snapshot`` feeds the sync packing pipeline.

Real SQLite, migrated schema — same fixture style as test_library_packs_5a.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    building_catalog_from_snapshot,
)
from app.application.worldData.libraryPacks.domainAdapters.factory import (
    build_pack_domain_adapters,
)
from app.application.worldData.libraryPacks.effectiveCatalog import (
    EffectiveCatalogLoader,
)
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.application.worldData.libraryPacks.uidMap import pin_for_member
from app.application.worldData.templateSnapshotLoader import TemplateSnapshotLoader
from app.core.container import Container
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
)
from app.dataModel.locations.structure.building.structureTemplate import (
    StructureTemplate,
)
from app.db.database import Database
from app.db.models.world import World
from app.db.repositories.sqlite.plotTemplateRepository import (
    SqlitePlotTemplateRepository,
)
from app.db.repositories.sqlite.structureTemplateRepository import (
    SqliteStructureTemplateRepository,
)
from app.db.repositories.sqlite.worldRepository import SqliteWorldRepository
from app.ids import LibraryKind

_STRUCT = LibraryKind.STRUCTURE_TEMPLATES
_PLOT = LibraryKind.PLOT_TEMPLATES


def _plot_body(local_uid: str, structure_uid: str, **extra) -> dict:
    body = {
        "system_name": local_uid,
        "display_name": local_uid.title(),
        "plot_type": "dwelling",
        "main_building": {"structure": structure_uid},
    }
    body.update(extra)
    return body


class _SnapshotCase(IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(str(Path(self.tmp.name) / "test.sqlite"))
        await self.db.connect()
        self.addAsyncCleanup(self.db.disconnect)
        await self.db.apply_migrations()
        self.container = Container(None, self.db)
        self.service = self.container.library_pack_service()
        self.packs = self.container.library_pack_repository()
        self.members = self.container.library_pack_member_repository()
        self.worlds = SqliteWorldRepository(self.db)
        self.plot_rows = SqlitePlotTemplateRepository(self.db)
        self.structure_rows = SqliteStructureTemplateRepository(self.db)
        # No ensure_defaults — the snapshot holds only explicitly created
        # membership, so assertions stay deterministic.
        self.adapters = build_pack_domain_adapters(
            relief_library=self.container.relief_template_library_service(),
            structure_library=self.container.structure_template_library_service(),
            building_library=self.container.building_template_library_service(),
            plot_library=self.container.plot_template_library_service(),
            relief_world_import=self.container.relief_world_import_service(),
        )
        self.loader = TemplateSnapshotLoader(
            EffectiveCatalogLoader(
                PackCatalogRepos(
                    packs=self.packs,
                    members=self.members,
                    deps=self.container.library_pack_dependency_repository(),
                ),
                self.adapters,
            ),
        )

    async def _world(self, world_uid: str) -> World:
        world = World(world_uid=world_uid, name=world_uid, created_at="2026-10-13")
        await self.worlds.create(world)
        return world

    async def _pack_with_graph(self, world_uid: str, system_name: str,
                               plots: dict[str, str]):
        """World-owned pack: one structure member + plots referencing it."""
        pack = await self.service.create_pack(
            system_name=system_name, owner_world_uid=world_uid
        )
        struct = await self.service.create_member(
            pack.pack_uid, library_kind=_STRUCT, local_uid="geometry",
            body={"display_name": "Geometry", "structure_types": ["tavern"]},
            world_uid=world_uid,
        )
        plot_members = {}
        for local_uid in plots:
            plot_members[local_uid] = await self.service.create_member(
                pack.pack_uid, library_kind=_PLOT, local_uid=local_uid,
                body=_plot_body(local_uid, struct.template_uid),
                world_uid=world_uid,
            )
        return pack, struct, plot_members


class SnapshotLoaderTests(_SnapshotCase):

    async def test_snapshot_is_uid_keyed_typed_and_immutable(self):
        world = await self._world("w1")
        pack, struct, plots = await self._pack_with_graph(
            "w1", "world.w1.plots", {"hall": None, "yard": None})

        snapshot = await self.loader.load(world)

        self.assertEqual(snapshot.world_uid, "w1")
        self.assertEqual(
            set(snapshot.plots),
            {m.template_uid for m in plots.values()},
        )
        self.assertEqual(list(snapshot.plots), sorted(snapshot.plots))
        for uid, entry in snapshot.plots.items():
            self.assertEqual(entry.template_uid, uid)
            self.assertEqual(entry.pack_uid, pack.pack_uid)
            self.assertIsInstance(entry.body, PlotLayoutTemplate)
        self.assertEqual(set(snapshot.structures), {struct.template_uid})
        entry = snapshot.structures[struct.template_uid]
        self.assertIsInstance(entry.body, StructureTemplate)
        self.assertEqual(str(entry.body.system_name), struct.template_uid)
        self.assertEqual(snapshot.buildings, {})

        with self.assertRaises(TypeError):
            snapshot.plots["other"] = next(iter(snapshot.plots.values()))
        with self.assertRaises(AttributeError):
            snapshot.plots = {}

    async def test_same_name_plots_across_packs_stay_distinct(self):
        world = await self._world("w1")
        pack_a, _, plots_a = await self._pack_with_graph(
            "w1", "world.w1.a", {"hall": None})
        pack_b, _, plots_b = await self._pack_with_graph(
            "w1", "world.w1.b", {"hall": None})

        snapshot = await self.loader.load(world)

        uid_a = plots_a["hall"].template_uid
        uid_b = plots_b["hall"].template_uid
        self.assertNotEqual(uid_a, uid_b)
        self.assertEqual(set(snapshot.plots), {uid_a, uid_b})
        self.assertEqual(snapshot.plots[uid_a].pack_uid, pack_a.pack_uid)
        self.assertEqual(snapshot.plots[uid_b].pack_uid, pack_b.pack_uid)
        self.assertEqual(snapshot.plots[uid_a].body.system_name, "hall")
        self.assertEqual(snapshot.plots[uid_b].body.system_name, "hall")

    async def test_foreign_world_and_unpinned_members(self):
        world = await self._world("w1")
        await self._world("w2")
        _, _, own = await self._pack_with_graph("w1", "world.w1.plots", {"hall": None})
        _, _, foreign = await self._pack_with_graph("w2", "world.w2.plots", {"hall": None})
        pinned = own["hall"].template_uid
        await self.container.world_service().update(
            "w1", {"library_pins": [
                pin_for_member(_PLOT, pinned).model_dump(mode="json")
            ]}
        )

        snapshot = await self.loader.load(world)

        self.assertEqual(set(snapshot.plots), {pinned})
        self.assertNotIn(foreign["hall"].template_uid, snapshot.plots)
        self.assertNotIn(foreign["hall"].template_uid, snapshot.structures)

    async def test_member_without_body_is_excluded(self):
        world = await self._world("w1")
        _, _, plots = await self._pack_with_graph(
            "w1", "world.w1.plots", {"hall": None, "yard": None})
        await self.plot_rows.delete(plots["hall"].template_uid)

        snapshot = await self.loader.load(world)

        self.assertEqual(set(snapshot.plots), {plots["yard"].template_uid})

    async def test_plot_with_dangling_structure_ref_is_excluded(self):
        world = await self._world("w1")
        _, struct, plots = await self._pack_with_graph(
            "w1", "world.w1.plots", {"hall": None})
        await self.members.delete(struct.template_uid)
        await self.structure_rows.delete(struct.template_uid)

        snapshot = await self.loader.load(world)

        self.assertEqual(snapshot.plots, {})
        self.assertEqual(snapshot.structures, {})

    async def test_building_catalog_from_snapshot_resolves_by_uid(self):
        world = await self._world("w1")
        _, struct, plots = await self._pack_with_graph(
            "w1", "world.w1.plots", {"hall": None})

        snapshot = await self.loader.load(world)
        catalog = building_catalog_from_snapshot(snapshot)

        uid = plots["hall"].template_uid
        body = catalog.by_uid(uid)
        self.assertIsInstance(body, PlotLayoutTemplate)
        self.assertEqual(catalog.entry_for(uid).template_uid, uid)
        self.assertIs(catalog.structures.resolve(struct.template_uid),
                      snapshot.structures[struct.template_uid].body)
        picked = catalog.of_structure_type("tavern")
        self.assertEqual([e.template_uid for e in picked], [uid])
        self.assertIsNone(catalog.by_uid(plots["hall"].local_uid))


if __name__ == "__main__":
    unittest.main()
