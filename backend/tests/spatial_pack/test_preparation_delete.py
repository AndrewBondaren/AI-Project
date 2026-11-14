import unittest
from pydantic import ValidationError

from app.application.worldData.pack.preparation.errors import PackPreparationFailure
from app.application.worldData.pack.preparation.packPreparationService import PackPreparationService
from app.core.constants import FINE_CELL_SIZE
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.worldPack.meta.parts import PackStoredPart
from app.dataModel.worldPack.preparation.addresses import PackMapTileAddress
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput, PackTileAssembly
from app.dataModel.worldPack.preparation.errors import PackPreparationFailureReason, PackPreparationIssueCode
from app.dataModel.worldPack.preparation.operations import PackDeletePartInput
from app.dataModel.worldPack.preparation.provenance import PackStoredProvenance
from app.dataModel.worldPack.preparation.state import PackPreparationState
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldPack.preparation.operations import PackDeleteLocationTerrainInput, PackDeleteSettlementStructureInput
from app.dataModel.worldPack.preparation.addresses import (
    PackLocationTerrainAddress, PackSettlementAddress, PackLocationMetadataAddress,
    PackSettlementMetadataAddress, PackLocationGradeSlotsAddress,
)
from app.dataModel.worldPack.preparation.assembly import PackLocationAssembly, PackSettlementAssembly
from app.dataModel.worldPack.meta.metadataAttribution import PackStoredAssemblyProvenance
from app.dataModel.worldPack.wire.territoryVolume import TerritoryVolume


class PreparationDeleteTests(unittest.TestCase):
    def setUp(self):
        provenance = PackStoredProvenance(
            source_proof=SourceDurableProof(schema_version=1, world_uid="world", uses=()), planning=())
        ref = ArtifactRef(kind=ArtifactKind.BLOB, format_key="test.payload", format_version=1,
                          content_hash="a" * 64, nbytes=1)
        self.first = PackStoredPart(address=PackMapTileAddress(kind="map_tile", gx=0, gy=0),
                                    artifact=ref, provenance=provenance)
        self.second = self.first.model_copy(update={"address": PackMapTileAddress(kind="map_tile", gx=1, gy=0)})
        self.state = PackPreparationState(
            base_publication=WorldPublicationRef(world_uid="world", publication_id="base", pack_hash=None,
                snapshot_head=None, active_timeline_id=None, gameplay_started=False),
            parts=(self.first, self.second), assembly=PackAssemblyInput(
                last_l0_mode="light", fine_cells_per_map_cell=1000, world_map_cells_per_tile=32,
                fine_cell_size=FINE_CELL_SIZE, map_subsurface_depth=0, terrain_chunk_columns=32,
                tiles=(PackTileAssembly(gx=0, gy=0, climate_status="coarse", wilderness_refine_status="absent", chunks=()),),
                locations=(), settlements=(), wilderness_regions=()),
            assembly_provenance=(), metadata_dependencies=())
        self.service = PackPreparationService()

    def test_deletes_by_address_preserving_shared_artifact_and_metadata(self):
        result = self.service.delete_part(PackDeletePartInput(state=self.state, address=self.first.address))
        self.assertEqual(result.parts, (self.second,))
        self.assertEqual(result.parts[0].artifact, self.first.artifact)
        self.assertEqual(result.parts[0].provenance, self.second.provenance)
        for field in ("base_publication", "assembly", "assembly_provenance", "metadata_dependencies"):
            self.assertEqual(getattr(result, field), getattr(self.state, field))
        self.assertEqual(self.state.parts, (self.first, self.second))
        repeated = self.service.delete_part(PackDeletePartInput(state=result, address=self.first.address))
        self.assertEqual(repeated, result)

    def test_duplicate_state_is_rejected_instead_of_repaired(self):
        invalid = self.state.model_copy(update={"parts": (self.first, self.first)})
        with self.assertRaises(PackPreparationFailure) as caught:
            self.service.delete_part(PackDeletePartInput(state=invalid, address=self.first.address))
        issue, = caught.exception.error.issues
        self.assertIs(issue.code, PackPreparationIssueCode.DUPLICATE_ADDRESS)
        self.assertEqual(issue.path.projection(), ("state", "parts", 1, "address"))
        self.assertEqual(invalid.parts, (self.first, self.first))

    def test_absent_address_still_requires_valid_state(self):
        foreign_proof = self.first.provenance.source_proof.model_copy(update={"world_uid": "foreign"})
        foreign_part = self.first.model_copy(update={"provenance": self.first.provenance.model_copy(
            update={"source_proof": foreign_proof})})
        invalid = self.state.model_copy(update={"parts": (foreign_part,)})
        with self.assertRaises(PackPreparationFailure) as caught:
            self.service.delete_part(PackDeletePartInput(state=invalid, address=self.second.address))
        self.assertIs(caught.exception.error.issues[0].code, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH)

    def test_forged_request_collects_independent_schema_errors(self):
        request = PackDeletePartInput(state=self.state, address=self.first.address).model_copy(update={
            "state": self.state.model_copy(update={"parts": []}),
            "address": self.first.address.model_copy(update={"gx": True}),
        })
        with self.assertRaises(PackPreparationFailure) as caught:
            self.service.delete_part(request)
        self.assertIs(caught.exception.error.reason, PackPreparationFailureReason.INVALID_INPUT)
        self.assertEqual(len(caught.exception.error.issues), 2)

    def test_each_representation_removes_its_own_rows_and_keeps_sidecar(self):
        volume = TerritoryVolume(x0=0, y0=0, z0=0, x1=1, y1=1, z1=1)
        location = PackLocationAssembly(location_uid="place", territory_volume=volume, climate_status="coarse")
        settlement = PackSettlementAssembly(location_uid="place", territory_volume=volume,
                                            structure_status="partial", packed_district_uids=("district",))
        terrain_address = PackLocationTerrainAddress(kind="location_terrain", location_uid="place")
        settlement_address = PackSettlementAddress(kind="settlement", location_uid="place")
        sidecar_address = PackLocationGradeSlotsAddress(kind="location_grade_slots", location_uid="place")
        terrain = self.first.model_copy(update={"address": terrain_address})
        structure = self.first.model_copy(update={"address": settlement_address})
        sidecar = self.first.model_copy(update={"address": sidecar_address})
        location_proof = PackStoredAssemblyProvenance(
            address=PackLocationMetadataAddress(kind="location", location_uid="place"),
            provenance=self.first.provenance, attribution=None)
        settlement_proof = PackStoredAssemblyProvenance(
            address=PackSettlementMetadataAddress(kind="settlement", location_uid="place"),
            provenance=self.first.provenance, attribution=None)
        state = self.state.model_copy(update={
            "parts": (terrain, structure, sidecar, self.first),
            "assembly": self.state.assembly.model_copy(update={"locations": (location,), "settlements": (settlement,)}),
            "assembly_provenance": (location_proof, settlement_proof),
        })
        for method, request, remaining, proofs, locations, settlements in (
            (self.service.delete_location_terrain, PackDeleteLocationTerrainInput(state=state, address=terrain_address),
             (structure, sidecar, self.first), (settlement_proof,), (), (settlement,)),
            (self.service.delete_settlement_structure, PackDeleteSettlementStructureInput(state=state, address=settlement_address),
             (terrain, sidecar, self.first), (location_proof,), (location,), ()),
        ):
            with self.subTest(method=method.__name__):
                result = method(request)
                self.assertEqual(result.parts, remaining)
                self.assertEqual(result.assembly_provenance, proofs)
                self.assertEqual(result.assembly.locations, locations)
                self.assertEqual(result.assembly.settlements, settlements)
                self.assertEqual(result.assembly.tiles, state.assembly.tiles)
                self.assertEqual(result.base_publication, state.base_publication)
                self.assertEqual(method(request.model_copy(update={"state": result})), result)
        self.assertEqual(state.parts, (terrain, structure, sidecar, self.first))
        self.assertEqual(state.assembly.locations, (location,))
        with self.assertRaises(ValidationError):
            PackDeleteLocationTerrainInput(state=state, address=settlement_address)
        with self.assertRaises(ValidationError):
            PackDeleteSettlementStructureInput(state=state, address=terrain_address)

    def test_deleting_partial_representation_without_payload(self):
        volume = TerritoryVolume(x0=0, y0=0, z0=0, x1=1, y1=1, z1=1)
        location = PackLocationAssembly(location_uid="place", territory_volume=volume, climate_status="coarse")
        state = self.state.model_copy(update={"assembly": self.state.assembly.model_copy(update={"locations": (location,)})})
        result = self.service.delete_location_terrain(PackDeleteLocationTerrainInput(
            state=state, address=PackLocationTerrainAddress(kind="location_terrain", location_uid="place")))
        self.assertEqual(result.parts, state.parts)
        self.assertEqual(result.assembly.locations, ())
