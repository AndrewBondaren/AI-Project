"""Storage representations tested entirely in memory."""
import subprocess
import sys
from hashlib import sha256
from textwrap import dedent
from unittest import TestCase
from unittest.mock import patch
from typing import TypeAliasType

from app.encoding.canonicalCodec import CanonicalEncodingError, decode, encode
from app.application.worldData.generators.hydrology.encoding import packSchema
from app.application.worldData.generators.hydrology.planning.assembly.final.publication import NATIVE_FINAL
from app.application.worldData.generators.hydrology.planning.assembly.nativeRoutesPublication import NATIVE_ROUTES_CONTRACT
from app.application.worldData.generators.hydrology.water.planning.fine.publication import FINE_WATER_CONTRACT
from app.application.worldData.generators.terrain.planning.preWater.terrainWindowJob import PRE_WATER_WINDOW
from app.application.worldData.generators.terrain.relief.planning.river.publication import NATIVE_RIVER_RELIEF
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.hydrology.pack.root import HydrologyPackRoot, HydrologyShardRef
from app.dataModel.hydrology.pack.shard import HydrologyPackShard
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.registryKey import RegistryKey
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.surfacePlanning.surfacePlanBindings import geo_surface_plan_binding
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.natural.preparedTerrain import NATURAL_TERRAIN_CONTRACT
from tests.geo1.canonical_source.test_source_models import source, union
from app.application.worldData.generators.hydrology.encoding import sourceBindings
from tests.spatial_pack.test_source_schema import diagnostics, ref


def dependencies():
    metadata = (
        ("fine_water", FINE_WATER_CONTRACT), ("hydrology_routes", NATIVE_ROUTES_CONTRACT),
        ("native_final", NATIVE_FINAL), ("pre_water_surface", PRE_WATER_WINDOW),
        ("prepared_natural", NATURAL_TERRAIN_CONTRACT), ("river_relief", NATIVE_RIVER_RELIEF),
        ("water_placement", geo_surface_plan_binding(SurfacePlanSlot.WATER_PLACEMENT).metadata),
    )
    result = []
    for slot, contract in metadata:
        base = ref(contract.id)
        key = base.key.model_copy(update=dict(schema_version=contract.schema_version,
                                              algorithm_version=contract.algorithm_version))
        result.append(PlanDependency(slot=slot, ref=base.model_copy(update={"key": key})))
    return tuple(result)


def records():
    data = source()
    artifact = ArtifactRef(kind=ArtifactKind.BLOB, format_key="hydrology.open_water.shard.tlv",
                           format_version=1, content_hash="a" * 64, nbytes=100)
    descriptor = HydrologyShardRef(tx=0, ty=-1, artifact=artifact)
    root = HydrologyPackRoot(source_ref=ref(), dependencies=dependencies(), diagnostics=diagnostics(),
                             topology=data.bed.topology, coverage_region_uid=data.bed.coverage.region_uid,
                             z_min=data.z_min, z_max=data.z_max, bodies=data.bodies, unions=data.unions,
                             source_mapping=data.source_mapping, shards=(descriptor,))
    shard = HydrologyPackShard(source_ref=root.source_ref, tx=0, ty=-1, bed=data.bed,
                               wet_runs=data.wet_runs, shore_rows=data.shore_rows)
    return root, shard


class StorageSchemaTests(TestCase):
    def test_storage_bindings_reject_missing_extra_and_substituted_record(self):
        class OtherShard(HydrologyPackShard):
            pass

        manifest = packSchema.OPEN_WATER_PACK_SCHEMA_V1
        entry = next(entry for entry in manifest.entries if entry.python_type is HydrologyPackShard)
        remaining = tuple(item for item in manifest.entries if item is not entry)
        for label, entries in (
            ("missing", remaining),
            ("extra", (*manifest.entries, entry.model_copy(update={"type_id": 65000, "python_type": OtherShard}))),
            ("substituted", (*remaining, entry.model_copy(update={"python_type": OtherShard}))),
        ):
            malformed = type(manifest)(entries=entries)
            with self.subTest(label=label), patch.object(packSchema, "OPEN_WATER_PACK_SCHEMA_V1", malformed):
                with self.assertRaisesRegex(CanonicalEncodingError, "storage v1 binding drift"):
                    packSchema.require_pack_schema_v1()

    def test_dict_binding_rejected_by_schema_before_reconstruction(self):
        root, _ = records()
        manifest = packSchema.OPEN_WATER_PACK_SCHEMA_V1
        entries = tuple(dict(entry) if entry.type_id == 60005 else entry for entry in manifest.entries)
        malformed = manifest.model_copy(update={"entries": entries})
        with patch.object(packSchema, "OPEN_WATER_PACK_SCHEMA_V1", malformed):
            for check, args in ((packSchema.require_pack_schema_v1, ()),
                                (packSchema.require_pack_record_v1, (root,))):
                with self.subTest(check=check.__name__), self.assertRaisesRegex(CanonicalEncodingError, "binding drift"):
                    check(*args)

    def test_equal_but_mistyped_binding_refused_before_encode(self):
        root, _ = records()
        manifest = packSchema.OPEN_WATER_PACK_SCHEMA_V1
        for update in ({"kind": "record"}, {"type_id": 60005.0}):
            entries = tuple(entry.model_copy(update=update) if entry.type_id == 60005 else entry
                            for entry in manifest.entries)
            malformed = manifest.model_copy(update={"entries": entries})
            with patch.object(packSchema, "OPEN_WATER_PACK_SCHEMA_V1", malformed):
                for check, args in ((packSchema.require_pack_schema_v1, ()),
                                    (packSchema.require_pack_record_v1, (root,))):
                    with self.subTest(update=update, check=check.__name__), self.assertRaises(CanonicalEncodingError):
                        check(*args)

    def test_artifact_kind_effective_wire_value_is_locked(self):
        root, _ = records()
        manifest = packSchema.OPEN_WATER_PACK_SCHEMA_V1
        wire = encode(root, manifest)
        artifact_bytes = encode(root.shards[0].artifact, manifest)
        self.assertEqual(sha256(artifact_bytes).hexdigest(),
                         "317b6f08b0f450c2d118f67eb90bbc1619d261e6baf9554482f2fd24758c3d25")
        override = property(lambda kind: "binary" if kind is ArtifactKind.BLOB else kind.value)
        with patch.object(ArtifactKind, "wire_value", override, create=True):
            with self.assertRaisesRegex(CanonicalEncodingError, "shape drift: 60006"):
                packSchema.require_pack_schema_v1()
            with self.assertRaisesRegex(CanonicalEncodingError, "shape drift: 60006"):
                packSchema.require_pack_record_v1(root)
        self.assertEqual(decode(wire, HydrologyPackRoot, manifest), root)

    def test_duplicate_pack_binding_is_refused_at_admission(self):
        root, _ = records()
        manifest = packSchema.OPEN_WATER_PACK_SCHEMA_V1
        duplicate = manifest.model_copy(update={"entries": manifest.entries + (manifest.entries[-1],)})
        with patch.object(packSchema, "OPEN_WATER_PACK_SCHEMA_V1", duplicate):
            with self.assertRaisesRegex(CanonicalEncodingError, "binding drift"):
                packSchema.require_pack_schema_v1()
            with self.assertRaisesRegex(CanonicalEncodingError, "binding drift"):
                packSchema.require_pack_record_v1(root)

    def test_branded_liquid_key_requires_nonempty_wire_string(self):
        root, _ = records()
        for name in ("", "fresh-water"):
            body = WaterBody(**(vars(root.bodies[0]) | {"liquid": RegistryKey(name)}))
            candidate = HydrologyPackRoot(**(vars(root) | {"bodies": (body,)}))
            if not name:
                with self.assertRaises(CanonicalEncodingError):
                    packSchema.require_pack_record_v1(candidate)
            else:
                packSchema.require_pack_record_v1(candidate)
                manifest = packSchema.OPEN_WATER_PACK_SCHEMA_V1
                self.assertEqual(candidate, decode(encode(candidate, manifest), HydrologyPackRoot, manifest))

    def test_storage_strings_require_lossless_utf8(self):
        root, _ = records()
        for text in (chr(0xD800), "Р В РЎвЂўР В Р’В·Р В Р’ВµР РЋР вЂљР В РЎвЂўРЎР‚РЎСџР Р‰Р вЂ°"):
            body = WaterBody(**(vars(root.bodies[0]) | {"location_uid": text}))
            candidate = HydrologyPackRoot(**(vars(root) | {"bodies": (body,)}))
            if text == chr(0xD800):
                with self.assertRaises(CanonicalEncodingError):
                    packSchema.require_pack_record_v1(candidate)
            else:
                packSchema.require_pack_record_v1(candidate)
                manifest = packSchema.OPEN_WATER_PACK_SCHEMA_V1
                self.assertEqual(candidate, decode(encode(candidate, manifest), HydrologyPackRoot, manifest))

    def test_recursive_storage_alias_drift_terminates(self):
        script = dedent("""
            from unittest.mock import patch
            from app.application.worldData.generators.hydrology.encoding import packSchema as schema
            type FormatVersion = int | tuple[FormatVersion, ...]
            with patch.object(schema.ArtifactRef.model_fields['format_version'], 'annotation', FormatVersion):
                try:
                    schema.require_pack_schema_v1()
                except schema.CanonicalEncodingError:
                    pass
                else:
                    raise AssertionError('recursive alias admitted')
        """)
        subprocess.run([sys.executable, "-B", "-c", script], timeout=8, check=True)

    def test_admission_rejects_unregistered_nested_body_class(self):
        class DerivedBody(WaterBody):
            pass

        root, _ = records()
        body = DerivedBody(**vars(root.bodies[0]))
        candidate = root.model_copy(update={"bodies": (body,)})
        with self.assertRaises(CanonicalEncodingError):
            packSchema.require_pack_record_v1(candidate)

    def test_roster_and_exact_storage_shapes(self):
        root, shard = records()
        for item in (root, shard):
            packSchema.require_pack_record_v1(item)
            manifest = packSchema.OPEN_WATER_PACK_SCHEMA_V1
            wire = encode(item, manifest)
            decoded = decode(wire, type(item), manifest)
            self.assertEqual(decoded, item)
            if isinstance(decoded, HydrologyPackRoot):
                self.assertEqual(decoded.diagnostics, diagnostics())
                for actual, expected in zip(decoded.diagnostics, diagnostics(), strict=True):
                    self.assertIs(type(actual), type(expected))
                    self.assertIs(type(actual.issue), type(expected.issue))
        source_entries = sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1.entries
        storage = {e.type_id: e.python_type for e in packSchema.OPEN_WATER_PACK_SCHEMA_V1.entries}
        for entry in source_entries:
            self.assertIs(storage.pop(entry.type_id), entry.python_type)
        self.assertEqual(storage, {60001: HydrologyPackRoot, 60002: HydrologyShardRef, 60003: HydrologyPackShard,
                                   60005: ArtifactRef, 60006: ArtifactKind})
        replaced = tuple[tuple[TypeAliasType("FineXY", str), MapCellHydrology], ...]
        with patch.object(HydrologyPackShard.model_fields["shore_rows"], "annotation", replaced):
            with self.assertRaises(CanonicalEncodingError):
                packSchema.require_pack_schema_v1()
        self.assertEqual(tuple(HydrologyPackRoot.model_fields), (
            "source_ref", "dependencies", "diagnostics", "topology", "coverage_region_uid", "z_min", "z_max",
            "bodies", "unions", "source_mapping", "shards"))
        self.assertEqual(tuple(HydrologyPackShard.model_fields), ("source_ref", "tx", "ty", "bed", "wet_runs", "shore_rows"))
        with patch.object(HydrologyShardRef.model_fields["tx"], "default", 0):
            with self.assertRaisesRegex(CanonicalEncodingError, "shape drift"):
                packSchema.require_pack_schema_v1()
        with self.assertRaises(CanonicalEncodingError):
            packSchema.require_pack_record_v1(root.source_ref)

    def test_v1_descriptor_limits(self):
        root, _ = records()
        row = root.shards[0]
        for changes in (dict(kind=ArtifactKind.SQL_ROWS, row_count=1), dict(row_count=0),
                        dict(format_version=2), dict(format_key="hydrology.open_water.root.tlv"),
                        dict(nbytes=0), dict(nbytes=4194305), dict(nbytes=True)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                HydrologyShardRef(tx=0, ty=-1, artifact=row.artifact.model_copy(update=changes))
        HydrologyShardRef(tx=0, ty=-1, artifact=row.artifact.model_copy(update={"nbytes": 4194304}))

    def test_invalid_catalog_and_strict_nested_graph(self):
        root, _ = records()
        dep = root.dependencies[0]
        for changes in (dict(shards=root.shards * 2), dict(dependencies=root.dependencies[::-1]),
                        dict(shards=root.shards * 65537),
                        dict(shards=(root.shards[0].model_copy(update={"ty": 0}),)),
                        dict(dependencies=(PlanDependency(slot=dep.slot, ref=ref(dep.slot)),) + root.dependencies[1:]),
                        dict(z_min=True), dict(bodies=[]), dict(bodies=()), dict(source_ref=ref("hydrology.native_final")),
                        dict(bodies=(root.bodies[0].model_copy(update={"z_water_level": True}),)),
                        dict(topology=root.topology.model_dump()), dict(source_mapping=None), dict(extra=1)):
            with self.subTest(fields=tuple(changes)), self.assertRaises(ValueError):
                HydrologyPackRoot(**(vars(root) | changes))
        values = dict(vars(root))
        del values["diagnostics"]
        with self.assertRaises(ValueError):
            HydrologyPackRoot(**values)

    def test_local_observation_and_tile_bounds(self):
        root, shard = records()
        run = shard.wet_runs[0]
        dry = HydrologyPackShard(**(vars(shard) | {"wet_runs": ()}))
        self.assertTrue(dry.bed.surface_z)
        self.assertEqual(HydrologyPackRoot(**(vars(root) | {"shards": ()})).shards, ())
        for changes in (dict(tx=True), dict(ty=0), dict(wet_runs=[run]), dict(wet_runs=(run, run)),
                        dict(wet_runs=(run.model_copy(update={"x1": 2**40}),)), dict(wet_runs=(run,) * 4097)):
            with self.subTest(fields=tuple(changes)), self.assertRaises(ValueError):
                HydrologyPackShard(**(vars(shard) | changes))

    def test_catalog_physical_ancestry_and_world_binding(self):
        root, _ = records()
        lake = root.bodies[0].model_copy(update={"parent_system_uid": "basin"})
        valid = vars(root) | {"bodies": (lake,), "unions": (union("basin"),)}
        HydrologyPackRoot(**valid)
        for invalid in (union("basin", members=()), union("basin", parent="basin", children=("basin",)),
                        union("basin", level=1)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                HydrologyPackRoot(**(valid | {"unions": (invalid,)}))
        first = root.dependencies[0]
        other = first.ref.model_copy(update={"key": first.ref.key.model_copy(update={"world_uid": "other"})})
        with self.assertRaises(ValueError):
            HydrologyPackRoot(**(valid | {"dependencies": (first.model_copy(update={"ref": other}),)
                                           + root.dependencies[1:]}))

    def test_diagnostics_use_source_v1_admission(self):
        root, _ = records()
        issue = root.diagnostics[0]
        invalid = next(value for value in PlanDiagnosticDisposition if value != issue.disposition)
        changed = issue.model_copy(update={"disposition": invalid})
        with self.assertRaises(CanonicalEncodingError):
            packSchema.require_pack_record_v1(root.model_copy(update={"diagnostics": (changed,)}))
