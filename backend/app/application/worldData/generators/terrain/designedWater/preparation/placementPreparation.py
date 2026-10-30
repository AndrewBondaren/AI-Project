"""One signed-field quantization/prefix boundary (GEO-1 G4-C)."""

from decimal import Decimal

from pydantic import TypeAdapter

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure
from app.dataModel.placement.prepared import PlacementCandidate, PlacementFootprint
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterDesignDecision
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.terrain.designedWater.draft import AuthoredWaterDesignDraft, ProceduralWaterDesignDraft, WaterDesignDraft
from app.dataModel.terrain.designedWater.fields.field import ContinentalFieldValue
from app.dataModel.terrain.designedWater.input import (
    AuthoredWaterDesignInput, NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput, WaterStrategyInput,
)
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError

_INPUT = TypeAdapter(WaterStrategyInput)
_ADMISSION = TypeAdapter(WaterDesignDecision)


def _wet_score(value: ContinentalFieldValue, bits: int) -> int:
    numerator, denominator = Decimal(str(value)).as_integer_ratio()
    return ((denominator - numerator) * ((1 << bits) - 1) + denominator) // (2 * denominator)


class DesignedWaterPlacementPreparer:
    def bind_admission(self, input: WaterStrategyInput, preparation: WaterDesignPreparation, *,
                       intent: PlacementIntent, admission: PlacementAdmissionInput) -> PreparedPlacementV2:
        """Bind computed geometry to its original intent and ready common decision."""
        try:
            input = _INPUT.validate_python(input, strict=True)
            preparation = WaterDesignPreparation.model_validate(preparation, strict=True)
            intent = PlacementIntent.model_validate(intent, strict=True)
            admission = PlacementAdmissionInput.model_validate(admission, strict=True)
            decision = _ADMISSION.validate_python(admission.decision, strict=True)
            if decision.state is not PolicyState.READY or decision.require_behavior() is not input.strategy:
                raise ValueError("water geometry binding requires the same ready strategy admission")
            if PlacementHeader.from_intent(intent) != admission.header:
                raise ValueError("water geometry must retain its exact admission header")
            if (intent.identity.source_uid != input.metadata.source_uid
                    or intent.identity.world_uid != input.pre_hydrology.ref.key.world_uid
                    or preparation.metadata != input.metadata or preparation.pre_hydrology_ref != input.pre_hydrology_ref
                    or preparation.grid != input.grid):
                raise ValueError("water geometry requires exact source/world/metadata/terrain/grid binding")
            if preparation.coordinate_space is not CoordinateSpace.WORLD_SURFACE_GRID:
                raise ValueError("water P2 requires coarse world surface geometry without implicit scaling")
            cells = frozenset(cell for candidate in preparation.candidates for cell in candidate.footprint.cells)
            if any(input.topology.canonicalize(*cell) != cell for cell in cells):
                raise ValueError("water P2 requires canonical coarse geometry")
            if isinstance(input, AuthoredWaterDesignInput):
                authored = frozenset(cell for footprint in input.geometry.footprints for cell in footprint)
                if input.geometry.coordinate_space != preparation.coordinate_space or cells != authored:
                    raise ValueError("authored P2 must retain its supplied geometry result")
            else:
                profile = preparation.floor_profile
                if (not isinstance(profile, FieldFloorProfile) or profile.recipe != input.field_policy
                        or profile.depth != input.metadata.default_depth or profile.z_min != input.z_min):
                    raise ValueError("procedural P2 must retain its captured floor recipe")
            return PreparedPlacementV2(intent=intent, original_area=preparation.original_area,
                candidates=preparation.candidates, decision=admission.decision)
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("water_design", "binding"), str(error),
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),)) from error

    def prepare(self, input: WaterStrategyInput, draft: WaterDesignDraft, *,
                selection_policy: WaterFieldSelectionPolicy) -> WaterDesignPreparation:
        """Return geometry for G8; never bind admission or invoke spatial competition."""
        if not isinstance(input, (AuthoredWaterDesignInput, NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput)):
            raise TypeError("preparation requires typed water design input")
        if not isinstance(draft, (AuthoredWaterDesignDraft, ProceduralWaterDesignDraft)):
            raise TypeError("preparation requires typed water draft")
        if not isinstance(selection_policy, WaterFieldSelectionPolicy):
            raise TypeError("preparation requires typed field selection policy")
        try:
            input = _INPUT.validate_python(input, strict=True)
            draft = input.validate_draft(draft)
            policy = WaterFieldSelectionPolicy.model_validate(selection_policy, strict=True)
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("water_design", "preparation"), str(error),
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),)) from error

        notices: tuple[FieldPathError, ...] = ()
        if isinstance(draft, AuthoredWaterDesignDraft):
            cells = frozenset(c for footprint in draft.footprints for c in footprint)
            space = draft.coordinate_space
            if isinstance(input, AuthoredWaterDesignInput):
                notices = input.geometry.notices
        else:
            notices = draft.field.notices
            coordinates = tuple(c for c, _ in draft.field.samples)
            areas = RegionCoverageMeasure.coarse_cell_areas(input.region_coverage, coordinates, input.grid)
            full_area = input.grid.fine_span ** 2
            constraints = input.constraints
            allowed = constraints.allowed_cells if constraints is not None else None
            required = constraints.required_cells if constraints is not None else frozenset()
            full_cells = frozenset((coord.gx, coord.gy) for coord, area in zip(coordinates, areas) if area == full_area)
            allocated = input.budget.allocated_fine2
            required_area = len(required) * full_area
            if not required <= full_cells or required_area > allocated:
                raise PlanBuildFailure((FieldPathError(input.metadata.source_path,
                    f"required coastline strip cannot fit region/budget; required_fine2={required_area}, allocated_fine2={allocated}",
                    code=WaterDesignIssueCode.CONSTRAINT_CONFLICT.value),))
            # One prefix selection: captured hard constraints fix the required
            # strip; the same quantized ordering chooses all remaining cells.
            ranked = sorted(((coord, _wet_score(value, policy.score_bits), area)
                for (coord, value), area in zip(draft.field.samples, areas)
                if area == full_area and (coord.gx, coord.gy) not in required
                and (allowed is None or (coord.gx, coord.gy) in allowed)),
                key=lambda item: (-item[1], item[0].gy, item[0].gx))
            best, selected_area, cumulative, error = 0, required_area, required_area, abs(required_area - allocated)
            for count, (_, _, weight) in enumerate(ranked, 1):
                cumulative += weight
                difference = abs(cumulative - allocated)
                if difference < error:
                    best, selected_area, error = count, cumulative, difference
            cells: frozenset[Coord] = required | frozenset((coord.gx, coord.gy) for coord, _, _ in ranked[:best])
            if constraints is not None:
                notices += constraints.notices
            capacity = (len(ranked) + len(required)) * full_area
            space = CoordinateSpace.WORLD_SURFACE_GRID
            if not cells:
                raise PlanBuildFailure((FieldPathError(input.metadata.source_path,
                    f"empty water prefix; allocated_fine2={allocated}, capacity_fine2={capacity}",
                    code=WaterDesignIssueCode.EMPTY_GENERATION_TARGET.value),))
            if selected_area < allocated:
                notices += (FieldPathError(input.metadata.source_path,
                    f"water coverage shortfall; allocated_fine2={allocated}, selected_fine2={selected_area}, capacity_fine2={capacity}",
                    code=WaterDesignIssueCode.COVERAGE_SHORTFALL.value),)

        candidate = PlacementCandidate(candidate_uid=input.metadata.source_uid, preference=0,
            footprint=PlacementFootprint(cells=cells, z_min=None, z_max=None))
        return WaterDesignPreparation(metadata=draft.metadata, pre_hydrology_ref=input.pre_hydrology_ref,
            coordinate_space=space, grid=input.grid, candidates=(candidate,), original_area=float(len(cells)),
            floor_z=draft.floor_z, floor_profile=draft.floor_profile, notices=notices)
