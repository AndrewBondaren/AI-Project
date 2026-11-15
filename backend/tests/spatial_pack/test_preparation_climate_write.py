import unittest

from app.application.worldData.pack.preparation.errors import PackPreparationFailure
from app.application.worldData.pack.preparation.packPreparationService import PackPreparationService
from app.core.constants import FINE_CELL_SIZE
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.worldPack.meta.parts import PackStoredPart
from app.dataModel.worldPack.preparation.addresses import PackCoarseClimateAddress, PackFineClimateAddress
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput, PackTileAssembly
from app.dataModel.worldPack.preparation.operations import PackCoarseClimateInput
from app.dataModel.worldPack.preparation.parts import PackCoarseClimatePartInput
from app.dataModel.worldPack.preparation.provenance import PackNewPartProvenance, PackStoredProvenance
from app.dataModel.worldPack.preparation.provenance import PackInheritedPartProvenance
from app.dataModel.worldPack.preparation.state import PackPreparationState
from app.dataModel.worldPack.preparation.errors import PackPreparationIssueCode
from app.dataModel.worldPack.wire.climateFieldWire import CLIMATE_FIELD_FORMAT_KEY, CLIMATE_FIELD_FORMAT_VERSION
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldPack.preparation.operations import PackLocationsIndexInput
from app.dataModel.worldPack.preparation.parts import PackLocationsIndexPartInput
from app.dataModel.worldPack.preparation.addresses import PackLocationsIndexAddress
from app.dataModel.worldPack.meta.locationsIndexStorageFormat import LOCATIONS_INDEX_FORMAT_KEY, LOCATIONS_INDEX_FORMAT_VERSION


class PreparationClimateWriteTests(unittest.TestCase):
    def test_bad_element_does_not_hide_other_parts_duplicates(self):
        from app.application.worldData.pack.preparation.packPreparationValidator import PackPreparationValidator
        bad = self.fine.model_copy(update={"artifact": self.fine.artifact.model_copy(update={"nbytes": "bad"})})
        for elements, malformed_index, duplicate_index in (
            ((self.fine, self.fine, bad), 2, 1), ((bad, self.fine, self.fine), 0, 2),
            ((self.fine, bad, self.fine), 1, 2),
        ):
            state = self.state.model_copy(update={"parts": elements})
            for method, model, part in self._writes():
                with self.subTest(method=method.__name__, malformed_index=malformed_index):
                    with self.assertRaises(PackPreparationFailure) as caught:
                        method(model.model_construct(state=state, part=part))
                    self.assertEqual([issue.path.projection() for issue in caught.exception.error.issues], [
                        ("state", "parts", malformed_index, "artifact", "nbytes"),
                        ("state", "parts", duplicate_index, "address")])
                    self.assertIs(caught.exception.error.issues[1].code, PackPreparationIssueCode.DUPLICATE_ADDRESS)
            with self.assertRaises(PackPreparationFailure) as caught:
                PackPreparationValidator().validate_state(state)
            self.assertEqual(caught.exception.error.issues[1].path.projection(), ("parts", duplicate_index, "address"))

    def test_bad_assembly_does_not_hide_incoming_proof_world(self):
        state = self.state.model_copy(update={"assembly": self.state.assembly.model_copy(update={"fine_cell_size": "bad"})})
        for method, model, part in self._writes():
            origin = part.provenance.provenance
            foreign = part.model_copy(update={"provenance": PackNewPartProvenance(kind="new", provenance=origin.model_copy(
                update={"source_proof": origin.source_proof.model_copy(update={"world_uid": "foreign"})}))})
            with self.subTest(method=method.__name__), self.assertRaises(PackPreparationFailure) as caught:
                method(model.model_construct(state=state, part=foreign))
            self.assertEqual([issue.path.projection() for issue in caught.exception.error.issues], [
                ("state", "assembly", "fine_cell_size"), ("part", "provenance")])
            self.assertIs(caught.exception.error.issues[1].code, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH)

    def test_bad_assembly_does_not_hide_duplicate_parts(self):
        from app.application.worldData.pack.preparation.packPreparationValidator import PackPreparationValidator
        state = self.state.model_copy(update={"parts": (self.fine, self.fine),
            "assembly": self.state.assembly.model_copy(update={"fine_cell_size": "bad"})})
        for method, model, part in self._writes():
            with self.subTest(method=method.__name__), self.assertRaises(PackPreparationFailure) as caught:
                method(model.model_construct(state=state, part=part))
            self.assertEqual([issue.path.projection() for issue in caught.exception.error.issues], [
                ("state", "assembly", "fine_cell_size"), ("state", "parts", 1, "address")])
            self.assertIs(caught.exception.error.issues[1].code, PackPreparationIssueCode.DUPLICATE_ADDRESS)
        with self.assertRaises(PackPreparationFailure) as caught:
            PackPreparationValidator().validate_state(state)
        self.assertEqual([issue.path.projection() for issue in caught.exception.error.issues], [
            ("assembly", "fine_cell_size"), ("parts", 1, "address")])
        self.assertEqual(state.parts, (self.fine, self.fine))

    def _writes(self):
        index = PackLocationsIndexPartInput(address=PackLocationsIndexAddress(kind="locations_index"),
            artifact=self.part.artifact.model_copy(update={"format_key": LOCATIONS_INDEX_FORMAT_KEY,
                                                           "format_version": LOCATIONS_INDEX_FORMAT_VERSION}),
            provenance=self.part.provenance)
        return ((self.service.write_coarse_climate, PackCoarseClimateInput, self.part),
                (self.service.replace_locations_index, PackLocationsIndexInput, index))

    def test_inherited_is_not_erased_without_verified_base_admission(self):
        for method, model, part in self._writes():
            for pack_hash in (None, "d" * 64):
                with self.subTest(method=method.__name__, pack_hash=pack_hash):
                    state = self.state.model_copy(update={"base_publication": self.state.base_publication.model_copy(
                        update={"pack_hash": pack_hash})})
                    inherited = part.model_copy(update={"provenance": PackInheritedPartProvenance(
                        kind="inherited", provenance=part.provenance.provenance)})
                    with self.assertRaises(PackPreparationFailure) as caught:
                        method(model(state=state, part=inherited))
                    issue, = caught.exception.error.issues
                    self.assertIs(issue.code, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH)
                    self.assertEqual(issue.path.projection(), ("part", "provenance"))
                    self.assertEqual(state.parts, (self.fine,))

    def test_bad_part_schema_does_not_hide_duplicate_state(self):
        for method, model, part in self._writes():
            with self.subTest(method=method.__name__):
                state = self.state.model_copy(update={"parts": (self.fine, self.fine)})
                malformed = part.model_copy(update={"artifact": part.artifact.model_copy(update={"nbytes": "bad"})})
                with self.assertRaises(PackPreparationFailure) as caught:
                    method(model.model_construct(state=state, part=malformed))
                issues = caught.exception.error.issues
                self.assertEqual(len(issues), 2)
                self.assertEqual(issues[0].path.projection(), ("part", "artifact", "nbytes"))
                self.assertIs(issues[1].code, PackPreparationIssueCode.DUPLICATE_ADDRESS)
                self.assertEqual(issues[1].path.projection(), ("state", "parts", 1, "address"))

    def test_bad_state_schema_does_not_hide_part_format_error(self):
        for method, model, part in self._writes():
            with self.subTest(method=method.__name__):
                state = self.state.model_copy(update={"parts": []})
                bad = part.model_copy(update={"artifact": part.artifact.model_copy(update={"format_version": 100})})
                with self.assertRaises(PackPreparationFailure) as caught:
                    method(model.model_construct(state=state, part=bad))
                self.assertEqual(len(caught.exception.error.issues), 2)
                self.assertIs(caught.exception.error.issues[1].code, PackPreparationIssueCode.FORMAT_MISMATCH)

    def setUp(self):
        provenance = PackStoredProvenance(source_proof=SourceDurableProof(schema_version=1, world_uid="world", uses=()), planning=())
        ref = ArtifactRef(kind=ArtifactKind.BLOB, format_key=CLIMATE_FIELD_FORMAT_KEY,
                          format_version=CLIMATE_FIELD_FORMAT_VERSION, content_hash="a" * 64, nbytes=1)
        self.part = PackCoarseClimatePartInput(address=PackCoarseClimateAddress(kind="climate_coarse"), artifact=ref,
                                              provenance=PackNewPartProvenance(kind="new", provenance=provenance))
        self.fine = PackStoredPart(address=PackFineClimateAddress(kind="climate_fine", gx=0, gy=0), artifact=ref, provenance=provenance)
        self.state = PackPreparationState(
            base_publication=WorldPublicationRef(world_uid="world", publication_id="base", pack_hash=None,
                snapshot_head=None, active_timeline_id=None, gameplay_started=False), parts=(self.fine,),
            assembly=PackAssemblyInput(last_l0_mode="light", fine_cells_per_map_cell=1000, world_map_cells_per_tile=32,
                fine_cell_size=FINE_CELL_SIZE, map_subsurface_depth=0, terrain_chunk_columns=32,
                tiles=(PackTileAssembly(gx=0, gy=0, climate_status="fine", wilderness_refine_status="absent", chunks=()),),
                locations=(), settlements=(), wilderness_regions=()), assembly_provenance=(), metadata_dependencies=())
        self.service = PackPreparationService()

    def test_add_replace_and_delete_keep_fine_and_metadata(self):
        first = self.service.write_coarse_climate(PackCoarseClimateInput(state=self.state, part=self.part))
        changed = self.part.model_copy(update={"artifact": self.part.artifact.model_copy(update={"content_hash": "b" * 64})})
        second = self.service.write_coarse_climate(PackCoarseClimateInput(state=first, part=changed))
        self.assertEqual(len(second.parts), 2)
        self.assertEqual(second.parts[0], self.fine)
        self.assertEqual(second.parts[1].artifact, changed.artifact)
        self.assertEqual(second.parts[1].provenance, self.part.provenance.provenance)
        self.assertEqual(second.assembly, self.state.assembly)
        self.assertEqual(second.base_publication, self.state.base_publication)
        self.assertEqual(first.parts[1].artifact, self.part.artifact)
        self.assertEqual(self.state.parts, (self.fine,))
        from app.dataModel.worldPack.preparation.operations import PackDeletePartInput
        deleted = self.service.delete_part(PackDeletePartInput(state=second, address=self.part.address))
        self.assertEqual(deleted, self.state)

    def test_format_and_world_errors_aggregate_before_change(self):
        stored = self.part.provenance.provenance
        bad = self.part.model_copy(update={
            "artifact": self.part.artifact.model_copy(update={"format_version": CLIMATE_FIELD_FORMAT_VERSION + 1}),
            "provenance": PackNewPartProvenance(kind="new", provenance=stored.model_copy(update={
                "source_proof": stored.source_proof.model_copy(update={"world_uid": "foreign"})})),
        })
        with self.assertRaises(PackPreparationFailure) as caught:
            self.service.write_coarse_climate(PackCoarseClimateInput(state=self.state, part=bad))
        self.assertEqual([issue.code for issue in caught.exception.error.issues],
                         [PackPreparationIssueCode.FORMAT_MISMATCH, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH])
        self.assertEqual([issue.path.projection() for issue in caught.exception.error.issues],
                         [("part", "artifact"), ("part", "provenance")])
        self.assertEqual(self.state.parts, (self.fine,))

    def test_locations_index_replace_preserves_other_parts_and_assembly(self):
        ref = ArtifactRef(kind=ArtifactKind.BLOB, format_key=LOCATIONS_INDEX_FORMAT_KEY,
                          format_version=LOCATIONS_INDEX_FORMAT_VERSION, content_hash="b" * 64, nbytes=2)
        part = PackLocationsIndexPartInput(address=PackLocationsIndexAddress(kind="locations_index"),
                                           artifact=ref, provenance=self.part.provenance)
        first = self.service.replace_locations_index(PackLocationsIndexInput(state=self.state, part=part))
        replacement = part.model_copy(update={"artifact": ref.model_copy(update={"content_hash": "c" * 64})})
        second = self.service.replace_locations_index(PackLocationsIndexInput(state=first, part=replacement))
        self.assertEqual(second.parts[0], self.fine)
        self.assertEqual(len(second.parts), 2)
        self.assertEqual(second.parts[1].artifact, replacement.artifact)
        self.assertEqual(second.parts[1].provenance, part.provenance.provenance)
        self.assertEqual(second.assembly, self.state.assembly)
        self.assertEqual(second.assembly_provenance, self.state.assembly_provenance)
        self.assertEqual(second.metadata_dependencies, self.state.metadata_dependencies)
        self.assertEqual(first.parts[1].artifact, ref)
        self.assertEqual(self.state.parts, (self.fine,))

    def test_index_rejects_climate_descriptor_and_foreign_proof(self):
        origin = self.part.provenance.provenance
        part = PackLocationsIndexPartInput(address=PackLocationsIndexAddress(kind="locations_index"),
            artifact=self.part.artifact, provenance=PackNewPartProvenance(kind="new", provenance=origin.model_copy(update={
                "source_proof": origin.source_proof.model_copy(update={"world_uid": "foreign"})})))
        with self.assertRaises(PackPreparationFailure) as caught:
            self.service.replace_locations_index(PackLocationsIndexInput(state=self.state, part=part))
        self.assertEqual([issue.code for issue in caught.exception.error.issues],
                         [PackPreparationIssueCode.FORMAT_MISMATCH, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH])
        self.assertEqual([issue.path.projection() for issue in caught.exception.error.issues],
                         [("part", "artifact"), ("part", "provenance")])
