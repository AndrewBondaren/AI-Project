from copy import replace
from unittest import TestCase

from app.application.worldData.generators.hydrology.query.sourceBed import build_source_bed
from app.application.worldData.generators.hydrology.query.sourceMembership import build_wet_runs
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.query.source import WaterMembershipRun
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from tests.geo1.final_publication import test_publication as publication
from tests.geo1.hill_hosts.test_hosts import coverage
from tests.geo1.terrain_base.fixtures import Control


def fact(role=Role.LAKE, uid="lake", level=0):
    return MapCellHydrology(role=role, water_body_uid=uid, z_water_level=level)


def run(y, x0, x1, uid="lake"):
    return WaterMembershipRun(y=y, x0=x0, x1=x1, body_uid=uid)


class SourceMembershipTests(TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = publication.PublicationTests()
        fixture.setUp()
        cls.water = fixture.water.payload
        cls.final = fixture.publish().payload
        cls.bed = build_source_bed(before=fixture.before.payload, post=cls.water[0],
            routes=fixture.routes.payload, river=fixture.river.payload, final=cls.final,
            z_min=fixture.inputs.z_min, z_max=fixture.inputs.z_max, control=Control())

    def test_published_lake_and_river(self):
        self.assertTrue(any(f.role is Role.RIVER_BED and f.water_body_uid
                            for _, f in self.final.sparse_fine_hydro))
        actual = build_wet_runs(water=self.water, final=self.final, bed=self.bed, control=Control())
        self.assertEqual(actual, tuple(run(y, 10, 14) for y in range(10, 14)))

    def inputs(self, rows, *, native=None):
        post, assembled = self.water
        materialized = assembled.materialized
        bodies = (*materialized.bodies, replace(materialized.bodies[0], water_body_uid="other"))
        geometry = replace(materialized, cells=rows, bodies=bodies)
        final = replace(self.final, sparse_fine_hydro=rows if native is None else native, water_bodies=bodies)
        return dict(water=(post, replace(assembled, materialized=geometry)), final=final,
                    bed=self.bed, control=Control())

    def test_dry_gap_roles_uid_row_and_wrapped_seam(self):
        rows = (((0, 0), fact(Role.OPEN_OCEAN)), ((1, 0), fact(Role.COASTAL_SEA)),
                ((2, 0), fact(Role.INLAND_SEA, "other")), ((3, 0), fact(Role.SHORE)),
                ((5, 0), fact()), ((31, 0), fact()), ((0, 1), fact()))
        args = self.inputs(rows)
        wrapped = replace(self.bed.topology, mode=WorldTopologyMode.WRAPPED)
        bed = replace(self.bed, topology=wrapped, surface_z=tuple((c, -1) for c, _ in self.bed.surface_z))
        args.update(bed=bed, water=(bed, args["water"][1]))
        self.assertEqual(build_wet_runs(**args), (run(0, 0, 2), run(0, 2, 3, "other"),
                                                  run(0, 5, 6), run(0, 31, 32), run(1, 0, 1)))

    def test_dry_with_nonwater_roles_and_unoccupied_bodies(self):
        rows = (((10, 10), fact(Role.SHORE)), ((11, 10), fact(Role.RIVER_BED)))
        self.assertEqual(build_wet_runs(**self.inputs(rows)), ())

    def test_final_extra_missing_or_changed_wet_facts(self):
        first = ((10, 10), fact())
        tail = ((11, 10), fact())
        for source, native in (
            ((first,), (first, tail)), ((first, tail), (first,)),
            ((first,), ((first[0], fact(Role.OPEN_OCEAN)),)),
            ((first,), ((first[0], fact(uid="other")),)),
            ((first,), ((first[0], fact(level=1)),)),
        ):
            args = self.inputs(source, native=native)
            with self.subTest(native=native), self.assertRaisesRegex(ValueError, "facts disagree"):
                build_wet_runs(**args)

    def test_requires_body_and_level_in_both_inputs(self):
        args = self.inputs((((10, 10), fact(uid="other")),))
        lake, other = args["final"].water_bodies
        for bodies in ((lake,), (lake, replace(other, z_water_level=1))):
            final = replace(args["final"], water_bodies=bodies)
            with self.assertRaisesRegex(ValueError, "effective level"):
                build_wet_runs(**(args | dict(final=final)))
        for level in (None, 1):
            args = self.inputs((((10, 10), fact(level=level)),))
            with self.assertRaisesRegex(ValueError, "effective level"):
                build_wet_runs(**args)

    def test_requires_observed_bed_strictly_below_level(self):
        args = self.inputs((((32, 31), fact()),))
        with self.assertRaisesRegex(ValueError, "outside observed"):
            build_wet_runs(**args)
        args = self.inputs((((10, 10), fact()),))
        bed = replace(self.bed, surface_z=tuple((c, 0 if c == (10, 10) else z) for c, z in self.bed.surface_z))
        with self.assertRaisesRegex(ValueError, "below effective level"):
            build_wet_runs(**(args | dict(bed=bed)))

    def test_rejects_foreign_frame_coverage_or_protection_even_when_dry(self):
        args = self.inputs(())
        for bed in (
            replace(self.bed, topology=replace(self.bed.topology, mode=WorldTopologyMode.WRAPPED)),
            replace(self.bed, coverage=coverage(0, 1, 0, 1), surface_z=(self.bed.surface_z[0],)),
            replace(self.bed, protected_cells=frozenset({(0, 0)})),
        ):
            with self.assertRaisesRegex(ValueError, "frame, coverage and protection"):
                build_wet_runs(**(args | dict(bed=bed)))

    def test_shutdown_while_skipping_shore(self):
        class StopDuringScan:
            checks = 0

            def raise_if_shutdown(self):
                self.checks += 1
                if self.checks == 12:
                    raise InterruptedError()

        rows = tuple(((x, 0), fact(Role.SHORE)) for x in range(32))
        args = self.inputs(rows)
        with self.assertRaises(InterruptedError):
            build_wet_runs(**(args | dict(control=StopDuringScan())))
