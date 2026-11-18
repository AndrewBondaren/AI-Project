"""Guard workload boundaries; these fixtures do not establish real-world performance."""

import unittest

from measure_wilderness_chunk_batch import fixture, execute
import test_preparation_wilderness_chunks as chunk_tests
from app.application.worldData.pack.preparation.metadataProjection import metadata_input_fingerprint, metadata_value_fingerprint
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataInputField, PackMetadataValueInputSelector
from app.dataModel.worldPack.preparation.addresses import PackChunkMetadataAddress, PackTileMetadataAddress
from app.dataModel.worldPack.meta.metadataAttribution import PackStoredAssemblyProvenance, PackMetadataGroup


class MeasurementScopeTests(unittest.TestCase):
    def test_full_rewrite_replaces_every_chunk_and_preserves_neighbor_tile(self) -> None:
        state, original_entries = fixture(2, None, False, True)
        usage = chunk_tests.WildernessChunkTransitionTests().usage("b")
        entries = []
        for item in original_entries:
            evidence = []
            for supplied in item.metadata_inputs:
                assert isinstance(supplied.input, PackMetadataValueInputSelector)
                value = item.part.address if supplied.input.field is PackMetadataInputField.ADDRESS else "scene"
                evidence.append(supplied.model_copy(update={"source_usage": usage,
                    "value_fingerprint": metadata_input_fingerprint(supplied.input, value)}))
            entries.append(item.model_copy(update={"refine_role": "scene", "metadata_inputs": tuple(evidence)}))
        bindings = tuple(PackStoredAssemblyProvenance(address=description.subject.address,
            provenance=state.parts[0].provenance, attribution=None) for description in state.metadata_dependencies)
        state = state.model_copy(update={"assembly_provenance": bindings})
        before = state.model_dump()
        result = execute(state, tuple(entries))

        self.assertEqual(len(entries), 1024)
        self.assertEqual(len(result.parts), 2048)
        self.assertEqual(tuple(part.address for part in result.parts), tuple(part.address for part in state.parts))
        self.assertEqual(len(set(part.address for part in result.parts)), 2048)
        for part, item in zip(result.parts[:1024], entries, strict=True):
            self.assertEqual(part.artifact, item.part.artifact)
            self.assertEqual(part.provenance, item.part.provenance.provenance)
            self.assertEqual(part.artifact.content_hash, "f" * 64)
        self.assertEqual(result.parts[1024:], state.parts[1024:])
        self.assertEqual(result.assembly.tiles[1], state.assembly.tiles[1])
        self.assertEqual(result.assembly.tiles[0].climate_status, state.assembly.tiles[0].climate_status)
        self.assertEqual(result.assembly.tiles[0].wilderness_refine_status, "partial")
        self.assertEqual(len(result.assembly.tiles[0].chunks), 1024)
        self.assertTrue(all(chunk.refine_role == "scene" for chunk in result.assembly.tiles[0].chunks))

        descriptions = {description.subject.address: description for description in result.metadata_dependencies}
        for item in entries:
            a = item.part.address
            address = PackChunkMetadataAddress(kind="chunk", gx=a.gx, gy=a.gy, cx=a.cx, cy=a.cy)
            description = descriptions[address]
            self.assertEqual(description.subject.value_fingerprint, metadata_value_fingerprint(address, (a.cx, a.cy, "scene")))
            self.assertEqual(tuple(use.group for use in description.dependencies),
                             (PackMetadataGroup.IDENTITY, PackMetadataGroup.REFINE_ROLE))
            self.assertEqual(tuple(use.source_usage for use in description.dependencies), (usage, usage))
        for old in state.metadata_dependencies:
            if (isinstance(old.subject.address, PackTileMetadataAddress)
                    or isinstance(old.subject.address, PackChunkMetadataAddress) and old.subject.address.gx == 1):
                self.assertEqual(descriptions[old.subject.address], old)
        tile = descriptions[PackTileMetadataAddress(kind="tile", gx=0, gy=3)]
        basis = tile.dependencies[2].basis
        assert basis is not None
        self.assertIsNone(basis.expected_chunks)
        self.assertEqual(basis.chunk_addresses, tuple(sorted((item.part.address for item in entries), key=lambda a: (a.gx, a.gy, a.cx, a.cy))))
        self.assertEqual(result.assembly_provenance, tuple(binding for binding in bindings
            if not (isinstance(binding.address, PackChunkMetadataAddress) and binding.address.gx == 0)))
        self.assertEqual(state.model_dump(), before)

    def test_full_l2_tile_uses_two_dimensional_grid(self) -> None:
        state, entries = fixture(0, None, False, False)
        addresses = tuple(item.part.address for item in entries)
        self.assertEqual(len(addresses), 1024)
        self.assertEqual({(address.gx, address.gy) for address in addresses}, {(0, 3)})
        self.assertEqual({(address.cx, address.cy) for address in addresses},
                         {(cx, cy) for cx in range(32) for cy in range(32)})
        result = execute(state, entries)
        self.assertEqual(len(result.assembly.tiles), 1)
        self.assertEqual(len(result.parts), 1024)

    def test_base_volume_is_independent_of_single_tile_update(self) -> None:
        for replacement in (False, True):
            with self.subTest(replacement=replacement):
                state, entries = fixture(1, 2, False, replacement)
                self.assertEqual(len(state.parts), 1024)
                self.assertEqual(len(entries), 2)
                self.assertEqual({item.part.address.gx for item in entries}, {0 if replacement else 1})
                before = state.model_dump()
                result = execute(state, entries)
                self.assertEqual(len(result.parts), 1024 if replacement else 1026)
                self.assertEqual(state.model_dump(), before)
                if not replacement:
                    self.assertEqual(result.parts[:1024], state.parts)

    def test_invalid_workloads_are_rejected(self) -> None:
        for args in ((0, 1025, False, False), (0, 0, False, False), (0, None, False, True), (-1, None, False, False)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                fixture(*args)

    def test_sparse_replacement_preserves_unselected_chunks(self) -> None:
        state, full = fixture(1, None, False, True)
        selected = (full[0], full[-1])
        changed = tuple(item.part.address for item in selected)
        result = execute(state, selected)
        self.assertEqual(len(result.parts), len(state.parts))
        self.assertEqual(result.assembly, state.assembly)
        self.assertEqual(result.metadata_dependencies, state.metadata_dependencies)
        for old, new in zip(state.parts, result.parts, strict=True):
            if old.address in changed:
                self.assertNotEqual(old.artifact, new.artifact)
            else:
                self.assertEqual(old, new)
