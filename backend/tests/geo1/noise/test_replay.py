"""Hash iteration order is never a field RNG input."""
import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase


class NoiseReplayTests(TestCase):
    def test_same_full_field_across_python_hash_seeds(self):
        script="from tests.geo1.noise.fixtures import case; from app.application.worldData.generators.terrain.designedWater.strategies.procedural.continentalNoiseStrategy import ContinentalNoiseStrategy; print(ContinentalNoiseStrategy().design(case()).model_dump_json())"
        outputs=[]
        for seed in ("0","1","42"):
            result=subprocess.run([sys.executable,"-c",script],cwd=Path(__file__).resolve().parents[3],
                env={**os.environ,"PYTHONHASHSEED":seed},capture_output=True,text=True,check=True)
            outputs.append(result.stdout)
        self.assertEqual(outputs[0],outputs[1]);self.assertEqual(outputs[1],outputs[2])
