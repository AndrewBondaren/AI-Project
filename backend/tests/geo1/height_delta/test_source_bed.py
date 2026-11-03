from copy import replace
from unittest import TestCase

from app.application.worldData.generators.hydrology.query.sourceBed import build_source_bed
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from tests.geo1.final_publication import test_publication as publication
from tests.geo1.fine_water.fixtures import decisions
from tests.geo1.fine_water.test_fill import fill
from tests.geo1.hill_hosts.test_hosts import coverage
from tests.geo1.native_relief.test_beds import run
from tests.geo1.source_projection.test_projection import assemble
from tests.geo1.terrain_base.fixtures import Control


class SourceBedTests(TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = publication.PublicationTests()
        fixture.setUp()
        cls.before = fixture.before.payload
        cls.post = fixture.water.payload[0]
        cls.routes = fixture.routes.payload
        cls.river = fixture.river.payload
        cls.final = fixture.publish().payload
        cls.fixture = fixture

    def build(self, **changes):
        args = dict(before=self.before, post=self.post, routes=self.routes, river=self.river,
                    final=self.final, z_min=self.fixture.inputs.z_min, z_max=self.fixture.inputs.z_max,
                    control=Control())
        return build_source_bed(**(args | changes))

    def test_complete_published_bed(self):
        expected = dict(self.before.surface_z)
        expected.update({(x, y): -5 for y in range(10, 14) for x in range(10, 14)})
        expected.update({(x, 11): 9 if x < 5 else 8 for x in range(2, 10)})
        self.assertEqual(self.build(), replace(self.before, surface_z=tuple(expected.items())))

    def test_dry_publication_with_protection(self):
        inputs = replace(self.fixture.inputs, enabled=False, declared_rivers=())
        water = fill(self.fixture.before, self.before.topology, physical=inputs)
        routes = assemble(inputs, water, (), decisions(inputs))
        river = run(inputs, water, routes)
        final = self.fixture.publish(inputs=inputs, specs=(), water=water, expected_water=water.ref,
                                     routes=routes, expected_routes=routes.ref, river=river, expected_river=river.ref)
        self.assertFalse(final.payload.sparse_fine_hydro)
        protected = frozenset({(0, 0)})
        before = replace(self.before, protected_cells=protected)
        bed = self.build(before=before, post=replace(water.payload[0], protected_cells=protected),
                         routes=routes.payload, river=river.payload, final=final.payload)
        self.assertEqual(bed, before)

    def test_requires_exact_native_delta_including_unchanged_retained_sample(self):
        rows = self.final.fine_z_overrides
        retained = self.before.surface_z[0]
        base = self.routes.base
        routes = replace(self.routes, base=replace(base, fine_base_surface_z=(retained, *base.fine_base_surface_z)))
        river = replace(self.river, fine_surface_z=(retained, *self.river.fine_surface_z))
        complete = replace(self.final, fine_z_overrides=(retained, *rows))
        self.assertEqual(self.build(routes=routes, river=river, final=complete), self.build())
        for wrong in ((), rows):
            with self.subTest(size=len(wrong)), self.assertRaisesRegex(ValueError, "native final height delta"):
                self.build(routes=routes, river=river, final=replace(self.final, fine_z_overrides=wrong))

    def test_inconsistent_river_geometry(self):
        rows = self.river.fine_surface_z
        first, last = rows[0], rows[-1]
        for wrong, message in (
            (rows[:-1], "retained H samples"),
            (((first[0], first[1] - 1), *rows[1:]), "actual bed"),
            ((*rows[:-1], (last[0], last[1] - 1)), "outside actual beds"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.build(river=replace(self.river, fine_surface_z=wrong))

    def test_mismatched_window_or_vertical_bounds(self):
        other_frame = replace(self.post.topology, mode=WorldTopologyMode.WRAPPED)
        cases = (
            (dict(post=replace(self.post, topology=other_frame)), "observation domain"),
            (dict(post=replace(self.post, coverage=coverage(0, 1, 0, 1),
                               surface_z=(self.post.surface_z[0],))), "observation domain"),
            (dict(before=replace(self.before, protected_cells=frozenset({(0, 0)}))), "protection"),
            (dict(z_min=2, z_max=1), "ordered vertical bounds"),
            (dict(z_min=-4), "exceeds captured"),
            (dict(z_max=9), "exceeds captured"),
        )
        for changes, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.build(**changes)

    def test_cancellation(self):
        class Stop:
            def raise_if_shutdown(self):
                raise InterruptedError()

        with self.assertRaises(InterruptedError):
            self.build(control=Stop())
