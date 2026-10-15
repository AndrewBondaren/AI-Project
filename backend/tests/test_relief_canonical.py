"""Step 7: empty canonical relief source, public reads and world isolation."""

import asyncio
import os
import shutil
from contextlib import chdir
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from test_library_packs_4b import _ServiceCase
from app.application.canonicalLibrary import CanonicalSourceError, ensure_canonical
from app.application.jsonValidation.resolve import UnresolvedModelError
from app.application.worldData.generators.terrain.relief.pick.templatePick import pick_template
from app.application.worldData.libraryPacks.defaults import default_pack_names, is_default_pack_uid
from app.application.worldData.libraryPacks.reliefCanonicalSpec import RELIEF_CANONICAL_SPEC
from app.application.worldData.loadReliefTemplatesForWorld import load_relief_templates_for_world
from app.application.worldData.reliefErrors import ReliefNotFoundError
from app.application.worldData.reliefTemplateLibraryService import resolve_relief_domain_root
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy, WorldReliefPickPolicy
from app.ids import LibraryKind, runtime_uid

R = LibraryKind.RELIEF_TEMPLATES
REPO_ROOT = Path(__file__).resolve().parents[2]
RELIEF_ROOT = REPO_ROOT / "relief_templates"


class ReliefCanonicalTests(_ServiceCase):
    async def test_all_public_reads_attach_empty_spec_without_discovering_fs(self):
        root = Path(self.tmp.name) / "relief"
        (root / "smoke_003").mkdir(parents=True)
        (root / "smoke_003/pack.manifest.json").write_text("{broken", encoding="utf-8")
        library = self.container.relief_template_library_service()
        uid = runtime_uid()
        with patch.dict(os.environ, {"RELIEF_TEMPLATES_ROOT": str(root)}), patch(
            "app.application.worldData.reliefTemplateLibraryService.ensure_canonical",
            wraps=ensure_canonical,
        ) as attach:
            self.assertEqual(await library.list_all(), [])
            self.assertIsNone(await library.find_by_uid(uid))
            with self.assertRaises(ReliefNotFoundError):
                await library.get_by_uid(uid)
            self.assertEqual(attach.await_count, 3)
            for call in attach.await_args_list:
                self.assertIs(call.args[0], RELIEF_CANONICAL_SPEC)
        self.assertEqual(default_pack_names(R), ())
        self.assertEqual(await self.packs.list_all(), [])
        self.assertEqual(await self.members.list_by_packs([]), [])
        self.assertEqual(await self.relief_rows.list_all(), [])

    async def test_partial_sql_and_override_survive_repeated_concurrent_reads(self):
        imported = await self.service.import_fs_pack(R, RELIEF_ROOT / "smoke_003", domain_root=RELIEF_ROOT)
        row = imported.bodies[0]
        changed = replace(row, display_name="User override", source_file="user/edited.json",
                          data={**row.data, "display_name": "User override"})
        await self.relief_rows.upsert(changed)
        await self.relief_rows.delete(imported.bodies[1].template_uid)
        before = await self.relief_rows.list_all()
        library = self.container.relief_template_library_service()
        for _ in range(2):
            results = await asyncio.gather(library.list_all(), library.find_by_uid(row.template_uid),
                                           library.get_by_uid(row.template_uid))
            self.assertEqual(results, [before, changed, changed])
        self.assertEqual(await self.relief_rows.list_all(), before)
        self.assertIsNone(await library.find_by_uid(imported.bodies[1].template_uid))
        self.assertFalse(is_default_pack_uid(imported.pack.pack_uid))

    async def test_root_and_explicit_import_are_independent_of_cwd(self):
        with patch.dict(os.environ, {"RELIEF_TEMPLATES_ROOT": ""}):
            for cwd in (REPO_ROOT, REPO_ROOT / "backend"):
                with self.subTest(cwd=cwd), chdir(cwd):
                    self.assertEqual(resolve_relief_domain_root(), RELIEF_ROOT)
        root = Path(self.tmp.name) / "external_relief"
        shutil.copytree(RELIEF_ROOT / "smoke_003", root / "smoke_003")
        library = self.container.relief_template_library_service()
        with patch.dict(os.environ, {"RELIEF_TEMPLATES_ROOT": str(root)}), chdir(REPO_ROOT / "backend"):
            self.assertEqual(resolve_relief_domain_root(), root.resolve())
            rows = await library.import_path("smoke_003")
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row.source_file.startswith("relief_templates/smoke_003/") for row in rows))

    async def test_user_pack_resolves_only_after_instantiation_in_each_world(self):
        a, b = await self._world("a"), await self._world("b")
        imported = await self.service.import_fs_pack(R, RELIEF_ROOT / "smoke_003", domain_root=RELIEF_ROOT)
        loader = self.container.template_snapshot_loader()
        self.assertEqual(await load_relief_templates_for_world(loader, a), {})
        self.assertEqual(await load_relief_templates_for_world(loader, b), {})
        instance = await self.service.instantiate_pack(imported.pack.pack_uid, world_uid="a")
        a_bodies = await load_relief_templates_for_world(loader, a)
        self.assertEqual(set(a_bodies), {m.template_uid for m in instance.members})
        self.assertEqual(await load_relief_templates_for_world(loader, b), {})
        target_uid = next(uid for uid, body in a_bodies.items() if body.context.value == "open_land")
        policy = WorldReliefPickPolicy(open_land=ReliefContextPickPolicy(
            mode="fixed", default_template_uid=target_uid))
        before = policy.model_dump(mode="json")
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as logs, \
                self.assertRaises(UnresolvedModelError) as rejected:
            pick_template(context="open_land", templates={}, world_policy=policy,
                          world_seed="seed", site_id="b")
        self.assertEqual(rejected.exception.issues[0].code, "DOMAIN_NO_CANDIDATE")
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(policy.model_dump(mode="json"), before)
        picked = pick_template(context="open_land", templates=a_bodies, world_policy=policy,
                               world_seed="seed", site_id="a")
        self.assertEqual(picked.template_uid, target_uid)
        second = await self.service.instantiate_pack(imported.pack.pack_uid, world_uid="b")
        self.assertEqual(set(await load_relief_templates_for_world(loader, b)),
                         {m.template_uid for m in second.members})
        self.assertTrue(set(a_bodies).isdisjoint(m.template_uid for m in second.members))
        # Body reads after membership resolution are allowed; a global list
        # or administrative get must never supply generation candidates.
        library = self.container.relief_template_library_service()
        with patch.object(library, "list_all", side_effect=AssertionError("global list bypass")), \
                patch.object(library, "get_by_uid", side_effect=AssertionError("global get bypass")):
            b_bodies = await load_relief_templates_for_world(loader, b)
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as logs, \
                self.assertRaises(UnresolvedModelError) as rejected:
            pick_template(context="open_land", templates=b_bodies, world_policy=policy,
                          world_seed="seed", site_id="b")
        self.assertEqual(rejected.exception.issues[0].code, "REF_W_UNKNOWN")
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(policy.model_dump(mode="json"), before)

    async def test_empty_attach_does_not_commit_caller_transaction(self):
        with self.assertRaisesRegex(ValueError, "rollback"):
            async with self.db.transaction():
                await self._world("rolled-back")
                await self.container.relief_template_library_service().list_all()
                raise ValueError("rollback")
        self.assertIsNone(await self.worlds.get_by_id("rolled-back"))

    async def test_changed_default_declaration_requires_a_real_source(self):
        with patch("app.application.worldData.libraryPacks.reliefCanonicalSpec.default_pack_names",
                   return_value=("unexpected",)):
            with self.assertRaises(CanonicalSourceError):
                await self.container.relief_template_library_service().list_all()
        self.assertEqual(await self.packs.list_all(), [])
