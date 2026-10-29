"""Fine wet/dry stencils and topology-aware association without path snapping."""
from unittest import TestCase
from dataclasses import replace

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.boundaries.boundaryGeometry import BoundaryGeometry
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.dataModel.hydrology.boundaries.attachedCoastline import BoundaryIssueCode
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.enums.waterSide import WaterSide
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from tests.geo1.boundaries.fixtures import make


def geometry(case):
    return BoundaryGeometry().prepare(case.source,case.snapshot)


def raster(part):
    points=[(p.x,p.y) for p in part.path]
    if len(points)==1:return {points[0]}
    pairs=list(zip(points,points[1:]))
    if part.closed and points[-1]!=points[0]:pairs.append((points[-1],points[0]))
    return rasterize_segments(pairs)


class BoundaryGeometryTests(TestCase):
    def test_exact_single_body_path_and_metadata_preserved(self):
        case = make()
        before = case.snapshot.model_dump_json()
        result = geometry(case)
        self.assertEqual(result.boundary.parts[0].path,case.source.path)
        self.assertEqual(result.boundary.parts[0].body_uid,"body-a")
        self.assertEqual(result.boundary.target_source_uid,"water-source")
        self.assertEqual(result.boundary.coordinate_space,CoordinateSpace.WORLD_FINE_GRID)
        self.assertEqual(result.cells,frozenset({(2,y) for y in range(1,5)}))
        self.assertEqual(case.snapshot.model_dump_json(),before)

    def test_missing_sample_is_unknown_not_dry(self):
        case = make(missing_samples=((1,2),))
        with self.assertRaises(PlanBuildFailure) as caught:geometry(case)
        self.assertEqual(caught.exception.issues[0].code,BoundaryIssueCode.UNKNOWN_FINE_WATER.value)

    def test_land_and_interior_water_paths_are_off_target(self):
        for x in (0,4,6):
            case = make()
            source = case.source.model_copy(update={"path":tuple(p.model_copy(update={"x":x}) for p in case.source.path)})
            with self.assertRaises(PlanBuildFailure) as caught:geometry(replace(case,source=source))
            self.assertEqual(caught.exception.issues[0].code,BoundaryIssueCode.BOUNDARY_OFF_TARGET.value)

    def test_other_water_does_not_count_as_dry(self):
        wet={(x,y):("body-a" if x>=3 else "body-b") for y in range(6) for x in range(6)}
        case=make(wet=wet)
        with self.assertRaises(PlanBuildFailure) as caught:geometry(case)
        self.assertEqual(caught.exception.issues[0].code,BoundaryIssueCode.BOUNDARY_OFF_TARGET.value)

    def test_split_parts_preserve_original_raster_without_choosing_a_level(self):
        case=make(split=True)
        result=geometry(case)
        self.assertEqual({part.body_uid for part in result.boundary.parts},{"body-a","body-b"})
        self.assertEqual(set().union(*(raster(part) for part in result.boundary.parts)),set(result.cells))
        for part in result.boundary.parts:self.assertFalse(part.closed)
        self.assertNotIn("z_water_level",type(result.boundary).model_fields)

    def test_closed_partial_body_runs_stitch_without_phantom_segments(self):
        base=make()
        source=base.source.model_copy(update={"closed":True,"water_side":WaterSide.INTERIOR,
            "path":tuple(HydrologyWaypoint(x=x,y=y) for x,y in ((1,1),(3,1),(3,3),(1,3)))})
        wet={(x,y):("body-b" if x==3 and y>=2 else "body-a") for y in range(1,4) for x in range(1,4)}
        case=make(source=source,wet=wet)
        result=geometry(case)
        from app.dataModel.hydrology.boundaries.attachedCoastline import CoastlinePart
        expected=raster(CoastlinePart(body_uid="body-a",closed=True,path=source.path))
        self.assertEqual(set().union(*(raster(part) for part in result.boundary.parts)),expected)
        for part in result.boundary.parts:
            if not part.closed:
                self.assertTrue(all(max(abs(a.x-b.x),abs(a.y-b.y))<=1 for a,b in zip(part.path,part.path[1:])))

    def test_whole_closed_line_keeps_authored_vertices(self):
        base=make()
        source=base.source.model_copy(update={"closed":True,"water_side":WaterSide.INTERIOR,
            "path":tuple(HydrologyWaypoint(x=x,y=y) for x,y in ((2,2),(3,2),(3,3),(2,3)))})
        result=geometry(make(source=source,wet={(x,y):"body-a" for y in (2,3) for x in (2,3)}))
        self.assertTrue(result.boundary.parts[0].closed)
        self.assertEqual(result.boundary.parts[0].path,source.path)

    def test_wrapped_seam_keeps_unrolled_path(self):
        base=make()
        source=base.source.model_copy(update={"path":tuple(p.model_copy(update={"x":-1}) for p in base.source.path)})
        result=geometry(make(source=source,mode=Mode.WRAPPED))
        self.assertEqual(result.cells,frozenset((5,y) for y in range(1,5)))
        self.assertEqual(result.boundary.parts[0].path,source.path)

    def test_sphere_pole_uses_actual_neighbor_map(self):
        source=make().source.model_copy(update={"path":(HydrologyWaypoint(x=0,y=-1),HydrologyWaypoint(x=2,y=-1))})
        result=geometry(make(source=source,mode=Mode.SPHERE))
        self.assertEqual(result.cells,frozenset({(4,0),(5,0),(6,0)}))
        self.assertEqual(result.boundary.parts[0].path,source.path)

    def test_snapshot_refs_scale_and_physical_uid_contracts(self):
        snapshot=make().snapshot
        for update in ({"mapping_hydrology_ref":snapshot.placement_ref},
                       {"placement_ref":snapshot.placement_ref.model_copy(update={"output_fingerprint":b"x"*32})},
                       {"coordinate_space":CoordinateSpace.WORLD_SURFACE_GRID},
                       {"fine_cells":tuple(reversed(snapshot.fine_cells))},
                       {"water_outcomes":snapshot.water_outcomes*2},
                       {"fine_cells":(snapshot.fine_cells[0].model_copy(update={"body_uid":"system-not-a-body"}),)}):
            with self.assertRaises(ValidationError):BoundaryWaterSnapshot.model_validate(snapshot.model_copy(update=update))
        self.assertEqual(BoundaryWaterSnapshot.model_validate(snapshot),snapshot)

    def test_missing_mapping_is_not_inferred_from_equal_source_body_uid(self):
        wet={(x,y):"water-source" for y in range(6) for x in range(3,6)}
        with self.assertRaises(PlanBuildFailure):geometry(make(wet=wet,mapping=False))

    def test_input_round_trip_and_tampered_legacy_points_are_validated(self):
        from app.dataModel.hydrology.boundaries.attachedCoastline import CoastlineBoundaryInput
        case=make()
        self.assertEqual(CoastlineBoundaryInput.model_validate_json(case.input.model_dump_json()),case.input)
        points=case.source.path
        bad=case.source.model_copy(update={"path":(points[0].model_copy(update={"x":True}),points[1])})
        with self.assertRaises(ValidationError):
            CoastlineBoundaryInput.model_validate(case.input.model_copy(update={"sources":(bad,)}))
