"""R1 unified reads over real SQL and a freshly opened building pack."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.container import Container
from app.db.database import Database
from app.db.models.world import World
from app.db.models.namedLocation import NamedLocation
from app.db.models.locationLevel import LocationLevel
from app.db.repositories.sqlite.transitionRepository import SqliteTransitionRepository
from app.db.repositories.iTransitionRepository import TransitionRepositoryContext
from app.application.worldData.transitions.transitionReadService import BuildingTransitionPackBinding
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.io.packBlobWire import InteriorTransitionsRebuildRequired
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.transitionSide import TransitionSide
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.dataModel.worldPack.settlementStructureWire import SettlementStructureWire, BuildingInteriorTransitionsWire


class TransitionReadTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "read.sqlite"))
        await self.db.connect()
        await self.db.apply_migrations()
        self.container = Container(None, self.db)
        self.registry = WorldTransitionTypeRegistry.model_validate([
            *WorldTransitionTypeRegistry.canonical_engine().model_dump(mode="json"),
            {"system_type": "custom_entry", "display_name": "Entry", "behaves_as": "main_entrance"},
        ])
        self.world = World("w", "Read", "2026-10-06", transition_type_registry=self.registry.model_dump(mode="json"))
        self.house = NamedLocation("house", "w", "House", "building", "2026-10-06")
        self.room = NamedLocation("room", "w", "Room", "room", "2026-10-06")
        self.locations = {item.location_uid: item for item in (self.house, self.room)}
        self.levels = {"level": LocationLevel("level", "house", 7, 3, "Level")}
        await self.container.world_repository().create(self.world)
        await self.container.location_repository().upsert_bulk(list(self.locations.values()))
        await self.container.location_level_repository().upsert_bulk(list(self.levels.values()))
        self.context = TransitionRepositoryContext("w", self.registry, self.levels, self.locations, {})
        self.repo = SqliteTransitionRepository(self.db, self.context)
        self.outer = self.item("outer", source=TransitionEndpoint(), owner="house", key="custom_entry")
        self.interior = self.item("interior", owner="room", key="custom_entry")
        self.door = self.item("door", owner="room")
        self.runtime = self.item("runtime", owner="house", origin="runtime")
        await self.repo.upsert_bulk([self.outer, self.runtime])
        self.paths = WorldPackPaths(Path(self.tmp.name) / "pack", "w")
        self.binding = BuildingTransitionPackBinding("settlement", "house", frozenset(self.levels), frozenset(self.locations))
        self.publish([self.interior, self.door])
        self.service = self.read_service([self.binding])

    async def asyncTearDown(self):
        await self.db.disconnect()
        self.tmp.cleanup()

    def item(self, uid, *, owner, key="door", source=None, origin="generated"):
        endpoint = TransitionEndpoint(space="level", level_uid="level", x=1, y=2, z=7)
        return Transition.model_validate({
            "transition_uid": uid, "world_uid": "w", "system_transition_type": key,
            "source": endpoint if source is None else source,
            "destination": endpoint.model_copy(update={"x": 2}),
            "destination_side": TransitionSide(owner_location_uid=owner, is_discovered=False,
                is_accessible=False, entry_difficulty_override=0),
            "origin": origin, "is_active": False,
        }, context={"transition_type_registry": self.registry})

    def publish(self, transitions, *, interior=True, settlement_uid="settlement", world_uid="w"):
        block = BuildingInteriorTransitionsWire.model_validate({"format": "building-interior-transitions-v1", "world_uid": world_uid,
            "level_uids": list(self.levels), "transitions": transitions}, context={"transition_type_registry": self.registry})
        wire = SettlementStructureWire.model_validate({"settlement_uid": settlement_uid, "districts": [{
            "location_uid": "district", "areas": [{"area_uid": "area", "slot": {"ground_z": 7, "facing": "south"},
            "buildings": [{"location_uid": "house", **({"interior_transitions": block} if interior else {})}]}]}]},
            context={"transition_type_registry": self.registry})
        writer = WorldPackWriter(self.paths)
        receipt = writer.encode_settlement_structure_tmp(settlement_uid, wire, registry=self.registry)
        writer.publish_settlement_structure(receipt,
            territory_volume={"x0": 0, "y0": 0, "z0": 0, "x1": 10, "y1": 10, "z1": 10},
            packed_district_uids=["district"], structure_status="complete")

    def read_service(self, bindings):
        with patch.object(self.container, "world_pack_paths_for", return_value=self.paths):
            return self.container.transition_read_service(self.world, levels=self.levels,
                locations=self.locations, nodes={}, bindings=bindings)

    async def test_level_combines_sql_outer_runtime_and_pack_without_filtering_state(self):
        items = await self.service.for_level("w", "level")
        self.assertEqual({item.transition_uid for item in items}, {"outer", "runtime", "interior", "door"})
        for item in items:
            self.assertFalse(item.is_active)
            self.assertFalse(item.destination_side.is_accessible)
            self.assertFalse(item.destination_side.is_discovered)
            self.assertEqual(item.destination_side.entry_difficulty_override, 0)
        outer = next(item for item in items if item.transition_uid == "outer")
        self.assertIsNone(outer.source.geometry)
        self.assertIsNone(outer.source.host_location_uid)

    async def test_entries_use_destination_owner_and_custom_type_without_parent_requirement(self):
        self.assertIsNone(self.room.parent_location_uid)
        self.assertEqual(await self.service.entries_of("w", "house"), [self.outer])
        self.assertEqual(await self.service.entries_of("w", "room"), [self.interior])

    async def test_uid_collision_uses_latest_sql_state_and_deduplicates_bindings(self):
        await self.repo.create(self.interior)
        changed = await self.repo.update("interior", {"destination_side": {"is_accessible": True}})
        service = self.read_service([self.binding, self.binding])
        items = await service.for_level("w", "level")
        self.assertEqual(len(items), 4)
        self.assertEqual(next(item for item in items if item.transition_uid == "interior"), changed)
        self.assertEqual(await service.entries_of("w", "room"), [changed])
        await self.repo.update("interior", {"system_transition_type": "door"})
        self.assertEqual(await service.entries_of("w", "room"), [])

    async def test_changed_sql_endpoints_do_not_resurrect_old_packed_level(self):
        await self.repo.create(self.door)
        await self.repo.update("door", {"source": {"space": "surface", "level_uid": None},
            "destination": {"space": "surface", "level_uid": None}})
        self.assertNotIn("door", {item.transition_uid for item in await self.service.for_level("w", "level")})

    async def test_unknown_scope_is_sql_only_and_cross_world_is_rejected(self):
        self.assertEqual(await self.service.for_level("w", "unknown"), [])
        self.assertEqual(await self.service.entries_of("w", "unknown"), [])
        sql_only = self.read_service([])
        self.assertEqual({item.transition_uid for item in await sql_only.for_level("w", "level")}, {"outer", "runtime"})
        with self.assertRaisesRegex(ValueError, "another world"):
            await self.service.entries_of("another-world", "house")

    async def test_shell_only_pack_requires_rebuild_and_missing_pack_is_explicit(self):
        self.publish([], interior=False, settlement_uid="legacy")
        service = self.read_service([BuildingTransitionPackBinding("legacy", "house", self.binding.level_uids,
            self.binding.owner_location_uids)])
        with self.assertRaises(InteriorTransitionsRebuildRequired):
            await service.for_level("w", "level")
        self.paths.settlement_structure_path("legacy").unlink()
        with self.assertRaises(FileNotFoundError):
            await service.entries_of("w", "room")

    async def test_empty_foreign_pack_and_unknown_refs_are_rejected(self):
        self.publish([], world_uid="foreign", settlement_uid="foreign-pack")
        service = self.read_service([BuildingTransitionPackBinding("foreign-pack", "house", self.binding.level_uids,
            self.binding.owner_location_uids)])
        with self.assertRaisesRegex(ValueError, "another world"):
            await service.for_level("w", "level")
        invalid = self.door.model_copy(update={"destination_side": TransitionSide(owner_location_uid="unknown")})
        self.publish([invalid], settlement_uid="invalid-pack")
        service = self.read_service([BuildingTransitionPackBinding("invalid-pack", "house", self.binding.level_uids,
            self.binding.owner_location_uids)])
        with self.assertRaisesRegex(ValueError, "unknown.*location"):
            await service.for_level("w", "level")
