import json
import unittest

from app.application.worldData.pack.encoding.jsonDecodeBudget import JsonDecodeBudget, JsonDecodeLimitError
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.application.worldData.pack.encoding.jsonDecodeErrors import JsonDecodeInputError, JsonDecodeConfigurationError


class JsonDecodeBudgetTests(unittest.TestCase):
    def limits(self, **changes):
        return DecodeLimits(**(dict(max_bytes=100000, max_nodes=10000, max_depth=100, max_items=10000) | changes))

    def test_exact_caps_and_one_below(self):
        payload = b'{"a":[0,1],"b":{}}'
        exact = dict(max_bytes=len(payload), max_nodes=5, max_depth=2, max_items=2)
        JsonDecodeBudget(self.limits(**exact)).check(payload)
        for field, cap in exact.items():
            with self.subTest(field=field), self.assertRaises(JsonDecodeLimitError):
                JsonDecodeBudget(self.limits(**(exact | {field: cap - 1}))).check(payload)

    def test_frames_share_bytes_and_nodes(self):
        for limits in (self.limits(max_bytes=4), self.limits(max_nodes=3)):
            budget = JsonDecodeBudget(limits)
            budget.check(b'[0]')
            with self.assertRaises(JsonDecodeLimitError):
                budget.check(b'[1]')
        budget = JsonDecodeBudget(self.limits(max_depth=1, max_items=1))
        budget.check(b'[0]')
        budget.check(b'{"a":1}')

    def test_supported_json_agrees_with_parser(self):
        values = [None, True, False, 0, -123, 1.5e-12, "", "привет \U0001f600",
                  '[{},]"\\\n\t', [], {}, [[], {"x": [1, None]}], {"a": 1, "b": [2, 3]}]
        for value in values:
            for ascii_only in (True, False):
                payload = json.dumps(value, ensure_ascii=ascii_only).encode("utf-8")
                with self.subTest(value=value, ascii_only=ascii_only):
                    JsonDecodeBudget(self.limits()).check(payload)
                    self.assertEqual(json.loads(payload), value)
        for payload in (b'1E+10', b'-0', b'0.12e-4', b' "\\/\\b\\f\\r\\u0041" \n'):
            JsonDecodeBudget(self.limits()).check(payload)
            json.loads(payload)

    def test_malformed_syntax_is_not_a_limit(self):
        for payload in (b'', b' ', b'[', b'{', b'[1,]', b'{"a":1,}', b'01', b'1e', b'--2',
                        b'[true false]', b'{"a" 1}', b'{1:2}', b'[] []', b'"\\x"', b'"\\u123"',
                        b'"\n"', b'"unfinished', b'truex', b'NaN', b'Infinity'):
            with self.subTest(payload=payload):
                with self.assertRaises(JsonDecodeInputError) as caught:
                    JsonDecodeBudget(self.limits()).check(payload)
                self.assertNotIsInstance(caught.exception, JsonDecodeLimitError)
                self.assertEqual(caught.exception.issue.pydantic_type, "json_invalid")
                self.assertEqual(caught.exception.issue.code, "SCHEMA_VIOLATION")
                self.assertEqual(caught.exception.issue.location.parts, ())

    def test_duplicate_keys_count_as_members_before_parser(self):
        payload = b'{"x":0,"x":1}'
        JsonDecodeBudget(self.limits(max_items=2, max_nodes=3)).check(payload)
        with self.assertRaises(JsonDecodeLimitError):
            JsonDecodeBudget(self.limits(max_items=1)).check(payload)

    def test_deep_input_uses_bounded_stack(self):
        with self.assertRaises(JsonDecodeLimitError):
            JsonDecodeBudget(self.limits(max_depth=4)).check(b'[' * 2000 + b']' * 2000)

    def test_scalar_needs_no_container_budget(self):
        JsonDecodeBudget(self.limits(max_nodes=1, max_depth=0, max_items=0)).check(b'0')
        JsonDecodeBudget(self.limits(max_nodes=1, max_depth=1, max_items=0)).check(b'[]')

    def test_invalid_configuration_is_not_resource_failure(self):
        for field in ('max_bytes', 'max_nodes', 'max_depth', 'max_items'):
            for bad in (-1, True, '10'):
                with self.subTest(field=field, bad=bad), self.assertRaises(JsonDecodeConfigurationError) as caught:
                    JsonDecodeBudget(self.limits(**{field: bad}))
                self.assertNotIsInstance(caught.exception, JsonDecodeLimitError)
                self.assertEqual(caught.exception.issues[0].location.parts, (field,))
        with self.assertRaises(JsonDecodeInputError) as caught:
            JsonDecodeBudget(self.limits()).check('[]')
        self.assertEqual(caught.exception.issue.pydantic_type, "bytes_type")

    def test_configuration_collects_independent_errors(self):
        with self.assertRaises(JsonDecodeConfigurationError) as caught:
            JsonDecodeBudget(self.limits(max_bytes=-1, max_nodes=True, max_depth='bad'))
        self.assertEqual([(issue.location.parts, issue.pydantic_type) for issue in caught.exception.issues], [
            (("max_bytes",), "greater_than_equal"), (("max_nodes",), "int_type"), (("max_depth",), "int_type")])
