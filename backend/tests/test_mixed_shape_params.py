"""Chosen L/T parameters, preserved RNG order and defensive degradation."""
import unittest
from copy import deepcopy
from random import Random
from unittest.mock import patch

from app.application.worldData.generators.structure.room.roomFactory import (
    _resolve_shape_params, instantiate_level_rooms,
)
from app.application.worldData.generators.structure.shapes import (
    footprint_l_shape, footprint_t_shape, room_footprint,
)
from app.application.worldData.generators.structure.shapeType import ShapeType
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.dataModel.locations.structure.room.roomDef import RoomDef
from app.dataModel.locations.structure.building.levelDef import LevelDef
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing
from tests.structureWire import room_wire
from tests.test_structure_orientation import simple_structure, test_world_building

FACTORY = "app.application.worldData.generators.structure.room.roomFactory"


class MixedShapeParamsTests(unittest.TestCase):
    def definition(self, shapes, **params):
        return RoomDef.model_validate(room_wire(shape_type=shapes,
            size={"width_range": [6, 6], "depth_range": [4, 4]}, shape_params=params))

    def instantiate(self, definition, rng=None):
        world, _ = test_world_building()
        level = LevelDef.model_construct(z_offset=0, display_name="Ground", rooms=[definition])
        with patch(FACTORY + ".resolve_room_materials", return_value=("stone", "wood")):
            instance = instantiate_level_rooms(level, simple_structure(), 5, 0, world, rng or Random(1))[0]
        instance.origin_x = instance.origin_y = 0
        return instance

    def test_mixed_l_uses_authored_params_and_footprint(self):
        definition = self.definition(["l_shape", "rectangle"], arm_width_range=[8, 8],
                                     arm_depth_range=[6, 6], arm_corner="southwest")
        instance = self.instantiate(definition)
        self.assertEqual(instance.shape_type, "l_shape")
        self.assertEqual(instance.shape_params, dict(arm_width=8, arm_depth=6, arm_corner="southwest"))
        self.assertEqual(instance.get_footprint(), footprint_l_shape(0, 0, 6, 4, 8, 6, "southwest"))
        self.assertNotEqual(instance.get_footprint(), room_footprint("l_shape", 0, 0, 6, 4))

    def test_mixed_t_uses_authored_stem_and_normalizes_once(self):
        definition = self.definition(["t_shape", "rectangle"], stem_width_range=[4, 4], stem_wall="east")
        instance = self.instantiate(definition)
        self.assertEqual(instance.shape_type, "t_shape")
        self.assertEqual(instance.shape_params, dict(stem_width=4, stem_wall=Facing.EAST))
        self.assertEqual(instance.get_footprint(), footprint_t_shape(0, 0, 6, 4, 4, Facing.EAST))
        self.assertNotEqual(instance.get_footprint(), footprint_t_shape(0, 0, 6, 4, 2, Facing.EAST))

    def test_rectangle_has_no_params_or_extra_rng_draws(self):
        definition = self.definition(["rectangle", "l_shape"], arm_width_range=[2, 3], arm_depth_range=[2, 3])
        rng = Random(1)
        state = rng.getstate()
        self.assertEqual(_resolve_shape_params(definition, ShapeType.RECTANGLE, rng), {})
        self.assertEqual(rng.getstate(), state)
        instance = self.instantiate(definition, rng)
        self.assertEqual(instance.shape_type, "rectangle")
        self.assertEqual(instance.shape_params, {})

    def test_scalar_and_singleton_keep_exact_draw_order_and_rng_state(self):
        for shape in (ShapeType.L_SHAPE, ShapeType.T_SHAPE):
            for singleton in (False, True):
                with self.subTest(shape=shape, singleton=singleton):
                    params = dict(arm_width_range=[2, 3], arm_depth_range=[3, 4]) if shape is ShapeType.L_SHAPE else dict(stem_width_range=[2, 3])
                    declared = [shape.value] if singleton else shape.value
                    definition = self.definition(declared, **params)
                    rng, reference = Random(42), Random(42)
                    if singleton:
                        reference.choice(declared)
                    # Existing factory order: shape, params, size. Any choice precedes ranges.
                    if shape is ShapeType.L_SHAPE:
                        corner = reference.choice(["northeast", "northwest", "southeast", "southwest"])
                        expected = dict(arm_width=reference.randint(2, 3), arm_depth=reference.randint(3, 4), arm_corner=corner)
                    else:
                        wall = reference.choice(list(CARDINAL_FACINGS))
                        expected = dict(stem_width=reference.randint(2, 3), stem_wall=wall)
                    reference.randint(6, 6)
                    reference.randint(4, 4)
                    reference.randint(3, 3)
                    instance = self.instantiate(definition, rng)
                    self.assertEqual(instance.shape_params, expected)
                    self.assertEqual(rng.getstate(), reference.getstate())

    def test_incomplete_specs_after_validation_bypass_log_and_use_footprint_defaults(self):
        for shape, params in ((ShapeType.L_SHAPE, dict(arm_width_range=[2, 3], arm_depth_range=[2, 3])),
                              (ShapeType.T_SHAPE, dict(stem_width_range=[2, 3]))):
            complete = self.definition(shape.value, **params)
            partial = complete.shape_params.model_copy(update={
                "arm_depth_range" if shape is ShapeType.L_SHAPE else "stem_width_range": None})
            for broken in (None, partial):
                with self.subTest(shape=shape, broken=broken):
                    definition = complete.model_copy(update={"shape_params": broken})
                    with self.assertLogs(FACTORY, "ERROR") as captured:
                        instance = self.instantiate(definition)
                    self.assertEqual(len(captured.records), 1)
                    self.assertIn("footprint defaults", captured.output[0])
                    self.assertEqual(instance.shape_params, {})
                    if shape is ShapeType.T_SHAPE:
                        with self.assertLogs("app.application.worldData.generators.structure.shapes", "ERROR"):
                            footprint = instance.get_footprint()
                        self.assertEqual(footprint, footprint_t_shape(0, 0, 6, 4, 2, Facing.SOUTH))
                    else:
                        self.assertEqual(instance.get_footprint(), room_footprint(shape.value, 0, 0, 6, 4))

    def test_mixed_generation_is_deterministic_and_template_immutable(self):
        world, building = test_world_building()
        for shape in ("l_shape", "t_shape"):
            template = simple_structure()
            definition = template.levels[0]["rooms"][0]
            definition.update(shape_type=[shape, "rectangle"], shape_params=(
                dict(arm_width_range=[2, 3], arm_depth_range=[2, 3]) if shape == "l_shape"
                else dict(stem_width_range=[2, 3])))
            before = deepcopy(template.model_dump())
            first = StructureGeneratorService().generate_from_template(world, building, template)
            second = StructureGeneratorService().generate_from_template(world, building, template)
            self.assertEqual((first.cells, first.passages), (second.cells, second.passages))
            self.assertEqual(template.model_dump(), before)
