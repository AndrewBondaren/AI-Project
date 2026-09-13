"""LocationCityPackRenderer — FineTerrain@z + settlement.zst shell, occupied z only."""

import unittest

from app.application.worldData.render.locationCityPackRenderer import LocationCityPackRenderer
from app.application.worldData.render.renderPayloads import (
    city_level_key,
    parse_city_level_key,
)
from app.application.worldData.render.structureAsciiSymbols import (
    symbol_for_building_element,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.worldPack import (
    AreaSlotWire,
    AreaStructureWire,
    BuildingShellWire,
    DistrictStructureWire,
    FineTerrainChunkWire,
    FineTerrainColumnWire,
    FineTerrainZRun,
    SettlementStructureWire,
    ShellCellWire,
    TerritoryVolume,
)


class TestCityLevelKey(unittest.TestCase):
    def test_roundtrip(self) -> None:
        self.assertEqual(city_level_key(5), "city_5")
        self.assertEqual(parse_city_level_key("city_5"), 5)
        self.assertEqual(parse_city_level_key("city_-2"), -2)
        self.assertIsNone(parse_city_level_key("5"))
        self.assertIsNone(parse_city_level_key("grade_5"))
        self.assertIsNone(parse_city_level_key("city_"))


class TestStructureAsciiSymbols(unittest.TestCase):
    def test_roof_and_gate(self) -> None:
        self.assertEqual(symbol_for_building_element("roof"), "^")
        self.assertEqual(symbol_for_building_element("gate"), "G")
        self.assertEqual(symbol_for_building_element("wall"), "#")


class TestLocationCityPackRenderer(unittest.TestCase):
    def _chunk(self) -> FineTerrainChunkWire:
        return FineTerrainChunkWire(
            cx=0,
            cy=0,
            chunk_columns=32,
            columns=[
                FineTerrainColumnWire(
                    lx=0,
                    ly=0,
                    runs=[FineTerrainZRun(z0=0, z1=4, system_terrain="plains")],
                ),
                FineTerrainColumnWire(
                    lx=1,
                    ly=0,
                    runs=[
                        FineTerrainZRun(z0=0, z1=2, system_terrain="plains"),
                        FineTerrainZRun(z0=3, z1=5, system_terrain="forest"),
                    ],
                ),
                FineTerrainColumnWire(
                    lx=0,
                    ly=1,
                    runs=[FineTerrainZRun(z0=1, z1=3, system_terrain="liquid_body")],
                ),
            ],
        )

    def _volume(self) -> TerritoryVolume:
        return TerritoryVolume(x0=100, y0=200, z0=0, x1=110, y1=210, z1=20)

    def _renderer(self, wire: SettlementStructureWire) -> LocationCityPackRenderer:
        return LocationCityPackRenderer(
            self._chunk(),
            volume=self._volume(),
            location_uid="loc-a",
            wire=wire,
        )

    def _area(self, *, yard=None, buildings=None, barriers=None) -> AreaStructureWire:
        return AreaStructureWire(
            area_uid="a1",
            slot=AreaSlotWire(
                cells=[(101, 200)],
                ground_z=3,
                facing=Facing.NORTH,
            ),
            yard_cells=list(yard or []),
            barrier_cells=list(barriers or []),
            buildings=list(buildings or []),
        )

    def _wire(self, area: AreaStructureWire) -> SettlementStructureWire:
        return SettlementStructureWire(
            settlement_uid="loc-a",
            districts=[
                DistrictStructureWire(location_uid="d1", areas=[area]),
            ],
        )

    def test_empty_wire_omits_keys(self) -> None:
        wire = SettlementStructureWire(settlement_uid="loc-a")
        levels = self._renderer(wire).render_all_city_levels()
        self.assertEqual(levels, {})

    def test_land_visible_and_shell_overlays(self) -> None:
        wire = self._wire(
            self._area(
                buildings=[
                    BuildingShellWire(
                        location_uid="b1",
                        shell_cells=[
                            ShellCellWire(
                                x=101, y=200, z=3,
                                system_building_element="wall",
                            ),
                        ],
                    ),
                ],
            ),
        )
        text = self._renderer(wire).render_at_z(3)
        self.assertIn("city z=3", text)
        self.assertIn("|_#|", text)  # plains (0,0) + wall overlay (1,0)

    def test_occupied_z_skips_hole(self) -> None:
        wire = self._wire(
            self._area(
                buildings=[
                    BuildingShellWire(
                        location_uid="b1",
                        shell_cells=[
                            ShellCellWire(
                                x=101, y=200, z=3,
                                system_building_element="wall",
                            ),
                            ShellCellWire(
                                x=101, y=200, z=5,
                                system_building_element="roof",
                            ),
                            ShellCellWire(
                                x=100, y=201, z=3,
                                system_building_element="gate",
                            ),
                        ],
                    ),
                ],
            ),
        )
        renderer = self._renderer(wire)
        self.assertEqual(renderer.occupied_city_z(), [3, 5])
        levels = renderer.render_all_city_levels()
        self.assertIn(city_level_key(3), levels)
        self.assertIn(city_level_key(5), levels)
        self.assertNotIn(city_level_key(4), levels)
        self.assertNotIn("4", levels)
        self.assertIn("^", levels[city_level_key(5)])
        self.assertIn("G", levels[city_level_key(3)])

    def test_yard_without_element_uses_terrain(self) -> None:
        wire = self._wire(
            self._area(
                yard=[
                    ShellCellWire(x=101, y=200, z=3, system_terrain="plains"),
                ],
            ),
        )
        text = self._renderer(wire).render_at_z(3)
        self.assertIn("_", text)

    def test_floor_and_stair_glyphs(self) -> None:
        wire = self._wire(
            self._area(
                buildings=[
                    BuildingShellWire(
                        location_uid="b1",
                        shell_cells=[
                            ShellCellWire(
                                x=100, y=200, z=3,
                                system_building_element="staircase",
                                system_facing="north",
                            ),
                            ShellCellWire(
                                x=101, y=200, z=3,
                                system_building_element="floor",
                            ),
                        ],
                    ),
                ],
            ),
        )
        text = self._renderer(wire).render_at_z(3)
        self.assertIn("|↑.|", text)


if __name__ == "__main__":
    unittest.main()
