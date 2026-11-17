"""Public chunk writes: transitions, provenance and aggregated refusal contracts."""

import unittest
from unittest.mock import patch

from app.application.worldData.pack.preparation.packPreparationService import PackPreparationService
from app.application.worldData.pack.preparation.errors import PackPreparationFailure
from app.dataModel.worldPack.preparation.errors import PackPreparationIssue
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.application.worldData.pack.preparation.metadataProjection import metadata_input_fingerprint, metadata_value_fingerprint
from app.dataModel.artifacts.references import ArtifactRef, ArtifactKind, ArtifactFormatRegistry
from app.dataModel.registryKey import RegistryKey
from app.dataModel.sourceVersioning.sourceCaptureRef import SourceCaptureRef
from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection
from app.dataModel.worldPack.meta.metadataAttribution import PackMetadataAttribution, PackMetadataGroupAdmission
from app.dataModel.worldPack.preparation.addresses import PackChunkAddress, PackTileMetadataAddress, PackChunkMetadataAddress
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput
from app.dataModel.worldPack.preparation.operations import PackWildernessChunkWrite, PackWildernessChunksInput, PackWildernessChunkInput
from app.dataModel.worldPack.preparation.parts import PackWildernessChunkPartInput
from app.dataModel.worldPack.preparation.provenance import PackNewPartProvenance, PackStoredProvenance
from app.dataModel.worldPack.preparation.state import PackPreparationState
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataInputEvidence, PackMetadataInputField, PackMetadataValueInputSelector
from app.dataModel.worldPack.meta.metadataAttribution import PackMetadataGroup, PackStoredAssemblyProvenance
from app.dataModel.worldPack.meta.fineTerrainStorageFormat import FINE_TERRAIN_FORMAT_KEY, FINE_TERRAIN_STORAGE_VERSION
from app.dataModel.worldPack.meta.worldPackManifest import ChunkRefineRole
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.core.constants import FINE_CELL_SIZE


class WildernessChunkTransitionTests(unittest.TestCase):
    def test_stored_status_basis_must_match_provisional_basis(self) -> None:
        initial = self.apply(self.state, self.item(5))
        tile = PackTileMetadataAddress(kind="tile", gx=-2, gy=3)
        description = next(entry for entry in initial.metadata_dependencies if entry.subject.address == tile)
        status = description.dependencies[2]
        assert status.basis is not None
        selection = SourceProofSelection(proof_fingerprint="a" * 64, dependency_indices=())
        for expected in (None, 2):
            binding = PackStoredAssemblyProvenance(address=tile, provenance=self.proof,
                attribution=PackMetadataAttribution(groups=tuple(PackMetadataGroupAdmission(
                    group=use.group, selection=selection,
                    basis=status.basis.model_copy(update={"expected_chunks": expected})
                    if use.group is PackMetadataGroup.WILDERNESS_REFINE_STATUS else use.basis)
                    for use in description.dependencies)))
            state = initial.model_copy(update={"assembly_provenance": (binding,)})
            before = state.model_dump()
            for single in (False, True):
                with self.subTest(expected=expected, single=single):
                    result = self.single(state, self.item(5)) if single else self.apply(state, self.item(5))
                    self.assertEqual(result.assembly_provenance, (binding,) if expected is None else ())
                    self.assertEqual(result.metadata_dependencies, initial.metadata_dependencies)
                    self.assertEqual(state.model_dump(), before)
            self.assertEqual(self.apply(state), state)

    def setUp(self) -> None:
        self.state = PackPreparationState(parts=(), assembly=PackAssemblyInput(last_l0_mode="light",
            fine_cells_per_map_cell=1000, world_map_cells_per_tile=32, fine_cell_size=FINE_CELL_SIZE,
            map_subsurface_depth=0, terrain_chunk_columns=32, tiles=(), locations=(), settlements=(), wilderness_regions=()),
            assembly_provenance=(), metadata_dependencies=(), base_publication=WorldPublicationRef(world_uid="world",
                publication_id="base", pack_hash=None, snapshot_head=None, active_timeline_id=None, gameplay_started=False))
        self.proof = PackStoredProvenance(source_proof=SourceDurableProof(schema_version=1, world_uid="world", uses=()), planning=())

    def usage(self, marker: str) -> SourceProofInput:
        return SourceProofInput(world_uid="world", uses=(SourceCaptureUsage(capture=SourceCaptureRef(world_uid="world",
            artifact=ArtifactRef(kind=ArtifactKind.SQL_ROWS, format_key=RegistryKey[ArtifactFormatRegistry]("source.capture-witness"), format_version=1,
                                 content_hash=marker * 64, nbytes=1, row_count=1)),
            dependencies=SourceDependencySet(objects=(), collections=())),))

    def item(self, cx: int, marker: str = "a", gx: int = -2, role: ChunkRefineRole | None = None) -> PackWildernessChunkWrite:
        address = PackChunkAddress(kind="wilderness_chunk", gx=gx, gy=3, cx=cx, cy=4)
        address_slot = PackMetadataValueInputSelector(kind="value", field=PackMetadataInputField.ADDRESS)
        role_slot = PackMetadataValueInputSelector(kind="value", field=PackMetadataInputField.REFINE_ROLE)
        return PackWildernessChunkWrite(part=PackWildernessChunkPartInput(address=address,
            artifact=ArtifactRef(kind=ArtifactKind.BLOB, format_key=FINE_TERRAIN_FORMAT_KEY,
                format_version=FINE_TERRAIN_STORAGE_VERSION, content_hash=marker * 64, nbytes=1),
            provenance=PackNewPartProvenance(kind="new", provenance=self.proof)), refine_role=role, metadata_inputs=(
                PackMetadataInputEvidence(input=address_slot, value_fingerprint=metadata_input_fingerprint(address_slot, address), source_usage=self.usage(marker)),
                PackMetadataInputEvidence(input=role_slot, value_fingerprint=metadata_input_fingerprint(role_slot, role), source_usage=self.usage(marker))))

    def apply(self, state: PackPreparationState, *items: PackWildernessChunkWrite) -> PackPreparationState:
        return PackPreparationService().write_wilderness_chunks(PackWildernessChunksInput(state=state, entries=items))

    def single(self, state: PackPreparationState, item: PackWildernessChunkWrite) -> PackPreparationState:
        return PackPreparationService().write_wilderness_chunk(PackWildernessChunkInput(
            state=state, part=item.part, refine_role=item.refine_role, metadata_inputs=item.metadata_inputs))

    def test_batch_equals_chain_with_order_and_first_identity(self) -> None:
        items = (self.item(5), self.item(2, "b"), self.item(3, "c", gx=8))
        before = self.state.model_dump()
        batch = self.apply(self.state, *items)
        chain = self.state
        for item in items:
            chain = self.single(chain, item)
        self.assertEqual(batch, chain)
        self.assertEqual(self.state.model_dump(), before)
        self.assertEqual(tuple(part.address for part in batch.parts), tuple(item.part.address for item in items))
        self.assertEqual(tuple(chunk.cx for chunk in batch.assembly.tiles[0].chunks), (5, 2))
        self.assertEqual(tuple(tile.gx for tile in batch.assembly.tiles), (-2, 8))
        descriptions = {entry.subject.address: entry for entry in batch.metadata_dependencies}
        tile = descriptions[PackTileMetadataAddress(kind="tile", gx=-2, gy=3)]
        groups = {use.group: use for use in tile.dependencies}
        self.assertEqual(groups[PackMetadataGroup.IDENTITY].source_usage, self.usage("a"))
        self.assertEqual(groups[PackMetadataGroup.CLIMATE_STATUS].source_usage.uses, ())
        status = groups[PackMetadataGroup.WILDERNESS_REFINE_STATUS]
        self.assertEqual(status.source_usage.uses, ())
        assert status.basis is not None
        self.assertEqual(tuple(address.cx for address in status.basis.chunk_addresses), (2, 5))
        self.assertIsNone(status.basis.expected_chunks)
        self.assertEqual(batch.assembly.tiles[0].climate_status, "coarse")
        self.assertEqual(batch.assembly.tiles[0].wilderness_refine_status, "partial")
        for item in items:
            address = item.part.address
            chunk = descriptions[PackChunkMetadataAddress(kind="chunk", gx=address.gx, gy=address.gy, cx=address.cx, cy=address.cy)]
            self.assertEqual(tuple(use.source_usage for use in chunk.dependencies), (item.metadata_inputs[0].source_usage, item.metadata_inputs[1].source_usage))

    def test_replacement_retains_fine_and_invalidates_changed_rows_only(self) -> None:
        initial = self.apply(self.state, self.item(5), self.item(2, gx=8))
        tile_address = PackTileMetadataAddress(kind="tile", gx=-2, gy=3)
        chunk_address = PackChunkMetadataAddress(kind="chunk", gx=-2, gy=3, cx=5, cy=4)
        untouched_address = PackTileMetadataAddress(kind="tile", gx=8, gy=3)
        descriptions = {entry.subject.address: entry for entry in initial.metadata_dependencies}
        old_description = descriptions[tile_address]
        groups = list(old_description.dependencies)
        assert groups[2].basis is not None
        groups[2] = groups[2].model_copy(update={"basis": groups[2].basis.model_copy(update={"expected_chunks": 1})})
        groups[1] = groups[1].model_copy(update={"source_usage": self.usage("c")})
        descriptions[tile_address] = old_description.model_copy(update={"dependencies": tuple(groups),
            "subject": old_description.subject.model_copy(update={"value_fingerprint": metadata_value_fingerprint(tile_address, (-2, 3, "fine", "complete"))})})
        tiles = (initial.assembly.tiles[0].model_copy(update={"climate_status": "fine", "wilderness_refine_status": "complete"}), initial.assembly.tiles[1])
        initial = initial.model_copy(update={"assembly": initial.assembly.model_copy(update={"tiles": tiles}),
            "metadata_dependencies": tuple(descriptions.values()), "assembly_provenance": tuple(
                PackStoredAssemblyProvenance(address=address, provenance=self.proof, attribution=None)
                for address in (tile_address, chunk_address, untouched_address))})
        before = initial.model_dump()
        result = self.apply(initial, self.item(5, "b", role="scene"))
        self.assertEqual(initial.model_dump(), before)
        self.assertEqual(tuple(part.address for part in result.parts), tuple(part.address for part in initial.parts))
        self.assertEqual(result.assembly.tiles[0].climate_status, "fine")
        self.assertEqual(result.assembly.tiles[0].wilderness_refine_status, "partial")
        self.assertEqual(result.assembly.tiles[0].chunks[0].refine_role, "scene")
        self.assertEqual(tuple(entry.address for entry in result.assembly_provenance), (untouched_address,))
        updated = {entry.subject.address: entry for entry in result.metadata_dependencies}[tile_address]
        self.assertEqual(updated.dependencies[:2], tuple(groups[:2]))
        assert updated.dependencies[2].basis is not None
        self.assertIsNone(updated.dependencies[2].basis.expected_chunks)

    def test_equal_value_changed_usage_invalidates_chunk_but_not_unchanged_tile(self) -> None:
        state = self.apply(self.state, self.item(5))
        tile = PackTileMetadataAddress(kind="tile", gx=-2, gy=3)
        chunk = PackChunkMetadataAddress(kind="chunk", gx=-2, gy=3, cx=5, cy=4)
        state = state.model_copy(update={"assembly_provenance": tuple(
            PackStoredAssemblyProvenance(address=address, provenance=self.proof, attribution=None) for address in (tile, chunk))})
        result = self.apply(state, self.item(5, "b"))
        self.assertEqual(tuple(entry.address for entry in result.assembly_provenance), (tile,))
        self.assertIsNone(result.assembly.tiles[0].chunks[0].refine_role)
        self.assertEqual(self.apply(result), result)

    def test_partial_membership_change_invalidates_tile_binding(self) -> None:
        state = self.apply(self.state, self.item(5))
        tile = PackTileMetadataAddress(kind="tile", gx=-2, gy=3)
        state = state.model_copy(update={"assembly_provenance": (
            PackStoredAssemblyProvenance(address=tile, provenance=self.proof, attribution=None),)})
        result = self.apply(state, self.item(2, "b"))
        self.assertEqual(result.assembly.tiles[0].wilderness_refine_status, "partial")
        self.assertEqual(result.assembly_provenance, ())

    def test_mixed_replacements_and_additions_equal_chain(self) -> None:
        state = self.apply(self.state, self.item(5), self.item(2, gx=8))
        items = (self.item(1, "b"), self.item(5, "c", role="path"), self.item(2, "d", gx=8), self.item(4, "e", gx=9))
        batch = self.apply(state, *items)
        chain = state
        for item in items:
            chain = self.single(chain, item)
        self.assertEqual(batch, chain)
        self.assertEqual(tuple((part.address.gx, part.address.cx) for part in batch.parts
                               if isinstance(part.address, PackChunkAddress)), ((-2, 5), (8, 2), (-2, 1), (9, 4)))

    def test_unchanged_values_basis_and_usage_preserve_bindings(self) -> None:
        item = self.item(5)
        state = self.apply(self.state, item)
        tile = PackTileMetadataAddress(kind="tile", gx=-2, gy=3)
        chunk = PackChunkMetadataAddress(kind="chunk", gx=-2, gy=3, cx=5, cy=4)
        state = state.model_copy(update={"assembly_provenance": tuple(
            PackStoredAssemblyProvenance(address=address, provenance=self.proof, attribution=None) for address in (tile, chunk))})
        self.assertEqual(self.apply(state, item), state)

    def test_missing_retained_usage_rejects_before_transition(self) -> None:
        state = self.apply(self.state, self.item(5))
        tile = PackTileMetadataAddress(kind="tile", gx=-2, gy=3)
        state = state.model_copy(update={"metadata_dependencies": (), "assembly_provenance": (
            PackStoredAssemblyProvenance(address=tile, provenance=self.proof, attribution=None),)})
        before = state.model_dump()
        for single in (False, True):
            with self.subTest(single=single), patch(
                "app.application.worldData.pack.preparation.packPreparationService.apply_wilderness_chunks") as transition:
                with self.assertRaises(PackPreparationFailure) as caught:
                    if single:
                        self.single(state, self.item(2))
                    else:
                        self.apply(state, self.item(2))
                transition.assert_not_called()
                self.assertEqual(caught.exception.error.reason.value, "dependency_mismatch")
                self.assertEqual(len(caught.exception.error.issues), 1)
                issue = caught.exception.error.issues[0]
                assert isinstance(issue, PackPreparationIssue)
                self.assertEqual(issue.code.value, "metadata_attribution_unavailable")
                self.assertEqual(issue.path.projection(), ("state", "assembly_provenance", 0, "attribution"))
        self.assertEqual(state.model_dump(), before)

    def test_forged_batch_aggregates_before_transition(self) -> None:
        item = self.item(5)
        origin = PackNewPartProvenance(kind="new", provenance=self.proof)
        bad_proof = self.proof.model_copy(update={"planning": [],
            "source_proof": self.proof.source_proof.model_copy(update={"world_uid": "foreign"})})
        bad_part = item.part.model_copy(update={"artifact": item.part.artifact.model_copy(update={"format_version": 100}),
            "provenance": origin.model_copy(update={"provenance": bad_proof})})
        bad = item.model_copy(update={"part": bad_part})
        request = PackWildernessChunksInput.model_construct(state=self.state, entries=(bad, item))
        with patch("app.application.worldData.pack.preparation.packPreparationService.apply_wilderness_chunks") as transition:
            with self.assertRaises(PackPreparationFailure) as caught:
                PackPreparationService().write_wilderness_chunks(request)
            transition.assert_not_called()
        self.assertEqual(caught.exception.error.reason.value, "invalid_input")
        issues = caught.exception.error.issues
        self.assertEqual(len(issues), 4)
        assert isinstance(issues[0], WireShapeIssue)
        self.assertEqual(issues[0].code.value, "SCHEMA_VIOLATION")
        self.assertEqual(issues[0].location.parts, ("entries", 0, "part", "provenance", "new", "provenance", "planning"))
        expected = (("format_mismatch", ("entries", 0, "part", "artifact")),
                    ("source_proof_mismatch", ("entries", 0, "part", "provenance")),
                    ("duplicate_address", ("entries", 1, "part", "address")))
        for issue, (code, path) in zip(issues[1:], expected, strict=True):
            assert isinstance(issue, PackPreparationIssue)
            self.assertEqual((issue.code.value, issue.path.projection()), (code, path))

    def test_empty_batch_still_revalidates_state(self) -> None:
        state = self.state.model_copy(update={"assembly": self.state.assembly.model_copy(update={"fine_cell_size": "bad"})})
        with patch("app.application.worldData.pack.preparation.packPreparationService.apply_wilderness_chunks") as transition:
            with self.assertRaises(PackPreparationFailure) as caught:
                PackPreparationService().write_wilderness_chunks(PackWildernessChunksInput.model_construct(state=state, entries=()))
            transition.assert_not_called()
        self.assertEqual(caught.exception.error.reason.value, "invalid_input")
        self.assertEqual(len(caught.exception.error.issues), 1)
        issue = caught.exception.error.issues[0]
        assert isinstance(issue, JsonFieldError)
        self.assertEqual(issue.path.projection(), ("state", "assembly", "fine_cell_size"))

    def test_metadata_evidence_refusals_on_both_public_methods(self) -> None:
        item = self.item(5)
        bad_fingerprint = item.metadata_inputs[0].model_copy(update={"value_fingerprint": "f" * 64})
        extra = item.metadata_inputs[0].model_copy(update={"input":
            PackMetadataValueInputSelector(kind="value", field=PackMetadataInputField.MODE)})
        for evidence, suffix in (
            ((), ("metadata_inputs",)),
            ((item.metadata_inputs[0], item.metadata_inputs[0], item.metadata_inputs[1]), ("metadata_inputs", 1, "input")),
            ((bad_fingerprint, item.metadata_inputs[1]), ("metadata_inputs", 0, "value_fingerprint")),
            ((*item.metadata_inputs, extra), ("metadata_inputs", 2, "input")),
        ):
            bad = item.model_copy(update={"metadata_inputs": evidence})
            for single in (False, True):
                with self.subTest(single=single, path=suffix), patch(
                    "app.application.worldData.pack.preparation.packPreparationService.apply_wilderness_chunks") as transition:
                    with self.assertRaises(PackPreparationFailure) as caught:
                        if single:
                            self.single(self.state, bad)
                        else:
                            self.apply(self.state, bad)
                    transition.assert_not_called()
                    self.assertEqual(caught.exception.error.reason.value, "dependency_mismatch")
                    expected_path = suffix if single else ("entries", 0, *suffix)
                    self.assertEqual(len(caught.exception.error.issues), 1)
                    issue = caught.exception.error.issues[0]
                    assert isinstance(issue, PackPreparationIssue)
                    self.assertEqual((issue.code.value, issue.path.projection()), ("metadata_input_mismatch", expected_path))

    def test_single_request_inside_forged_batch_is_rejected(self) -> None:
        item = self.item(5)
        single = PackWildernessChunkInput(state=self.state, part=item.part, refine_role=None, metadata_inputs=item.metadata_inputs)
        request = PackWildernessChunksInput.model_construct(state=self.state, entries=(single,))
        with patch("app.application.worldData.pack.preparation.packPreparationService.apply_wilderness_chunks") as transition:
            with self.assertRaises(PackPreparationFailure) as caught:
                PackPreparationService().write_wilderness_chunks(request)
            transition.assert_not_called()
        self.assertEqual(caught.exception.error.reason.value, "invalid_input")
        self.assertEqual(len(caught.exception.error.issues), 1)
        issue = caught.exception.error.issues[0]
        assert isinstance(issue, (JsonFieldError, WireShapeIssue))
        self.assertEqual(issue.code.value, "SCHEMA_VIOLATION")

    def test_stale_subject_and_basis_reject_before_transition(self) -> None:
        state = self.apply(self.state, self.item(5))
        description = state.metadata_dependencies[0]
        status = description.dependencies[2]
        assert status.basis is not None
        stale = description.model_copy(update={
            "subject": description.subject.model_copy(update={"value_fingerprint": "f" * 64}),
            "dependencies": (*description.dependencies[:2], status.model_copy(update={
                "basis": status.basis.model_copy(update={"chunk_addresses": ()})}))})
        state = state.model_copy(update={"metadata_dependencies": (stale, *state.metadata_dependencies[1:])})
        before = state.model_dump()
        for single in (False, True):
            with self.subTest(single=single), patch(
                "app.application.worldData.pack.preparation.packPreparationService.apply_wilderness_chunks") as transition:
                with self.assertRaises(PackPreparationFailure) as caught:
                    if single:
                        self.single(state, self.item(2))
                    else:
                        self.apply(state, self.item(2))
                transition.assert_not_called()
                self.assertEqual(caught.exception.error.reason.value, "dependency_mismatch")
                issues = caught.exception.error.issues
                self.assertEqual(len(issues), 2)
                expected = (("metadata_basis_mismatch", ("state", "metadata_dependencies", 0, "dependencies", 2, "basis")),
                            ("source_proof_mismatch", ("state", "metadata_dependencies", 0, "subject", "value_fingerprint")))
                for issue, (code, path) in zip(issues, expected, strict=True):
                    assert isinstance(issue, PackPreparationIssue)
                    self.assertEqual((issue.code.value, issue.path.projection()), (code, path))
        self.assertEqual(state.model_dump(), before)

    def test_missing_nullable_role_has_only_structural_error(self) -> None:
        item = self.item(5)
        request = PackWildernessChunkInput.model_construct(state=self.state, part=item.part, metadata_inputs=item.metadata_inputs)
        with patch("app.application.worldData.pack.preparation.packPreparationService.apply_wilderness_chunks") as transition:
            with self.assertRaises(PackPreparationFailure) as caught:
                PackPreparationService().write_wilderness_chunk(request)
            transition.assert_not_called()
        self.assertEqual(caught.exception.error.reason.value, "invalid_input")
        self.assertEqual(len(caught.exception.error.issues), 1)
        issue = caught.exception.error.issues[0]
        assert isinstance(issue, JsonFieldError)
        self.assertEqual(issue.path.projection(), ("refine_role",))
