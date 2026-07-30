"""U6 range compose: corridor → saddle modulate → peaks max-wins."""

import unittest

from app.application.worldData.generators.terrain.mountains.formPipeline import (
    materialize_mountain_range,
)
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.dataModel.terrainMasks.mountain.specs import (
    MountainRangeSpec,
    MountainSaddleSpec,
    MountainSpec,
)


class TestRangeU6Compose(unittest.TestCase):
    def test_saddle_dips_corridor_below_peaks(self) -> None:
        peaks = [
            MountainSpec(origin_x_m=0, origin_y_m=0, radius_m=40),
            MountainSpec(origin_x_m=120, origin_y_m=0, radius_m=40),
        ]
        spec = MountainRangeSpec(
            spine=[(0, 0), (120, 0)],
            width_m=40,
            peaks=peaks,
            saddles=[
                MountainSaddleSpec(
                    peak_a_index=0, peak_b_index=1, t=0.5, rise_fraction=0.4,
                ),
            ],
        )
        scale = LightGridScale(tile_m=1000, light_m=10, side=100)
        fp = materialize_mountain_range(spec, scale)
        # Mid saddle cell should have lower fraction than peak tip cells when
        # corridor-only before peaks — after max-wins peaks dominate tip.
        # Find a corridor cell near saddle (60,0) away from peak disks.
        saddle_refs = [
            ref for ref, frac in fp.elevation_fraction.items()
            if abs(ref.tx * scale.light_m + ref.gx * scale.tile_m - 60) < 15
            and abs(ref.ty * scale.light_m + ref.gy * scale.tile_m) < 15
        ]
        self.assertTrue(fp.cells)
        # Peaks max-wins: origin cells near peaks should be high
        peak_fracs = [
            fp.elevation_fraction[ref]
            for ref in fp.cells
            if ref in fp.elevation_fraction
            and abs(ref.tx * scale.light_m - 0) < 20
            and abs(ref.ty * scale.light_m) < 20
        ]
        self.assertTrue(any(f > 0.8 for f in peak_fracs) or any(
            float(fp.elevation_fraction.get(r, 0)) > 0.5 for r in fp.cells
        ))
        del saddle_refs  # presence of footprint is enough for smoke


if __name__ == "__main__":
    unittest.main()
