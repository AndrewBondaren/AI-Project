"""Structural dependent binding delegates fine geometry and preserves source admission."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.boundaries.boundaryGeometry import BoundaryGeometry
from app.application.worldData.placement.adapters.coastline.attachedCoastline import AttachedCoastlinePreparer
from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose
from app.dataModel.placement.common import PlacementMode
from app.dataModel.policy.policyEnums import PolicySupportState
from tests.geo1.boundaries.fixtures import make


def prepare(case):
    return AttachedCoastlinePreparer().prepare_boundary(case.source,case.snapshot,case.admission)


class AttachedBoundaryAdapterTests(TestCase):
    def test_ready_boundary_uses_common_prepared_placement_and_exact_decision(self):
        case=make()
        result=prepare(case)
        self.assertEqual(result.prepared.decision,case.admission.decision)
        self.assertEqual(result.prepared.intent.dependencies,case.admission.header.dependencies)
        self.assertEqual(result.boundary.parts[0].path,case.source.path)
        self.assertEqual(result.prepared.original_area,4.0)
        self.assertIsNone(result.prepared.candidates[0].footprint.z_min)
        self.assertEqual(set(result.__dataclass_fields__),{"prepared","boundary"})

    def test_not_ready_admission_never_calls_geometry(self):
        for case in (make(priority=0),make(dry=True),make(support=PolicySupportState.MISSING),
                     make(support=PolicySupportState.DISABLED),make(support=PolicySupportState.FAILED)):
            with patch.object(BoundaryGeometry,"prepare",side_effect=AssertionError("geometry")),self.assertRaises(PlanBuildFailure):
                prepare(case)

    def test_header_dependency_overlap_world_and_mode_must_match(self):
        case=make()
        header=case.admission.header
        for update in ({"dependencies":()},{"permitted_overlaps":()},{"mode":PlacementMode.SEMANTIC},
                       {"identity":header.identity.model_copy(update={"world_uid":"other"})},
                       {"identity":header.identity.model_copy(update={"source_uid":"other"})}):
            admission=case.admission.model_copy(update={"header":header.model_copy(update=update)})
            with patch.object(BoundaryGeometry,"prepare",side_effect=AssertionError("geometry")),self.assertRaises(PlanBuildFailure):
                prepare(replace(case,admission=admission))

    def test_source_and_physical_body_identity_are_distinct(self):
        case=make()
        self.assertNotEqual(case.source.target_source_uid,case.snapshot.source_mapping.entries[0].body_uids[0])
        result=prepare(case)
        self.assertEqual(result.prepared.intent.dependencies[0].target_uid,"water-region")
        self.assertEqual(result.boundary.parts[0].body_uid,"body-a")

    def test_water_source_and_missing_target_do_not_use_boundary_geometry(self):
        case=make()
        water_source=case.source.model_copy(update={"purpose":CoastlinePurpose.WATER_SOURCE,"target_source_uid":None})
        for source in (water_source,case.source.model_copy(update={"target_source_uid":"absent"})):
            with patch.object(BoundaryGeometry,"prepare",side_effect=AssertionError("geometry")),self.assertRaises(PlanBuildFailure):
                prepare(replace(case,source=source))

    def test_no_fake_water_or_basin_writes(self):
        case=make()
        before=case.snapshot.model_dump_json()
        result=prepare(case)
        self.assertNotIn("coastline",type(result.prepared).model_fields)
        self.assertNotIn("floor_z",type(result.boundary).model_fields)
        self.assertNotIn("basin_specs",type(result.boundary).model_fields)
        self.assertEqual(case.snapshot.model_dump_json(),before)

    def test_raw_inputs_rejected(self):
        case=make()
        for values in (({},case.snapshot,case.admission),(case.source,{},case.admission),(case.source,case.snapshot,{})):
            with self.assertRaises(TypeError):AttachedCoastlinePreparer().prepare_boundary(*values)
