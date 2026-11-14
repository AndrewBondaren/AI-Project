import unittest

from pydantic import BaseModel, ConfigDict

from app.application.worldData.pack.preparation.errors import PackPreparationFailure, preparation_errors, raise_preparation_errors
from app.application.worldData.pack.preparation.packPreparationValidator import PackPreparationValidator
from app.core.constants import FINE_CELL_SIZE
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection
from app.dataModel.worldPack.meta.metadataAttribution import PackMetadataAttribution, PackMetadataGroupAdmission
from app.dataModel.worldPack.meta.parts import PackStoredPart
from app.dataModel.worldPack.meta.metadataAttribution import PackMetadataGroup, PackStoredAssemblyProvenance, PackWildernessStatusBasis
from app.dataModel.worldPack.preparation.addresses import PackAssemblyHeaderAddress, PackLocationTerrainAddress, PackTileMetadataAddress, PackChunkAddress
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput, PackChunkAssembly, PackTileAssembly
from app.dataModel.worldPack.preparation.errors import PackPreparationFailureReason, PackPreparationIssueCode
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataDependencyUse, PackMetadataDescription
from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
from app.dataModel.worldPack.preparation.provenance import PackStoredProvenance
from app.dataModel.worldPack.preparation.state import PackPreparationState
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class IdentityRequest(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, revalidate_instances="always", extra="forbid")
    state: PackPreparationState


class PreparationIdentityAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.base = WorldPublicationRef(world_uid="world", publication_id="publication", pack_hash=None,
                                       snapshot_head=None, active_timeline_id=None, gameplay_started=False)
        self.assembly = PackAssemblyInput(
            last_l0_mode="light", fine_cells_per_map_cell=1000, world_map_cells_per_tile=32,
            fine_cell_size=FINE_CELL_SIZE, map_subsurface_depth=0, terrain_chunk_columns=32,
            tiles=(), locations=(), settlements=(), wilderness_regions=(),
        )
        self.provenance = PackStoredProvenance(
            source_proof=SourceDurableProof(schema_version=1, world_uid="world", uses=()), planning=(),
        )
        self.part = PackStoredPart(address=PackLocationTerrainAddress(kind="location_terrain", location_uid="location"),
            artifact=ArtifactRef(kind=ArtifactKind.BLOB, format_key="test.payload", format_version=1,
                                 content_hash="a" * 64, nbytes=1), provenance=self.provenance)
        self.state = PackPreparationState(base_publication=self.base, parts=(self.part,), assembly=self.assembly,
                                         assembly_provenance=(), metadata_dependencies=())
        self.validator = PackPreparationValidator()

    def test_identity_stage_allows_incomplete_composition(self):
        self.assertEqual(self.validator.validate_state(self.state), self.state)

    def test_multiple_independent_identity_errors_keep_source_indices(self):
        foreign = PackStoredProvenance(
            source_proof=SourceDurableProof(schema_version=1, world_uid="foreign", uses=()), planning=(),
        )
        repeated = self.part.model_copy(update={"provenance": foreign})
        header = PackAssemblyHeaderAddress(kind="header")
        stored = PackStoredAssemblyProvenance(address=header, provenance=foreign, attribution=None)
        usage = PackMetadataDependencyUse(group=PackMetadataGroup.LAST_L0_MODE,
                                          source_usage=SourceProofInput(world_uid="foreign", uses=()), basis=None)
        description = PackMetadataDescription(
            subject=PackMetadataSubject(base_publication=self.base.model_copy(update={"publication_id": "other"}),
                                        address=header, value_fingerprint="b" * 64), dependencies=(usage, usage),
        )
        invalid = self.state.model_copy(update={"parts": (self.part, repeated),
                                               "assembly_provenance": (stored,), "metadata_dependencies": (description,)})
        with self.assertRaises(PackPreparationFailure) as caught:
            self.validator.validate_state(invalid)
        issues = caught.exception.error.issues
        self.assertEqual([issue.code for issue in issues], [
            PackPreparationIssueCode.DUPLICATE_ADDRESS, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
            PackPreparationIssueCode.SOURCE_PROOF_MISMATCH, PackPreparationIssueCode.BASE_PUBLICATION_MISMATCH,
            PackPreparationIssueCode.METADATA_GROUP_MISMATCH, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
            PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
            PackPreparationIssueCode.METADATA_GROUP_MISMATCH,
        ])
        self.assertEqual([issue.path.projection() for issue in issues], [
            ("parts", 1, "address"), ("parts", 1, "provenance", "source_proof", "world_uid"),
            ("assembly_provenance", 0, "provenance", "source_proof", "world_uid"),
            ("metadata_dependencies", 0, "subject", "base_publication"),
            ("metadata_dependencies", 0, "dependencies", 1, "group"),
            ("metadata_dependencies", 0, "dependencies", 0, "source_usage", "world_uid"),
            ("metadata_dependencies", 0, "dependencies", 1, "source_usage", "world_uid"),
            ("metadata_dependencies", 0, "dependencies"),
        ])
        self.assertEqual(self.state.parts, (self.part,))

    def test_duplicate_chunks_are_scoped_to_their_tile(self):
        chunk = PackChunkAssembly(cx=0, cy=0, refine_role=None)
        tile = PackTileAssembly(gx=0, gy=0, climate_status="coarse", wilderness_refine_status="partial", chunks=(chunk,))
        second = tile.model_copy(update={"gx": 1})
        valid = self.state.model_copy(update={"assembly": self.assembly.model_copy(update={"tiles": (tile, second)})})
        self.assertEqual(self.validator.validate_state(valid), valid)
        invalid = valid.model_copy(update={"assembly": self.assembly.model_copy(update={
            "tiles": (tile.model_copy(update={"chunks": (chunk, chunk)}), tile),
        })})
        with self.assertRaises(PackPreparationFailure) as caught:
            self.validator.validate_state(invalid)
        self.assertEqual([issue.path.projection() for issue in caught.exception.error.issues],
                         [("assembly", "tiles", 1), ("assembly", "tiles", 0, "chunks", 1)])

    def test_paths_can_be_rooted_in_named_operation_input(self):
        state = self.state.model_copy(update={"parts": (self.part, self.part)})
        errors = preparation_errors()
        path = CheckedPath.root(IdentityRequest).field(FieldRef(lambda: IdentityRequest, lambda value: value.state))
        self.validator.check_state_identities(state, path, errors)
        with self.assertRaises(PackPreparationFailure) as caught:
            raise_preparation_errors(errors, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
        issue, = caught.exception.error.issues
        self.assertEqual(issue.path.projection(), ("state", "parts", 1, "address"))

    def test_forged_structure_is_still_rejected(self):
        with self.assertRaises(PackPreparationFailure) as caught:
            self.validator.validate_state(self.state.model_copy(update={"parts": []}))
        self.assertIs(caught.exception.error.reason, PackPreparationFailureReason.INVALID_INPUT)

    def test_complete_header_and_each_missing_group_for_both_representations(self):
        groups = (PackMetadataGroup.LAST_L0_MODE, PackMetadataGroup.FINE_CELLS_PER_MAP_CELL,
                  PackMetadataGroup.WORLD_MAP_CELLS_PER_TILE, PackMetadataGroup.FINE_CELL_SIZE,
                  PackMetadataGroup.MAP_SUBSURFACE_DEPTH, PackMetadataGroup.TERRAIN_CHUNK_COLUMNS)
        header = PackAssemblyHeaderAddress(kind="header")
        source = SourceProofInput(world_uid="world", uses=())
        selection = SourceProofSelection(proof_fingerprint="c" * 64, dependency_indices=())
        description = PackMetadataDescription(
            subject=PackMetadataSubject(base_publication=self.base, address=header, value_fingerprint="b" * 64),
            dependencies=tuple(PackMetadataDependencyUse(group=group, source_usage=source, basis=None) for group in groups))
        stored = PackStoredAssemblyProvenance(address=header, provenance=self.provenance,
            attribution=PackMetadataAttribution(groups=tuple(
                PackMetadataGroupAdmission(group=group, selection=selection, basis=None) for group in groups)))
        for representation in ("transient", "stored"):
            complete = self.state.model_copy(update={
                "metadata_dependencies": (description,) if representation == "transient" else (),
                "assembly_provenance": (stored,) if representation == "stored" else (),
            })
            self.assertEqual(self.validator.validate_state(complete), complete)
            for missing in groups:
                with self.subTest(representation=representation, missing=missing):
                    if representation == "transient":
                        invalid = complete.model_copy(update={"metadata_dependencies": (description.model_copy(update={
                            "dependencies": tuple(use for use in description.dependencies if use.group is not missing),
                        }),)})
                        expected_path = ("metadata_dependencies", 0, "dependencies")
                    else:
                        invalid = complete.model_copy(update={"assembly_provenance": (stored.model_copy(update={
                            "attribution": PackMetadataAttribution(groups=tuple(
                                group for group in stored.attribution.groups if group.group is not missing)),
                        }),)})
                        expected_path = ("assembly_provenance", 0, "attribution", "groups")
                    with self.assertRaises(PackPreparationFailure) as caught:
                        self.validator.validate_state(invalid)
                    issue, = caught.exception.error.issues
                    self.assertIs(issue.code, PackPreparationIssueCode.METADATA_GROUP_MISMATCH)
                    self.assertEqual(issue.path.projection(), expected_path)
                    self.assertIn(missing.value, issue.message)

    def test_metadata_group_and_basis_failures_are_independent(self):
        description = PackMetadataDescription(
            subject=PackMetadataSubject(base_publication=self.base, address=PackAssemblyHeaderAddress(kind="header"),
                                        value_fingerprint="b" * 64),
            dependencies=(PackMetadataDependencyUse(group=PackMetadataGroup.WILDERNESS_REFINE_STATUS,
                          source_usage=SourceProofInput(world_uid="world", uses=()), basis=None),),
        )
        with self.assertRaises(PackPreparationFailure) as caught:
            self.validator.validate_state(self.state.model_copy(update={"metadata_dependencies": (description,)}))
        self.assertEqual([issue.code for issue in caught.exception.error.issues], [
            PackPreparationIssueCode.METADATA_GROUP_MISMATCH, PackPreparationIssueCode.METADATA_BASIS_MISMATCH,
            PackPreparationIssueCode.METADATA_GROUP_MISMATCH,
        ])

    def test_wilderness_basis_keeps_tile_identity_and_rejects_duplicates(self):
        chunk = PackChunkAddress(kind="wilderness_chunk", gx=0, gy=0, cx=0, cy=0)
        usage = PackMetadataDependencyUse(group=PackMetadataGroup.WILDERNESS_REFINE_STATUS,
            source_usage=SourceProofInput(world_uid="world", uses=()),
            basis=PackWildernessStatusBasis(chunk_addresses=(chunk,), expected_chunks=None))
        description = PackMetadataDescription(
            subject=PackMetadataSubject(base_publication=self.base, address=PackTileMetadataAddress(kind="tile", gx=0, gy=0),
                                        value_fingerprint="b" * 64), dependencies=(usage,
                usage.model_copy(update={"group": PackMetadataGroup.IDENTITY, "basis": None}),
                usage.model_copy(update={"group": PackMetadataGroup.CLIMATE_STATUS, "basis": None})))
        state = self.state.model_copy(update={"metadata_dependencies": (description,)})
        self.assertEqual(self.validator.validate_state(state), state)
        foreign = chunk.model_copy(update={"gx": 1})
        bad = usage.model_copy(update={"basis": PackWildernessStatusBasis(
            chunk_addresses=(chunk, chunk, foreign), expected_chunks=-1)})
        with self.assertRaises(PackPreparationFailure) as caught:
            self.validator.validate_state(state.model_copy(update={"metadata_dependencies": (
                description.model_copy(update={"dependencies": (bad, *description.dependencies[1:])}),)}))
        self.assertEqual([issue.path.projection() for issue in caught.exception.error.issues], [
            ("metadata_dependencies", 0, "dependencies", 0, "basis", "chunk_addresses", 1),
            ("metadata_dependencies", 0, "dependencies", 0, "basis", "chunk_addresses", 2),
        ])
