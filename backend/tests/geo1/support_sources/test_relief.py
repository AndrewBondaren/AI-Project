"""Relief arrays remain wire arrays while the domain source graph is immutable."""
import json
from unittest import TestCase

from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.reliefRoleCase import ReliefRoleCase
from app.dataModel.terrain.relief.reliefGradeKnobs import ReliefGradeKnobs
from app.dataModel.validation.immutableValue import validate_immutable
from tests.geo1.support_sources.fixtures import template


class ReliefSourceTests(TestCase):
    def test_template_source_arrays_are_tuples_and_json_arrays(self):
        value=ReliefTemplate.model_validate({**template().model_dump(),"structure_refs":["ref"]})
        self.assertIsInstance(value.conditions,tuple);self.assertIsInstance(value.structure_refs,tuple)
        self.assertEqual(json.loads(value.model_dump_json())["structure_refs"],["ref"])
        validate_immutable(value)
        self.assertEqual(ReliefTemplate.model_validate_json(value.model_dump_json()),value)

    def test_mode_b_empty_bands_remain_distinct_from_none(self):
        value=ReliefRoleCase(policy="slope_none",bands=[])
        self.assertEqual(value.bands,());self.assertFalse(value.is_mode_a)
        self.assertEqual(json.loads(value.model_dump_json())["bands"],[])
        with self.assertRaises(ValueError):ReliefRoleCase(policy="slope_none",bands=None)
        self.assertIsNone(ReliefRoleCase(policy="slope_none",delta_z=0,slope_weight=.5,sheer_weight=.5).bands)

    def test_grade_knobs_refs_cannot_be_mutated_in_place(self):
        value=ReliefGradeKnobs(slope_weight=.5,sheer_weight=.5,structure_refs=["ref"])
        validate_immutable(value);self.assertEqual(value.structure_refs,("ref",))
        with self.assertRaises(AttributeError):value.structure_refs.append("another")
