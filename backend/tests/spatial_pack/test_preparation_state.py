import unittest

from pydantic import ValidationError

from app.application.worldData.pack.preparation.errors import (
    PackPreparationFailure, preparation_errors, raise_preparation_errors, validate_preparation_input,
)
from app.core.constants import FINE_CELL_SIZE
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection
from app.dataModel.worldPack.meta.metadataAttribution import (
    PackMetadataAttribution, PackMetadataGroup, PackMetadataGroupAdmission,
    PackStoredAssemblyProvenance, PackWildernessStatusBasis,
)
from app.dataModel.worldPack.preparation.addresses import PackAssemblyHeaderAddress
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput
from app.dataModel.worldPack.preparation.errors import PackPreparationFailureReason
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataDependencyUse, PackMetadataDescription
from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
from app.dataModel.worldPack.preparation.provenance import PackStoredProvenance
from app.dataModel.worldPack.preparation.state import PackPreparationState
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class PreparationStateTests(unittest.TestCase):
    def setUp(self):
        self.publication = WorldPublicationRef(world_uid="world", publication_id="publication", pack_hash=None,
                                               snapshot_head=None, active_timeline_id=None, gameplay_started=False)
        self.assembly = PackAssemblyInput(
            last_l0_mode="light", fine_cells_per_map_cell=1000, world_map_cells_per_tile=32,
            fine_cell_size=FINE_CELL_SIZE, map_subsurface_depth=0, terrain_chunk_columns=32,
            tiles=(), locations=(), settlements=(), wilderness_regions=(),
        )
        self.address = PackAssemblyHeaderAddress(kind="header")
        self.usage = PackMetadataDependencyUse(group=PackMetadataGroup.LAST_L0_MODE,
                                              source_usage=SourceProofInput(world_uid="world", uses=()), basis=None)
        self.description = PackMetadataDescription(
            subject=PackMetadataSubject(base_publication=self.publication, address=self.address,
                                        value_fingerprint="a" * 64), dependencies=(self.usage,),
        )
        self.state = PackPreparationState(base_publication=self.publication, parts=(), assembly=self.assembly,
                                         assembly_provenance=(), metadata_dependencies=(self.description,))

    def test_partial_state_preserves_transient_usage_without_fabricating_proof(self):
        result = PackPreparationState.model_validate(self.state, strict=True)
        self.assertEqual(result.metadata_dependencies, (self.description,))
        self.assertEqual(result.assembly_provenance, ())
        self.assertEqual(result.base_publication, self.publication)
        self.assertEqual(result.assembly, self.assembly)
        with self.assertRaises(ValidationError):
            result.metadata_dependencies = ()

    def test_state_fields_are_explicit_and_collections_strict(self):
        for field in PackPreparationState.model_fields:
            raw = dict(vars(self.state))
            del raw[field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                PackPreparationState.model_validate(raw)
        for field in ("parts", "assembly_provenance", "metadata_dependencies"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                PackPreparationState.model_validate(self.state.model_copy(update={field: []}))

    def test_forged_usage_and_subject_are_revalidated_with_precise_diagnostics(self):
        description = self.description.model_copy(update={
            "subject": self.description.subject.model_copy(update={"value_fingerprint": "bad"}),
            "dependencies": (self.usage.model_copy(update={
                "source_usage": self.usage.source_usage.model_copy(update={"world_uid": False}),
            }),),
        })
        forged = self.state.model_copy(update={"metadata_dependencies": (description,)})
        errors = preparation_errors()
        self.assertIsNone(validate_preparation_input(PackPreparationState, forged, errors))
        with self.assertRaises(PackPreparationFailure) as caught:
            raise_preparation_errors(errors, PackPreparationFailureReason.INVALID_INPUT)
        self.assertEqual([issue.path.projection() for issue in caught.exception.error.issues], [
            ("metadata_dependencies", 0, "subject", "value_fingerprint"),
            ("metadata_dependencies", 0, "dependencies", 0, "source_usage", "world_uid"),
        ])
        self.assertEqual(self.state.metadata_dependencies, (self.description,))

    def test_stored_attribution_uses_owning_selection_validation(self):
        selection = SourceProofSelection(proof_fingerprint="b" * 64, dependency_indices=())
        group = PackMetadataGroupAdmission(group=PackMetadataGroup.LAST_L0_MODE, selection=selection, basis=None)
        stored = PackStoredAssemblyProvenance(
            address=self.address,
            provenance=PackStoredProvenance(source_proof=SourceDurableProof(schema_version=1, world_uid="world", uses=()),
                                             planning=()),
            attribution=PackMetadataAttribution(groups=(group,)),
        )
        state = PackPreparationState.model_validate(self.state.model_copy(update={"assembly_provenance": (stored,)}))
        self.assertEqual(state.assembly_provenance, (stored,))
        malformed = stored.model_copy(update={"attribution": stored.attribution.model_copy(update={
            "groups": (group.model_copy(update={"selection": selection.model_copy(update={"dependency_indices": (True,)})}),),
        })})
        with self.assertRaises(ValidationError):
            PackPreparationState.model_validate(state.model_copy(update={"assembly_provenance": (malformed,)}))

    def test_basis_preserves_nullable_and_negative_expected_policy(self):
        for expected in (None, -1, 0, 10):
            self.assertEqual(PackWildernessStatusBasis(chunk_addresses=(), expected_chunks=expected).expected_chunks,
                             expected)
        with self.assertRaises(ValidationError):
            PackWildernessStatusBasis(chunk_addresses=(), expected_chunks=True)
        with self.assertRaises(ValidationError):
            PackMetadataDependencyUse(group="last_l0_mode", source_usage=self.usage.source_usage, basis=None)
