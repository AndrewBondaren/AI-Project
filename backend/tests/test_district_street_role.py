"""DistrictConnection.role → street classes, grid spine/fill, alley by role."""

from __future__ import annotations

import random
import unittest

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.connectionEntry import (
    ConnectionEntry,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.road.connectionPolicy import paint_for_connection
from app.application.worldData.generators.road.layouts.gridLayout import generate_grid
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.dataModel.settlement.district.districtConnection import (
    DistrictConnection,
    street_classes_for,
)
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.district.worldDistrictTemplateRegistry import (
    WorldDistrictTemplateRegistry,
)
from app.dataModel.settlement.enums.districtDensity import DistrictDensity
from app.dataModel.settlement.enums.districtEntryRole import DistrictEntryRole
from app.dataModel.settlement.enums.districtStreetRole import DistrictStreetRole
from app.dataModel.spatial.facing import Facing
from app.db.models.connectionNode import ConnectionNode


def _template(*connections: DistrictConnection) -> DistrictTemplateEntry:
    return DistrictTemplateEntry(
        system_name="civic_center",
        display_name="x",
        district_type="civic",
        density=DistrictDensity.DENSE,
        connections=list(connections) or None,
    )


class TestDistrictStreetClasses(unittest.TestCase):
    def test_canon_civic_is_main_whole_grid(self) -> None:
        civic = WorldDistrictTemplateRegistry.canonical_defaults().entry_for("civic_center")
        assert civic is not None
        classes = street_classes_for(civic)
        self.assertIsNotNone(classes.main)
        self.assertIsNone(classes.service)
        self.assertIsNone(classes.alley)
        self.assertIs(classes.spine, classes.main)
        self.assertIs(classes.fill, classes.main)
        self.assertEqual(classes.main.role, DistrictStreetRole.MAIN_STREET.value)

    def test_canon_industrial_is_service_whole_grid(self) -> None:
        industrial = WorldDistrictTemplateRegistry.canonical_defaults().entry_for(
            "industrial_quarter",
        )
        assert industrial is not None
        classes = street_classes_for(industrial)
        self.assertIsNone(classes.main)
        self.assertIsNotNone(classes.service)
        self.assertIs(classes.spine, classes.service)
        self.assertIs(classes.fill, classes.service)

    def test_main_and_service_split(self) -> None:
        classes = street_classes_for(_template(
            DistrictConnection(connection_type="road", role="main_street", sidewalk=True),
            DistrictConnection(connection_type="road", role="service_road", sidewalk=False),
        ))
        self.assertTrue(classes.main.sidewalk)
        self.assertFalse(classes.service.sidewalk)
        self.assertIs(classes.spine, classes.main)
        self.assertIs(classes.fill, classes.service)

    def test_alley_by_type_and_by_role(self) -> None:
        by_type = street_classes_for(_template(
            DistrictConnection(connection_type="alley"),
        ))
        self.assertIsNotNone(by_type.alley)
        self.assertEqual(by_type.alley.connection_type, "alley")

        by_role = street_classes_for(_template(
            DistrictConnection(connection_type="road", role="back_alley"),
        ))
        self.assertIsNotNone(by_role.alley)
        self.assertEqual(by_role.alley.role, DistrictStreetRole.BACK_ALLEY.value)

    def test_unknown_role_skipped(self) -> None:
        with self.assertLogs(
            "app.dataModel.settlement.district.districtConnection",
            level="WARNING",
        ) as captured:
            classes = street_classes_for(_template(
                DistrictConnection(connection_type="road", role="boulevard"),
                DistrictConnection(connection_type="road", role="main_street"),
            ))
        self.assertEqual(classes.skipped_roles, ("boulevard",))
        self.assertIsNotNone(classes.main)
        self.assertIsNone(classes.unlabeled)
        self.assertTrue(any("boulevard" in line for line in captured.output))


class TestGridSpineFillPaint(unittest.TestCase):
    def test_through_thread_uses_main_rest_service(self) -> None:
        template = _template(
            DistrictConnection(connection_type="road", role="main_street", sidewalk=True),
            DistrictConnection(connection_type="road", role="service_road", sidewalk=False),
        )
        west = ConnectionNode(
            node_uid="west", x=0, y=50, z=0,
            node_type=ConnectionNodeType.INTERSECTION.value,
            graph_level=GraphLevel.DISTRICT.value,
            world_uid="w",
        )
        east = ConnectionNode(
            node_uid="east", x=100, y=50, z=0,
            node_type=ConnectionNodeType.INTERSECTION.value,
            graph_level=GraphLevel.DISTRICT.value,
            world_uid="w",
        )
        slot = DistrictSlot(
            origin_x=0, origin_y=0, width_fine=100, depth_fine=100, ground_z=0,
            district_template=template,
            entry_nodes=[
                ConnectionEntry(
                    node=west, connection_type="road",
                    role=DistrictEntryRole.THROUGH_ROAD, facing=Facing.WEST,
                    paired_exit_uid=east.node_uid,
                ),
                ConnectionEntry(
                    node=east, connection_type="road",
                    role=DistrictEntryRole.THROUGH_ROAD, facing=Facing.EAST,
                    paired_exit_uid=west.node_uid,
                ),
            ],
        )
        skeleton = CitySkeleton(
            economic_tier=None,
            architectural_style=None,
            dominant_material=None,
            settlement_density=DistrictDensity.DENSE,
            system_city_size=None,
            system_location_mood=None,
        )
        classes = street_classes_for(template)
        nodes, edges, roles = generate_grid(
            slot, skeleton, "w",
            paint_for_connection(classes.fill),
            paint_for_connection(classes.spine),
            random.Random(0),
        )
        self.assertTrue(nodes)
        self.assertTrue(edges)
        by_y: dict[int, list] = {}
        node_by_uid = {n.node_uid: n for n in nodes}
        for edge in edges:
            a = node_by_uid[edge.from_node_uid]
            b = node_by_uid[edge.to_node_uid]
            if a.y != b.y:
                continue
            by_y.setdefault(a.y, []).append(edge)
        mid = by_y.get(50) or []
        self.assertTrue(mid)
        self.assertTrue(all(e.has_sidewalk for e in mid))
        self.assertTrue(all(roles.get(e.edge_uid) is DistrictStreetRole.MAIN_STREET for e in mid))
        other_h = [e for y, group in by_y.items() if y != 50 for e in group]
        self.assertTrue(other_h)
        self.assertTrue(all(not e.has_sidewalk for e in other_h))
        self.assertTrue(
            all(roles.get(e.edge_uid) is DistrictStreetRole.SERVICE_ROAD for e in other_h),
        )


if __name__ == "__main__":
    unittest.main()
