"""Legacy owner identities and cold transport of a named path."""
import subprocess
import sys
import unittest
from functools import partial

from app.application.encoding.boundedCanonicalDecode import decode_bounded
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.fields.validatedFieldPath import ModelIdentity, ModelIdentityError
from app.encoding.canonicalCodec import CanonicalEncodingError, decode, encode


class IdentityWireTests(unittest.TestCase):
    def test_registered_specializations_are_records_only(self):
        checked = set()
        bounded = partial(decode_bounded, limits=DecodeLimits(100000, 10000, 100, 1024))
        for entry in SURFACE_MANIFEST.entries:
            owner = entry.python_type
            metadata = getattr(owner, "__pydantic_generic_metadata__", None)
            if not metadata or metadata["origin"] is None:
                continue
            with self.subTest(type_id=entry.type_id):
                checked.add(entry.type_id)
                self.assertEqual(entry.kind.value, "record")
                with self.assertRaises(ModelIdentityError):
                    ModelIdentity.of(owner)
                legacy = ModelIdentity(module=owner.__module__, qualname=owner.__qualname__)
                data = encode(legacy, SURFACE_MANIFEST)
                for reader in (decode, bounded):
                    with self.subTest(reader=reader), self.assertRaises(CanonicalEncodingError):
                        reader(data, ModelIdentity, SURFACE_MANIFEST)
        self.assertTrue({287, 289, 291, 296} <= checked)

    def test_cold_water_kind(self):
        manifest = "from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST"
        path = """
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.hydrology.waterBody import WaterBody
path = CheckedPath.from_pydantic_loc(WaterBody, ("kind",))
"""
        writer = """
import sys
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
PlanEnvelope[FineWaterResult]
assert 'app.application.worldData.planning.encoding.surfaceManifest' not in sys.modules
""" + path + manifest + """
from app.encoding.canonicalCodec import encode
sys.stdout.buffer.write(encode(path, SURFACE_MANIFEST))
"""
        reader = manifest + path + """
import sys
from app.encoding.canonicalCodec import encode, decode
from app.dataModel.fields.validatedFieldPath import ValidatedFieldPath
data = sys.stdin.buffer.read()
restored = decode(data, ValidatedFieldPath, SURFACE_MANIFEST)
assert restored == path
sys.stdout.buffer.write(encode(restored, SURFACE_MANIFEST))
"""
        data = subprocess.check_output([sys.executable, "-c", writer])
        self.assertEqual(subprocess.check_output([sys.executable, "-c", reader], input=data), data)
