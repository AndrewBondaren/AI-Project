"""Library packs — plan library-packs-model.md step B-3.

Covers the step-3 contracts: typed ``pack.manifest.json`` loading and
validation (TZ §4, template-pack-layout), manifest-aware FS importers
(manifest never parsed as a body, lone root files rejected), the explicit
old→new uid map, declared default sources (no wildcard scans), and routing
of manifest-less bundle bodies into the world-owned ``legacy`` pack.

Real SQLite for catalog writes — same pattern as test_library_packs_schema.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from app.application.worldData.buildingTemplateLibraryService import (
    BuildingTemplateLibraryService,
)
from app.ids import LibraryKind, library_uid
from app.application.worldData.libraryPacks.defaults import default_pack_names
from app.application.worldData.libraryPacks.legacyPack import (
    LEGACY_PACK_NAME,
    ensure_legacy_pack,
    legacy_member_row,
    legacy_member_uid,
    legacy_pack_uid,
)
from app.application.worldData.libraryPacks.manifest import (
    PACK_MANIFEST_FILENAME,
    PackManifestError,
    load_pack_manifest,
)
from app.application.worldData.libraryPacks.uidMap import (
    RELIEF_SMOKE_003_FORMER_UIDS,
    STRUCTURE_MEMBER_RENAMES,
    base_member_uid,
    former_template_uid,
    mapped_template_uid,
    pin_for_member,
    smoke_003_member_uid,
)
from app.application.worldData.reliefErrors import ReliefValidationError
from app.application.worldData.reliefTemplateFsImport import import_relief_path
from app.application.worldData.structureTemplateErrors import (
    StructureTemplateValidationError,
)
from app.application.worldData.structureTemplateFsImport import (
    import_structure_templates_path,
    load_structure_stdlib,
)
from app.core.container import Container
from app.dataModel.libraryPacks.packManifest import LibraryPackManifest
from app.db.database import Database
from app.db.models.world import World
from app.db.repositories.sqlite.libraryPackMemberRepository import (
    SqliteLibraryPackMemberRepository,
)
from app.db.repositories.sqlite.libraryPackRepository import (
    SqliteLibraryPackRepository,
)
from app.db.repositories.sqlite.reliefTemplateRepository import (
    SqliteReliefTemplateRepository,
)
from app.db.repositories.sqlite.worldRepository import SqliteWorldRepository

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STRUCTURES_ROOT = _REPO_ROOT / "structures_templates"
_RELIEF_ROOTS = (
    _REPO_ROOT / "relief_templates",
    _REPO_ROOT / "backend" / "relief_templates",
)
_FIXTURES = _REPO_ROOT / "fixtures"

_STRUCT = LibraryKind.STRUCTURE_TEMPLATES
_RELIEF = LibraryKind.RELIEF_TEMPLATES
_BUILDING = LibraryKind.BUILDING_TEMPLATES
_PACKS = LibraryKind.LIBRARY_PACKS


def _member_dict(
    pack_name: str,
    *,
    kind: LibraryKind,
    pack_uid: str,
    local_uid: str = "item_1",
    stem: str | None = None,
) -> dict:
    template_uid = library_uid(kind, local_uid, pack_uid=pack_uid)
    file_stem = stem if stem is not None else (
        template_uid if kind is _STRUCT else local_uid
    )
    return {
        "library_kind": kind.value,
        "local_uid": local_uid,
        "template_uid": template_uid,
        "source_file": f"{pack_name}/{file_stem}.json",
    }


def _manifest_dict(
    pack_name: str,
    *,
    kind: LibraryKind = _STRUCT,
    system_name: str | None = None,
    members: list[dict] | None = None,
    **extra,
) -> dict:
    system_name = system_name or f"test.pack.{pack_name}"
    pack_uid = library_uid(_PACKS, system_name)
    if members is None:
        members = [_member_dict(pack_name, kind=kind, pack_uid=pack_uid)]
    manifest = {
        "pack_uid": pack_uid,
        "system_name": system_name,
        "pack_name": pack_name,
        "display_name": pack_name,
        "members": members,
    }
    manifest.update(extra)
    return manifest


def _write_pack(
    root: Path,
    pack_name: str,
    *,
    kind: LibraryKind = _STRUCT,
    manifest: dict | None = None,
    bodies: dict[str, dict] | None = None,
) -> Path:
    """Materialise a pack folder: manifest + body files for its members."""
    pack_dir = root / pack_name
    pack_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest or _manifest_dict(pack_name, kind=kind)
    (pack_dir / PACK_MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    for member in manifest["members"]:
        rel = Path(member["source_file"])
        body = bodies.get(member["local_uid"], {}) if bodies else {}
        target = pack_dir / rel.name
        target.write_text(json.dumps(body or {"x": 1}), encoding="utf-8")
    return pack_dir


class ManifestPojoTests(unittest.TestCase):
    """Typed POJO — TZ §4 field shape."""

    def test_valid_manifest_parses(self):
        manifest = LibraryPackManifest.model_validate(_manifest_dict("base"))
        member = manifest.members[0]
        self.assertEqual(manifest.pack_name, "base")
        self.assertEqual(manifest.version, "1.0")
        self.assertEqual(manifest.dependencies, [])
        self.assertIsNone(manifest.source_pack_uid)
        self.assertEqual(member.local_uid, "item_1")
        self.assertEqual(member.library_kind, _STRUCT.value)
        self.assertIsNone(member.source_template_uid)

    def test_missing_required_member_field_rejected(self):
        from pydantic import ValidationError

        raw = _manifest_dict("p")
        del raw["members"][0]["template_uid"]
        with self.assertRaises(ValidationError):
            LibraryPackManifest.model_validate(raw)
        raw = _manifest_dict("p")
        del raw["pack_uid"]
        with self.assertRaises(ValidationError):
            LibraryPackManifest.model_validate(raw)


class LoadPackManifestTests(unittest.TestCase):
    """Filesystem layout validation — template-pack-layout.mdc + TZ §4."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "structures_templates"
        self.root.mkdir(parents=True)

    def _load(self, pack_dir: Path, *, kind: LibraryKind = _STRUCT):
        return load_pack_manifest(
            pack_dir, domain_root=self.root, library_kind=kind
        )

    def test_valid_pack_loads_members(self):
        pack_dir = _write_pack(self.root, "base")
        loaded = self._load(pack_dir)
        self.assertEqual(loaded.manifest.pack_name, "base")
        self.assertEqual(len(loaded.members), 1)
        self.assertTrue(loaded.members[0].file.is_file())

    def test_missing_manifest_rejected(self):
        (self.root / "p").mkdir()
        with self.assertRaisesRegex(PackManifestError, PACK_MANIFEST_FILENAME):
            self._load(self.root / "p")

    def test_pack_name_must_match_folder(self):
        manifest = _manifest_dict("declared")
        pack_dir = _write_pack(self.root, "actual", manifest=manifest)
        with self.assertRaisesRegex(PackManifestError, "pack_name"):
            self._load(pack_dir)

    def test_pack_uid_must_match_central_formula(self):
        manifest = _manifest_dict("p")
        manifest["pack_uid"] = library_uid(_PACKS, "test.pack.other")
        pack_dir = _write_pack(self.root, "p", manifest=manifest)
        with self.assertRaisesRegex(PackManifestError, "pack_uid"):
            self._load(pack_dir)

    def test_pack_must_be_direct_child_of_domain_root(self):
        nested = self.root / "outer" / "p"
        nested.mkdir(parents=True)
        with self.assertRaisesRegex(PackManifestError, "direct child"):
            self._load(nested)

    def test_member_kind_must_match_domain(self):
        manifest = _manifest_dict("p", kind=_RELIEF)
        pack_dir = _write_pack(self.root, "p", manifest=manifest)
        with self.assertRaisesRegex(PackManifestError, "domains never mix"):
            self._load(pack_dir)

    def test_member_template_uid_must_match_central_formula(self):
        manifest = _manifest_dict("p")
        manifest["members"][0]["template_uid"] = library_uid(
            _STRUCT, "item_1", pack_uid=library_uid(_PACKS, "test.pack.other")
        )
        pack_dir = _write_pack(self.root, "p", manifest=manifest)
        with self.assertRaisesRegex(PackManifestError, "template_uid"):
            self._load(pack_dir)

    def test_member_file_stem_must_match(self):
        manifest = _manifest_dict("p")
        manifest["members"][0]["source_file"] = "p/renamed.json"
        pack_dir = self.root / "p"
        pack_dir.mkdir()
        (pack_dir / PACK_MANIFEST_FILENAME).write_text(json.dumps(manifest))
        (pack_dir / "renamed.json").write_text("{}")
        with self.assertRaisesRegex(PackManifestError, "file stem"):
            self._load(pack_dir)

    def test_member_source_file_must_stay_inside_pack(self):
        for rel in ("other/x.json", "p/../x.json", "../x.json"):
            with self.subTest(source_file=rel):
                manifest = _manifest_dict("p")
                manifest["members"][0]["source_file"] = rel
                pack_dir = self.root / "p"
                pack_dir.mkdir(exist_ok=True)
                (pack_dir / PACK_MANIFEST_FILENAME).write_text(json.dumps(manifest))
                with self.assertRaises(PackManifestError):
                    self._load(pack_dir)

    def test_manifest_never_a_member_body(self):
        manifest = _manifest_dict("p")
        manifest["members"][0]["source_file"] = f"p/{PACK_MANIFEST_FILENAME}"
        pack_dir = self.root / "p"
        pack_dir.mkdir()
        (pack_dir / PACK_MANIFEST_FILENAME).write_text(json.dumps(manifest))
        with self.assertRaisesRegex(PackManifestError, "never a template body"):
            self._load(pack_dir)

    def test_undeclared_json_in_pack_rejected(self):
        pack_dir = _write_pack(self.root, "p")
        (pack_dir / "stray.json").write_text("{}")
        with self.assertRaisesRegex(PackManifestError, "undeclared"):
            self._load(pack_dir)

    def test_missing_member_file_rejected(self):
        manifest = _manifest_dict("p")
        pack_dir = self.root / "p"
        pack_dir.mkdir()
        (pack_dir / PACK_MANIFEST_FILENAME).write_text(json.dumps(manifest))
        with self.assertRaisesRegex(PackManifestError, "does not exist"):
            self._load(pack_dir)

    def test_duplicate_local_uid_rejected(self):
        pack_dir = _write_pack(
            self.root, "p",
            manifest=_manifest_dict(
                "p",
                members=[
                    _member_dict(
                        "p", kind=_STRUCT,
                        pack_uid=library_uid(_PACKS, "test.pack.p"),
                        local_uid="dup",
                    ),
                    _member_dict(
                        "p", kind=_STRUCT,
                        pack_uid=library_uid(_PACKS, "test.pack.p"),
                        local_uid="dup",
                    ),
                ],
            ),
        )
        # Both members point at the same file — duplicate local_uid fires first.
        with self.assertRaisesRegex(PackManifestError, "duplicate"):
            self._load(pack_dir)

    def test_empty_members_rejected(self):
        pack_dir = _write_pack(
            self.root, "p", manifest=_manifest_dict("p", members=[])
        )
        with self.assertRaisesRegex(PackManifestError, "no members"):
            self._load(pack_dir)

    def test_fs_manifest_never_declares_provenance(self):
        manifest = _manifest_dict("p", source_pack_uid=library_uid(_PACKS, "x"))
        pack_dir = _write_pack(self.root, "p", manifest=manifest)
        with self.assertRaisesRegex(PackManifestError, "source_pack_uid"):
            self._load(pack_dir)

        manifest = _manifest_dict("q")
        manifest["members"][0]["source_template_uid"] = "old-uid"
        pack_dir = _write_pack(self.root, "q", manifest=manifest)
        with self.assertRaisesRegex(PackManifestError, "source_template_uid"):
            self._load(pack_dir)

    def test_dependencies_validated(self):
        uid = library_uid(_PACKS, "test.pack.p")
        for deps, marker in (
            ([uid, uid], "duplicate"),
            ([uid], "itself"),
            (["bad|uid"], r"'\|'"),
        ):
            with self.subTest(deps=deps):
                manifest = _manifest_dict("p", dependencies=deps)
                pack_dir = _write_pack(self.root, "p", manifest=manifest)
                with self.assertRaisesRegex(PackManifestError, marker):
                    self._load(pack_dir)


class FsImporterTests(IsolatedAsyncioTestCase):
    """Manifest-aware importers — pack only, no lone files, no wildcard."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "structures_templates"
        self.root.mkdir(parents=True)

    @staticmethod
    def _collector():
        calls = []

        async def upsert(raw, **kwargs):
            calls.append(kwargs)
            return kwargs

        return upsert, calls

    async def test_pack_import_passes_pack_identity_and_skips_manifest(self):
        pack_dir = _write_pack(self.root, "base")
        upsert, calls = self._collector()
        outcome = await import_structure_templates_path(
            pack_dir, upsert_from_dict=upsert, domain_root=self.root
        )
        member = outcome.manifest.members[0]
        self.assertEqual(len(outcome.rows), 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["pack_uid"], outcome.manifest.pack_uid)
        self.assertEqual(calls[0]["local_uid"], member.local_uid)
        self.assertEqual(calls[0]["expected_stem"], member.template_uid)
        self.assertTrue(
            calls[0]["source_file"].startswith("structures_templates/base/")
        )

    async def test_lone_file_in_domain_root_rejected(self):
        lone = self.root / "orphan.json"
        lone.write_text("{}")
        upsert, calls = self._collector()
        with self.assertRaisesRegex(
            StructureTemplateValidationError, "lone file"
        ):
            await import_structure_templates_path(
                lone, upsert_from_dict=upsert, domain_root=self.root
            )
        self.assertEqual(calls, [])

    async def test_single_member_file_imports_via_owning_pack(self):
        pack_dir = _write_pack(self.root, "base")
        member_file = next(
            p for p in pack_dir.glob("*.json") if p.name != PACK_MANIFEST_FILENAME
        )
        upsert, calls = self._collector()
        outcome = await import_structure_templates_path(
            member_file, upsert_from_dict=upsert, domain_root=self.root
        )
        self.assertEqual(len(outcome.rows), 1)
        self.assertEqual(calls[0]["pack_uid"], outcome.manifest.pack_uid)

    async def test_pack_without_manifest_rejected(self):
        (self.root / "p").mkdir()
        (self.root / "p" / "body.json").write_text("{}")
        upsert, _ = self._collector()
        with self.assertRaises(StructureTemplateValidationError):
            await import_structure_templates_path(
                self.root / "p", upsert_from_dict=upsert, domain_root=self.root
            )

    async def test_path_outside_domain_root_rejected(self):
        outside = Path(self._tmp.name) / "elsewhere" / "x.json"
        outside.parent.mkdir()
        outside.write_text("{}")
        upsert, _ = self._collector()
        with self.assertRaises(StructureTemplateValidationError):
            await import_structure_templates_path(
                outside, upsert_from_dict=upsert, domain_root=self.root
            )

    async def test_relief_pack_import_symmetric(self):
        root = Path(self._tmp.name) / "relief_templates"
        pack_dir = _write_pack(root, "user_pack", kind=_RELIEF)
        upsert, calls = self._collector()
        outcome = await import_relief_path(
            pack_dir, upsert_from_dict=upsert, domain_root=root
        )
        self.assertEqual(len(outcome.rows), 1)
        self.assertEqual(calls[0]["pack_uid"], outcome.manifest.pack_uid)
        self.assertEqual(calls[0]["expected_stem"], "item_1")

        lone = root / "orphan.json"
        lone.write_text("{}")
        with self.assertRaisesRegex(ReliefValidationError, "lone file"):
            await import_relief_path(
                lone, upsert_from_dict=upsert, domain_root=root
            )


class DefaultSourceTests(unittest.TestCase):
    """Declared defaults only — never a wildcard scan of the domain root."""

    def test_declared_defaults(self):
        self.assertEqual(default_pack_names(_STRUCT), ("base",))
        self.assertEqual(default_pack_names(_RELIEF), ())
        self.assertEqual(default_pack_names(_BUILDING), ())

    def test_stdlib_reads_only_declared_packs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "structures_templates"
            manifest = _manifest_dict("base")
            member_uid = manifest["members"][0]["template_uid"]
            _write_pack(
                root, "base", manifest=manifest,
                bodies={"item_1": {"system_name": member_uid, "display_name": "X"}},
            )
            # A foreign pack folder — even a malformed one — is never read.
            (root / "foreign").mkdir()
            (root / "foreign" / "anything.json").write_text("{broken")
            loaded = load_structure_stdlib(root)
            self.assertEqual([str(o.system_name) for o in loaded], [member_uid])

    def test_shipped_base_pack_loads_through_manifest(self):
        loaded = load_structure_stdlib(_STRUCTURES_ROOT)
        uids = [str(o.system_name) for o in loaded]
        self.assertEqual(len(uids), 13)
        self.assertEqual(uids, sorted(uids))
        for local in STRUCTURE_MEMBER_RENAMES.values():
            self.assertIn(base_member_uid(local), uids)
        # Repeated load is uid-stable.
        self.assertEqual(uids, [str(o.system_name) for o in load_structure_stdlib(_STRUCTURES_ROOT)])


class UidMapTests(unittest.TestCase):
    """Explicit old→new artifact — covers pointers, bodies, refs, files."""

    def test_structure_map_covers_every_old_uid(self):
        for old_uid, local in STRUCTURE_MEMBER_RENAMES.items():
            with self.subTest(local=local):
                self.assertEqual(mapped_template_uid(old_uid), base_member_uid(local))
                self.assertEqual(former_template_uid(_STRUCT, local), old_uid)

    def test_relief_map_covers_every_old_uid(self):
        for old_uid, local in RELIEF_SMOKE_003_FORMER_UIDS.items():
            with self.subTest(local=local):
                self.assertEqual(mapped_template_uid(old_uid), smoke_003_member_uid(local))
                self.assertEqual(former_template_uid(_RELIEF, local), old_uid)

    def test_unmapped_uid_returns_none(self):
        self.assertIsNone(mapped_template_uid("00000000-0000-0000-0000-000000000000"))
        self.assertIsNone(former_template_uid(_BUILDING, "anything"))

    def test_pin_form(self):
        self.assertEqual(
            pin_for_member(_RELIEF, "open_land_soft"),
            {"library_kind": "relief_templates", "local_uid": "open_land_soft"},
        )


class SuppliedContentTests(unittest.TestCase):
    """Migrated shipped content — manifest/body/refs consistency."""

    def test_base_pack_manifest_validates_against_files(self):
        loaded = load_pack_manifest(
            _STRUCTURES_ROOT / "base",
            domain_root=_STRUCTURES_ROOT,
            library_kind=_STRUCT,
        )
        self.assertEqual(loaded.manifest.system_name, "engine.structures.base")
        self.assertEqual(len(loaded.members), 13)
        for lm in loaded.members:
            body = json.loads(lm.file.read_text(encoding="utf-8"))
            self.assertEqual(body["system_name"], lm.member.template_uid)
            self.assertEqual(lm.file.stem, lm.member.template_uid)

    def test_no_old_structure_uids_left_in_supplied_files(self):
        old_uids = set(STRUCTURE_MEMBER_RENAMES)
        for folder in (_STRUCTURES_ROOT, _FIXTURES / "templates"):
            for path in folder.rglob("*.json"):
                text = path.read_text(encoding="utf-8")
                leaked = [uid for uid in old_uids if uid in text]
                self.assertEqual(leaked, [], path)

    def test_plot_fixtures_reference_base_member_uids(self):
        member_uids = {
            base_member_uid(local) for local in STRUCTURE_MEMBER_RENAMES.values()
        }
        hits = 0
        for path in (_FIXTURES / "templates").glob("*.json"):
            body = json.loads(path.read_text(encoding="utf-8"))
            structure = (body.get("main_building") or {}).get("structure")
            if structure:
                self.assertIn(structure, member_uids, path.name)
                hits += 1
        self.assertTrue(hits)

    def test_inn_small_points_at_migrated_tavern(self):
        body = json.loads(
            (_FIXTURES / "templates" / "inn_small.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            body["main_building"]["structure"], base_member_uid("tavern_1")
        )

    def test_relief_smoke_003_manifests_validate(self):
        for root in _RELIEF_ROOTS:
            if not (root / "smoke_003").is_dir():
                continue
            with self.subTest(root=root):
                loaded = load_pack_manifest(
                    root / "smoke_003",
                    domain_root=root,
                    library_kind=_RELIEF,
                )
                self.assertEqual(loaded.manifest.system_name, "user.relief.smoke_003")
                self.assertEqual(
                    {lm.member.local_uid for lm in loaded.members},
                    set(RELIEF_SMOKE_003_FORMER_UIDS.values()),
                )

    def test_gen_003_world_pins_and_pick_policy_migrated(self):
        fixture = json.loads(
            (_FIXTURES / "world_test_gen_003.json").read_text(encoding="utf-8")
        )
        world_uid = fixture["world"]["world_uid"]
        pins = {
            (p["library_kind"], p["local_uid"]) for p in fixture["world"]["library_pins"]
        }
        self.assertEqual(
            pins,
            {(_RELIEF.value, local) for local in RELIEF_SMOKE_003_FORMER_UIDS.values()},
        )
        policy = fixture["world"]["relief_pick_policy"]
        expected = {
            "open_land": "open_land_soft",
            "shore": "shore_soft",
            "road_shoulder": "road_shoulder_soft",
            "ravine": "ravine_soft",
        }
        for key, local in expected.items():
            self.assertEqual(
                policy[key]["default_template_uid"],
                legacy_member_uid(_RELIEF, local, world_uid=world_uid),
                key,
            )


class _DbCase(IsolatedAsyncioTestCase):
    """Real SQLite + migrated schema, like test_library_packs_schema."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(str(Path(self.tmp.name) / "test.sqlite"))
        await self.db.connect()
        self.addAsyncCleanup(self.db.disconnect)
        await self.db.apply_migrations()
        self.packs = SqliteLibraryPackRepository(self.db)
        self.members = SqliteLibraryPackMemberRepository(self.db)

    async def _world(self, world_uid: str) -> World:
        world = World(world_uid=world_uid, name=world_uid, created_at="2026-10-09")
        await SqliteWorldRepository(self.db).create(world)
        return world


class LegacyPackTests(_DbCase):
    """World-owned ``legacy`` pack — destination of manifest-less bodies."""

    async def test_ensure_legacy_pack_idempotent(self):
        await self._world("w1")
        first = await ensure_legacy_pack("w1", self.packs)
        again = await ensure_legacy_pack("w1", self.packs)
        self.assertEqual(first.pack_uid, again.pack_uid)
        self.assertEqual(first.pack_uid, legacy_pack_uid("w1"))
        self.assertEqual(first.pack_name, LEGACY_PACK_NAME)
        self.assertEqual(first.owner_world_uid, "w1")
        stored = await self.packs.get_by_uid(first.pack_uid)
        self.assertIsNotNone(stored)
        self.assertEqual(
            len([p for p in await self.packs.list_all() if p.pack_uid == first.pack_uid]),
            1,
        )

    def test_member_row_uid_and_provenance(self):
        row = legacy_member_row(_RELIEF, "open_land_soft", world_uid="w1")
        self.assertEqual(
            row.template_uid,
            legacy_member_uid(_RELIEF, "open_land_soft", world_uid="w1"),
        )
        self.assertEqual(row.pack_uid, legacy_pack_uid("w1"))
        self.assertEqual(row.local_uid, "open_land_soft")
        # Known shipped content keeps its former uid as provenance.
        self.assertEqual(row.source_template_uid, "21fb5cb8-eb9a-5f5d-a75b-e632135fc0b5")
        # World-authored bodies have no former identity.
        self.assertIsNone(
            legacy_member_row(_RELIEF, "world_made", world_uid="w1").source_template_uid
        )


class LegacyBodyImportTests(_DbCase):
    """Manifest-less bundle bodies → world legacy members + pointers."""

    async def test_relief_bodies_become_legacy_members(self):
        from app.application.worldData.reliefWorldImportService import (
            ReliefWorldImportService,
        )

        await self._world("w-relief")
        container = Container(None, self.db)
        service = ReliefWorldImportService(
            world_service=container.world_service(),
            library=container.relief_template_library_service(),
            packs=self.packs,
            members=self.members,
            db=self.db,
        )
        body = {
            "system_name": "open_land_soft",
            "display_name": "Open land",
            "context": "open_land",
        }
        result = await service.import_outlines_into_world("w-relief", [body])
        uid = legacy_member_uid(_RELIEF, "open_land_soft", world_uid="w-relief")
        self.assertEqual(result["uids"], [uid])

        member = await self.members.get_by_uid(uid)
        self.assertIsNotNone(member)
        self.assertEqual(member.pack_uid, legacy_pack_uid("w-relief"))
        self.assertEqual(member.local_uid, "open_land_soft")

        row = await SqliteReliefTemplateRepository(self.db).get_by_uid(uid)
        self.assertIsNotNone(row)

        world = await SqliteWorldRepository(self.db).get_by_id("w-relief")
        self.assertIn(uid, {e["system_template_uid"] for e in world.relief_template_registry})

        # Re-import is stable — same uid, no duplicate member.
        again = await service.import_outlines_into_world("w-relief", [body])
        self.assertEqual(again["uids"], [uid])
        self.assertEqual(
            len(await self.members.list_by_pack(legacy_pack_uid("w-relief"))), 1
        )

    async def test_building_bodies_become_legacy_members(self):
        await self._world("w-build")
        container = Container(None, self.db)
        service = BuildingTemplateLibraryService(
            repo=container.building_template_repository(),
            world_service=container.world_service(),
            db=self.db,
            packs=self.packs,
            members=self.members,
        )
        result = await service.import_bodies_into_world("w-build", [{
            "system_name": "mill_x",
            "structure_types": ["farm"],
            "display_name": "Mill",
        }])
        self.assertEqual(result.failed, 0, result.errors)
        uid = legacy_member_uid(_BUILDING, "mill_x", world_uid="w-build")

        member = await self.members.get_by_uid(uid)
        self.assertIsNotNone(member)
        self.assertEqual(member.library_kind, _BUILDING.value)

        world = await SqliteWorldRepository(self.db).get_by_id("w-build")
        self.assertIn(
            uid, {e["system_template_uid"] for e in world.building_template_registry}
        )


class FsPackImportCatalogTests(_DbCase):
    """Pack FS import lands bodies + catalog rows in one unit of work."""

    async def test_structure_pack_import_attaches_catalog(self):
        loaded = load_pack_manifest(
            _STRUCTURES_ROOT / "base",
            domain_root=_STRUCTURES_ROOT,
            library_kind=_STRUCT,
        )
        container = Container(None, self.db)
        service = container.structure_template_library_service()
        rows = await service.import_path(
            _STRUCTURES_ROOT / "base", domain_root=_STRUCTURES_ROOT
        )
        self.assertEqual(len(rows), 13)

        pack = await self.packs.get_by_uid(loaded.manifest.pack_uid)
        self.assertIsNotNone(pack)
        self.assertIsNone(pack.owner_world_uid)
        members = await self.members.list_by_pack(loaded.manifest.pack_uid)
        self.assertEqual(len(members), 13)
        self.assertEqual(
            {m.template_uid for m in members}, {r.template_uid for r in rows}
        )
        for row in rows:
            self.assertTrue(row.source_file.startswith("structures_templates/base/"))

        # Repeated import is stable — bodies upsert, catalog insert-missing.
        again = await service.import_path(
            _STRUCTURES_ROOT / "base", domain_root=_STRUCTURES_ROOT
        )
        self.assertEqual({r.template_uid for r in again}, {r.template_uid for r in rows})
        self.assertEqual(
            len(await self.members.list_by_pack(loaded.manifest.pack_uid)), 13
        )


if __name__ == "__main__":
    unittest.main()
