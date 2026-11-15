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
    def _grade_writes(self):
        from app.dataModel.worldPack.preparation.operations import PackTileGradeSlotsInput, PackLocationGradeSlotsInput
        from app.dataModel.worldPack.preparation.parts import PackTileGradeSlotsPartInput, PackLocationGradeSlotsPartInput
        from app.dataModel.worldPack.preparation.addresses import PackTileGradeSlotsAddress, PackLocationGradeSlotsAddress
        from app.dataModel.worldPack.meta.gradeSlotsStorageFormat import GRADE_SLOTS_FORMAT_KEY, GRADE_SLOTS_STORAGE_VERSION
        artifact = self.part.artifact.model_copy(update={"format_key": GRADE_SLOTS_FORMAT_KEY,
                                                        "format_version": GRADE_SLOTS_STORAGE_VERSION})
        tile = PackTileGradeSlotsPartInput(address=PackTileGradeSlotsAddress(kind="tile_grade_slots", gx=0, gy=0),
                                          artifact=artifact, provenance=self.part.provenance)
        location = PackLocationGradeSlotsPartInput(address=PackLocationGradeSlotsAddress(kind="location_grade_slots", location_uid="place"),
                                                  artifact=artifact, provenance=self.part.provenance)
        return ((self.service.write_tile_grade_slots, PackTileGradeSlotsInput, tile),
                (self.service.write_location_grade_slots, PackLocationGradeSlotsInput, location))

    def test_grade_writes_replace_only_exact_address(self):
        state = self.state
        for method, model, part in self._grade_writes():
            original = state
            first = method(model(state=state, part=part))
            replacement = part.model_copy(update={"artifact": part.artifact.model_copy(update={"content_hash": "b" * 64})})
            state = method(model(state=first, part=replacement))
            self.assertEqual(state.parts[:-1], original.parts)
            self.assertEqual(state.parts[-1].artifact, replacement.artifact)
            self.assertEqual(first.parts[-1].artifact, part.artifact)
            self.assertEqual(state.assembly, original.assembly)
            self.assertEqual(state.assembly_provenance, original.assembly_provenance)
            self.assertEqual(state.metadata_dependencies, original.metadata_dependencies)
            self.assertEqual(state.base_publication, original.base_publication)
        self.assertEqual(len(state.parts), 3)

    def test_grade_planning_error_keeps_foreign_proof_diagnostic(self):
        for method, model, part in self._grade_writes():
            origin = part.provenance.provenance
            malformed = part.model_copy(update={"provenance": part.provenance.model_copy(update={"provenance":
                origin.model_copy(update={"planning": [], "source_proof": origin.source_proof.model_copy(update={"world_uid": "foreign"})})})})
            with self.assertRaises(PackPreparationFailure) as caught:
                method(model.model_construct(state=self.state, part=malformed))
            self.assertEqual([(issue.code, issue.path.projection() if hasattr(issue, "path") else issue.location.parts)
                              for issue in caught.exception.error.issues], [
                ("SCHEMA_VIOLATION", ("part", "provenance", "new", "provenance", "planning")),
                (PackPreparationIssueCode.SOURCE_PROOF_MISMATCH, ("part", "provenance")),
            ])

    def _spatial_part(self):
        from app.dataModel.worldPack.preparation.parts import PackSpatialRootPartInput
        from app.dataModel.worldPack.preparation.addresses import PackSpatialRootAddress
        from app.dataModel.worldPack.meta.spatial.domainRoot import SpatialDatasetKind
        from app.dataModel.hydrology.pack.profile import ROOT_V1, FORMAT_VERSION
        return PackSpatialRootPartInput(address=PackSpatialRootAddress(kind="spatial_root",
            domain=SpatialDatasetKind.HYDROLOGY_OPEN_WATER),
            artifact=self.part.artifact.model_copy(update={"format_key": ROOT_V1.key, "format_version": FORMAT_VERSION}),
            provenance=self.part.provenance)

    def test_spatial_root_add_replace_preserves_composition(self):
        from app.dataModel.worldPack.preparation.operations import PackSpatialRootInput
        part = self._spatial_part()
        for state in (self.state, self.state.model_copy(update={"parts": ()})):
            first = self.service.write_spatial_root(PackSpatialRootInput(state=state, part=part))
            replacement = part.model_copy(update={"artifact": part.artifact.model_copy(update={"content_hash": "b" * 64})})
            second = self.service.write_spatial_root(PackSpatialRootInput(state=first, part=replacement))
            self.assertEqual(second.parts[:-1], state.parts)
            self.assertEqual(second.parts[-1].artifact, replacement.artifact)
            self.assertEqual(first.parts[-1].artifact, part.artifact)
            self.assertEqual(second.assembly, state.assembly)
            self.assertEqual(second.assembly_provenance, state.assembly_provenance)
            self.assertEqual(second.metadata_dependencies, state.metadata_dependencies)
            self.assertEqual(second.base_publication, state.base_publication)

    def test_spatial_root_aggregates_schema_duplicate_and_descriptor(self):
        from app.dataModel.worldPack.preparation.operations import PackSpatialRootInput
        from app.dataModel.hydrology.pack.profile import SHARD_V1
        part = self._spatial_part()
        bad = part.model_copy(update={"address": part.address.model_copy(update={"kind": "bad"}),
                                      "artifact": part.artifact.model_copy(update={"format_key": SHARD_V1.key})})
        state = self.state.model_copy(update={"parts": (self.fine, self.fine)})
        for value in (bad, dict(vars(bad))):
            with self.assertRaises(PackPreparationFailure) as caught:
                self.service.write_spatial_root(PackSpatialRootInput.model_construct(state=state, part=value))
            self.assertEqual([(issue.code, issue.path.projection()) for issue in caught.exception.error.issues], [
                ("SCHEMA_VIOLATION", ("part", "address", "kind")),
                (PackPreparationIssueCode.DUPLICATE_ADDRESS, ("state", "parts", 1, "address")),
                (PackPreparationIssueCode.FORMAT_MISMATCH, ("part", "artifact")),
            ])

    def test_spatial_root_rejects_foreign_and_inherited_provenance(self):
        from app.dataModel.worldPack.preparation.operations import PackSpatialRootInput
        part = self._spatial_part()
        foreign = part.provenance.provenance.model_copy(update={"source_proof":
            part.provenance.provenance.source_proof.model_copy(update={"world_uid": "foreign"})})
        for provenance in (PackNewPartProvenance(kind="new", provenance=foreign),
                           PackInheritedPartProvenance(kind="inherited", provenance=part.provenance.provenance)):
            with self.assertRaises(PackPreparationFailure) as caught:
                self.service.write_spatial_root(PackSpatialRootInput(state=self.state,
                    part=part.model_copy(update={"provenance": provenance})))
            self.assertEqual([(issue.code, issue.path.projection()) for issue in caught.exception.error.issues],
                             [(PackPreparationIssueCode.SOURCE_PROOF_MISMATCH, ("part", "provenance"))])

    def test_spatial_planning_error_does_not_hide_proof_world(self):
        from app.dataModel.worldPack.preparation.operations import PackSpatialRootInput
        part = self._spatial_part()
        for world in ("foreign", "world", 123):
            origin = part.provenance.provenance.model_copy(update={"planning": [],
                "source_proof": part.provenance.provenance.source_proof.model_copy(update={"world_uid": world})})
            wrapper = part.provenance.model_copy(update={"provenance": origin})
            mapping = dict(vars(wrapper))
            mapping["provenance"] = dict(vars(origin))
            mapping["provenance"]["source_proof"] = dict(vars(origin.source_proof))
            for value in (wrapper, mapping):
                with self.subTest(world=world, representation=type(value).__name__):
                    bad = part.model_copy(update={"provenance": value})
                    with self.assertRaises(PackPreparationFailure) as caught:
                        self.service.write_spatial_root(PackSpatialRootInput.model_construct(state=self.state, part=bad))
                    expected = []
                    if world == 123:
                        expected.append(("SCHEMA_VIOLATION", ("part", "provenance", "new", "provenance", "source_proof", "world_uid")))
                    expected.append(("SCHEMA_VIOLATION", ("part", "provenance", "new", "provenance", "planning")))
                    if world == "foreign":
                        expected.append((PackPreparationIssueCode.SOURCE_PROOF_MISMATCH, ("part", "provenance")))
                    self.assertEqual([(issue.code, issue.path.projection() if hasattr(issue, "path") else issue.location.parts)
                                      for issue in caught.exception.error.issues], expected)

    def test_start_empty_preserves_explicit_header(self):
        from app.dataModel.worldPack.preparation.operations import PackPreparationEmptyInput
        assembly = self.state.assembly.model_copy(update={"tiles": ()})
        request = PackPreparationEmptyInput(base_publication=self.state.base_publication, initial_assembly=assembly)
        result = self.service.start_empty(request)
        self.assertEqual(result.assembly, assembly)
        self.assertEqual(result.base_publication, request.base_publication)
        self.assertEqual((result.parts, result.assembly_provenance, result.metadata_dependencies), ((), (), ()))
        self.assertEqual(self.state.parts, (self.fine,))
        self.assertEqual(len(self.state.assembly.tiles), 1)

    def test_start_empty_aggregates_schema_base_and_collection_refusals(self):
        from app.dataModel.worldPack.preparation.operations import PackPreparationEmptyInput
        base = self.state.base_publication.model_copy(update={"pack_hash": "a" * 64})
        assembly = self.state.assembly.model_copy(update={"fine_cell_size": "bad"})
        request = PackPreparationEmptyInput.model_construct(base_publication=base, initial_assembly=assembly)
        with self.assertRaises(PackPreparationFailure) as caught:
            self.service.start_empty(request)
        self.assertEqual([(issue.code, issue.path.projection()) for issue in caught.exception.error.issues], [
            ("SCHEMA_VIOLATION", ("initial_assembly", "fine_cell_size")),
            (PackPreparationIssueCode.BASE_PUBLICATION_MISMATCH, ("base_publication",)),
            (PackPreparationIssueCode.METADATA_INPUT_MISMATCH, ("initial_assembly", "tiles")),
        ])

    def test_start_empty_checks_pack_hash_independently(self):
        from app.dataModel.worldPack.preparation.operations import PackPreparationEmptyInput
        assembly = self.state.assembly.model_copy(update={"tiles": ()})
        for pack_hash in ("a" * 64, None, "bad"):
            base = self.state.base_publication.model_copy(update={"pack_hash": pack_hash, "publication_id": 123})
            for value in (base, dict(vars(base))):
                with self.subTest(pack_hash=pack_hash, representation=type(value).__name__):
                    request = PackPreparationEmptyInput.model_construct(base_publication=value, initial_assembly=assembly)
                    with self.assertRaises(PackPreparationFailure) as caught:
                        self.service.start_empty(request)
                    expected = [("SCHEMA_VIOLATION", ("base_publication", "publication_id"))]
                    if pack_hash == "bad":
                        expected.append(("SCHEMA_VIOLATION", ("base_publication", "pack_hash")))
                    elif pack_hash is not None:
                        expected.append((PackPreparationIssueCode.BASE_PUBLICATION_MISMATCH, ("base_publication",)))
                    self.assertEqual([(issue.code, issue.path.projection()) for issue in caught.exception.error.issues], expected)

    def test_missing_basis_is_distinct_from_explicit_null(self):
        from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection
        from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
        from app.dataModel.worldPack.meta.metadataAttribution import (
            PackStoredAssemblyProvenance, PackMetadataAttribution, PackMetadataGroupAdmission, PackMetadataGroup as G)
        from app.dataModel.worldPack.preparation.addresses import PackTileMetadataAddress
        from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataDescription, PackMetadataDependencyUse
        from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
        address = PackTileMetadataAddress(kind="tile", gx=0, gy=0)
        selection = SourceProofSelection(proof_fingerprint="b" * 64, dependency_indices=())
        usage = SourceProofInput(world_uid="world", uses=())
        for transient in (False, True):
            model = PackMetadataDependencyUse if transient else PackMetadataGroupAdmission
            payload = {"source_usage": usage} if transient else {"selection": selection}
            for basis_fields, expected_code in (({}, "SCHEMA_VIOLATION"), ({"basis": None}, PackPreparationIssueCode.METADATA_BASIS_MISMATCH),
                                                ({"basis": "bad"}, "SCHEMA_VIOLATION")):
                group = model.model_construct(group=G.WILDERNESS_REFINE_STATUS, **payload, **basis_fields)
                for as_mapping in (False, True):
                    groups = tuple(model(group=key, basis=None, **payload) for key in (G.IDENTITY, G.CLIMATE_STATUS))
                    groups += (dict(vars(group)) if as_mapping else group,)
                    if transient:
                        entry = PackMetadataDescription.model_construct(subject=PackMetadataSubject(
                            base_publication=self.state.base_publication, address=address, value_fingerprint="c" * 64),
                            dependencies=groups)
                        field, suffix = "metadata_dependencies", ("dependencies", 2, "basis")
                    else:
                        entry = PackStoredAssemblyProvenance.model_construct(address=address,
                            provenance=self.part.provenance.provenance,
                            attribution=PackMetadataAttribution.model_construct(groups=groups))
                        field, suffix = "assembly_provenance", ("attribution", "groups", 2, "basis")
                    state = self.state.model_copy(update={field: (entry,)})
                    for method, request_model, part in self._writes():
                        with self.subTest(transient=transient, basis=basis_fields, mapping=as_mapping, method=method.__name__):
                            with self.assertRaises(PackPreparationFailure) as caught:
                                method(request_model.model_construct(state=state, part=part))
                            self.assertEqual([(issue.code, issue.path.projection()) for issue in caught.exception.error.issues],
                                             [(expected_code, ("state", field, 0, *suffix))])

    def test_semantic_predicates_ignore_unrelated_invalid_fields(self):
        from app.dataModel.worldPack.meta.metadataAttribution import (
            PackStoredAssemblyProvenance, PackMetadataAttribution, PackMetadataGroupAdmission, PackMetadataGroup as G)
        from app.dataModel.worldPack.preparation.addresses import PackTileMetadataAddress
        from app.dataModel.worldPack.preparation.assembly import PackChunkAssembly
        from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataDescription, PackMetadataDependencyUse
        from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
        address = PackTileMetadataAddress(kind="tile", gx=0, gy=0)
        group = PackMetadataGroupAdmission.model_construct(group=G.WILDERNESS_REFINE_STATUS, basis=None, selection="bad")
        stored = PackStoredAssemblyProvenance.model_construct(address=address, provenance=self.part.provenance.provenance,
            attribution=PackMetadataAttribution.model_construct(groups=(group,)))
        plain = PackStoredAssemblyProvenance(address=address, provenance=self.part.provenance.provenance, attribution=None)
        subject = PackMetadataSubject(base_publication=self.state.base_publication.model_copy(update={"publication_id": "other"}),
                                      address=address, value_fingerprint="b" * 64)
        description = PackMetadataDescription.model_construct(subject=subject, dependencies=(
            PackMetadataDependencyUse.model_construct(group=G.IDENTITY, basis=None, source_usage="bad"),))
        tile = self.state.assembly.tiles[0]
        chunk = PackChunkAssembly(cx=0, cy=0, refine_role=None)
        cases = (
            ({"assembly_provenance": (stored,)}, PackPreparationIssueCode.METADATA_BASIS_MISMATCH,
             ("assembly_provenance", 0, "attribution", "groups", 0, "basis")),
            ({"assembly_provenance": (plain, plain.model_copy(update={"attribution": "bad"}))},
             PackPreparationIssueCode.DUPLICATE_ADDRESS, ("assembly_provenance", 1, "address")),
            ({"metadata_dependencies": (description,)}, PackPreparationIssueCode.BASE_PUBLICATION_MISMATCH,
             ("metadata_dependencies", 0, "subject", "base_publication")),
            ({"assembly": self.state.assembly.model_copy(update={"tiles": (tile, tile.model_copy(update={"climate_status": "bad"}))})},
             PackPreparationIssueCode.DUPLICATE_ADDRESS, ("assembly", "tiles", 1)),
            ({"assembly": self.state.assembly.model_copy(update={"tiles": (tile.model_copy(update={
                "chunks": (chunk, chunk.model_copy(update={"refine_role": "bad"}))}),)})},
             PackPreparationIssueCode.DUPLICATE_ADDRESS, ("assembly", "tiles", 0, "chunks", 1)),
        )
        for update, code, path in cases:
            state = self.state.model_copy(update=update)
            for method, model, part in self._writes():
                with self.subTest(path=path, method=method.__name__), self.assertRaises(PackPreparationFailure) as caught:
                    method(model.model_construct(state=state, part=part))
                matches = [issue for issue in caught.exception.error.issues
                           if hasattr(issue, "path") and issue.path.projection() == ("state", *path) and issue.code == code]
                self.assertEqual(len(matches), 1)

    def test_bad_artifact_does_not_hide_duplicate_address(self):
        bad = self.fine.model_copy(update={"artifact": self.fine.artifact.model_copy(update={"nbytes": "bad"})})
        state = self.state.model_copy(update={"parts": (self.fine, bad)})
        for method, model, part in self._writes():
            with self.subTest(method=method.__name__), self.assertRaises(PackPreparationFailure) as caught:
                method(model.model_construct(state=state, part=part))
            self.assertEqual([issue.path.projection() for issue in caught.exception.error.issues], [
                ("state", "parts", 1, "artifact", "nbytes"), ("state", "parts", 1, "address")])

    def test_bad_selection_does_not_hide_disallowed_group(self):
        from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection
        from app.dataModel.worldPack.meta.metadataAttribution import (
            PackMetadataGroup as G, PackMetadataGroupAdmission, PackMetadataAttribution, PackStoredAssemblyProvenance)
        from app.dataModel.worldPack.preparation.addresses import PackAssemblyHeaderAddress
        selection = SourceProofSelection(proof_fingerprint="b" * 64, dependency_indices=())
        groups = tuple(PackMetadataGroupAdmission(group=group, selection=selection, basis=None) for group in (
            G.LAST_L0_MODE, G.FINE_CELLS_PER_MAP_CELL, G.WORLD_MAP_CELLS_PER_TILE,
            G.FINE_CELL_SIZE, G.MAP_SUBSURFACE_DEPTH, G.TERRAIN_CHUNK_COLUMNS))
        bad = PackMetadataGroupAdmission.model_construct(group=G.STRUCTURE_STATUS, selection="bad", basis=None)
        stored = PackStoredAssemblyProvenance.model_construct(address=PackAssemblyHeaderAddress(kind="header"),
            provenance=self.part.provenance.provenance,
            attribution=PackMetadataAttribution.model_construct(groups=(*groups, bad)))
        state = self.state.model_copy(update={"assembly_provenance": (stored,)})
        for method, model, part in self._writes():
            with self.subTest(method=method.__name__), self.assertRaises(PackPreparationFailure) as caught:
                method(model.model_construct(state=state, part=part))
            self.assertEqual([issue.path.projection() for issue in caught.exception.error.issues], [
                ("state", "assembly_provenance", 0, "attribution", "groups", 6, "selection"),
                ("state", "assembly_provenance", 0, "attribution", "groups", 6, "group")])

    def test_invalid_metadata_group_keeps_sibling_duplicates(self):
        from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection
        from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
        from app.dataModel.worldPack.meta.metadataAttribution import (
            PackMetadataGroup, PackMetadataGroupAdmission, PackMetadataAttribution, PackStoredAssemblyProvenance)
        from app.dataModel.worldPack.preparation.addresses import PackAssemblyHeaderAddress
        from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataDescription, PackMetadataDependencyUse
        from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
        header = PackAssemblyHeaderAddress(kind="header")
        group = PackMetadataGroupAdmission(group=PackMetadataGroup.LAST_L0_MODE,
            selection=SourceProofSelection(proof_fingerprint="b" * 64, dependency_indices=()), basis=None)
        bad = group.model_copy(update={"group": PackMetadataGroup.FINE_CELL_SIZE, "selection": "bad"})
        usage = PackMetadataDependencyUse(group=PackMetadataGroup.LAST_L0_MODE,
            source_usage=SourceProofInput(world_uid="world", uses=()), basis=None)
        bad_use = usage.model_copy(update={"group": PackMetadataGroup.FINE_CELL_SIZE, "source_usage": "bad"})
        for bad_first in (False, True):
            groups = (bad, group, group) if bad_first else (group, group, bad)
            uses = (bad_use, usage, usage) if bad_first else (usage, usage, bad_use)
            stored = PackStoredAssemblyProvenance.model_construct(address=header, provenance=self.part.provenance.provenance,
                attribution=PackMetadataAttribution.model_construct(groups=groups))
            description = PackMetadataDescription.model_construct(subject=PackMetadataSubject(
                base_publication=self.state.base_publication, address=header, value_fingerprint="c" * 64), dependencies=uses)
            for field, entry, suffix in (
                ("assembly_provenance", stored, ("attribution", "groups")),
                ("metadata_dependencies", description, ("dependencies",)),
            ):
                state = self.state.model_copy(update={field: (entry,)})
                for method, model, part in self._writes():
                    with self.subTest(field=field, method=method.__name__, bad_first=bad_first):
                        with self.assertRaises(PackPreparationFailure) as caught:
                            method(model.model_construct(state=state, part=part))
                        expected = ("state", field, 0, *suffix, 2 if bad_first else 1, "group")
                        matching = [issue for issue in caught.exception.error.issues
                                    if hasattr(issue, "path") and issue.path.projection() == expected]
                        self.assertEqual(len(matching), 1)
                        self.assertIs(matching[0].code, PackPreparationIssueCode.METADATA_GROUP_MISMATCH)

    def test_forged_mapping_part_cannot_bypass_format_admission(self):
        for method, model, part in self._writes():
            for mapping in (dict(vars(part)), part.model_dump(mode="python")):
                artifact = dict(vars(part.artifact))
                artifact["format_version"] = 100
                mapping["artifact"] = artifact
                with self.subTest(method=method.__name__), self.assertRaises(PackPreparationFailure) as caught:
                    method(model.model_construct(state=self.state, part=mapping))
                self.assertIn(PackPreparationIssueCode.FORMAT_MISMATCH,
                              [issue.code for issue in caught.exception.error.issues])

    def test_mapping_state_cannot_bypass_delete_noop_admission(self):
        from app.dataModel.worldPack.preparation.operations import PackDeletePartInput
        mapping = dict(vars(self.state))
        mapping["parts"] = (self.fine, self.fine)
        with self.assertRaises(PackPreparationFailure) as caught:
            self.service.delete_part(PackDeletePartInput.model_construct(state=mapping, address=self.part.address))
        issue, = caught.exception.error.issues
        self.assertIs(issue.code, PackPreparationIssueCode.DUPLICATE_ADDRESS)
        self.assertEqual(issue.path.projection(), ("state", "parts", 1, "address"))
        self.assertEqual(mapping["parts"], (self.fine, self.fine))

    def test_bad_chunk_does_not_hide_valid_siblings(self):
        from app.dataModel.worldPack.preparation.assembly import PackChunkAssembly
        from app.application.worldData.pack.preparation.packPreparationValidator import PackPreparationValidator
        chunk = PackChunkAssembly(cx=0, cy=0, refine_role=None)
        bad = chunk.model_copy(update={"cx": "bad"})
        for chunks, duplicate in (((chunk, chunk, bad), 1), ((bad, chunk, chunk), 2)):
            tile = self.state.assembly.tiles[0].model_copy(update={"chunks": chunks})
            state = self.state.model_copy(update={"assembly": self.state.assembly.model_copy(update={"tiles": (tile,)})})
            for method, model, part in self._writes():
                with self.subTest(method=method.__name__, duplicate=duplicate), self.assertRaises(PackPreparationFailure) as caught:
                    method(model.model_construct(state=state, part=part))
                self.assertEqual(len(caught.exception.error.issues), 2)
                self.assertIs(caught.exception.error.issues[1].code, PackPreparationIssueCode.DUPLICATE_ADDRESS)
                self.assertEqual(caught.exception.error.issues[1].path.projection(),
                                 ("state", "assembly", "tiles", 0, "chunks", duplicate))
            with self.assertRaises(PackPreparationFailure) as caught:
                PackPreparationValidator().validate_state(state)
            self.assertEqual(caught.exception.error.issues[1].path.projection(),
                             ("assembly", "tiles", 0, "chunks", duplicate))

    def test_bad_address_does_not_hide_artifact_format(self):
        for method, model, part in self._writes():
            bad = part.model_copy(update={"address": part.address.model_copy(update={"kind": "bad"}),
                                         "artifact": part.artifact.model_copy(update={"format_version": 100})})
            with self.subTest(method=method.__name__), self.assertRaises(PackPreparationFailure) as caught:
                method(model.model_construct(state=self.state, part=bad))
            self.assertEqual([issue.path.projection() for issue in caught.exception.error.issues],
                             [("part", "address", "kind"), ("part", "artifact")])
            self.assertIs(caught.exception.error.issues[1].code, PackPreparationIssueCode.FORMAT_MISMATCH)

    def test_each_metadata_collection_preserves_valid_sibling_checks(self):
        from app.dataModel.worldPack.meta.metadataAttribution import PackStoredAssemblyProvenance
        from app.dataModel.worldPack.preparation.addresses import PackAssemblyHeaderAddress
        from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataDescription
        from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
        from app.dataModel.worldPack.preparation.assembly import PackLocationAssembly, PackSettlementAssembly
        from app.dataModel.worldPack.wire.territoryVolume import TerritoryVolume
        from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry, WildernessRegionStatus, RegionIndexBounds
        from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
        volume = TerritoryVolume(x0=0, y0=0, z0=0, x1=1, y1=1, z1=1)
        location = PackLocationAssembly(location_uid="place", territory_volume=volume, climate_status="coarse")
        settlement = PackSettlementAssembly(location_uid="place", territory_volume=volume,
                                            structure_status="absent", packed_district_uids=())
        region = WildernessRegionEntry(region_uid="region", entry_type=WorldTerrainRegistry.forest_terrain_key(),
            current_type=WorldTerrainRegistry.forest_terrain_key(), bbox=RegionIndexBounds(x_min=0, y_min=0, x_max=1, y_max=1),
            status=WildernessRegionStatus.DECLARED, parent_region_uid=None, spec_fingerprint=None)
        entry = PackStoredAssemblyProvenance(address=PackAssemblyHeaderAddress(kind="header"),
                                            provenance=self.part.provenance.provenance, attribution=None)
        description = PackMetadataDescription(subject=PackMetadataSubject(base_publication=self.state.base_publication,
            address=entry.address, value_fingerprint="b" * 64), dependencies=())
        cases = (
            ("tiles", self.state.assembly.tiles[0], "gx", True, ()),
            ("locations", location, "climate_status", True, ()),
            ("settlements", settlement, "structure_status", True, ()),
            ("wilderness_regions", region, "status", True, ()),
            ("assembly_provenance", entry, "attribution", False, ("address",)),
            ("metadata_dependencies", description, "subject", False, ("subject", "address")),
        )
        for field, row, bad_field, in_assembly, suffix in cases:
            bad = row.model_copy(update={bad_field: "bad"})
            for position in (0, 1, 2):
                rows = (bad, row, row) if position == 0 else ((row, bad) if position == 1 else (row, row, bad))
                duplicate_index = 2 if position == 0 else 1
                state = (self.state.model_copy(update={"assembly": self.state.assembly.model_copy(update={field: rows})})
                         if in_assembly else self.state.model_copy(update={field: rows}))
                expected = ("state",) + (("assembly",) if in_assembly else ()) + (field, duplicate_index) + suffix
                for method, model, part in self._writes():
                    with self.subTest(field=field, position=position, method=method.__name__):
                        with self.assertRaises(PackPreparationFailure) as caught:
                            method(model.model_construct(state=state, part=part))
                        duplicates = [issue.path.projection() for issue in caught.exception.error.issues
                                      if issue.code == PackPreparationIssueCode.DUPLICATE_ADDRESS]
                        identity_survives = field in ("locations", "settlements", "wilderness_regions", "assembly_provenance")
                        expected_duplicates = (
                            [("state",) + (("assembly",) if in_assembly else ()) + (field, i) + suffix
                             for i in range(1, len(rows))] if identity_survives
                            else ([] if position == 1 else [expected]))
                        self.assertEqual(duplicates, expected_duplicates)
                        structural_path = ("state",) + (("assembly",) if in_assembly else ()) + (field, position, bad_field)
                        self.assertEqual(caught.exception.error.issues[0].path.projection(), structural_path)
                        self.assertEqual(caught.exception.error.issues[0].code, "SCHEMA_VIOLATION")

    def test_bad_element_does_not_hide_other_parts_duplicates(self):
        from app.application.worldData.pack.preparation.packPreparationValidator import PackPreparationValidator
        bad = self.fine.model_copy(update={"address": self.fine.address.model_copy(update={"gx": 9}),
                                          "artifact": self.fine.artifact.model_copy(update={"nbytes": "bad"})})
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
                (self.service.replace_locations_index, PackLocationsIndexInput, index), *self._grade_writes())

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
