"""Library packs — plan library-packs-model-done.md step 5a-1.

``EffectiveCatalog``: membership-scoped runtime read facade (TZ §1/§1.1):
world-owned packs ∪ declared defaults, isolation from other worlds and
engine user packs, deterministic candidate order, lazy body reads, pins
never narrowing the catalog.

Real SQLite, migrated schema — same fixture style as test_library_packs_4a.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from app.application.jsonValidation import resolve as resolve_module
from app.application.templateLibrary.packs.domainAdapters.factory import (
    build_pack_domain_adapters,
)
from app.application.templateLibrary.packs.effectiveCatalog import (
    EffectiveCatalog,
    EffectiveCatalogLoader,
)
from app.application.templateLibrary.packs.errors import LibraryPackValidationError
from app.application.templateLibrary.packs.membership import membership_pack_uids
from app.application.templateLibrary.packs.packCatalog import PackCatalogRepos
from app.application.templateLibrary.packs.refResolve import (
    RefOutcome,
    RefRejected,
    RefResolver,
    TemplateRef,
)
from app.application.templateLibrary.packs.uidMap import pin_for_member
from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.types import ReferenceIssueReason
from app.core.container import Container
from app.db.database import Database
from app.db.models.world import World
from app.db.repositories.sqlite.reliefTemplateRepository import (
    SqliteReliefTemplateRepository,
)
from app.db.repositories.sqlite.worldRepository import SqliteWorldRepository
from app.ids import LibraryKind, library_uid
from app.application.templateLibrary.packs.defaults import default_pack_uids

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STRUCTURES_ROOT = _REPO_ROOT / "structures_templates"
_BASE_PACK_UID = library_uid(LibraryKind.LIBRARY_PACKS, "engine.structures.base")

_STRUCT = LibraryKind.STRUCTURE_TEMPLATES
_RELIEF = LibraryKind.RELIEF_TEMPLATES


def _relief_body(local_uid: str) -> dict:
    return {
        "system_name": local_uid,
        "display_name": local_uid.title(),
        "context": "open_land",
    }


class _CatalogCase(IsolatedAsyncioTestCase):

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
        self.repos = PackCatalogRepos(
            packs=self.packs,
            members=self.members,
            deps=self.container.library_pack_dependency_repository(),
        )
        self.loader = EffectiveCatalogLoader(self.repos, self.adapters)
        self.resolver = RefResolver(self.repos, self.adapters)

    async def _world(self, world_uid: str) -> World:
        world = World(world_uid=world_uid, name=world_uid, created_at="2026-10-11")
        await self.worlds.create(world)
        return world

    async def _world_pack(self, world_uid: str, system_name: str, *local_uids: str):
        pack = await self.service.create_pack(
            system_name=system_name, owner_world_uid=world_uid
        )
        members = []
        for local_uid in local_uids:
            members.append(await self.service.create_member(
                pack.pack_uid, library_kind=_RELIEF, local_uid=local_uid,
                body=_relief_body(local_uid), world_uid=world_uid,
            ))
        return pack, members

    async def _import_base(self):
        return await self.service.import_fs_pack(
            _STRUCT, _STRUCTURES_ROOT / "base", domain_root=_STRUCTURES_ROOT
        )


class MembershipTests(_CatalogCase):

    async def test_world_membership_is_owned_plus_defaults(self):
        await self._world("w1")
        await self._world("w2")
        own, own_members = await self._world_pack("w1", "world.w1.relief", "meadow", "bog")
        other, other_members = await self._world_pack("w2", "world.w2.relief", "ridge")
        engine = await self.service.create_pack(system_name="user.relief.extra")
        engine_member = await self.service.create_member(
            engine.pack_uid, library_kind=_RELIEF, local_uid="dune",
            body=_relief_body("dune"),
        )
        base = (await self._import_base()).pack

        catalog = await self.loader.load("w1")
        self.assertIsInstance(catalog, EffectiveCatalog)
        self.assertEqual(catalog.world_uid, "w1")
        self.assertEqual(catalog.pack_uids, tuple(sorted({own.pack_uid} | default_pack_uids())))
        self.assertEqual(base.pack_uid, _BASE_PACK_UID)

        for m in own_members:
            self.assertTrue(catalog.available(m.template_uid, _RELIEF))
            self.assertIs(catalog.member(m.template_uid), catalog.member(m.template_uid))
        # Other world's pack and the engine user pack are not in membership.
        for m in other_members + [engine_member]:
            self.assertFalse(catalog.available(m.template_uid, _RELIEF))
            self.assertIsNone(catalog.member(m.template_uid))
        # Default pack members are available to every world.
        base_members = await self.members.list_by_pack(base.pack_uid)
        self.assertTrue(base_members)
        for m in base_members:
            self.assertTrue(catalog.available(m.template_uid, _STRUCT))
        # Kind mismatch is not availability.
        self.assertFalse(catalog.available(base_members[0].template_uid, _RELIEF))

        # The other world sees only its own pack + defaults.
        other_catalog = await self.loader.load("w2")
        self.assertEqual(other_catalog.pack_uids, tuple(sorted({other.pack_uid} | default_pack_uids())))
        self.assertFalse(other_catalog.available(own_members[0].template_uid, _RELIEF))

    async def test_membership_helper_matches_loader_and_engine_scope(self):
        await self._world("w1")
        own, _ = await self._world_pack("w1", "world.w1.relief", "meadow")
        engine = await self.service.create_pack(system_name="user.relief.extra")
        base = (await self._import_base()).pack

        self.assertEqual(
            await membership_pack_uids(self.packs, "w1"),
            sorted({own.pack_uid} | default_pack_uids()),
        )
        self.assertEqual(
            await membership_pack_uids(self.packs, None),
            sorted({engine.pack_uid} | default_pack_uids()),
        )

    async def test_loader_requires_world_uid(self):
        with self.assertRaises(LibraryPackValidationError):
            await self.loader.load("")


class CandidateTests(_CatalogCase):

    async def test_candidates_sorted_by_template_uid_regardless_of_insert_order(self):
        await self._world("w1")
        # Two world packs created in "reverse" order with interleaved members.
        _, late = await self._world_pack("w1", "world.w1.zeta", "ridge", "bog")
        _, early = await self._world_pack("w1", "world.w1.alpha", "meadow")
        base = (await self._import_base()).pack

        catalog = await self.loader.load("w1")
        relief = catalog.candidates(_RELIEF)
        self.assertEqual(
            [m.template_uid for m in relief],
            sorted(m.template_uid for m in late + early),
        )
        self.assertTrue(all(m.library_kind == _RELIEF.value for m in relief))
        structures = catalog.candidates(_STRUCT)
        self.assertEqual(
            [m.template_uid for m in structures],
            sorted(m.template_uid for m in await self.members.list_by_pack(base.pack_uid)),
        )
        self.assertEqual(catalog.candidates(LibraryKind.BUILDING_TEMPLATES), ())

    async def test_pins_do_not_narrow_catalog(self):
        await self._world("w1")
        _, members = await self._world_pack("w1", "world.w1.relief", "meadow", "bog")
        pinned = members[0]
        await self.container.world_service().update(
            "w1", {"library_pins": [
                pin_for_member(_RELIEF, pinned.template_uid).model_dump(mode="json")
            ]}
        )
        catalog = await self.loader.load("w1")
        self.assertEqual(
            {m.template_uid for m in catalog.candidates(_RELIEF)},
            {m.template_uid for m in members},
        )


class BodyTests(_CatalogCase):

    async def test_body_is_lazy_and_cached_per_catalog(self):
        await self._world("w1")
        _, (meadow, bog) = await self._world_pack("w1", "world.w1.relief", "meadow", "bog")
        catalog = await self.loader.load("w1")

        body = await catalog.body(meadow.template_uid)
        self.assertEqual(body["system_name"], "meadow")
        # Lazy: a body row removed after load is not seen for an unread uid …
        await self.relief_rows.delete(bog.template_uid)
        self.assertIsNone(await catalog.body(bog.template_uid))
        self.assertIsNotNone(catalog.member(bog.template_uid))  # still a member
        # … while an already-read body stays cached on this catalog object.
        await self.relief_rows.delete(meadow.template_uid)
        self.assertEqual((await catalog.body(meadow.template_uid))["system_name"], "meadow")
        # A fresh catalog (another call) does not inherit the cache.
        fresh = await self.loader.load("w1")
        self.assertIsNone(await fresh.body(meadow.template_uid))

    async def test_body_outside_membership_is_none(self):
        await self._world("w1")
        await self._world("w2")
        _, (ridge,) = await self._world_pack("w2", "world.w2.relief", "ridge")
        catalog = await self.loader.load("w1")
        self.assertIsNone(await catalog.body(ridge.template_uid))
        self.assertIsNone(await catalog.body("no-such-uid"))


_RESOLVE_LOGGER = resolve_module.__name__


class ResolveTests(_CatalogCase):
    """Step 5a-2: three input states × three outcomes, one warning per event."""

    async def _resolve(self, catalog, kind, ref, *, warnings: int):
        """Run one resolve asserting exactly *warnings* records hit the sink."""
        ctx = ResolveContext()
        if warnings == 0:
            with self.assertNoLogs(_RESOLVE_LOGGER, level="WARNING"):
                result = await self.resolver.resolve(
                    catalog, kind, ref, consumer="test", path="ref", ctx=ctx)
            self.assertEqual(ctx.report.issues, [])
            return result, None
        with self.assertLogs(_RESOLVE_LOGGER, level="WARNING") as cm:
            try:
                result = await self.resolver.resolve(
                    catalog, kind, ref, consumer="test", path="ref", ctx=ctx)
            except RefRejected as exc:
                result = exc.result
        self.assertEqual(len(cm.records), warnings)
        self.assertEqual(len(ctx.report.issues), warnings)
        return result, ctx.report.issues[0].reference

    async def test_uid_resolves_to_member_and_body(self):
        await self._world("w1")
        _, (meadow,) = await self._world_pack("w1", "world.w1.relief", "meadow")
        catalog = await self.loader.load("w1")
        result, _ = await self._resolve(
            catalog, _RELIEF, TemplateRef.of(meadow.template_uid), warnings=0)
        self.assertIs(result.outcome, RefOutcome.RESOLVED)
        self.assertTrue(result.resolved)
        self.assertEqual(result.member.template_uid, meadow.template_uid)
        self.assertEqual(result.body["system_name"], "meadow")

    async def test_relief_unknown_uid_is_rejected_with_one_warning(self):
        await self._world("w1")
        catalog = await self.loader.load("w1")
        result, ref = await self._resolve(
            catalog, _RELIEF, TemplateRef.of("no-such-uid"), warnings=1)
        self.assertIs(result.outcome, RefOutcome.REJECTED)
        self.assertIs(ref.reason, ReferenceIssueReason.UNKNOWN_TEMPLATE)
        self.assertEqual(ref.world_uid, "w1")
        self.assertEqual(ref.requested_template_uid, "no-such-uid")
        self.assertEqual(ref.domain, _RELIEF.value)
        self.assertEqual(ref.consumer, "test")
        self.assertIsNone(ref.selected_default)
        self.assertEqual(result.issue.path, ("test", "ref"))

    async def test_other_world_member_is_owner_unavailable(self):
        await self._world("w1")
        await self._world("w2")
        other, (ridge,) = await self._world_pack("w2", "world.w2.relief", "ridge")
        catalog = await self.loader.load("w1")
        result, ref = await self._resolve(
            catalog, _RELIEF, TemplateRef.of(ridge.template_uid), warnings=1)
        self.assertIs(result.outcome, RefOutcome.REJECTED)
        self.assertIs(ref.reason, ReferenceIssueReason.OWNER_UNAVAILABLE)
        self.assertEqual(ref.owner_pack_uid, other.pack_uid)
        # The ref itself is untouched — the result carries the requested uid.
        self.assertEqual(result.ref.uid, ridge.template_uid)

    async def test_kind_mismatch(self):
        await self._world("w1")
        own, (meadow,) = await self._world_pack("w1", "world.w1.relief", "meadow")
        catalog = await self.loader.load("w1")
        result, ref = await self._resolve(
            catalog, _STRUCT, TemplateRef.of(meadow.template_uid), warnings=1)
        self.assertIs(result.outcome, RefOutcome.REJECTED)
        self.assertIs(ref.reason, ReferenceIssueReason.KIND_MISMATCH)
        self.assertEqual(ref.owner_pack_uid, own.pack_uid)

    async def test_building_unknown_uid_is_not_replaced_with_builtin_plots(self):
        await self._world("w1")
        catalog = await self.loader.load("w1")
        result, ref = await self._resolve(
            catalog, LibraryKind.BUILDING_TEMPLATES, TemplateRef.of("ghost"), warnings=1)
        self.assertIs(result.outcome, RefOutcome.REJECTED)
        self.assertIs(ref.reason, ReferenceIssueReason.UNKNOWN_TEMPLATE)
        self.assertIsNone(ref.selected_default)
        self.assertIsNone(result.default)
        self.assertEqual(result.ref.uid, "ghost")  # stored ref not rewritten

    async def test_building_explicit_default_marker_requires_declared_fallback(self):
        await self._world("w1")
        catalog = await self.loader.load("w1")
        result, _ = await self._resolve(
            catalog, LibraryKind.BUILDING_TEMPLATES, TemplateRef.default(), warnings=1)
        self.assertIs(result.outcome, RefOutcome.REJECTED)
        self.assertIsNone(result.default)

    async def test_building_empty_ref_warns_and_rejects(self):
        await self._world("w1")
        catalog = await self.loader.load("w1")
        result, ref = await self._resolve(
            catalog, LibraryKind.BUILDING_TEMPLATES, TemplateRef.of("  "), warnings=1)
        self.assertIs(result.outcome, RefOutcome.REJECTED)
        self.assertIs(ref.reason, ReferenceIssueReason.DEFAULT_APPLIED)
        self.assertIsNone(ref.requested_template_uid)

    async def test_relief_explicit_default_marker_is_rejected(self):
        await self._world("w1")
        catalog = await self.loader.load("w1")
        result, ref = await self._resolve(
            catalog, _RELIEF, TemplateRef.default(), warnings=1)
        self.assertIs(result.outcome, RefOutcome.REJECTED)
        self.assertIs(ref.reason, ReferenceIssueReason.DEFAULT_APPLIED)

    async def test_member_without_body(self):
        await self._world("w1")
        own, (meadow,) = await self._world_pack("w1", "world.w1.relief", "meadow")
        await self.relief_rows.delete(meadow.template_uid)
        catalog = await self.loader.load("w1")
        result, ref = await self._resolve(
            catalog, _RELIEF, TemplateRef.of(meadow.template_uid), warnings=1)
        self.assertIs(result.outcome, RefOutcome.REJECTED)
        self.assertIs(ref.reason, ReferenceIssueReason.BODY_MISSING)
        self.assertEqual(ref.owner_pack_uid, own.pack_uid)

    async def test_missing_dependency_and_cycle(self):
        await self._world("w1")
        a, (meadow,) = await self._world_pack("w1", "world.w1.a", "meadow")
        b, (bog,) = await self._world_pack("w1", "world.w1.b", "bog")
        # Cycle inside membership: a → b → a — must terminate and resolve.
        await self.service.set_dependencies(a.pack_uid, [b.pack_uid], world_uid="w1")
        await self.service.set_dependencies(b.pack_uid, [a.pack_uid], world_uid="w1")
        catalog = await self.loader.load("w1")
        result, _ = await self._resolve(
            catalog, _RELIEF, TemplateRef.of(meadow.template_uid), warnings=0)
        self.assertIs(result.outcome, RefOutcome.RESOLVED)

        # Transitive dependency on an engine user pack (not in membership).
        engine = await self.service.create_pack(system_name="user.relief.extra")
        await self.service.set_dependencies(
            b.pack_uid, [a.pack_uid, engine.pack_uid], world_uid="w1")
        catalog = await self.loader.load("w1")
        result, ref = await self._resolve(
            catalog, _RELIEF, TemplateRef.of(meadow.template_uid), warnings=1)
        self.assertIs(result.outcome, RefOutcome.REJECTED)
        self.assertIs(ref.reason, ReferenceIssueReason.MISSING_DEPENDENCY)
        self.assertEqual(ref.owner_pack_uid, a.pack_uid)
        self.assertEqual(ref.dependency_pack_uid, engine.pack_uid)
        # No instance was created by the check.
        self.assertEqual(
            {p.pack_uid for p in await self.packs.list_world_owned("w1")},
            {a.pack_uid, b.pack_uid},
        )

    async def test_resolver_requires_dependency_repository(self):
        with self.assertRaises(LibraryPackValidationError):
            RefResolver(PackCatalogRepos(packs=self.packs, members=self.members), self.adapters)


class ContainerWiringTests(_CatalogCase):
    """Step 5a-3: container seams + generation transcript carries the record."""

    async def test_container_seams_are_cached_and_share_adapters(self):
        loader = self.container.effective_catalog_loader()
        resolver = self.container.ref_resolver()
        self.assertIs(loader, self.container.effective_catalog_loader())
        self.assertIs(resolver, self.container.ref_resolver())
        self.assertIs(self.container.pack_domain_adapters(), self.container.pack_domain_adapters())
        self.assertIsNotNone(self.container.pack_catalog_repos().deps)

    async def test_end_to_end_isolation_and_transcript_record(self):
        from app.core.generationLogging import generation_world_log

        await self._world("w1")
        await self._world("w2")
        _, (meadow,) = await self._world_pack("w1", "world.w1.relief", "meadow")
        other, (ridge,) = await self._world_pack("w2", "world.w2.relief", "ridge")
        await self._import_base()
        loader = self.container.effective_catalog_loader()
        resolver = self.container.ref_resolver()

        root = Path(self.tmp.name) / "gen"
        with generation_world_log("w1", mode="light", root=root) as log_path:
            catalog = await loader.load("w1")
            ok = await resolver.resolve(
                catalog, _RELIEF, TemplateRef.of(meadow.template_uid),
                consumer="generator", path="relief_ref")
            self.assertIs(ok.outcome, RefOutcome.RESOLVED)
            with self.assertRaises(RefRejected) as cm:
                await resolver.resolve(
                    catalog, _RELIEF, TemplateRef.of(ridge.template_uid),
                    consumer="generator", path="relief_ref")

        self.assertIs(cm.exception.result.outcome, RefOutcome.REJECTED)
        lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        records = [r for r in lines if r.get("code") == "LIBRARY_REFERENCE"
                   or "LIBRARY_REFERENCE" in r.get("msg", "")]
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["level"], "WARNING")
        self.assertEqual(rec["reason"], str(ReferenceIssueReason.OWNER_UNAVAILABLE))
        self.assertEqual(rec["world_uid"], "w1")
        self.assertEqual(rec["requested_template_uid"], ridge.template_uid)
        self.assertEqual(rec["owner_pack_uid"], other.pack_uid)
        self.assertEqual(rec["domain"], _RELIEF.value)
        self.assertEqual(rec["consumer"], "generator")


if __name__ == "__main__":
    unittest.main()
