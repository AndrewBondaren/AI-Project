"""Pure manifest version admission and legacy writer guard boundaries."""
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.application.worldData.pack import WorldPackPaths, WorldPackReader, WorldPackWriter
from app.application.worldData.pack.encoding.packManifestCodec import (
    decode_manifest, encode_candidate_manifest, encode_legacy_manifest,
)
from app.application.worldData.pack.io.packManifestStore import PackManifestStore
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.worldPack.meta.spatial.domainRoot import SpatialDatasetKind, SpatialDomainRootRef
from app.dataModel.registryKey import RegistryKey
from app.dataModel.worldPack.meta.wildernessRegionEntry import RegionIndexBounds, WildernessRegionEntry, WildernessRegionStatus
from app.dataModel.worldPack.meta.worldPackManifest import TileManifestEntry, WorldPackManifest


def payload(**fields):
    return json.dumps({"world_uid": "w", **fields}).encode()


def descriptor():
    return dict(domain="hydrology_open_water", root=dict(kind="blob", format_key="hydrology.open_water.root.tlv",
                format_version=1, content_hash="a"*64, nbytes=128))


class ManifestVersionsTests(TestCase):
    def test_candidate_checks_both_json_integer_readers_before_serialization(self):
        candidate = decode_manifest(payload(pack_version="2.0.0", spatial_roots=[]))
        original_limit = sys.get_int_max_str_digits()
        try:
            for limit in (4300, 0, 640):
                sys.set_int_max_str_digits(limit)
                digits = min(limit or 4300, 4300)
                for value in (10**(digits-1), -(10**(min(digits, 4299)-1))):
                    valid = candidate.model_copy(update={"world_map_cells": value})
                    self.assertEqual(decode_manifest(encode_candidate_manifest(valid)), valid)
                for value in (10**digits, -(10**min(digits, 4299))):
                    invalid = candidate.model_copy(update={"world_map_cells": value})
                    with self.subTest(limit=limit, negative=value < 0), patch.object(
                            WorldPackManifest, "model_dump_json", side_effect=AssertionError), self.assertRaises(ValueError):
                        encode_candidate_manifest(invalid)
        finally:
            sys.set_int_max_str_digits(original_limit)

    def test_candidate_checks_utf8_before_serialization(self):
        candidate = decode_manifest(payload(pack_version="2.0.0", spatial_roots=[], world_map_cells=1))
        for field in ("world_uid", "registry_hash"):
            invalid = candidate.model_copy(update={field: chr(0xD800)})
            with self.subTest(field=field), patch.object(
                    WorldPackManifest, "model_dump_json", side_effect=AssertionError), self.assertRaises(ValueError):
                encode_candidate_manifest(invalid)
        nested = candidate.model_copy(update={"tiles": [TileManifestEntry(gx=0, gy=0, world_map_path=chr(0xDFFF))]})
        with patch.object(WorldPackManifest, "model_dump_json", side_effect=AssertionError), self.assertRaises(ValueError):
            encode_candidate_manifest(nested)
        valid = candidate.model_copy(update={"world_uid": chr(0x1F30D)})
        self.assertEqual(decode_manifest(encode_candidate_manifest(valid)), valid)

    def test_candidate_refuses_undeclared_tile_subclass_before_serialization(self):
        class ExtendedTile(TileManifestEntry):
            marker: str

        candidate = decode_manifest(payload(pack_version="2.0.0", spatial_roots=[]))
        candidate.tiles.append(ExtendedTile(gx=1, gy=0, marker="keep"))
        with patch.object(WorldPackManifest, "model_dump_json", side_effect=AssertionError), self.assertRaises(ValueError):
            encode_candidate_manifest(candidate)

    def test_candidate_refuses_empty_branded_keys_before_serialization(self):
        candidate = decode_manifest(payload(pack_version="2.0.0", spatial_roots=[]))
        for entry, current in (("", "forest"), ("forest", ""), ("forest", "forest")):
            candidate.wilderness_region_entries[:] = [WildernessRegionEntry(
                region_uid="r", entry_type=RegistryKey(entry), current_type=RegistryKey(current),
                bbox=RegionIndexBounds(x_min=0, y_min=0, x_max=1, y_max=1), status=WildernessRegionStatus.DECLARED)]
            if entry and current:
                self.assertEqual(decode_manifest(encode_candidate_manifest(candidate)), candidate)
            else:
                with self.subTest(entry=entry, current=current), patch.object(
                        WorldPackManifest, "model_dump_json", side_effect=AssertionError), self.assertRaises(ValueError):
                    encode_candidate_manifest(candidate)

    def test_candidate_revalidates_nested_pojos_before_serializing(self):
        wire = payload(pack_version="2.0.0", spatial_roots=[descriptor()],
                       tiles=[{"gx": 1, "gy": 0, "chunks": [{"cx": 2, "cy": 3}]}])
        candidate = decode_manifest(wire)
        self.assertEqual(decode_manifest(encode_candidate_manifest(candidate)), candidate)
        tile, = candidate.tiles
        for broken in (tile.model_copy(update={"gx": "bad"}),
                       tile.model_copy(update={"chunks": [tile.chunks[0].model_copy(update={"cx": True})]})):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                encode_candidate_manifest(candidate.model_copy(update={"tiles": [broken]}))
        tile.chunks.append(42)
        with self.assertRaises(ValueError):
            encode_candidate_manifest(candidate)

    def test_v2_strict_numeric_fields_preserve_v1_decoding(self):
        volume = dict(x0=0, y0=0, z0=0, x1="1", y1=1, z1=1)
        for fields in ({"world_map_cells": "12"}, {"tiles": [{"gx": True, "gy": 0}]},
                       {"location_terrain_entries": [{"location_uid": "a", "territory_volume": volume}]}):
            with self.subTest(fields=fields):
                self.assertEqual(decode_manifest(payload(**fields)).pack_version, "1.0.0")
                with self.assertRaises(ValueError):
                    decode_manifest(payload(pack_version="2.0.0", spatial_roots=[], **fields))
        valid = decode_manifest(payload(pack_version="2.0.0", spatial_roots=[], world_map_cells=12,
                                        tiles=[{"gx": 1, "gy": 0}]))
        self.assertEqual((valid.world_map_cells, valid.tiles[0].gx), (12, 1))

    def test_v2_json_converts_nested_wire_values_and_requires_known_top_level_fields(self):
        region = dict(region_uid="r", entry_type="forest", current_type="forest", status="declared",
                      bbox=dict(x_min=0, x_max=1, y_min=0, y_max=1))
        candidate = decode_manifest(payload(pack_version="2.0.0", spatial_roots=[descriptor()],
                                            wilderness_region_entries=[region]))
        self.assertEqual(decode_manifest(encode_candidate_manifest(candidate)), candidate)
        with self.assertRaises(ValueError):
            decode_manifest(payload(pack_version="2.0.0", spatial_roots=[], unknown=True))
        self.assertEqual(decode_manifest(payload(unknown=True)).pack_version, "1.0.0")

    def test_v2_requires_typed_objects_before_candidate_encoding(self):
        candidate = decode_manifest(payload(pack_version="2.0.0", spatial_roots=[descriptor()]))
        self.assertIs(type(candidate), WorldPackManifest)
        self.assertIs(type(candidate.spatial_roots), tuple)
        row, = candidate.spatial_roots
        self.assertIs(type(row), SpatialDomainRootRef)
        self.assertIs(type(row.root), ArtifactRef)
        for name, rows in (
            ("list", [row]),
            ("descriptor dict", (row.model_dump(mode="python"),)),
            ("artifact dict", (row.model_copy(update={"root": row.root.model_dump(mode="python")}),)),
        ):
            forged = candidate.model_copy(update={"spatial_roots": rows})
            with self.subTest(name=name), self.assertRaises(ValueError):
                encode_candidate_manifest(forged)
        with self.assertRaises(ValueError):
            encode_candidate_manifest(candidate.model_copy(update={"tiles": [{"gx": 0, "gy": 0}]}))

    def test_versions_and_malformed_wire(self):
        legacy = decode_manifest(payload())
        self.assertEqual((legacy.pack_version, legacy.spatial_roots), ("1.0.0", ()))
        self.assertNotIn("spatial_roots", json.loads(encode_legacy_manifest(legacy)))
        for data in (payload(spatial_roots=[]), payload(pack_version="1.0.0", spatial_roots=None),
                     payload(pack_version="2.0.0"), payload(pack_version="2.0.0", spatial_roots=None),
                     *(payload(pack_version=v) for v in ("1.0.1", "2.1.0", "3.0.0", None, 2, [])),
                     b'{"world_uid":"w","world_uid":"w"}', b'{"extra":{"a":0,"a":1},"world_uid":"w"}',
                     b'{"world_uid":"w","extra":NaN}', b'[]', b'not json'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                decode_manifest(data)

    def test_candidate_round_trip_and_invalid_descriptors(self):
        row = descriptor()
        for rows in ([], [row]):
            candidate = decode_manifest(payload(pack_version="2.0.0", spatial_roots=rows))
            self.assertEqual(decode_manifest(encode_candidate_manifest(candidate)), candidate)
            if rows:
                self.assertIs(candidate.spatial_roots[0].domain, SpatialDatasetKind.HYDROLOGY_OPEN_WATER)
                self.assertIs(candidate.spatial_roots[0].root.kind, ArtifactKind.BLOB)
            with self.assertRaises(ValueError):
                encode_legacy_manifest(candidate)
        for rows in ([row, row], [row | {"domain": "other"}], [row | {"extra": 0}],
                     *([row | {"root": row["root"] | change}] for change in (
                         {"kind": "sql_rows", "row_count": 0}, {"format_key": "hydrology.open_water.shard.tlv"},
                         {"format_version": 2}, {"nbytes": "1"}, {"format_version": True}, {"nbytes": 0}))):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                decode_manifest(payload(pack_version="2.0.0", spatial_roots=rows))

    def test_legacy_guard_precedes_directory_counters_hash_and_store(self):
        candidate = decode_manifest(payload(pack_version="2.0.0", spatial_roots=[descriptor()]))
        with TemporaryDirectory() as tmp:
            paths = WorldPackPaths(Path(tmp) / "pack", "w")
            path = paths.manifest_path()
            store = PackManifestStore()
            with self.assertRaises(ValueError):
                WorldPackWriter(paths, manifest=candidate)
            with self.assertRaises(ValueError):
                store.save(path, candidate)
            self.assertFalse(paths.root.exists())
            writer = WorldPackWriter(paths)
            writer.manifest.world_map_cells = 99
            writer.manifest.pack_version = "2.0.0"
            with self.assertRaises(ValueError):
                writer.save_manifest()
            self.assertEqual(writer.manifest.world_map_cells, 99)
            self.assertIsNone(writer.manifest.content_hash)
            self.assertFalse(path.exists())
            writer.manifest.pack_version = "1.0.0"
            wire = encode_candidate_manifest(candidate)
            path.write_bytes(wire)
            self.assertEqual(WorldPackReader(paths).load_manifest(), candidate)
            with patch.object(paths, "ensure_dirs", side_effect=AssertionError), patch(
                    "tempfile.NamedTemporaryFile", side_effect=AssertionError):
                for operation in (lambda: WorldPackWriter(paths), lambda: WorldPackWriter(paths, manifest=writer.manifest),
                                  writer.save_manifest, lambda: store.save(path, writer.manifest)):
                    with self.assertRaises(ValueError):
                        operation()
            self.assertEqual(writer.manifest.world_map_cells, 99)
            self.assertIsNone(writer.manifest.content_hash)
            self.assertEqual(path.read_bytes(), wire)

    def test_v1_hash_still_uses_original_document(self):
        with TemporaryDirectory() as tmp:
            paths = WorldPackPaths(Path(tmp), "w")
            writer = WorldPackWriter(paths)
            writer.save_manifest()
            saved = json.loads(paths.manifest_path().read_bytes())
            self.assertNotIn("spatial_roots", saved)
            saved["content_hash"] = None
            expected = hashlib.sha256(json.dumps(saved, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            self.assertEqual(writer.manifest.content_hash, expected)
            with self.assertRaises(ValueError):
                encode_candidate_manifest(WorldPackManifest(world_uid="w"))
