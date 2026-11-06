"""Policy, causal facts and integrity boundaries of Physics settings."""

import asyncio
from copy import deepcopy
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from app.application.jsonValidation.resolution.diagnostics import ResolveContext, ResolveMode
from app.application.physics.settings.capture import (
    PhysicsSettingsBoundaryFault, build_settings_view, validate_settings_view, validation_failure,
)
from app.application.physics.settings.input import (
    resolve_world_physics_settings_input_runtime, validate_world_physics_settings_input,
)
from app.application.physics.settings.prepare import prepare_reset_world_physics_settings
from app.dataModel.physics.settings.settingsCapture import WorldPhysicsSettingsView
from app.dataModel.physics.settings.settingsChange import WorldPhysicsSettingsReset
from app.dataModel.physics.settings.settingsInput import (
    PhysicsGravityDefaultApplied, PhysicsSettingsInputRefused, PhysicsSettingsInputResolved,
)
from app.dataModel.physics.settings.settingsIssues import (
    GRAVITY_PATH, PhysicsGravityArguments, PhysicsGravityCode, PhysicsGravityTypeError,
    PhysicsSettingsAdmissionFailure, PhysicsSettingsSubject, SettingsContentMismatch,
    SettingsMalformedContract, SettingsPolicyMismatch, SettingsSchemaMismatch, SettingsWorldMismatch,
)
from app.dataModel.physics.settings.settingsResults import PhysicsSettingsChangeRefused
from app.dataModel.physics.settings.worldPhysicsSettings import STANDARD_GRAVITY_M_S2, WorldPhysicsSettings
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.physics.settings.settingsCapture import WorldPhysicsSettingsRef

LOG = "app.application.physics.settings"


class SettingsPolicyTests(unittest.TestCase):
    def test_negative_integer_and_string_keys_return_typed_refusal(self):
        for operation, validate in ((validate_world_physics_settings_input, True),
                                    (resolve_world_physics_settings_input_runtime, False)):
            for key in (-1, "-1"):
                for prefix in ((), ("settings",)):
                    results = []
                    for collect_only in (False, True):
                        with self.subTest(operation=operation.__name__, key=key,
                                          prefix=prefix, collect_only=collect_only):
                            raw = {key: 1}
                            before = deepcopy(raw)
                            ctx = ResolveContext(validate_only=validate, collect_only=collect_only,
                                                 location=WireLocation(parts=prefix))
                            with patch("app.application.physics.settings.reporting.logger.warning") as warning:
                                result = operation(raw, ctx=ctx)
                            self.assertIs(type(result), PhysicsSettingsInputRefused)
                            self.assertEqual(len(result.issues), 1)
                            issue = result.issues[0]
                            self.assertIs(type(issue), WireShapeIssue)
                            self.assertIs(issue.code, JsonValidationCode.VALIDATION_ERROR)
                            self.assertEqual(issue.location.parts, prefix if key == -1 else (*prefix, "-1"))
                            self.assertEqual(tuple(ctx.report.issues), result.issues)
                            self.assertEqual(ctx.report.diagnostics, ())
                            self.assertEqual(raw, before)
                            self.assertIs(type(next(iter(raw))), type(key))
                            self.assertEqual(ctx.location.parts, prefix)
                            self.assertEqual(warning.call_count, int(not validate and not collect_only))
                            results.append(result)
                    if len(results) == 2:
                        self.assertEqual(results[0], results[1])

    def test_invalid_key_and_gravity_do_not_publish_a_fallback(self):
        for operation, validate in ((validate_world_physics_settings_input, True),
                                    (resolve_world_physics_settings_input_runtime, False)):
            with self.subTest(operation=operation.__name__):
                raw = {"gravity_acceleration_m_s2": None, -1: 1}
                before = deepcopy(raw)
                ctx = ResolveContext(validate_only=validate, collect_only=True)
                with self.assertNoLogs(LOG):
                    result = operation(raw, ctx=ctx)
                self.assertIs(type(result), PhysicsSettingsInputRefused)
                self.assertEqual(tuple(type(issue) for issue in result.issues),
                                 (PhysicsGravityTypeError, WireShapeIssue))
                self.assertEqual(tuple(ctx.report.issues), result.issues)
                self.assertEqual(ctx.report.diagnostics, ())
                self.assertEqual(raw, before)

    def view(self, value=STANDARD_GRAVITY_M_S2, world="w") -> WorldPhysicsSettingsView:
        result = build_settings_view(world, WorldPhysicsSettings(gravity_acceleration_m_s2=value))
        assert isinstance(result, WorldPhysicsSettingsView)
        return result

    def test_same_invalid_cause_refuses_validation_and_defaults_runtime(self):
        invalid = (None, True, False, "1", -1, float("nan"), float("inf"), [], {}, 10**400)
        for raw in invalid:
            with self.subTest(kind=type(raw).__name__):
                authored = {"gravity_acceleration_m_s2": raw}
                validate = ResolveContext(validate_only=True, location=WireLocation(parts=("settings",)))
                runtime = ResolveContext(location=validate.location)
                with self.assertNoLogs(LOG):
                    rejected = validate_world_physics_settings_input(authored, ctx=validate)
                with self.assertLogs(LOG, "WARNING") as logs:
                    resolved = resolve_world_physics_settings_input_runtime(authored, ctx=runtime)
                self.assertIsInstance(rejected, PhysicsSettingsInputRefused)
                self.assertIsInstance(resolved, PhysicsSettingsInputResolved)
                self.assertEqual(resolved.settings.gravity_acceleration_m_s2, STANDARD_GRAVITY_M_S2)
                self.assertEqual(len(logs.records), 1)
                self.assertIn("WarningError", logs.output[0])
                self.assertIn(str(STANDARD_GRAVITY_M_S2), logs.output[0])
                first, second = rejected.issues[0], resolved.diagnostics[0].cause
                self.assertIsInstance(first, PhysicsGravityTypeError)
                self.assertEqual((first.code, first.path, first.arguments, first.location),
                                 (second.code, second.path, second.arguments, second.location))
                self.assertEqual(first.path, GRAVITY_PATH)
                self.assertEqual(validate.report.issues, [first])
                self.assertEqual(runtime.report.issues, [])
                self.assertEqual(runtime.report.diagnostics, (second,))
                self.assertEqual(self.view().ref, build_settings_view("w", resolved.settings).ref)

    def test_zero_valid_custom_and_missing_are_not_fallbacks(self):
        for authored, expected in (({}, STANDARD_GRAVITY_M_S2),
                                   ({"gravity_acceleration_m_s2": 0}, 0),
                                   ({"gravity_acceleration_m_s2": -0.0}, 0),
                                   ({"gravity_acceleration_m_s2": 3.71}, 3.71)):
            with self.subTest(authored=authored), self.assertNoLogs(LOG):
                result = resolve_world_physics_settings_input_runtime(authored, ctx=ResolveContext())
                self.assertEqual(result.settings.gravity_acceleration_m_s2, expected)
                self.assertEqual(result.diagnostics, ())

    def test_silent_and_emitted_runtime_have_identical_results_and_one_cause(self):
        raw = {"gravity_acceleration_m_s2": None}
        emitted, silent = ResolveContext(), ResolveContext(collect_only=True)
        with self.assertLogs(LOG, "WARNING") as logs:
            result = resolve_world_physics_settings_input_runtime(raw, ctx=emitted)
            repeated = resolve_world_physics_settings_input_runtime(raw, ctx=emitted)
        with self.assertNoLogs(LOG):
            quiet = resolve_world_physics_settings_input_runtime(raw, ctx=silent)
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(result, repeated)
        self.assertEqual(result, quiet)
        self.assertEqual(emitted.report.diagnostics, silent.report.diagnostics)

    def test_mixed_removed_unknown_shape_and_captured_inputs_never_default(self):
        for raw in ({"g": 1}, {"extra": 1}, {"gravity_acceleration_m_s2": None, "extra": 1},
                    None, [], WorldPhysicsSettings(), self.view()):
            with self.subTest(raw=raw):
                ctx = ResolveContext(collect_only=True)
                result = resolve_world_physics_settings_input_runtime(raw, ctx=ctx)
                self.assertIsInstance(result, PhysicsSettingsInputRefused)
                self.assertEqual(ctx.report.diagnostics, ())
                self.assertEqual(tuple(ctx.report.issues), result.issues)
        partial = resolve_world_physics_settings_input_runtime({}, ctx=ResolveContext(partial=True, collect_only=True))
        self.assertIsInstance(partial, PhysicsSettingsInputRefused)

    def test_wrong_policy_cannot_select_another_operation(self):
        cases = (
            (validate_world_physics_settings_input, ResolveContext()),
            (resolve_world_physics_settings_input_runtime, ResolveContext(validate_only=True)),
            (resolve_world_physics_settings_input_runtime, ResolveContext(mode=ResolveMode.IMPORT)),
        )
        for operation, ctx in cases:
            with self.subTest(operation=operation.__name__), self.assertNoLogs(LOG):
                result = operation({}, ctx=ctx)
                self.assertIsInstance(result, PhysicsSettingsAdmissionFailure)
                self.assertIsInstance(result.cause, SettingsPolicyMismatch)
                self.assertEqual(ctx.report.issues, [])

    def test_integrity_causes_and_expected_revision_have_distinct_outcomes(self):
        current = self.view()
        request = WorldPhysicsSettingsReset(world_uid="w", expected_ref=self.view(0).ref)
        conflict = prepare_reset_world_physics_settings(request, current)
        self.assertIsInstance(conflict, PhysicsSettingsChangeRefused)
        self.assertEqual(conflict.expected_ref, request.expected_ref)
        self.assertEqual(conflict.observed_ref, current.ref)
        cases = (
            (current.model_copy(update={"settings": WorldPhysicsSettings(gravity_acceleration_m_s2=2)}), SettingsContentMismatch),
            (current.model_copy(update={"ref": current.ref.model_copy(update={"schema_version": 2})}), SettingsSchemaMismatch),
        )
        for invalid, cause_type in cases:
            failure = prepare_reset_world_physics_settings(request, invalid)
            self.assertIsInstance(failure, PhysicsSettingsAdmissionFailure)
            self.assertIsInstance(failure.cause, cause_type)
            restored = PhysicsSettingsAdmissionFailure.model_validate_json(failure.model_dump_json())
            self.assertEqual(restored, failure)
            self.assertIsInstance(restored.cause, cause_type)
        wrong_world = prepare_reset_world_physics_settings(request, self.view(world="other"))
        self.assertIsInstance(wrong_world.cause, SettingsWorldMismatch)

    def test_corrupted_records_never_recover_defaults(self):
        current = self.view(0)
        settings = current.settings.model_copy()
        object.__delattr__(settings, "gravity_acceleration_m_s2")
        damaged = current.model_copy(update={"settings": settings})
        failure = validate_settings_view(damaged)
        self.assertIsInstance(failure.cause, SettingsMalformedContract)
        forged = WorldPhysicsSettingsReset.model_construct(world_uid="other", expected_ref=current.ref)
        failure = prepare_reset_world_physics_settings(forged, current)
        self.assertIsInstance(failure.cause, SettingsWorldMismatch)
        self.assertEqual(current.settings.gravity_acceleration_m_s2, 0)

    def test_diagnostic_json_and_runtime_admission_preserve_concrete_types(self):
        with self.assertNoLogs(LOG):
            result = resolve_world_physics_settings_input_runtime(
                {"gravity_acceleration_m_s2": None}, ctx=ResolveContext(collect_only=True))
        restored = PhysicsSettingsInputResolved.model_validate_json(result.model_dump_json())
        self.assertEqual(restored, result)
        cause = restored.diagnostics[0].cause
        self.assertIsInstance(cause, PhysicsGravityTypeError)
        with self.assertRaises(ValidationError):
            PhysicsGravityTypeError(code=JsonValidationCode.DOMAIN_RANGE, path=GRAVITY_PATH,
                                    arguments=cause.arguments, location=WireLocation(), message="bad")
        with self.assertRaises(ValidationError):
            PhysicsGravityArguments(pydantic_type="missing")
        with self.assertRaises(ValidationError):
            PhysicsGravityDefaultApplied(cause=cause, selected=0)
        with self.assertRaises(ValidationError):
            PhysicsSettingsInputResolved(settings=WorldPhysicsSettings(gravity_acceleration_m_s2=0),
                                         diagnostics=result.diagnostics)

    def test_technical_fault_and_cancellation_are_not_defaulted(self):
        for failure in (RuntimeError("technical"), asyncio.CancelledError()):
            with self.subTest(failure=type(failure).__name__), patch(
                "app.application.physics.settings.input.WorldPhysicsSettings.model_validate", side_effect=failure,
            ), self.assertNoLogs(LOG), self.assertRaises(type(failure)):
                resolve_world_physics_settings_input_runtime({}, ctx=ResolveContext())

    def test_unknown_validator_code_is_a_boundary_fault(self):
        unknown = ValidationError.from_exception_data("settings", [{
            "type": PydanticCustomError("unknown_physics_contract", "unrecognized"), "loc": (), "input": {},
        }])
        with patch("app.application.physics.settings.input.WorldPhysicsSettings.model_validate", side_effect=unknown):
            with self.assertRaises(PhysicsSettingsBoundaryFault):
                resolve_world_physics_settings_input_runtime({}, ctx=ResolveContext())
        with self.assertRaises(PhysicsSettingsBoundaryFault):
            validation_failure(WorldPhysicsSettings, unknown, PhysicsSettingsSubject.SETTINGS)

    def test_malformed_and_refused_json_restore_without_erasing_field_types(self):
        malformed = build_settings_view("w", WorldPhysicsSettings.model_construct(gravity_acceleration_m_s2=True))
        restored = PhysicsSettingsAdmissionFailure.model_validate_json(malformed.model_dump_json())
        self.assertEqual(restored, malformed)
        self.assertEqual(type(restored.cause.issues[0]), type(malformed.cause.issues[0]))
        for raw in ({"gravity_acceleration_m_s2": None}, {"g": 1},
                    {"gravity_acceleration_m_s2": -1, "extra": 1}):
            result = validate_world_physics_settings_input(raw, ctx=ResolveContext(validate_only=True))
            self.assertEqual(PhysicsSettingsInputRefused.model_validate_json(result.model_dump_json()), result)
        current = self.view()
        request = WorldPhysicsSettingsReset(world_uid="w", expected_ref=self.view(0).ref)
        mismatch = prepare_reset_world_physics_settings(request, current)
        self.assertEqual(PhysicsSettingsChangeRefused.model_validate_json(mismatch.model_dump_json()), mismatch)

    def test_unknown_path_and_foreign_arguments_are_rejected(self):
        error = ValidationError.from_exception_data("settings", [{
            "type": "float_type", "loc": ("not_a_field",), "input": None,
        }])
        with self.assertRaises(PhysicsSettingsBoundaryFault):
            validation_failure(WorldPhysicsSettings, error, PhysicsSettingsSubject.SETTINGS)
        foreign_path = CheckedPath.root(WorldPhysicsSettingsRef).field(
            FieldRef(lambda: WorldPhysicsSettingsRef, lambda ref: ref.world_uid)).freeze()
        for path, arguments in ((foreign_path, PhysicsGravityArguments(pydantic_type="float_type")),
                                (GRAVITY_PATH, WorldPhysicsSettings())):
            with self.assertRaises(ValidationError):
                PhysicsGravityTypeError(code=PhysicsGravityCode.INVALID_GRAVITY, path=path,
                                        arguments=arguments, location=WireLocation(), message="invalid")

    def test_codec_fault_does_not_become_an_admission_or_default(self):
        with patch("app.dataModel.physics.settings.settingsCapture.encode", side_effect=RuntimeError("codec")):
            with self.assertRaises(RuntimeError):
                build_settings_view("w", WorldPhysicsSettings())


if __name__ == "__main__":
    unittest.main()
