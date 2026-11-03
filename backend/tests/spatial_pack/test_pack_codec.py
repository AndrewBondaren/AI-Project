"""Golden TLV, in-memory domain admission and artifact contract boundaries."""
from dataclasses import replace
from hashlib import sha256
from unittest import TestCase
from unittest.mock import patch

from app.application.encoding.canonicalCodec import CanonicalEncodingError, encode
from app.application.worldData.generators.hydrology.encoding import packSchema
from app.application.worldData.generators.hydrology.encoding.packCodec import (
    decode_root, decode_shard, encode_root, encode_shard,
)
from app.application.worldData.generators.hydrology.encoding.packFormats import ROOT_FORMAT, SHARD_FORMAT, UnsupportedPackFormat
from app.application.worldData.generators.hydrology.encoding.packSchema import OPEN_WATER_PACK_SCHEMA_V1 as MANIFEST
from app.dataModel.artifacts.references import ArtifactKind
from app.dataModel.planning.identity.planRef import PlanRef
from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.worldData.generators.hydrology.encoding.sourceSchema import OPEN_WATER_SOURCE_SCHEMA_V1
from app.dataModel.hydrology.query.source import CanonicalOpenWaterSource, WaterMembershipRun
from app.dataModel.hydrology.pack.root import HydrologyPackRoot, HydrologyShardRef
from app.dataModel.hydrology.pack.shard import HydrologyPackShard
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from tests.spatial_pack.test_bounded_decode import tlv
from tests.spatial_pack.test_storage_schema import records


def raw_root(root, **overrides):
    values = vars(root) | overrides
    return tlv(7, encode((60001, tuple(values.items())), MANIFEST))


class PackCodecTests(TestCase):
    def test_v1_wire_ids_refuse_renamed_attribute_even_with_updated_shape_hash(self):
        root, _ = records()
        wire = encode_root(root)
        renamed = {("tiles" if key == "shards" else key): field
                   for key, field in HydrologyPackRoot.model_fields.items()}
        with patch.object(HydrologyPackRoot, "__pydantic_fields__", renamed), patch.dict(
                packSchema._STORAGE_SHAPES, {60001: packSchema._shape(HydrologyPackRoot)}):
            for operation in (lambda: encode_root(root), lambda: decode_root(wire, 1)):
                with self.assertRaisesRegex(CanonicalEncodingError, "wire field binding drift: 60001"):
                    operation()
        self.assertEqual(encode_root(decode_root(wire, 1)), wire)

    def test_source_replay_from_three_in_memory_tiles(self):
        catalog, _ = records()
        topology = catalog.topology.model_copy(update={"bounds": catalog.topology.bounds.model_copy(
            update=dict(x_min=-1, x_max=64, y_min=0, y_max=0))})
        shore = ((2, 0), MapCellHydrology.shore(HydrologyShoreKind.LAKE))
        def span(x0, x1):
            return CoverageSpan(y=0, x0=x0, x1=x1)
        def run(x0, x1):
            return WaterMembershipRun(y=0, x0=x0, x1=x1, body_uid=catalog.bodies[0].water_body_uid)
        def bed(spans):
            cells = tuple((x, 0) for row in spans for x in range(row.x0, row.x1))
            return FineSurfaceWindow(coverage=RegionCoverage(region_uid=catalog.coverage_region_uid, spans=spans),
                                     topology=topology, surface_z=tuple((xy, -2) for xy in cells),
                                     protected_cells=frozenset(c for c in cells if c == (-1, 0)))
        mapping = SourceBodyMapping(entries=(SourceBodyMappingEntry(source_uid="dry", body_uids=()),
                                             SourceBodyMappingEntry(source_uid="lake", body_uids=(run(0, 1).body_uid,))))
        payload = CanonicalOpenWaterSource(space=CoordinateSpace.WORLD_FINE_GRID, bed=bed((span(-1, 3), span(63, 65))),
            z_min=catalog.z_min, z_max=catalog.z_max, wet_runs=(run(-1, 1), run(63, 65)),
            bodies=catalog.bodies, unions=(), source_mapping=mapping, shore_rows=(shore,))
        def fingerprint(src, deps, issues):
            return output_fingerprint(src, deps, issues, OPEN_WATER_SOURCE_SCHEMA_V1)
        ref = catalog.source_ref.model_copy(update={
            "output_fingerprint": fingerprint(payload, catalog.dependencies, catalog.diagnostics)})
        original = PlanEnvelope[CanonicalOpenWaterSource](payload=payload, dependencies=catalog.dependencies,
                                                          diagnostics=catalog.diagnostics, ref=ref)
        descriptors, blobs = [], {}
        for tx, spans, runs, shores in ((-1, (span(-1, 0),), (run(-1, 0),), ()),
                (0, (span(0, 3), span(63, 64)), (run(0, 1), run(63, 64)), (shore,)),
                (1, (span(64, 65),), (run(64, 65),), ())):
            data = encode_shard(HydrologyPackShard(source_ref=ref, tx=tx, ty=0, bed=bed(spans),
                                                   wet_runs=runs, shore_rows=shores))
            key = sha256(data).hexdigest()
            blobs[key] = data
            artifact = catalog.shards[0].artifact.model_copy(update={"content_hash": key, "nbytes": len(data)})
            descriptors.append(HydrologyShardRef(tx=tx, ty=0, artifact=artifact))
        root = decode_root(encode_root(HydrologyPackRoot(**(vars(catalog) | dict(source_ref=ref, topology=topology,
            source_mapping=mapping, shards=tuple(descriptors))))), 1)
        def admitted_tiles(rows, artifacts):
            tiles = []
            for row in rows:
                tile = decode_shard(artifacts[row.artifact.content_hash], 1)
                if ((tile.tx, tile.ty, tile.source_ref) != (row.tx, row.ty, root.source_ref)
                        or tile.bed.topology != root.topology or tile.bed.coverage.region_uid != root.coverage_region_uid):
                    raise ValueError("foreign shard")
                tiles.append(tile)
            return tiles
        tiles = admitted_tiles(root.shards, blobs)
        with self.assertRaises(KeyError):
            admitted_tiles(root.shards, {root.shards[0].artifact.content_hash: blobs[root.shards[0].artifact.content_hash]})
        with self.assertRaisesRegex(ValueError, "foreign shard"):
            admitted_tiles(root.shards, blobs | {root.shards[1].artifact.content_hash: blobs[root.shards[0].artifact.content_hash]})

        # Test oracle for this row: restore adjacent coverage and same-body run boundaries.
        def merge(rows):
            result = []
            for row in rows:
                if result and result[-1].x1 > row.x0:
                    raise ValueError("overlapping shards")
                if result and result[-1].x1 == row.x0 and getattr(result[-1], "body_uid", None) == getattr(row, "body_uid", None):
                    result[-1] = result[-1].model_copy(update={"x1": row.x1})
                else:
                    result.append(row)
            return tuple(result)
        coverage = RegionCoverage(region_uid=root.coverage_region_uid,
                                  spans=merge(row for t in tiles for row in t.bed.coverage.spans))
        restored = CanonicalOpenWaterSource(space=CoordinateSpace.WORLD_FINE_GRID,
            bed=FineSurfaceWindow(coverage=coverage, topology=root.topology,
                surface_z=tuple(row for t in tiles for row in t.bed.surface_z),
                protected_cells=frozenset(c for t in tiles for c in t.bed.protected_cells)),
            z_min=root.z_min, z_max=root.z_max, wet_runs=merge(row for t in tiles for row in t.wet_runs),
            bodies=root.bodies, unions=root.unions, source_mapping=root.source_mapping,
            shore_rows=tuple(row for t in tiles for row in t.shore_rows))
        self.assertEqual(PlanEnvelope[CanonicalOpenWaterSource](ref=root.source_ref, payload=restored,
            dependencies=root.dependencies, diagnostics=root.diagnostics), original)
        self.assertEqual(fingerprint(restored, root.dependencies, root.diagnostics), ref.output_fingerprint)
        with self.assertRaisesRegex(ValueError, "overlapping shards"):
            merge(row for t in [tiles[0], *tiles] for row in t.bed.coverage.spans)
        bad_run = tiles[1].wet_runs[0].model_copy(update={"body_uid": "absent"})
        bad_tile = tiles[1].model_copy(update={"wet_runs": (bad_run, tiles[1].wet_runs[1])})
        bad_runs = merge(row for t in (tiles[0], decode_shard(encode_shard(bad_tile), 1), tiles[2]) for row in t.wet_runs)
        with self.assertRaisesRegex(ValueError, "wet run body is missing"):
            CanonicalOpenWaterSource(**(vars(restored) | {"wet_runs": bad_runs}))

    def test_existing_wire_reconstructed_exactly(self):
        root, shard = records()
        for obj, write, read, golden in (
                (root, encode_root, decode_root, "ef55146133c7271a635a006aa8d3667511d12bfe4bf114e52a74460cc9caadef"),
                (shard, encode_shard, decode_shard, "efc45c2be06b296c3190f3128aa657abda3858d978b2de5448d9eae0f68bb308")):
            with self.subTest(model=type(obj).__name__):
                data = write(obj)
                self.assertEqual(data, encode(obj, MANIFEST))
                self.assertEqual(sha256(data).hexdigest(), golden)
                decoded = read(data, 1)
                self.assertEqual(decoded, obj)
                self.assertEqual(write(decoded), data)

    def test_exact_top_level_and_versions(self):
        root, shard = records()
        for write, other, read in ((encode_shard, root, decode_shard), (encode_root, shard, decode_root)):
            with self.assertRaises(CanonicalEncodingError):
                write(other)
            with self.assertRaises(CanonicalEncodingError):
                read(encode(other, MANIFEST), 1)
            for bad in (False, True, 2, 1.0, "1"):
                with self.subTest(version=bad), self.assertRaises(UnsupportedPackFormat):
                    read(b"", bad)

    def test_pure_blob_contracts(self):
        payload = b"opaque"
        for contract, part in ((ROOT_FORMAT, "root"), (SHARD_FORMAT, "shard")):
            self.assertEqual(contract.key, f"hydrology.open_water.{part}.tlv")
            self.assertIs(contract.kind, ArtifactKind.BLOB)
            self.assertIs(contract.content_model, bytes)
            self.assertIsNone(contract.row_count)
            self.assertIs(contract.encode(payload), payload)
            self.assertIs(contract.decode(payload, 1), payload)
            with self.assertRaises(UnsupportedPackFormat):
                contract.decode(payload, 2)
            with self.assertRaises(CanonicalEncodingError):
                contract.encode(bytearray(payload))

    def test_no_partial_or_coerced_root(self):
        root, _ = records()
        for data in (raw_root(root, dependencies=root.dependencies[:-1]), raw_root(root, z_min=False),
                     raw_root(root, shards=root.shards*2)):
            with self.assertRaises(CanonicalEncodingError):
                decode_root(data, 1)
        issue = root.diagnostics[0]
        altered = issue.model_copy(update={"issue": replace(issue.issue, code="UNKNOWN_EMISSION")})
        with self.assertRaisesRegex(CanonicalEncodingError, "diagnostic pair"):
            decode_root(raw_root(root, diagnostics=(altered,)), 1)
        with self.assertRaisesRegex(CanonicalEncodingError, "diagnostic pair"):
            encode_root(root.model_copy(update={"diagnostics": (altered,)}))

    def test_bad_record_roster_and_enum_refuse_before_constructors(self):
        root, _ = records()
        items = tuple(vars(root).items())
        correct = encode(root, MANIFEST)
        # Change only the BLOB enum value, preserving the length of every wrapper.
        wrong_enum = correct.replace(encode("blob", MANIFEST), encode("lava", MANIFEST))
        self.assertNotEqual(wrong_enum, correct)
        cases = [tlv(7, encode((60001, roster), MANIFEST))
                 for roster in (items[:-1], items+(items[-1],), items[:1]+(items[0],)+items[2:])]
        with patch.object(PlanRef, "model_validate", side_effect=AssertionError):
            for wire in [*cases, wrong_enum]:
                with self.subTest(size=len(wire)), self.assertRaises(CanonicalEncodingError):
                    decode_root(wire, 1)

    def test_oversized_encoding_refuses_whole_shard(self):
        _, shard = records()
        shore = MapCellHydrology.shore(HydrologyShoreKind.LAKE, connection_edge_uid="x" * (4 << 20))
        candidate = HydrologyPackShard(**(vars(shard) | {"shore_rows": (((2, -1), shore),)}))
        with self.assertRaisesRegex(CanonicalEncodingError, "byte limit"):
            encode_shard(candidate)

    def test_hard_byte_and_shard_field_caps(self):
        _, shard = records()
        # Bypass the model constructor to exercise the decoder's collection guard.
        values = vars(shard) | {"wet_runs": shard.wet_runs * 4097}
        data = tlv(7, encode((60003, tuple(values.items())), MANIFEST))
        with patch.object(PlanRef, "model_validate", side_effect=AssertionError):
            with self.assertRaisesRegex(CanonicalEncodingError, "collection limit"):
                decode_shard(data, 1)
            for read, limit in ((decode_shard, 4 << 20), (decode_root, 16 << 20)):
                with self.assertRaisesRegex(CanonicalEncodingError, "byte limit"):
                    read(bytes(limit + 1), 1)
