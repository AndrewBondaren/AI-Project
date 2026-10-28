"""P2: reproducible diagnostic IDs, independent of runtime process and rule contents."""

import json
import os
from dataclasses import replace
from enum import IntEnum
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

from app.dataModel.cascade.cascadeGraph import BoundField
from app.dataModel.policy.declarations.policyIdentity import RuleIdentity, RuleKind, ValueBranch, make_rule_id
from tests.geo1.declarations.test_declarations import Action, Foreign, Key, Owner, OtherOwner, Settings


class IdentityTests(TestCase):
    def identity(self, value=False):
        return RuleIdentity(owner=Owner, kind=RuleKind.VALUE_CASE, field=BoundField(Settings, "enabled"),
                            branch=ValueBranch(value))

    def test_encoding_is_canonical_and_self_describing(self):
        value = make_rule_id(self.identity(False))
        self.assertTrue(value.startswith("policy-rule/v1:"))
        parts = json.loads(value.removeprefix("policy-rule/v1:"))
        self.assertEqual(parts, [[Owner.__module__, Owner.__qualname__], "value_case",
            [Settings.__module__, Settings.__qualname__, "enabled"], ["bool", False], None])
        self.assertEqual(value, "policy-rule/v1:" + json.dumps(parts, ensure_ascii=True, separators=(",", ":")))

    def test_type_tags_prevent_scalar_and_enum_collisions(self):
        class Number(IntEnum):
            ONE = 1
        values = (None, False, True, 0, 1, 0.0, -0.0, 1.0, "1", Number.ONE, Action.DECLARED, Foreign.DECLARED)
        self.assertEqual(len({make_rule_id(self.identity(v)) for v in values}), len(values))
        float_parts = json.loads(make_rule_id(self.identity(1.25)).removeprefix("policy-rule/v1:"))
        self.assertEqual(float_parts[3], ["float", (1.25).hex()])

    def test_rule_kind_owner_source_and_branch_are_identity(self):
        original = self.identity()
        variants = (original, replace(original, owner=OtherOwner),
            replace(original, field=BoundField(Settings, "priority")), replace(original, branch=ValueBranch(True)),
            RuleIdentity(owner=Owner, kind=RuleKind.ENABLED, field=original.field),
            RuleIdentity(owner=Owner, kind=RuleKind.COMPOSITE_CASE, case_key=Key.SELECT),
            RuleIdentity(owner=Owner, kind=RuleKind.ZERO_PRIORITY))
        self.assertEqual(len({make_rule_id(v) for v in variants}), len(variants))
        self.assertEqual(make_rule_id(original), make_rule_id(replace(original)))

    def test_strings_are_escaped_without_ambiguous_separators(self):
        value = 'a.b:["x"]\nкириллица'
        encoded = make_rule_id(self.identity(value))
        self.assertTrue(encoded.isascii())
        self.assertNotIn("\n", encoded)
        self.assertEqual(json.loads(encoded.removeprefix("policy-rule/v1:"))[3], ["str", value])

    def test_process_hash_seed_does_not_change_ids(self):
        script = (
            "from tests.geo1.declarations.test_identity import IdentityTests; "
            "from app.dataModel.policy.declarations.policyIdentity import make_rule_id; "
            "print(make_rule_id(IdentityTests().identity('process')))"
        )
        expected = make_rule_id(self.identity("process"))
        for seed in ("1", "98765"):
            completed = subprocess.run([sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parents[3], env={**os.environ, "PYTHONHASHSEED": seed},
                check=True, capture_output=True, text=True)
            self.assertEqual(completed.stdout.strip(), expected)
