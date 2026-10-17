"""WR-TD-1: source and current coverage are mandatory nominal terrain references."""
from dataclasses import fields, replace
from types import SimpleNamespace
import unittest

from pydantic import TypeAdapter, ValidationError

from app.application.jsonValidation.resolve import UnresolvedModelError
from app.application.worldData.generators.terrain.landcover.collect import resolve_collected
from app.application.worldData.generators.terrain.landcover.types import ResolvedRegion, StateSnapshotEntry
from app.application.worldData.pack.bake.wildernessRegionIndex import build_region_index
from app.application.worldData.pack.io.wildernessRegionIndexWriter import replace_region_index
from app.application.worldData.pack.read.wildernessRegionReadService import WildernessRegionReadService
from app.dataModel.registryKey import RegistryKey, registry_key_target
from app.dataModel.spatial.regionShape import BboxShape
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.regions import ForestSpec
from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry
from tests import test_landcover_materializer as fixture


class RegionCoverageContractTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.LandcoverMaterializerTests()
        self.f.setUp()
        self.f.no_auto()
        self.f.registry.root.extend([
            TerrainRegistryEntry(system_terrain="steppe",terrain_category="solid"),
            TerrainRegistryEntry(system_terrain="swamp",terrain_category="solid"),
        ])
        self.f.world.terrain_registry = self.f.registry.model_dump(mode="json")
        self.f.declare(ForestSpec(name="source",shape=BboxShape(x_min=0,y_min=0,x_max=7,y_max=7)))
        self.region = self.f.plugin().collect(self.f.ctx,self.f.policy)[0]

    def test_annotations_reference_terrain_registry_at_every_boundary(self):
        for cls, names in ((ResolvedRegion,("entry_type","current_type")),
                           (StateSnapshotEntry,("current_type",))):
            declared = {f.name:f.type for f in fields(cls)}
            for name in names:
                self.assertIs(registry_key_target(declared[name]),WorldTerrainRegistry)
        for name in ("entry_type","current_type"):
            self.assertIs(registry_key_target(WildernessRegionEntry.model_fields[name].annotation),WorldTerrainRegistry)

    def test_entry_type_is_required_non_null_and_runtime_branded(self):
        kwargs = {f.name:getattr(self.region,f.name) for f in fields(ResolvedRegion)}
        kwargs.pop("entry_type")
        with self.assertRaises(ValidationError):
            ResolvedRegion(**kwargs)
        for invalid in (None,"",123):
            with self.subTest(value=invalid), self.assertRaises(ValidationError):
                ResolvedRegion(**kwargs,entry_type=invalid)
        for value in (self.region.entry_type,self.region.current_type,StateSnapshotEntry("steppe").current_type):
            self.assertIsInstance(value,RegistryKey)
        with self.assertRaises(ValidationError):
            StateSnapshotEntry(None)

    def test_n_plus_one_keys_round_trip_and_state_changes_only_current(self):
        initial = replace(self.region,entry_type="steppe",current_type="steppe")
        inputs = replace(self.f.inputs,state_snapshot={initial.region_uid:StateSnapshotEntry("swamp")})
        result = resolve_collected([initial],self.f.ctx,inputs,self.f.registry)
        self.assertEqual((result[0].entry_type,result[0].current_type),("steppe","swamp"))
        self.assertEqual(initial.current_type,"steppe")
        entries = build_region_index(result,self.f.scale,registry=self.f.registry)
        manifest = WorldPackManifest(world_uid=initial.world_uid,wilderness_region_entries=entries)
        decoded = WorldPackManifest.model_validate_json(manifest.model_dump_json())
        self.assertEqual(decoded,manifest)
        self.assertIsInstance(decoded.wilderness_region_entries[0].entry_type,RegistryKey)
        self.assertIsInstance(decoded.wilderness_region_entries[0].current_type,RegistryKey)

    def test_both_unknown_keys_produce_ref_w_diagnostics_and_never_enter_index(self):
        for name in ("entry_type","current_type"):
            bad = replace(self.region,**{name:"unregistered"})
            with self.subTest(field=name):
                with self.assertLogs("app.application.jsonValidation.resolve",level="WARNING") as log:
                    self.assertEqual(resolve_collected([bad],self.f.ctx,self.f.inputs,self.f.registry),[])
                self.assertIn("REF_W_UNKNOWN"," ".join(log.output))
                self.assertIn(name," ".join(log.output))
                with self.assertRaises(UnresolvedModelError) as error:
                    build_region_index([bad],self.f.scale,registry=self.f.registry)
                self.assertEqual(error.exception.issues[0].code,"REF_W_UNKNOWN")
                self.assertEqual(error.exception.issues[0].path[-1],name)
                good = build_region_index([self.region],self.f.scale,registry=self.f.registry)
                manifest = WorldPackManifest(world_uid=self.region.world_uid,wilderness_region_entries=good)
                before = manifest.model_dump_json()
                with self.assertRaises(UnresolvedModelError):
                    replace_region_index(manifest,build_region_index([bad],self.f.scale,registry=self.f.registry))
                self.assertEqual(manifest.model_dump_json(),before)

    def test_state_override_cannot_hide_an_invalid_initial_key(self):
        bad = replace(self.region,entry_type="unregistered",current_type="unregistered")
        inputs = replace(self.f.inputs,state_snapshot={bad.region_uid:StateSnapshotEntry("swamp")})
        with self.assertLogs("app.application.jsonValidation.resolve",level="WARNING"):
            self.assertEqual(resolve_collected([bad],self.f.ctx,inputs,self.f.registry),[])

    def test_forged_dataclass_is_revalidated_at_index_boundary(self):
        bad = replace(self.region)
        object.__setattr__(bad,"entry_type",None)
        with self.assertRaises(UnresolvedModelError) as error:
            build_region_index([bad],self.f.scale,registry=self.f.registry)
        self.assertIn("entry_type",error.exception.issues[0].path)

    def test_authored_union_remains_closed_but_snapshot_does_not_require_live_membership(self):
        with self.assertRaises(ValidationError):
            ForestSpec(entry_type="steppe",name="invalid",shape=self.region.spec.shape)
        historical = replace(self.region,entry_type="steppe",current_type="swamp")
        entry = build_region_index([historical],self.f.scale,registry=self.f.registry)[0]
        manifest = WorldPackManifest.model_validate_json(WorldPackManifest(
            world_uid=historical.world_uid,wilderness_region_entries=[entry]).model_dump_json())
        # The present-day world has neither key. The reader must still expose baked facts.
        world = SimpleNamespace(world_uid=historical.world_uid,terrain_registry=[])
        context = SimpleNamespace(has_pack_for=lambda _:True,
                                  reader_for=lambda _:SimpleNamespace(manifest=manifest))
        snapshot = WildernessRegionReadService(context).get_snapshot(world,historical.region_uid)
        self.assertTrue(snapshot.snapshot)
        self.assertEqual((snapshot.entry.entry_type,snapshot.entry.current_type),("steppe","swamp"))


if __name__ == "__main__":
    unittest.main()
