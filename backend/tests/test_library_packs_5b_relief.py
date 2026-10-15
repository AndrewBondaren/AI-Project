"""Library packs — domain-template-libraries-5b step B5.

Relief reader/pick cutover: ``TemplateSnapshotLoader.load_relief`` builds a
membership-scoped ``ReliefTemplateSnapshot`` keyed by member
``template_uid``, and ``pick_template`` selects from those UID-keyed typed
bodies — the legacy ``relief_template_registry`` no longer drives either
body loading or candidate selection.

Candidate order is member-UID order; the registry declared order dies with
the registry (documented behavior diff), so round-robin follows sorted
uids. A missing/invalid body or an unknown fixed uid rejects through the
shared diagnostics instead of substituting another template.

Real SQLite, migrated schema — same fixture style as test_library_packs_5a.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from uuid import uuid4

from app.application.jsonValidation.resolve import UnresolvedModelError
from app.application.worldData.generators.terrain.relief.pick.templatePick import (
    pick_template,
)
from app.application.worldData.libraryPacks.domainAdapters.factory import (
    build_pack_domain_adapters,
)
from app.application.worldData.libraryPacks.effectiveCatalog import (
    EffectiveCatalogLoader,
)
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.application.worldData.loadReliefTemplatesForWorld import (
    load_relief_templates_for_world,
)
from app.application.worldData.templateSnapshotLoader import TemplateSnapshotLoader
from app.core.container import Container
from app.dataModel.terrain.relief.enums import ReliefContext, ReliefPickMode
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.worldReliefPickPolicy import (
    ReliefContextPickPolicy,
    WorldReliefPickPolicy,
)
from app.db.database import Database
from app.db.models.reliefTemplate import ReliefTemplateRow
from app.db.models.world import World
from app.db.repositories.sqlite.reliefTemplateRepository import (
    SqliteReliefTemplateRepository,
)
from app.db.repositories.sqlite.worldRepository import SqliteWorldRepository
from app.ids import LibraryKind
from tests.test_library_packs_4b import _relief_body

_RELIEF = LibraryKind.RELIEF_TEMPLATES


class _ReliefSnapshotCase(IsolatedAsyncioTestCase):

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
        self.relief_rows = SqliteReliefTemplateRepository(self.db)
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

    async def _relief_pack(
        self,
        world_uid: str,
        system_name: str,
        *local_uids: str,
        context: str = "open_land",
    ):
        pack = await self.service.create_pack(
            system_name=system_name, owner_world_uid=world_uid,
        )
        members = []
        for local_uid in local_uids:
            members.append(await self.service.create_member(
                pack.pack_uid, library_kind=_RELIEF, local_uid=local_uid,
                body=_relief_body(local_uid, context=context),
                world_uid=world_uid,
            ))
        return pack, members


class ReliefSnapshotTests(_ReliefSnapshotCase):

    async def test_snapshot_is_membership_scoped_uid_keyed_and_sorted(self):
        world = await self._world("w1")
        await self._world("w2")
        pack, own = await self._relief_pack("w1", "world.w1.relief", "meadow", "bog")
        _, foreign = await self._relief_pack("w2", "world.w2.relief", "ridge")

        snapshot = await self.loader.load_relief(world)

        self.assertEqual(snapshot.world_uid, "w1")
        self.assertEqual(set(snapshot.templates), {m.template_uid for m in own})
        self.assertNotIn(foreign[0].template_uid, snapshot.templates)
        self.assertEqual(list(snapshot.templates), sorted(snapshot.templates))
        for uid, entry in snapshot.templates.items():
            self.assertEqual(entry.template_uid, uid)
            self.assertEqual(entry.pack_uid, pack.pack_uid)
            self.assertIsInstance(entry.body, ReliefTemplate)

    async def test_member_without_body_and_invalid_body_are_excluded(self):
        world = await self._world("w1")
        _, members = await self._relief_pack("w1", "world.w1.relief", "meadow", "bog", "fen")
        await self.relief_rows.delete(members[0].template_uid)
        row = await self.relief_rows.get_by_uid(members[1].template_uid)
        await self.relief_rows.upsert(ReliefTemplateRow(
            template_uid=row.template_uid, system_name=row.system_name,
            display_name=row.display_name, context=row.context,
            data={"system_name": "renamed", "context": "open_land"},
        ))

        snapshot = await self.loader.load_relief(world)

        self.assertEqual(set(snapshot.templates), {members[2].template_uid})

    async def test_reader_returns_typed_bodies_from_membership(self):
        """Membership alone supplies candidates; no registry exists."""
        world = await self._world("w1")
        _, members = await self._relief_pack("w1", "world.w1.relief", "meadow")
        bodies = await load_relief_templates_for_world(self.loader, world)
        self.assertEqual(set(bodies), {members[0].template_uid})
        self.assertIsInstance(bodies[members[0].template_uid], ReliefTemplate)


class ReliefPickTests(_ReliefSnapshotCase):

    def _policy(self, mode: ReliefPickMode, default: str | None = None) -> WorldReliefPickPolicy:
        return WorldReliefPickPolicy(
            mountain=ReliefContextPickPolicy(mode=mode, default_template_uid=default),
        )

    async def test_round_robin_follows_member_uid_order(self):
        world = await self._world("w1")
        _, members = await self._relief_pack(
            "w1", "world.w1.relief", "dome", "peak", "ridge",
            context="mountain",
        )
        bodies = await load_relief_templates_for_world(self.loader, world)
        expected = sorted(m.template_uid for m in members)

        picks = [
            pick_template(
                context=ReliefContext.MOUNTAIN, templates=bodies,
                world_policy=self._policy(ReliefPickMode.ROUND_ROBIN),
                world_seed="seed", site_id=f"m{i}", occurrence_seq=i,
            ).template_uid
            for i in range(4)
        ]

        self.assertEqual(picks, [expected[0], expected[1], expected[2], expected[0]])

    async def test_fixed_member_uid_picks_without_registry(self):
        world = await self._world("w1")
        _, members = await self._relief_pack(
            "w1", "world.w1.relief", "dome", "peak", context="mountain",
        )
        bodies = await load_relief_templates_for_world(self.loader, world)
        target = members[1].template_uid

        result = pick_template(
            context="mountain", templates=bodies,
            world_policy=self._policy(ReliefPickMode.FIXED, target),
            world_seed="seed", site_id="m1",
        )

        self.assertEqual(result.template_uid, target)
        self.assertEqual(result.policy_level, "world")

    async def test_missing_candidates_and_unknown_fixed_reject_without_substitution(self):
        world = await self._world("w1")
        _, members = await self._relief_pack(
            "w1", "world.w1.relief", "dome", context="mountain",
        )
        bodies = await load_relief_templates_for_world(self.loader, world)

        # No candidates for a different context — no fallback to another template.
        with self.assertRaises(UnresolvedModelError) as empty:
            pick_template(
                context=ReliefContext.RAVINE, templates=bodies,
                world_policy=WorldReliefPickPolicy(),
                world_seed="seed", site_id="rv1",
            )
        self.assertEqual(empty.exception.issues[0].code, "DOMAIN_NO_CANDIDATE")

        # Fixed uid outside membership never resolves to an unrelated member.
        with self.assertRaises(UnresolvedModelError) as unknown:
            pick_template(
                context="mountain", templates=bodies,
                world_policy=self._policy(ReliefPickMode.FIXED, str(uuid4())),
                world_seed="seed", site_id="m1",
            )
        self.assertEqual(unknown.exception.issues[0].code, "REF_W_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
