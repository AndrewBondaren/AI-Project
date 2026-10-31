from copy import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.encoding.canonicalCodec import encode
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
from app.application.worldData.generators.hydrology.shore.fineRiverSampling import FineRiverSampling
from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.terrain.reliefObjects.riverBed.riverBedZ import river_bed_spec, apply_river_bed_z
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.placement.result import UnresolvedPlacementV2, PlacementDiagnostic, PlacementIssueCode
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.validation.immutableValue import validate_immutable
from tests.geo1.coating.fixtures import envelope
from tests.geo1.fine_water.fixtures import physical_inputs, decisions, placement
from tests.geo1.fine_water.test_fill import source, fill, basin
from tests.geo1.terrain_base.fixtures import Control


class FineReviewTests(TestCase):
    def test_operation_identity_covers_specs_policy_change_and_accepted_ref(self):
        window, _, topology = source()
        spec = basin("body", {(2, 2), (3, 2)})
        physical = physical_inputs(topology)
        original = fill(window, topology, (spec,), physical=physical)
        different_spec = replace(spec, bands=replace(spec.bands, max=spec.bands.max + 1))
        variants = (fill(window, topology, (different_spec,), physical=physical),
            fill(window, topology, (spec,), physical=replace(physical, change_uid="other-operation")),
            fill(window, topology, (spec,), physical=replace(physical,
                lakes=replace(physical.lakes, min_water_cells=1))))
        for result in variants:
            self.assertNotEqual(result.ref.key.input_fingerprint, original.ref.key.input_fingerprint)
        self.assertEqual(len(original.dependencies), 2)
        self.assertEqual(original.dependencies[0].ref, window.ref)
        validate_immutable(original)
        with self.assertRaises(TypeError):
            original.payload[1].materialized.cells[0] = original.payload[1].materialized.cells[0]
        accepted = placement(window, (spec,))
        changed = envelope("accepted_native", replace(accepted.payload, snapshot_uid="new-placement"), accepted.dependencies)
        result = fill(window, topology, (spec,), accepted=changed)
        self.assertNotEqual(result.ref.key, original.ref.key)

    def test_wrong_accepted_source_or_snapshot_cannot_be_published(self):
        window, _, topology = source()
        spec = basin("body", {(2, 2), (3, 2)})
        with self.assertRaisesRegex(ValueError, "accepted source"):
            fill(window, topology, (spec,), accepted=placement(window, ()))
        accepted = placement(window, (spec,))
        wrong = envelope("accepted_native", replace(accepted.payload, snapshot_revision=b"x" * 32), accepted.dependencies)
        with self.assertRaisesRegex(ValueError, "snapshot"):
            fill(window, topology, (spec,), accepted=wrong)
        changed_window, _, _ = source(hills=False)
        # Coarse terrain still matches, but accepted geometry belongs to another fine recipe.
        with self.assertRaisesRegex(ValueError, "snapshot"):
            fill(changed_window, topology, (spec,), accepted=accepted)
        physical = physical_inputs(topology)
        with self.assertRaisesRegex(ValueError, "expected"):
            WaterBodyPlanner().fill_fine(window, expected_surface=window.ref, placement=accepted,
                expected_placement=window.ref, inputs=physical, specs=(spec,),
                classification_decisions=decisions(physical), control=Control())

    def test_error_does_not_publish_empty_success_or_mutate_source(self):
        window, _, topology = source()
        before = encode(window, SURFACE_MANIFEST)
        with patch("app.application.worldData.generators.hydrology.waterBodyAssembler.depression_tree",
                   side_effect=ValueError("terrain resolution failed")):
            with self.assertRaises(PlanBuildFailure):
                fill(window, topology)
        spec = basin("puddle", {(2, 2), (3, 2)})
        physical = physical_inputs(topology)
        with self.assertRaises(PlanBuildFailure):
            fill(window, topology, (spec,), physical=replace(physical,
                lakes=replace(physical.lakes, min_water_cells=100)))
        error = PlanDiagnostic(issue=FieldPathError(("terrain",), "upstream failed"),
                               disposition=PlanDiagnosticDisposition.ERROR)
        failed = replace(window, diagnostics=(error,), ref=replace(window.ref,
            output_fingerprint=output_fingerprint(window.payload, window.dependencies, (error,), SURFACE_MANIFEST)))
        with self.assertRaises(PlanBuildFailure):
            fill(failed, topology)
        accepted = placement(window, (spec,))
        identity = accepted.payload.results[0].identity
        unresolved = UnresolvedPlacementV2(identity=identity, prepared=None, diagnostics=(PlacementDiagnostic(
            code=PlacementIssueCode.NO_CANDIDATES, region_uid=identity.region_uid, detail="no accepted geometry"),))
        failed_placement = envelope("accepted_native", replace(accepted.payload, results=(unresolved,)), accepted.dependencies)
        with self.assertRaises(PlanBuildFailure):
            fill(window, topology, (spec,), accepted=failed_placement)
        self.assertEqual(encode(window, SURFACE_MANIFEST), before)

    def test_auto_lakes_and_allowed_kinds_apply_to_fine_resolution(self):
        window, _, topology = source(hills=False)
        rows = tuple((cell, 0 if cell in {(8, 8), (9, 8), (8, 9), (9, 9)} else 10)
                     for cell, _ in window.payload.surface_z)
        window = envelope("pre_water", FineSurfaceWindow(coverage=window.payload.coverage, topology=topology,
            protected_cells=frozenset(), surface_z=rows), window.dependencies)
        physical = physical_inputs(topology)
        off = fill(window, topology, physical=physical)
        auto = decisions(physical, auto=True)
        on = fill(window, topology, physical=physical, category_decisions=auto)
        self.assertEqual(off.payload[1].materialized.bodies, ())
        self.assertTrue(on.payload[1].materialized.bodies)
        self.assertTrue(all(body.kind is BasinKind.LAKE for body in on.payload[1].materialized.bodies))
        restricted = fill(window, topology, physical=replace(physical, allowed_body_kinds=frozenset({BasinKind.OCEAN})),
                          category_decisions=auto)
        self.assertEqual(restricted.payload[1].materialized.bodies, ())
        self.assertNotEqual(off.ref.key, on.ref.key)
        # Keep AUTORESOLVE enabled while physical classification produces another kind.
        small_sea = replace(physical, seas=replace(physical.seas, inland_sea_min_area_fraction=0.0001))
        unfiltered = fill(window, topology, physical=small_sea, category_decisions=auto)
        self.assertTrue(any(body.kind is BasinKind.INLAND_SEA for body in unfiltered.payload[1].materialized.bodies))
        filtered = fill(window, topology, physical=replace(small_sea, allowed_body_kinds=frozenset({BasinKind.LAKE})),
                        category_decisions=auto)
        self.assertEqual(filtered.payload[1].materialized.bodies, ())

    def test_retained_output_depends_on_route_cells_not_world_size(self):
        route = ((1, 1), (2, 1), (3, 1))
        snapshots = []
        for side in (8, 64):
            surface = {(x, y): 10 for y in range(side) for x in range(side)}
            sampling = FineRiverSampling(SurfaceHeightmap("world", GridBBox(0, side - 1, 0, side - 1), surface),
                {}, surface, {}, set(), CoordinateSpace.WORLD_FINE_GRID, 1)
            retained = sampling.output_heightmap(iter(route))
            self.assertEqual(set(retained.surface_z), set(route))
            self.assertEqual(len(sampling.heightmap.surface_z), side * side)
            segment = RiverSegment(list(route), HydrologyConnectionType.RIVER.value)
            spec = river_bed_spec(retained, segment, depth_step=1, z_min=-10, occupied={}, receiver_cell=route[-1])
            apply_river_bed_z(retained, (spec,))
            self.assertEqual(retained.surface_z[route[-1]], 10)
            self.assertTrue(all(cell != route[-1] for cell, _ in spec.bed_z))
            snapshots.append(retained.surface_z)
        self.assertEqual(*snapshots)
