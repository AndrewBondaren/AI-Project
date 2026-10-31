from copy import replace
from unittest import TestCase

from app.application.worldData.generators.terrain.planning.projection.heightDelta import FineHeightDeltaJob
from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan, RiverBedRecord
from tests.geo1.fine_water.test_fill import source
from tests.geo1.terrain_base.fixtures import Control


class HeightDeltaTests(TestCase):
    def setUp(self):
        window, _, _ = source(hills=False)
        self.before = window.payload
        self.water = replace(self.before, surface_z=tuple((c, -5 if c in ((2, 2), (3, 2)) else z)
                                                       for c, z in self.before.surface_z))
        self.samples = (((3, 2), -5), ((4, 2), dict(self.before.surface_z)[4, 2]))
        self.river = RiverReliefPlan(surface_z=(), fine_surface_z=(((3, 2), -7), self.samples[1]),
            coarse_beds=(), fine_beds=(RiverBedRecord(river_uid="river", bed_z=(((3, 2), -7),)),))

    def compute(self, **changes):
        args = dict(samples=self.samples, river=self.river, control=Control()) | changes
        return FineHeightDeltaJob().compute(self.before, self.water, **args)

    def test_reconstruction_matches_full_overlay_and_retains_B_union_H(self):
        result = self.compute()
        actual = dict(self.before.surface_z) | dict(result)
        expected = dict(self.water.surface_z) | dict(self.river.fine_surface_z)
        self.assertEqual(actual, expected)
        self.assertEqual(result, (((2, 2), -5), ((3, 2), -7), self.samples[1]))
        self.assertEqual(len(result), 3)

    def test_empty_rivers_deliver_only_basins(self):
        river = RiverReliefPlan(surface_z=(), fine_surface_z=(), coarse_beds=(), fine_beds=())
        self.assertEqual(self.compute(samples=(), river=river), (((2, 2), -5), ((3, 2), -5)))

    def test_reverted_basin_still_retains_H_once(self):
        z = dict(self.before.surface_z)[3, 2]
        river = replace(self.river, fine_surface_z=(((3, 2), z), self.samples[1]),
            fine_beds=(RiverBedRecord(river_uid="river", bed_z=(((3, 2), z),)),))
        self.assertEqual(dict(self.compute(river=river))[3, 2], z)

    def test_mismatched_observation_domain_fails(self):
        from tests.geo1.hill_hosts.test_hosts import coverage
        other = replace(self.water, coverage=coverage(0, 1, 0, 1), surface_z=(((0, 0), 0),), protected_cells=frozenset())
        with self.assertRaises(ValueError):
            FineHeightDeltaJob().compute(self.before, other, samples=(), river=self.river, control=Control())

    def test_stale_missing_and_non_bed_changes_fail(self):
        with self.assertRaises(ValueError):
            self.compute(samples=(((3, 2), 999), self.samples[1]))
        with self.assertRaises(ValueError):
            self.compute(samples=())
        with self.assertRaises(ValueError):
            self.compute(river=replace(self.river, fine_surface_z=(((3, 2), -7), ((4, 2), -19))))
        with self.assertRaises(ValueError):
            self.compute(river=replace(self.river, fine_beds=(RiverBedRecord(river_uid="river", bed_z=(((3, 2), -8),)),)))

    def test_one_sequential_scan_per_frozen_surface(self):
        class Once(tuple):
            scans = 0
            def __iter__(self):
                self.scans += 1
                if self.scans > 1:
                    raise AssertionError("repeated full height scan")
                return super().__iter__()
        before, water = replace(self.before), replace(self.water)
        object.__setattr__(before, "surface_z", Once(before.surface_z))
        object.__setattr__(water, "surface_z", Once(water.surface_z))
        result = FineHeightDeltaJob().compute(before, water, samples=self.samples, river=self.river, control=Control())
        self.assertEqual(len(result), 3)
        self.assertEqual(before.surface_z.scans, 1)
        self.assertEqual(water.surface_z.scans, 1)

    def test_cancellation(self):
        class Stop:
            def raise_if_shutdown(self):
                raise InterruptedError()
        with self.assertRaises(InterruptedError):
            self.compute(control=Stop())
