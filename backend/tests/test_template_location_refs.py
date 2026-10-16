"""5b/B4: persisted template refs on named locations.

The building NL stores the member uid of the plot actually placed and of
the structure actually materialized — never a readable name. Both refs
survive bundle export/import, follow the member uid map on world copy,
gate member deletion through usage checks, and are never recomputed from
the current building body on ordinary reads.
"""

import json
import unittest
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5

from tests.test_library_packs_4b import _ServiceCase, _plot_body
from app.application.jsonValidation.types import ImportValidationError
from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.structureAreaAssembler import (
    StructureAreaAssembler,
)
from app.application.templateLibrary.packs.errors import LibraryPackInUseError
from app.application.templateLibrary.packs.legacy.legacyPack import legacy_pack_uid
from app.application.worldData.settlementOutdoor.settlementOutdoorUids import (
    area_uid, building_location_uid,
)
from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.dataModel.locations.structure.building.buildingBodyTemplate import BuildingBodyTemplate
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.building.structureCatalog import StructureCatalog
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.spatial.facing import Facing
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.ids import LibraryKind, library_uid, remapped_library_uid

_P = LibraryKind.PLOT_TEMPLATES
_S = LibraryKind.STRUCTURE_TEMPLATES
_STRUCT_UID = "00000000-0000-4000-8000-000000000041"
_PLOT_UID = "00000000-0000-4000-8000-000000000042"


def _structure_body(uid: str) -> dict:
    root = Path(__file__).resolve().parents[2] / "structures_templates/base"
    body = json.loads(next(p for p in sorted(root.glob("*.json"))
                           if p.name != "pack.manifest.json").read_text(encoding="utf-8"))
    body["system_name"] = uid
    return body


def _structure(uid: str) -> StructureTemplate:
    return StructureTemplate(
        system_name=uid,
        display_name="Hall",
        levels=[{
            "z_offset": 0, "display_name": "Ground",
            "rooms": [{
                "room_id": "hall", "display_name": "Hall", "room_type": "common_hall",
                "shape_type": "square", "size": {"width_range": [5, 5]},
                "required": True, "is_public": True, "is_forbidden": False,
                "entry_point": {"wall": "south", "passage_type": "main_entrance"},
            }],
        }],
    )


class AssemblerRefTests(unittest.TestCase):
    """Materialize persists member uids, not readable names."""

    def setUp(self):
        self.world = World(world_uid="ref-world", name="Ref", created_at="2026-10-10")
        self.skeleton = SettlementSkeleton()
        self.catalog = StructureCatalog.from_entries({_STRUCT_UID: _structure(_STRUCT_UID)})
        self.plot = PlotLayoutTemplate(
            system_name="readable-plot", display_name="Plot",
            occupied_footprint={"min_x": 0, "min_y": 0, "width": 5, "depth": 5},
            main_building=BuildingBodyTemplate(
                structure=_STRUCT_UID, foundation_type="none", roof_type="none"),
        )

    def test_member_uids_persisted_not_names(self):
        slot = AreaSlot([(x, y) for x in range(20, 25) for y in range(30, 35)], 7, Facing.SOUTH)
        area = StructureAreaAssembler().assemble(
            self.world, slot, self.plot, self.skeleton, None,
            structure_catalog=self.catalog, building_x=20, building_y=30,
            district_uid="district-1", template_uid=_PLOT_UID,
        )
        loc = area.building_location
        self.assertEqual(loc.system_template_uid, _PLOT_UID)
        self.assertEqual(loc.system_structure_template_uid, _STRUCT_UID)
        self.assertNotEqual(loc.system_template_uid, self.plot.system_name)
        # DET-1 identity recipe unchanged: member uid is the template key.
        expected_area = area_uid("ref-world", "district-1", 20, 30, Facing.SOUTH)
        self.assertEqual(loc.location_uid,
                         building_location_uid("ref-world", expected_area, _PLOT_UID, 20, 30))

    def test_plot_without_building_creates_no_location(self):
        plot = self.plot.model_copy(update={"main_building": None, "plot_type": "public"})
        slot = AreaSlot([(x, y) for x in range(20, 25) for y in range(30, 35)], 7, Facing.SOUTH)
        area = StructureAreaAssembler().assemble(
            self.world, slot, plot, self.skeleton, None,
            structure_catalog=self.catalog, district_uid="district-1",
            template_uid=_PLOT_UID,
        )
        self.assertIsNone(area.building_location)
        self.assertIsNone(area.building_layout)


class PersistedRefTests(_ServiceCase):
    """World copy remap, usage gating and read stability over real SQLite."""

    async def _world(self, world_uid):
        return await self.container.world_service().create(
            {"world_uid": world_uid, "name": world_uid, "created_at": "2026-10-10"})

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bundle = self.container.world_bundle_service()
        self.locations = self.container.location_repository()

    async def _graph(self):
        await self._world("src")
        structures = await self.service.create_pack(
            system_name="world.src.structures", owner_world_uid="src")
        structure_uid = library_uid(_S, "mill", pack_uid=structures.pack_uid)
        structure = await self.service.create_member(
            structures.pack_uid, library_kind=_S, local_uid="mill",
            body=_structure_body(structure_uid), world_uid="src")
        plots = await self.service.create_pack(
            system_name="world.src.plots", owner_world_uid="src",
            dependencies=(structures.pack_uid,))
        plot = await self.service.create_member(
            plots.pack_uid, library_kind=_P, local_uid="home",
            body=_plot_body("home", structure.template_uid), world_uid="src")
        return structure, plot

    async def _building(self, plot_uid, structure_uid, *, location_uid="b-src"):
        loc = NamedLocation(
            location_uid=location_uid, world_uid="src", display_name="Home",
            system_location_type="building", created_at="2026-10-10",
            map_x=1, map_y=2, map_z=7,
            system_template_uid=plot_uid,
            system_structure_template_uid=structure_uid,
        )
        await self.locations.create(loc)
        return loc

    async def test_world_copy_remaps_both_refs(self):
        structure, plot = await self._graph()
        await self._building(plot.template_uid, structure.template_uid)
        data = await self.bundle.export("src")
        results, rolled = await self.bundle.import_bundle(data)
        self.assertFalse(rolled, results)
        copied = next(w for w in await self.worlds.get_all() if w.world_uid != "src")
        packs = {p.source_pack_uid: p for p in await self.packs.list_world_owned(copied.world_uid)}
        copied_loc = (await self.locations.get_by_world(copied.world_uid))[0]
        self.assertEqual(copied_loc.system_template_uid, remapped_library_uid(
            _P, target_pack_uid=packs[plot.pack_uid].pack_uid,
            source_template_uid=plot.template_uid))
        self.assertEqual(copied_loc.system_structure_template_uid, remapped_library_uid(
            _S, target_pack_uid=packs[structure.pack_uid].pack_uid,
            source_template_uid=structure.template_uid))
        self.assertNotEqual(copied_loc.location_uid, "b-src")
        source_loc = await self.locations.get_by_id("b-src")
        self.assertEqual(source_loc.system_template_uid, plot.template_uid)
        self.assertEqual(source_loc.system_structure_template_uid, structure.template_uid)

    async def test_applied_structure_uid_survives_body_edit(self):
        structure, plot = await self._graph()
        await self._building(plot.template_uid, structure.template_uid)
        other_uid = library_uid(_S, "barn", pack_uid=structure.pack_uid)
        other = await self.service.create_member(
            structure.pack_uid, library_kind=_S, local_uid="barn",
            body=_structure_body(other_uid), world_uid="src")
        await self.service.update_member_body(
            plot.template_uid, _plot_body("home", other.template_uid), world_uid="src")
        loc = await self.locations.get_by_id("b-src")
        self.assertEqual(loc.system_template_uid, plot.template_uid)
        # Ordinary reads never recompute the applied structure identity.
        self.assertEqual(loc.system_structure_template_uid, structure.template_uid)

    async def test_location_usage_blocks_member_delete(self):
        structure, plot = await self._graph()
        await self._building(plot.template_uid, structure.template_uid)
        with self.assertRaises(LibraryPackInUseError):
            await self.service.delete_member(plot.template_uid, world_uid="src")
        with self.assertRaises(LibraryPackInUseError):
            await self.service.delete_member(structure.template_uid, world_uid="src")
        await self.locations.delete("b-src")
        result = await self.service.delete_member(plot.template_uid, world_uid="src")
        self.assertEqual(result.template_uid, plot.template_uid)


class LegacyRefTests(_ServiceCase):
    """Flat-body import: legacy names resolve through the explicit member map."""

    async def _world(self, world_uid):
        return await self.container.world_service().create(
            {"world_uid": world_uid, "name": world_uid, "created_at": "2026-10-10"})

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bundle = self.container.world_bundle_service()
        self.locations = self.container.location_repository()

    async def test_legacy_names_resolve_via_explicit_map(self):
        structure_source = str(uuid5(NAMESPACE_DNS, "b4.legacy-mill"))
        data = {
            "world": {"world_uid": "src", "name": "Src", "created_at": "2026-10-10"},
            "structure_templates": [{"system_name": structure_source, "local_uid": "mill",
                                     "display_name": "Mill"}],
            "building_templates": [{"system_name": "home", "display_name": "Home",
                                    "main_building": {"structure": "mill"}}],
            "locations": [{"location_uid": "b1", "display_name": "Home",
                           "system_location_type": "building",
                           "system_template_uid": "home",
                           "system_structure_template_uid": "mill"}],
        }
        results, rolled = await self.bundle.import_bundle(data)
        self.assertFalse(rolled, results)
        target = next(w for w in await self.worlds.get_all())
        members = await self.members.list_by_pack(legacy_pack_uid(target.world_uid))
        by_kind = {m.library_kind: m for m in members}
        loc = (await self.locations.get_by_world(target.world_uid))[0]
        self.assertEqual(loc.system_template_uid, by_kind[_P.value].template_uid)
        self.assertEqual(loc.system_structure_template_uid, by_kind[_S.value].template_uid)

    async def test_ambiguous_legacy_name_is_an_import_error(self):
        data = {
            "world": {"world_uid": "src", "name": "Src", "created_at": "2026-10-10"},
            "structure_templates": [{"system_name": str(uuid5(NAMESPACE_DNS, "b4.mill2")),
                                     "local_uid": "mill", "display_name": "Mill"}],
            "plot_templates": [{"system_name": "home", "display_name": "Home",
                                "main_building": {"structure": "mill"}}],
            "building_templates": [{"system_name": "home", "display_name": "Dup",
                                    "structure": "mill"}],
            "locations": [{"location_uid": "b1", "display_name": "Home",
                           "system_location_type": "building",
                           "system_template_uid": "home"}],
        }
        with self.assertRaises(ImportValidationError):
            await self.bundle.import_bundle(data)
        self.assertEqual(await self.worlds.get_all(), [])
