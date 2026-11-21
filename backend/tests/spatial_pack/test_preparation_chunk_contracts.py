"""Owning chunk input schema and canonical metadata identity contracts."""

import unittest

from pydantic import ValidationError
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError

from app.application.worldData.pack.preparation.metadataProjection import metadata_input_fingerprint
from app.dataModel.worldPack.encoding.metadataBindings import PACK_METADATA_SCHEMA
from app.dataModel.worldPack.preparation.addresses import PackChunkAddress
from app.dataModel.worldPack.preparation.metadataDependencies import (
    PackMetadataInputField, PackMetadataValueInputSelector, PackMetadataRegionInputSelector,
    PackRegionMetadataInputField,
)
from app.encoding.canonicalCodec import decode, encode
from app.core.constants import FINE_CELL_SIZE
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput, PackTileAssembly, PackChunkAssembly
from app.dataModel.worldPack.preparation.operations import PackWildernessChunkInput, PackWildernessChunksInput, PackWildernessChunkWrite
from app.dataModel.worldPack.preparation.parts import PackWildernessChunkPartInput
from app.dataModel.worldPack.preparation.provenance import PackNewPartProvenance, PackStoredProvenance
from app.dataModel.worldPack.preparation.state import PackPreparationState
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.artifacts.references import ArtifactRef, ArtifactKind
from app.dataModel.worldPack.meta.fineTerrainStorageFormat import FINE_TERRAIN_FORMAT_KEY, FINE_TERRAIN_STORAGE_VERSION
from app.application.worldData.pack.preparation.metadataProjection import metadata_projection, metadata_value_fingerprint
from app.dataModel.worldPack.preparation.addresses import PackTileMetadataAddress, PackChunkMetadataAddress
from app.application.worldData.pack.preparation.wildernessChunkAdmission import WildernessChunkAdmission
from app.application.worldData.pack.preparation.errors import PackPreparationFailure
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataInputEvidence
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.worldPack.preparation.errors import PackPreparationArtifactIssue, PackPreparationIssue
from app.dataModel.worldPack.meta.metadataAttribution import PackMetadataGroup, PackWildernessStatusBasis
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataDescription, PackMetadataDependencyUse
from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
from app.dataModel.worldPack.meta.parts import PackStoredPart
from app.dataModel.worldPack.meta.metadataAttribution import PackStoredAssemblyProvenance
from app.dataModel.worldPack.preparation.addresses import PackAssemblyHeaderAddress
from app.dataModel.worldPack.preparation.addresses import PackLocationMetadataAddress, PackSettlementMetadataAddress, PackRegionMetadataAddress
from app.dataModel.worldPack.preparation.assembly import PackLocationAssembly, PackSettlementAssembly
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry
from app.application.worldData.pack.preparation.metadataStateValidator import MetadataStateValidator
from app.application.worldData.pack.preparation.errors import preparation_errors
from app.dataModel.fields.checkedPath import CheckedPath
from tests.spatial_pack.metadata_vector_cases import vector_cases


class ChunkContractTests(unittest.TestCase):
    def test_duplicate_tile_does_not_choose_fingerprint_by_order(self) -> None:
        fine = PackTileAssembly(gx=-2, gy=3, climate_status="fine", wilderness_refine_status="absent", chunks=())
        coarse = fine.model_copy(update={"climate_status": "coarse"})
        description = self.tile_description()
        fingerprint = metadata_value_fingerprint(description.subject.address, (-2, 3, "fine", "absent"))
        description = description.model_copy(update={"subject": description.subject.model_copy(update={"value_fingerprint": fingerprint})})
        for tiles in ((fine, coarse), (coarse, fine)):
            with self.subTest(first=tiles[0].climate_status):
                state = self.state.model_copy(update={"assembly": self.assembly.model_copy(update={"tiles": tiles}),
                                                     "metadata_dependencies": (description,)})
                with self.assertRaises(PackPreparationFailure) as caught:
                    WildernessChunkAdmission().validate_wilderness_chunks(PackWildernessChunksInput(state=state, entries=()))
                self.assertEqual(caught.exception.error.reason.value, "identity_conflict")
                self.assertEqual(len(caught.exception.error.issues), 1)
                issue = caught.exception.error.issues[0]
                assert isinstance(issue, PackPreparationIssue)
                self.assertEqual(issue.code.value, "duplicate_address")
                self.assertEqual(issue.path.projection(), ("state", "assembly", "tiles", 1))

    def test_duplicate_projection_values_are_not_compared(self) -> None:
        cases = vector_cases()
        for name, collection, model, field, changed in (
            ("location", "locations", PackLocationAssembly, "climate_status", "coarse"),
            ("settlement", "settlements", PackSettlementAssembly, "structure_status", "complete"),
            ("region", "wilderness_regions", WildernessRegionEntry, "spec_fingerprint", "changed"),
        ):
            _, address, value = cases[name]
            assert isinstance(address, (PackLocationMetadataAddress, PackSettlementMetadataAddress, PackRegionMetadataAddress))
            assert isinstance(value, (PackLocationAssembly, PackSettlementAssembly, WildernessRegionEntry))
            other = model.model_validate(value.model_dump()).model_copy(update={field: changed})
            description = PackMetadataDescription(subject=PackMetadataSubject(base_publication=self.state.base_publication,
                address=address, value_fingerprint=metadata_value_fingerprint(address, value)), dependencies=())
            # Invalid siblings must not make the duplicate identity unambiguous either.
            for candidate in (other, other.model_copy(update={field: []})):
                for rows in ((value, candidate), (candidate, value)):
                    with self.subTest(kind=name, rows=rows):
                        state = self.state.model_copy(update={"assembly": self.assembly.model_copy(update={collection: rows}),
                                                             "metadata_dependencies": (description,)})
                        errors = preparation_errors()
                        MetadataStateValidator().check_subject_values(state, CheckedPath.root(PackPreparationState), errors)
                        self.assertEqual(errors.snapshot(), ())

    def test_duplicate_chunk_and_parent_tile_block_value_comparison(self) -> None:
        address = PackChunkMetadataAddress(kind="chunk", gx=-2, gy=3, cx=1, cy=4)
        chunk = PackChunkAssembly(cx=1, cy=4, refine_role=None)
        other = chunk.model_copy(update={"refine_role": "scene"})
        tile = PackTileAssembly(gx=-2, gy=3, climate_status="fine", wilderness_refine_status="partial", chunks=(chunk,))
        description = PackMetadataDescription(subject=PackMetadataSubject(base_publication=self.state.base_publication,
            address=address, value_fingerprint=metadata_value_fingerprint(address, (1, 4, None))), dependencies=())
        for candidate in (other, other.model_copy(update={"refine_role": "bad"})):
            for chunks in ((chunk, candidate), (candidate, chunk)):
                for tiles in ((tile.model_copy(update={"chunks": chunks}),),
                              (tile, tile.model_copy(update={"chunks": (candidate,)}))):
                    with self.subTest(tiles=tiles):
                        state = self.state.model_copy(update={"assembly": self.assembly.model_copy(update={"tiles": tiles}),
                                                             "metadata_dependencies": (description,)})
                        errors = preparation_errors()
                        MetadataStateValidator().check_subject_values(state, CheckedPath.root(PackPreparationState), errors)
                        self.assertEqual(errors.snapshot(), ())

    def test_pending_world_check_survives_invalid_uses(self) -> None:
        description = self.tile_description()
        tile = PackTileAssembly(gx=-2, gy=3, climate_status="fine", wilderness_refine_status="absent", chunks=())
        usage = SourceProofInput(world_uid="foreign", uses=()).model_copy(update={"uses": "bad"})
        dependencies = (description.dependencies[0].model_copy(update={"source_usage": usage}), *description.dependencies[1:])
        description = description.model_copy(update={"dependencies": dependencies, "subject": description.subject.model_copy(update={
            "value_fingerprint": metadata_value_fingerprint(description.subject.address, (-2, 3, "fine", "absent"))})})
        state = self.state.model_copy(update={"assembly": self.assembly.model_copy(update={"tiles": (tile,)}),
                                             "metadata_dependencies": (description,)})
        with self.assertRaises(PackPreparationFailure) as caught:
            WildernessChunkAdmission().validate_wilderness_chunks(PackWildernessChunksInput.model_construct(state=state, entries=()))
        self.assertEqual(caught.exception.error.reason.value, "invalid_input")
        issues = caught.exception.error.issues
        self.assertEqual(len(issues), 2)
        assert isinstance(issues[0], JsonFieldError)
        prefix = ("state", "metadata_dependencies", 0, "dependencies", 0, "source_usage")
        self.assertEqual(issues[0].path.projection(), (*prefix, "uses"))
        assert isinstance(issues[1], PackPreparationIssue)
        self.assertEqual(issues[1].code.value, "source_proof_mismatch")
        self.assertEqual(issues[1].path.projection(), (*prefix, "world_uid"))

    def test_stored_world_check_survives_invalid_base_hash(self) -> None:
        provenance = PackStoredProvenance(source_proof=SourceDurableProof(schema_version=1, world_uid="foreign", uses=()), planning=())
        part = PackStoredPart(address=self.part.address, artifact=self.part.artifact, provenance=provenance)
        state = self.state.model_copy(update={"parts": (part,),
            "base_publication": self.state.base_publication.model_copy(update={"pack_hash": "bad"})})
        with self.assertRaises(PackPreparationFailure) as caught:
            WildernessChunkAdmission().validate_wilderness_chunks(PackWildernessChunksInput.model_construct(state=state, entries=()))
        self.assertEqual(caught.exception.error.reason.value, "invalid_input")
        issues = caught.exception.error.issues
        self.assertEqual(len(issues), 2)
        assert isinstance(issues[0], JsonFieldError)
        self.assertEqual(issues[0].path.projection(), ("state", "base_publication", "pack_hash"))
        assert isinstance(issues[1], PackPreparationIssue)
        self.assertEqual(issues[1].code.value, "source_proof_mismatch")
        self.assertEqual(issues[1].path.projection(), ("state", "parts", 0, "provenance", "source_proof", "world_uid"))

    def tile_description(self) -> PackMetadataDescription:
        usage = SourceProofInput(world_uid="world", uses=())
        return PackMetadataDescription(subject=PackMetadataSubject(base_publication=self.state.base_publication,
            address=PackTileMetadataAddress(kind="tile", gx=-2, gy=3), value_fingerprint="a" * 64), dependencies=(
            PackMetadataDependencyUse(group=PackMetadataGroup.IDENTITY, source_usage=usage, basis=None),
            PackMetadataDependencyUse(group=PackMetadataGroup.CLIMATE_STATUS, source_usage=usage, basis=None),
            PackMetadataDependencyUse(group=PackMetadataGroup.WILDERNESS_REFINE_STATUS, source_usage=usage,
                basis=PackWildernessStatusBasis(chunk_addresses=(), expected_chunks=None))))

    def test_absent_projection_is_independent_of_header_error(self) -> None:
        state = self.state.model_copy(update={
            "assembly": self.assembly.model_copy(update={"fine_cell_size": "bad"}),
            "metadata_dependencies": (self.tile_description(),)})
        with self.assertRaises(PackPreparationFailure) as caught:
            WildernessChunkAdmission().validate_wilderness_chunks(PackWildernessChunksInput.model_construct(state=state, entries=()))
        issues = caught.exception.error.issues
        self.assertEqual(caught.exception.error.reason.value, "invalid_input")
        self.assertEqual(len(issues), 2)
        assert isinstance(issues[0], JsonFieldError)
        self.assertEqual(issues[0].path.projection(), ("state", "assembly", "fine_cell_size"))
        semantic = issues[1]
        assert isinstance(semantic, PackPreparationIssue)
        self.assertEqual(semantic.code.value, "address_mismatch")
        self.assertEqual(semantic.path.projection(), ("state", "metadata_dependencies", 0, "subject", "address"))

    def test_invalid_subject_value_is_not_missing_retained_usage(self) -> None:
        description = self.tile_description()
        description = description.model_copy(update={"subject": description.subject.model_copy(update={"value_fingerprint": "bad"})})
        tile = PackTileAssembly(gx=-2, gy=3, climate_status="fine", wilderness_refine_status="absent", chunks=())
        state = self.state.model_copy(update={"assembly": self.assembly.model_copy(update={"tiles": (tile,)}),
                                             "metadata_dependencies": (description,)})
        with self.assertRaises(PackPreparationFailure) as caught:
            WildernessChunkAdmission().validate_wilderness_chunks(PackWildernessChunksInput.model_construct(state=state, entries=(self.valid_item(),)))
        self.assertEqual(caught.exception.error.reason.value, "invalid_input")
        issues = caught.exception.error.issues
        self.assertEqual(len(issues), 1)
        assert isinstance(issues[0], JsonFieldError)
        self.assertEqual(issues[0].path.projection(), ("state", "metadata_dependencies", 0, "subject", "value_fingerprint"))

    def test_stored_proof_world_is_independent_of_planning(self) -> None:
        provenance = PackStoredProvenance(source_proof=SourceDurableProof(schema_version=1, world_uid="foreign", uses=()), planning=())
        part = PackStoredPart(address=self.part.address, artifact=self.part.artifact, provenance=provenance)
        metadata = PackStoredAssemblyProvenance(address=PackAssemblyHeaderAddress(kind="header"), provenance=provenance, attribution=None)
        bad = provenance.model_copy(update={"planning": "bad"})
        for field, entry in (("parts", part.model_copy(update={"provenance": bad})),
                             ("assembly_provenance", metadata.model_copy(update={"provenance": bad}))):
            with self.subTest(field=field):
                state = self.state.model_copy(update={field: (entry,)})
                with self.assertRaises(PackPreparationFailure) as caught:
                    WildernessChunkAdmission().validate_wilderness_chunks(PackWildernessChunksInput.model_construct(state=state, entries=()))
                self.assertEqual(caught.exception.error.reason.value, "invalid_input")
                issues = caught.exception.error.issues
                self.assertEqual(len(issues), 2)
                assert isinstance(issues[0], JsonFieldError)
                self.assertEqual(issues[0].path.projection(), ("state", field, 0, "provenance", "planning"))
                semantic = issues[1]
                assert isinstance(semantic, PackPreparationIssue)
                self.assertEqual(semantic.code.value, "source_proof_mismatch")
                self.assertEqual(semantic.path.projection(), ("state", field, 0, "provenance", "source_proof", "world_uid"))

    def test_existing_tile_requires_imported_usage(self) -> None:
        tile = PackTileAssembly(gx=-2, gy=3, climate_status="fine", wilderness_refine_status="absent", chunks=())
        state = self.state.model_copy(update={"assembly": self.assembly.model_copy(update={"tiles": (tile,)})})
        with self.assertRaises(PackPreparationFailure) as caught:
            WildernessChunkAdmission().validate_wilderness_chunks(PackWildernessChunksInput(state=state, entries=(self.valid_item(),)))
        issue = caught.exception.error.issues[0]
        assert isinstance(issue, PackPreparationIssue)
        self.assertEqual(issue.code.value, "metadata_attribution_unavailable")
        self.assertEqual(issue.path.projection(), ("state", "assembly_provenance"))

    def test_stale_subject_is_independent_of_header_error(self) -> None:
        tile = PackTileAssembly(gx=-2, gy=3, climate_status="fine", wilderness_refine_status="absent", chunks=())
        address = PackTileMetadataAddress(kind="tile", gx=-2, gy=3)
        usage = SourceProofInput(world_uid="world", uses=())
        description = PackMetadataDescription(subject=PackMetadataSubject(base_publication=self.state.base_publication,
            address=address, value_fingerprint="a" * 64), dependencies=(
            PackMetadataDependencyUse(group=PackMetadataGroup.IDENTITY, source_usage=usage, basis=None),
            PackMetadataDependencyUse(group=PackMetadataGroup.CLIMATE_STATUS, source_usage=usage, basis=None),
            PackMetadataDependencyUse(group=PackMetadataGroup.WILDERNESS_REFINE_STATUS, source_usage=usage,
                basis=PackWildernessStatusBasis(chunk_addresses=(), expected_chunks=None))))
        state = self.state.model_copy(update={"assembly": self.assembly.model_copy(update={"tiles": (tile,), "fine_cell_size": "bad"}),
                                             "metadata_dependencies": (description,)})
        with self.assertRaises(PackPreparationFailure) as caught:
            WildernessChunkAdmission().validate_wilderness_chunks(PackWildernessChunksInput.model_construct(state=state, entries=()))
        issue = caught.exception.error.issues[-1]
        assert isinstance(issue, PackPreparationIssue)
        self.assertEqual(issue.code.value, "source_proof_mismatch")
        self.assertEqual(issue.path.projection(), ("state", "metadata_dependencies", 0, "subject", "value_fingerprint"))

    def test_stale_basis_is_independent_of_climate_status(self) -> None:
        tile = PackTileAssembly(gx=-2, gy=3, climate_status="coarse", wilderness_refine_status="partial",
            chunks=(PackChunkAssembly(cx=1, cy=4, refine_role=None),))
        address = PackTileMetadataAddress(kind="tile", gx=-2, gy=3)
        usage = SourceProofInput(world_uid="world", uses=())
        description = PackMetadataDescription(subject=PackMetadataSubject(base_publication=self.state.base_publication,
            address=address, value_fingerprint="a" * 64), dependencies=(
            PackMetadataDependencyUse(group=PackMetadataGroup.IDENTITY, source_usage=usage, basis=None),
            PackMetadataDependencyUse(group=PackMetadataGroup.CLIMATE_STATUS, source_usage=usage, basis=None),
            PackMetadataDependencyUse(group=PackMetadataGroup.WILDERNESS_REFINE_STATUS, source_usage=usage,
                basis=PackWildernessStatusBasis(chunk_addresses=(), expected_chunks=None))))
        state = self.state.model_copy(update={"assembly": self.assembly.model_copy(update={"tiles": (
            tile.model_copy(update={"climate_status": "bad"}),)}), "metadata_dependencies": (description,)})
        with self.assertRaises(PackPreparationFailure) as caught:
            WildernessChunkAdmission().validate_wilderness_chunks(PackWildernessChunksInput.model_construct(state=state, entries=()))
        issues = caught.exception.error.issues
        self.assertEqual([issue.code.value for issue in issues if isinstance(issue, PackPreparationIssue)],
                         ["metadata_basis_mismatch"])
        semantic = issues[-1]
        assert isinstance(semantic, PackPreparationIssue)
        self.assertEqual(semantic.path.projection(), ("state", "metadata_dependencies", 0, "dependencies", 2, "basis"))

    def valid_item(self) -> PackWildernessChunkWrite:
        address = PackMetadataValueInputSelector(kind="value", field=PackMetadataInputField.ADDRESS)
        role = PackMetadataValueInputSelector(kind="value", field=PackMetadataInputField.REFINE_ROLE)
        usage = SourceProofInput(world_uid="world", uses=())
        return PackWildernessChunkWrite(part=self.part, refine_role=None, metadata_inputs=(
            PackMetadataInputEvidence(input=address, value_fingerprint=metadata_input_fingerprint(address, self.part.address), source_usage=usage),
            PackMetadataInputEvidence(input=role, value_fingerprint=metadata_input_fingerprint(role, None), source_usage=usage)))

    def test_chunk_admission_and_duplicate_reason(self) -> None:
        item = self.valid_item()
        validator = WildernessChunkAdmission()
        request = PackWildernessChunksInput(state=self.state, entries=(item,))
        self.assertEqual(validator.validate_wilderness_chunks(request), request)
        with self.assertRaises(PackPreparationFailure) as caught:
            validator.validate_wilderness_chunks(PackWildernessChunksInput(state=self.state, entries=(item, item)))
        self.assertEqual(caught.exception.error.reason.value, "identity_conflict")
        issue = caught.exception.error.issues[0]
        assert isinstance(issue, PackPreparationIssue)
        self.assertEqual(issue.code.value, "duplicate_address")

    def test_chunk_format_and_evidence_world_are_independent(self) -> None:
        item = self.valid_item()
        bad = item.model_copy(update={
            "part": item.part.model_copy(update={"address": item.part.address.model_copy(update={"kind": "bad"}),
                "artifact": item.part.artifact.model_copy(update={"format_version": 100})}),
            "metadata_inputs": (item.metadata_inputs[0].model_copy(update={"source_usage": SourceProofInput(world_uid="foreign", uses=())}), item.metadata_inputs[1]),
        })
        with self.assertRaises(PackPreparationFailure) as caught:
            WildernessChunkAdmission().validate_wilderness_chunks(PackWildernessChunksInput.model_construct(state=self.state, entries=(bad,)))
        self.assertEqual(caught.exception.error.reason.value, "invalid_input")
        self.assertEqual([(issue.issue if isinstance(issue, PackPreparationArtifactIssue) else issue).code.value
                          for issue in caught.exception.error.issues],
                         ["SCHEMA_VIOLATION", "format_mismatch", "source_proof_mismatch"])

    def setUp(self) -> None:
        self.assembly = PackAssemblyInput(last_l0_mode="light", fine_cells_per_map_cell=1000,
            world_map_cells_per_tile=32, fine_cell_size=FINE_CELL_SIZE, map_subsurface_depth=0,
            terrain_chunk_columns=32, tiles=(), locations=(), settlements=(), wilderness_regions=())
        self.state = PackPreparationState(parts=(), assembly=self.assembly, assembly_provenance=(), metadata_dependencies=(),
            base_publication=WorldPublicationRef(world_uid="world", publication_id="base", pack_hash=None,
                snapshot_head=None, active_timeline_id=None, gameplay_started=False))
        self.part = PackWildernessChunkPartInput(
            address=PackChunkAddress(kind="wilderness_chunk", gx=-2, gy=3, cx=1, cy=4),
            artifact=ArtifactRef(kind=ArtifactKind.BLOB, format_key=FINE_TERRAIN_FORMAT_KEY,
                format_version=FINE_TERRAIN_STORAGE_VERSION, content_hash="a" * 64, nbytes=1),
            provenance=PackNewPartProvenance(kind="new", provenance=PackStoredProvenance(
                source_proof=SourceDurableProof(schema_version=1, world_uid="world", uses=()), planning=())))

    def test_single_is_not_batch_item(self) -> None:
        single = PackWildernessChunkInput(state=self.state, part=self.part, refine_role=None, metadata_inputs=())
        with self.assertRaises(ValidationError) as caught:
            PackWildernessChunksInput.model_validate({"state": self.state, "entries": (single,)})
        self.assertEqual(caught.exception.errors()[0]["loc"], ("entries", 0))
        item = PackWildernessChunkWrite(part=self.part, refine_role=None, metadata_inputs=())
        self.assertEqual(PackWildernessChunksInput(state=self.state, entries=(item,)).entries, (item,))

    def test_missing_role_and_forged_nested_address(self) -> None:
        with self.assertRaises(ValidationError) as caught:
            PackWildernessChunkWrite.model_validate({"part": self.part, "metadata_inputs": ()})
        self.assertEqual(caught.exception.errors()[0]["loc"], ("refine_role",))
        bad = self.part.model_copy(update={"address": self.part.address.model_copy(update={"cx": True})})
        with self.assertRaises(ValidationError):
            PackWildernessChunkWrite(part=bad, refine_role=None, metadata_inputs=())

    def test_tile_projection_excludes_chunks(self) -> None:
        tile = PackTileAssembly(gx=-2, gy=3, climate_status="fine", wilderness_refine_status="partial", chunks=())
        assembly = self.assembly.model_copy(update={"tiles": (tile,)})
        changed = assembly.model_copy(update={"tiles": (tile.model_copy(update={"chunks": (
            PackChunkAssembly(cx=1, cy=4, refine_role=None),)}),)})
        address = PackTileMetadataAddress(kind="tile", gx=-2, gy=3)
        before = metadata_projection(assembly, address)
        after = metadata_projection(changed, address)
        self.assertEqual(before, (-2, 3, "fine", "partial"))
        self.assertEqual(metadata_value_fingerprint(address, before), metadata_value_fingerprint(address, after))
        chunk = PackChunkMetadataAddress(kind="chunk", gx=-2, gy=3, cx=1, cy=4)
        self.assertIsNone(metadata_projection(assembly, chunk))
        self.assertEqual(metadata_projection(changed, chunk), (1, 4, None))

    def test_address_round_trip_and_identity(self) -> None:
        address = PackChunkAddress(kind="wilderness_chunk", gx=-2, gy=3, cx=1, cy=4)
        selector = PackMetadataValueInputSelector(kind="value", field=PackMetadataInputField.ADDRESS)
        encoded = encode(address, PACK_METADATA_SCHEMA)
        self.assertEqual(decode(encoded, PackChunkAddress, PACK_METADATA_SCHEMA), address)
        self.assertNotEqual(metadata_input_fingerprint(selector, address),
                            metadata_input_fingerprint(selector, address.model_copy(update={"cy": 5})))

    def test_nullable_role_has_distinct_identity(self) -> None:
        selector = PackMetadataValueInputSelector(kind="value", field=PackMetadataInputField.REFINE_ROLE)
        fingerprints = {
            metadata_input_fingerprint(selector, None),
            metadata_input_fingerprint(selector, "scene"),
            metadata_input_fingerprint(selector, "background"),
            metadata_input_fingerprint(selector, "path"),
            metadata_input_fingerprint(selector, "location"),
        }
        self.assertEqual(len(fingerprints), 5)

    def test_region_selector_rejects_bool_and_missing_index(self) -> None:
        for index in (True, -1, "1"):
            with self.subTest(index=index), self.assertRaises(ValidationError):
                PackMetadataRegionInputSelector.model_validate({
                    "kind": "region_entry", "entry_index": index,
                    "field": PackRegionMetadataInputField.REGION_UID,
                })
        with self.assertRaises(ValidationError):
            PackMetadataRegionInputSelector.model_validate({
                "kind": "region_entry", "field": PackRegionMetadataInputField.REGION_UID,
            })

    def test_exact_registration_inventory(self) -> None:
        self.assertEqual(tuple(entry.type_id for entry in PACK_METADATA_SCHEMA.entries), tuple(range(20401, 20416)))
        self.assertEqual(len({entry.python_type for entry in PACK_METADATA_SCHEMA.entries}), 15)
