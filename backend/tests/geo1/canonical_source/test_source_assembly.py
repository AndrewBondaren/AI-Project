from copy import replace
from unittest import TestCase

from pydantic import ValidationError

from app.application.worldData.generators.hydrology.query.sourceAssembly import build_source_payload
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
from app.dataModel.hydrology.query.source import WaterMembershipRun
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from tests.geo1.canonical_source.test_source_models import union
from tests.geo1.final_publication import test_publication as publication
from tests.geo1.fine_water.fixtures import decisions
from tests.geo1.fine_water.test_fill import fill
from tests.geo1.native_relief.test_beds import run
from tests.geo1.source_projection.test_projection import assemble
from tests.geo1.terrain_base.fixtures import Control


class SourceAssemblyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = publication.PublicationTests()
        fixture.setUp()
        cls.fixture = fixture
        cls.final = fixture.publish().payload

    def build(self, **changes):
        f = self.fixture
        args = dict(before=f.before.payload, water=f.water.payload, routes=f.routes.payload,
                    river=f.river.payload, final=self.final, inputs=f.inputs, control=Control())
        return build_source_payload(**(args | changes))

    def test_complete_source_after_river_overlay(self):
        payload = self.build()
        f = self.fixture
        self.assertIs(payload.space, CoordinateSpace.WORLD_FINE_GRID)
        self.assertEqual((payload.z_min, payload.z_max), (f.inputs.z_min, f.inputs.z_max))
        heights = dict(f.water.payload[0].surface_z) | dict(f.river.payload.fine_surface_z)
        self.assertEqual(payload.bed, replace(f.before.payload, surface_z=tuple(heights.items())))
        self.assertEqual(payload.wet_runs, tuple(WaterMembershipRun(y=y, x0=10, x1=14, body_uid="lake")
                                                 for y in range(10, 14)))
        water = f.water.payload[1]
        self.assertEqual(payload.bodies, water.materialized.bodies)
        self.assertEqual(payload.unions, water.physical_unions)
        self.assertEqual(payload.source_mapping, water.materialized.source_mapping)
        shores = {c: fact for c, fact in water.materialized.cells if fact.role is Role.SHORE}
        self.assertIn((9, 11), shores)
        self.assertIs(dict(self.final.sparse_fine_hydro)[9, 11].role, Role.RIVER_BED)
        del shores[9, 11]
        self.assertEqual(payload.shore_rows, tuple(shores.items()))

    def test_dry_publication(self):
        f = self.fixture
        inputs = replace(f.inputs, enabled=False, declared_rivers=())
        water = fill(f.before, f.before.payload.topology, physical=inputs)
        routes = assemble(inputs, water, (), decisions(inputs))
        river = run(inputs, water, routes)
        final = f.publish(inputs=inputs, specs=(), water=water, expected_water=water.ref,
                          routes=routes, expected_routes=routes.ref, river=river, expected_river=river.ref)
        payload = self.build(inputs=inputs, water=water.payload, routes=routes.payload,
                             river=river.payload, final=final.payload)
        self.assertEqual(payload.bed, f.before.payload)
        self.assertEqual((payload.wet_runs, payload.shore_rows, payload.bodies, payload.unions), ((), (), (), ()))

    def test_unoccupied_body_union_and_explicit_dry_mapping_survive(self):
        f = self.fixture
        post, water = f.water.payload
        lake, = water.materialized.bodies
        bodies = (lake, replace(lake, water_body_uid="alias", parent_system_uid="system"))
        unions = (union("system", members=("alias",)),)
        mapping = SourceBodyMapping(entries=(SourceBodyMappingEntry(source_uid="dry", body_uids=()),
                                            *water.materialized.source_mapping.entries))
        materialized = replace(water.materialized, bodies=bodies, source_mapping=mapping)
        tables = dict(water_bodies=bodies, physical_unions=unions)
        routes = replace(f.routes.payload, base=replace(f.routes.payload.base, **tables), source_mapping=mapping)
        payload = self.build(water=(post, replace(water, materialized=materialized, physical_unions=unions)),
                             routes=routes, final=replace(self.final, **tables, source_mapping=mapping))
        self.assertEqual(payload.bodies, (bodies[1], lake))
        self.assertEqual(payload.unions, unions)
        self.assertEqual(payload.source_mapping, mapping)
        self.assertEqual({row.body_uid for row in payload.wet_runs}, {"lake"})

    def test_requires_full_table_agreement_with_both_stages(self):
        routes = self.fixture.routes.payload
        changed = (replace(self.final.water_bodies[0], declared_level=-1),)
        unions = (union("system", members=("lake",)),)
        mapping = SourceBodyMapping(entries=())
        cases = (
            ("body tables", dict(routes=replace(routes, base=replace(routes.base, water_bodies=changed)))),
            ("body tables", dict(final=replace(self.final, water_bodies=changed))),
            ("union tables", dict(routes=replace(routes, base=replace(routes.base, physical_unions=unions)))),
            ("union tables", dict(final=replace(self.final, physical_unions=unions))),
            ("source mappings", dict(routes=replace(routes, source_mapping=mapping))),
            ("source mappings", dict(final=replace(self.final, source_mapping=mapping))),
        )
        for message, changes in cases:
            with self.subTest(message=message, stage=tuple(changes)), self.assertRaisesRegex(ValueError, message):
                self.build(**changes)

    def test_captured_frame_and_liquid_membership(self):
        inputs = self.fixture.inputs
        foreign = replace(inputs.topology, mode=WorldTopologyMode.WRAPPED)
        with self.assertRaisesRegex(ValueError, "captured fine frame"):
            self.build(inputs=replace(inputs, topology=foreign))
        with self.assertRaisesRegex(ValueError, "captured material membership"):
            self.build(inputs=replace(inputs, liquid_keys=frozenset()))

    def test_invalid_final_shore_reaches_source_validation(self):
        rows = self.final.sparse_fine_hydro
        shore = next(fact for _, fact in rows if fact.role is Role.SHORE)
        for cell, fact, message in (
            ((31, 31), replace(shore, water_body_uid="missing"), "shore body is missing"),
            ((32, 31), shore, "shore must be observed"),
        ):
            final = replace(self.final, sparse_fine_hydro=(*rows, (cell, fact)))
            with self.subTest(cell=cell), self.assertRaisesRegex(ValidationError, message):
                self.build(final=final)

    def test_shutdown(self):
        class Stop:
            def raise_if_shutdown(self):
                raise InterruptedError()

        with self.assertRaises(InterruptedError):
            self.build(control=Stop())
