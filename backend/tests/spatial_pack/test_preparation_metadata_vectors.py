"""Fixed bytes/digests, projection coverage and cold-process identity."""

import json
from pathlib import Path
import subprocess
import sys
import unittest

from app.application.worldData.pack.preparation.metadataProjection import metadata_projection, metadata_value_fingerprint
from app.dataModel.worldPack.preparation.addresses import (
    PackAssemblyHeaderAddress, PackTileMetadataAddress, PackChunkMetadataAddress,
    PackLocationMetadataAddress, PackSettlementMetadataAddress, PackRegionMetadataAddress,
)
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput, PackTileAssembly, PackChunkAssembly, PackLocationAssembly, PackSettlementAssembly
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry
from app.dataModel.worldPack.encoding.metadataBindings import PACK_METADATA_SCHEMA
from app.encoding.canonicalCodec import content_digest, encode, merge_manifests, CanonicalEncodingError
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, RegisteredTypeEntry, CanonicalTypeKind
from tests.spatial_pack.metadata_vector_cases import encoded_vectors, vector_cases


class MetadataVectorTests(unittest.TestCase):
    def test_fixed_bytes_and_hashes(self) -> None:
        expected = json.loads(Path(__file__).with_name("metadata_canonical_vectors.json").read_text(encoding="utf-8"))
        self.assertEqual(encoded_vectors(), expected)

    def test_cold_process(self) -> None:
        result = subprocess.run([sys.executable, "-B", "-m", "tests.spatial_pack.metadata_vector_cases"],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, check=True, timeout=45)
        self.assertEqual(json.loads(result.stdout), encoded_vectors())

    def test_all_projection_variants(self) -> None:
        cases = vector_cases()
        location, settlement, region = cases["location"][2], cases["settlement"][2], cases["region"][2]
        assert isinstance(location, PackLocationAssembly)
        assert isinstance(settlement, PackSettlementAssembly)
        assert isinstance(region, WildernessRegionEntry)
        assembly = PackAssemblyInput(last_l0_mode="light", fine_cells_per_map_cell=1000,
            world_map_cells_per_tile=32, fine_cell_size=1, map_subsurface_depth=0, terrain_chunk_columns=32,
            tiles=(PackTileAssembly(gx=-2, gy=3, climate_status="coarse", wilderness_refine_status="partial",
                chunks=(PackChunkAssembly(cx=1, cy=4, refine_role=None),)),),
            locations=(location,), settlements=(settlement,), wilderness_regions=(region,))
        for name in ("header", "tile_coarse", "chunk", "location", "settlement", "region"):
            _, address, expected = cases[name]
            assert isinstance(address, (PackAssemblyHeaderAddress, PackTileMetadataAddress, PackChunkMetadataAddress,
                PackLocationMetadataAddress, PackSettlementMetadataAddress, PackRegionMetadataAddress))
            with self.subTest(name=name):
                actual = metadata_projection(assembly, address)
                self.assertEqual(actual, expected)
                self.assertEqual(metadata_value_fingerprint(address, actual), encoded_vectors()[name]["sha256"])

    def test_tuple_fields_affect_identity_and_tags_are_distinct(self) -> None:
        for name, value in vector_cases().items():
            original = content_digest(encode(value, PACK_METADATA_SCHEMA))
            with self.subTest(name=name):
                self.assertNotEqual(original, content_digest(encode(("different.domain", *value[1:]), PACK_METADATA_SCHEMA)))
            projection = value[2]
            if isinstance(projection, tuple):
                for index, field in enumerate(projection):
                    changed = (*projection[:index], field + 1 if type(field) is int else "changed", *projection[index + 1:])
                    with self.subTest(name=name, index=index):
                        self.assertNotEqual(original, content_digest(encode((*value[:2], changed), PACK_METADATA_SCHEMA)))

    def test_composition_rejects_id_collision(self) -> None:
        from app.dataModel.worldPack.encoding.pinBindings import PACK_PIN_SCHEMA
        merged = merge_manifests(PACK_METADATA_SCHEMA, PACK_PIN_SCHEMA)
        self.assertEqual(len(merged.entries), 16)
        conflict = CanonicalSchemaManifest(entries=(RegisteredTypeEntry(type_id=20401,
            python_type=PackTileMetadataAddress, kind=CanonicalTypeKind.RECORD),))
        with self.assertRaises(CanonicalEncodingError):
            merge_manifests(PACK_METADATA_SCHEMA, conflict)
