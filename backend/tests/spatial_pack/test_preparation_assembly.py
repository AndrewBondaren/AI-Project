import unittest

from pydantic import ValidationError

from app.application.worldData.pack.preparation.errors import (
    PackPreparationFailure, preparation_errors, raise_preparation_errors, validate_preparation_input,
)
from app.core.constants import FINE_CELL_SIZE
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.worldPack.meta.wildernessRegionEntry import (
    RegionIndexBounds, WildernessRegionEntry, WildernessRegionStatus,
)
from app.dataModel.worldPack.preparation.assembly import (
    PackAssemblyInput, PackChunkAssembly, PackLocationAssembly, PackSettlementAssembly, PackTileAssembly,
)
from app.dataModel.worldPack.preparation.errors import PackPreparationFailureReason
from app.dataModel.worldPack.wire.territoryVolume import TerritoryVolume


class PreparationAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.volume = TerritoryVolume(x0=0, y0=0, z0=0, x1=3, y1=4, z1=5)
        self.location = PackLocationAssembly(location_uid="location", territory_volume=self.volume,
                                             climate_status="coarse")
        self.assembly = PackAssemblyInput(
            last_l0_mode="light", fine_cells_per_map_cell=1000, world_map_cells_per_tile=32,
            fine_cell_size=FINE_CELL_SIZE, map_subsurface_depth=0, terrain_chunk_columns=32,
            tiles=(), locations=(self.location,), settlements=(), wilderness_regions=(),
        )
        self.region = WildernessRegionEntry(
            region_uid="region", entry_type=WorldTerrainRegistry.forest_terrain_key(),
            current_type=WorldTerrainRegistry.forest_terrain_key(),
            bbox=RegionIndexBounds(x_min=0, y_min=0, x_max=1, y_max=1),
            status=WildernessRegionStatus.DECLARED, parent_region_uid=None, spec_fingerprint=None,
        )

    def test_volume_normalization_is_preserved_for_forged_and_raw_input(self):
        for volume in (self.volume.model_copy(update={"x0": 7, "x1": -2}),
                       {"x0": 7, "y0": 0, "z0": 0, "x1": -2, "y1": 4, "z1": 5}):
            with self.subTest(volume=volume):
                result = PackLocationAssembly(location_uid="location", territory_volume=volume,
                                              climate_status="coarse")
                self.assertEqual((result.territory_volume.x0, result.territory_volume.x1), (-2, 7))
        self.assertEqual(self.volume.x0, 0)

    def test_bad_volume_coordinates_are_rejected_before_owning_int_coercion(self):
        for invalid in (True, 1.2, "2"):
            for field in TerritoryVolume.model_fields:
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValidationError):
                    PackLocationAssembly(location_uid="location", climate_status="coarse",
                        territory_volume=self.volume.model_copy(update={field: invalid}))

    def test_missing_and_extra_volume_fields_do_not_disappear(self):
        for volume in (self.volume.model_copy(update={"unexpected": 1}),
                       TerritoryVolume.model_construct(x0=0, y0=0, z0=0, x1=1, y1=1)):
            with self.subTest(volume=volume), self.assertRaises(ValidationError):
                PackSettlementAssembly(location_uid="location", territory_volume=volume,
                                       structure_status="absent", packed_district_uids=())

    def test_region_rechecks_bbox_types_order_and_parent_rule(self):
        for region in (
            self.region.model_copy(update={"bbox": self.region.bbox.model_copy(update={"x_min": True})}),
            self.region.model_copy(update={"bbox": self.region.bbox.model_copy(update={"x_min": 2})}),
            self.region.model_copy(update={"parent_region_uid": "parent"}),
            self.region.model_copy(update={"status": "declared"}),
            self.region.model_copy(update={"extra": "rejected"}),
        ):
            with self.subTest(region=region), self.assertRaises(ValidationError):
                PackAssemblyInput.model_validate(self.assembly.model_copy(update={"wilderness_regions": (region,)}))

    def test_valid_region_and_settlement_keep_owning_values(self):
        settlement = PackSettlementAssembly(location_uid="location", territory_volume=self.volume,
                                            structure_status="partial", packed_district_uids=("district",))
        value = PackAssemblyInput.model_validate(self.assembly.model_copy(update={
            "wilderness_regions": (self.region,), "settlements": (settlement,),
            "fine_cells_per_map_cell": 2000, "terrain_chunk_columns": 64, "world_map_cells_per_tile": 17,
        }))
        self.assertEqual(value.wilderness_regions, (self.region,))
        self.assertEqual(value.settlements, (settlement,))
        self.assertEqual(value.world_map_cells_per_tile, 17)

    def test_nested_diagnostics_preserve_all_available_paths(self):
        volume = self.volume.model_copy(update={"x0": True, "z1": "bad"})
        location = self.location.model_copy(update={"territory_volume": volume})
        forged = self.assembly.model_copy(update={"locations": (location,), "terrain_chunk_columns": False})
        errors = preparation_errors()
        self.assertIsNone(validate_preparation_input(PackAssemblyInput, forged, errors))
        with self.assertRaises(PackPreparationFailure) as caught:
            raise_preparation_errors(errors, PackPreparationFailureReason.INVALID_INPUT)
        issues = caught.exception.error.issues
        self.assertTrue(all(type(issue) is JsonFieldError for issue in issues))
        self.assertEqual([issue.path.projection() for issue in issues], [
            ("terrain_chunk_columns",), ("locations", 0, "territory_volume", "x0"),
            ("locations", 0, "territory_volume", "z1"),
        ])

    def test_effective_header_constraints_and_explicit_fields(self):
        for field, value in (
            ("fine_cells_per_map_cell", 999), ("fine_cells_per_map_cell", 1500),
            ("world_map_cells_per_tile", 0), ("fine_cell_size", FINE_CELL_SIZE + 1),
            ("map_subsurface_depth", -1), ("terrain_chunk_columns", 0),
            ("last_l0_mode", "detailed"), ("tiles", []),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                PackAssemblyInput.model_validate(self.assembly.model_copy(update={field: value}))
        for field in PackAssemblyInput.model_fields:
            raw = dict(vars(self.assembly))
            del raw[field]
            with self.subTest(missing=field), self.assertRaises(ValidationError):
                PackAssemblyInput.model_validate(raw)

    def test_nested_records_are_immutable_and_revalidated(self):
        chunk = PackChunkAssembly(cx=0, cy=1, refine_role=None)
        tile = PackTileAssembly(gx=-1, gy=-2, climate_status="coarse",
                                wilderness_refine_status="partial", chunks=(chunk,))
        valid = PackAssemblyInput.model_validate(self.assembly.model_copy(update={"tiles": (tile,)}))
        with self.assertRaises(ValidationError):
            valid.tiles[0].gx = 3
        with self.assertRaises(ValidationError):
            PackAssemblyInput.model_validate(valid.model_copy(update={
                "tiles": (tile.model_copy(update={"chunks": (chunk.model_copy(update={"cx": True}),)}),),
            }))

    def test_existing_legacy_models_keep_their_behavior(self):
        self.assertEqual(TerritoryVolume(x0="3", y0=0, z0=0, x1=1, y1=1, z1=1, extra=1).x0, 1)
        self.assertEqual(RegionIndexBounds(x_min="0", y_min=0, x_max=1, y_max=1).x_min, 0)
