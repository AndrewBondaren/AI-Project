"""A5: typed canonical source, graph-wide atomic fill and public read triggers."""
import asyncio
import json
import shutil
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from test_library_packs_4b import _ServiceCase
from app.application.canonicalLibrary import CanonicalContractError, CanonicalSourceError
from app.application.worldData.libraryPacks.defaults import default_pack_uids
from app.application.worldData.libraryPacks.templateCanonicalPersistence import TemplateCanonicalPersistence
from app.application.worldData.libraryPacks.templateCanonicalService import TemplateCanonicalService
from app.application.worldData.libraryPacks.templateCanonicalSource import SOURCE_ROOT, load_canonical_template_graph
from app.application.worldData.libraryPacks.templateGraphValidation import template_graph_issues
from app.application.worldData.libraryPacks.lifecycleContracts import CatalogSnapshot
from app.dataModel.locations.structure.building.worldBuildingLayoutDefaults import CANONICAL_PLOT_NAMES
from app.ids import LibraryKind, runtime_uid
from app.application.worldData.libraryPacks.refResolve import TemplateRef
from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.libraryPacks.errors import LibraryPackReadOnlyError

S, B, P = LibraryKind.STRUCTURE_TEMPLATES, LibraryKind.BUILDING_TEMPLATES, LibraryKind.PLOT_TEMPLATES


class TemplateDomainCanonicalTests(_ServiceCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.graph = load_canonical_template_graph()
        self.records = {e.uid: e.body for pack in self.graph for e in pack.entries}
        self.canonical = TemplateCanonicalService(db=self.db, catalog=self.container.pack_catalog_repos())

    def first(self, kind):
        return next(pack for pack in self.graph if pack.kind == kind).entries[0].body

    def repo(self, kind):
        return {S: self.structure_rows, B: self.building_rows,
                P: self.container.plot_template_repository()}[kind]

    async def assert_complete(self):
        packs = await self.packs.list_all()
        self.assertTrue(default_pack_uids().issubset({p.pack_uid for p in packs}))
        members = await self.members.list_by_packs(sorted(default_pack_uids()))
        bodies = {}
        for member in members:
            bodies[member.template_uid] = (await self.repo(LibraryKind(member.library_kind)).get_by_uid(
                member.template_uid)).data
        self.assertEqual({m.template_uid for m in members}, set(self.records))
        self.assertFalse(template_graph_issues(CatalogSnapshot(
            {m.template_uid: m for m in members}, bodies, {})))

    async def test_fresh_public_catalog_load_attaches_whole_scoped_graph_by_uid(self):
        await self._world("w1")
        catalog = await self.container.effective_catalog_loader().load("w1")
        self.assertEqual(set(catalog.pack_uids), default_pack_uids())
        self.assertEqual(len(catalog.candidates(S)), 13)
        self.assertEqual(len(catalog.candidates(B)), len(CANONICAL_PLOT_NAMES))
        self.assertEqual(len(catalog.candidates(P)), len(CANONICAL_PLOT_NAMES))
        for kind in (B, P):
            member = catalog.candidates(kind)[0]
            body = await catalog.body(member.template_uid)
            ref = body["structure"] if kind == B else body["main_building"]["structure"]
            self.assertTrue(catalog.available(ref, S))
            self.assertIsNotNone(await catalog.body(ref))
            resolved = await self.container.ref_resolver().resolve(catalog, kind,
                TemplateRef.of(member.template_uid), consumer="test", path="template", ctx=ResolveContext())
            self.assertTrue(resolved.resolved)
        self.assertFalse((await self.worlds.get_by_id("w1")).building_template_registry)
        await self.assert_complete()

    async def test_public_domain_reads_attach_but_internal_find_does_not(self):
        for kind in (P, B, S):
            service = {P: self.container.plot_template_library_service(),
                       B: self.container.building_template_library_service(),
                       S: self.container.structure_template_library_service()}[kind]
            uid = self.first(kind).member.template_uid
            self.assertIsNone(await service.find_by_uid(uid))
        self.assertFalse(await self.packs.list_all())
        for kind in (P, B, S):
            service = {P: self.container.plot_template_library_service(),
                       B: self.container.building_template_library_service(),
                       S: self.container.structure_template_library_service()}[kind]
            uid = self.first(kind).member.template_uid
            self.assertIsNotNone(await service.get_by_uid(uid))
            self.assertTrue(await service.list_all())
        await self.assert_complete()

    async def test_partial_existing_body_and_source_are_not_replaced(self):
        for kind in (P, B, S):
            original = self.first(kind).row
            changed = replace(original, display_name="Edited", source_file="user/original.json",
                              data={**original.data, "display_name": "Edited"})
            await self.repo(kind).insert(changed)
        await self.canonical.ensure()
        for kind in (P, B, S):
            row = await self.repo(kind).get_by_uid(self.first(kind).row.template_uid)
            self.assertEqual(row.display_name, "Edited")
            self.assertEqual(row.data["display_name"], "Edited")
            self.assertEqual(row.source_file, "user/original.json")
        await self.assert_complete()

    async def test_repeat_and_deleted_body_membership_dependency_are_restored(self):
        await self.canonical.ensure()
        repeated = await self.canonical.ensure()
        self.assertTrue(all(not r.added for r in repeated.values()))
        for kind in (P, B, S):
            record = self.first(kind)
            await self.repo(kind).delete(record.row.template_uid)
            await self.members.delete(record.member.template_uid)
        plot_pack = next(pack for pack in self.graph if pack.kind == P)
        await self.deps.delete_for_pack(plot_pack.manifest.pack_uid)
        await self.canonical.ensure()
        await self.assert_complete()
        self.assertEqual(await self.deps.required_uids(plot_pack.manifest.pack_uid),
                         set(plot_pack.manifest.dependencies))

    async def test_missing_membership_only_is_restored_without_rewriting_body(self):
        await self.canonical.ensure()
        record = self.first(P)
        before = await self.repo(P).get_by_uid(record.member.template_uid)
        await self.members.delete(record.member.template_uid)
        result = await self.canonical.ensure()
        self.assertIn(record.member.template_uid, result[P].added)
        self.assertEqual(await self.repo(P).get_by_uid(record.member.template_uid), before)
        await self.assert_complete()

    async def test_concurrent_attach_is_unique_and_complete(self):
        results = await asyncio.gather(*(self.canonical.ensure() for _ in range(3)))
        self.assertEqual(sum(len(result.added) for r in results for result in r.values()), len(self.records))
        await self.assert_complete()

    async def test_outer_uow_rollback_does_not_cache_completeness(self):
        with self.assertRaisesRegex(ValueError, "outer failed"):
            async with self.db.transaction():
                await self.canonical.ensure()
                raise ValueError("outer failed")
        self.assertFalse(await self.packs.list_all())
        self.assertFalse(await self.repo(P).list_all())
        await self.canonical.ensure()
        await self.assert_complete()

    async def test_later_domain_failure_rolls_back_earlier_domains_and_catalog(self):
        original = TemplateCanonicalPersistence.insert_missing
        async def fail_plot(adapter, snapshot, context):
            if context.pack.kind == P:
                raise ValueError("plot failed")
            return await original(adapter, snapshot, context)
        with patch.object(TemplateCanonicalPersistence, "insert_missing", fail_plot):
            with self.assertRaisesRegex(ValueError, "plot failed"):
                await self.canonical.ensure()
        self.assertFalse(await self.packs.list_all())
        for kind in (S, B, P):
            self.assertFalse(await self.repo(kind).list_all())
        await self.canonical.ensure()
        await self.assert_complete()

    async def test_conflicting_canonical_membership_is_rejected_without_reassignment(self):
        await self.canonical.ensure()
        record = self.first(P)
        foreign = await self.service.create_pack(system_name="user.foreign")
        await self.members.delete(record.member.template_uid)
        wrong = replace(record.member, pack_uid=foreign.pack_uid)
        await self.members.insert(wrong)
        with self.assertRaises(CanonicalContractError):
            await self.canonical.ensure()
        self.assertEqual(await self.members.get_by_uid(wrong.template_uid), wrong)

    async def test_canonical_attach_does_not_discover_user_files_or_packs(self):
        root = Path(self.tmp.name) / "sources"
        shutil.copytree(SOURCE_ROOT / "fixtures/templates", root / "fixtures/templates")
        shutil.copytree(SOURCE_ROOT / "structures_templates/base", root / "structures_templates/base")
        (root / "structures_templates/user").mkdir()
        (root / "structures_templates/user/pack.manifest.json").write_text("{broken")
        (root / "fixtures/templates/not_declared.json").write_text("{broken")
        service = TemplateCanonicalService(db=self.db, catalog=self.container.pack_catalog_repos(), source_root=root)
        await service.ensure()
        self.assertEqual({p.pack_uid for p in await self.packs.list_all()}, default_pack_uids())

    async def test_invalid_source_graph_is_rejected_before_any_sql_write(self):
        root = Path(self.tmp.name) / "sources"
        shutil.copytree(SOURCE_ROOT / "fixtures/templates", root / "fixtures/templates")
        shutil.copytree(SOURCE_ROOT / "structures_templates/base", root / "structures_templates/base")
        path = root / "fixtures/templates/mill.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["main_building"]["structure"] = runtime_uid()
        path.write_text(json.dumps(raw), encoding="utf-8")
        service = TemplateCanonicalService(db=self.db, catalog=self.container.pack_catalog_repos(), source_root=root)
        with self.assertRaises(CanonicalSourceError):
            await service.ensure()
        self.assertFalse(await self.packs.list_all())

    async def test_default_members_are_readonly_and_same_name_user_copies_require_instance(self):
        await self.canonical.ensure()
        await self._world("w1")
        user_pack = await self.service.create_pack(system_name="user.templates.base")
        copies = []
        for kind in (P, B):
            member = self.first(kind).member
            with self.assertRaises(LibraryPackReadOnlyError):
                await self.service.delete_member(member.template_uid)
            copied = await self.service.copy_member(member.template_uid, user_pack.pack_uid)
            self.assertEqual(copied.member.local_uid, member.local_uid)
            copies.append(copied.member)
        catalog = await self.container.effective_catalog_loader().load("w1")
        for member in copies:
            self.assertIsNone(catalog.member(member.template_uid))
        instance = await self.service.instantiate_pack(user_pack.pack_uid, world_uid="w1")
        catalog = await self.container.effective_catalog_loader().load("w1")
        for member in instance.members:
            self.assertTrue(catalog.available(member.template_uid, LibraryKind(member.library_kind)))
