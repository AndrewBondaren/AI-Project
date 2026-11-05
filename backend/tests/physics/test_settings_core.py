import json
import unittest

from pydantic import ValidationError

from app.application.physics.settings.capture import build_settings_view, validate_settings_view
from app.application.physics.settings.prepare import (
    prepare_replace_world_physics_settings, prepare_reset_world_physics_settings,
)
from app.dataModel.physics.settings.settingsChange import (
    PreparedPhysicsSettingsChange, WorldPhysicsSettingsReplace, WorldPhysicsSettingsReset,
)
from app.dataModel.physics.settings.settingsCapture import WorldPhysicsSettingsView
from app.dataModel.physics.settings.settingsResults import PhysicsSettingsChangeReason, PhysicsSettingsChangeRefused
from app.dataModel.physics.settings.worldPhysicsSettings import WorldPhysicsSettings


class SettingsCoreTests(unittest.TestCase):
    def test_default_zero_and_numeric_wire_round_trip(self):
        self.assertEqual(WorldPhysicsSettings().gravity_acceleration_m_s2, 9.80665)
        zero = WorldPhysicsSettings(gravity_acceleration_m_s2=0)
        self.assertEqual(zero.gravity_acceleration_m_s2, 0.0)
        self.assertEqual(WorldPhysicsSettings.model_validate_json(zero.model_dump_json()), zero)
        with self.assertRaises(ValidationError):
            zero.gravity_acceleration_m_s2 = 1

    def test_invalid_values_are_rejected_not_defaulted(self):
        for value in (None, True, False, "1", -1, float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                WorldPhysicsSettings(gravity_acceleration_m_s2=value)
        with self.assertRaises(ValidationError):
            WorldPhysicsSettings(g=1)

    def test_refs_are_stable_world_bound_and_zero_normalized(self):
        value = WorldPhysicsSettings()
        view = build_settings_view("earth", value)
        restored = WorldPhysicsSettings.model_validate_json(value.model_dump_json())
        self.assertEqual(view, build_settings_view("earth", restored))
        self.assertNotEqual(view.ref, build_settings_view("mars", value).ref)
        self.assertNotEqual(view.ref, build_settings_view("earth", WorldPhysicsSettings(gravity_acceleration_m_s2=1)).ref)
        self.assertEqual(build_settings_view("w", WorldPhysicsSettings(gravity_acceleration_m_s2=0)).ref,
                         build_settings_view("w", WorldPhysicsSettings(gravity_acceleration_m_s2=-0.0)).ref)
        self.assertEqual(validate_settings_view(view), view)

    def test_tampered_values_refs_and_constructed_models_cannot_enter_prepare(self):
        view = build_settings_view("w", WorldPhysicsSettings())
        request = WorldPhysicsSettingsReset(world_uid="w", expected_ref=view.ref)
        bad_views = (
            view.model_copy(update={"settings": WorldPhysicsSettings(gravity_acceleration_m_s2=2)}),
            view.model_copy(update={"ref": view.ref.model_copy(update={"schema_version": 2})}),
            view.model_copy(update={"ref": view.ref.model_copy(update={"content_revision": "0" * 64})}),
            view.model_copy(update={"settings": WorldPhysicsSettings.model_construct(gravity_acceleration_m_s2=True)}),
        )
        for bad in bad_views:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                prepare_reset_world_physics_settings(request, bad)
        broken = WorldPhysicsSettings()
        object.__delattr__(broken, "gravity_acceleration_m_s2")
        with self.assertRaises(ValueError):
            build_settings_view("w", broken)

    def test_replace_reset_are_pure_preparations_and_noop_keeps_revision(self):
        current = build_settings_view("w", WorldPhysicsSettings())
        original = current.model_dump_json()
        request = WorldPhysicsSettingsReplace(world_uid="w", expected_ref=current.ref,
                                              value=WorldPhysicsSettings(gravity_acceleration_m_s2=0))
        change = prepare_replace_world_physics_settings(request, current)
        self.assertIsInstance(change, PreparedPhysicsSettingsChange)
        self.assertEqual(change.proposed.gravity_acceleration_m_s2, 0)
        self.assertEqual(current.model_dump_json(), original)
        # Preparation has not changed the accepted/current view.
        self.assertEqual(change.expected_ref, current.ref)
        zero_view = build_settings_view("w", change.proposed)
        noop = prepare_replace_world_physics_settings(request.model_copy(update={"expected_ref": zero_view.ref}), zero_view)
        self.assertEqual(noop.proposed_ref, zero_view.ref)
        reset = prepare_reset_world_physics_settings(WorldPhysicsSettingsReset(world_uid="w", expected_ref=zero_view.ref), zero_view)
        self.assertEqual(reset.proposed_ref, current.ref)
        noop_reset = prepare_reset_world_physics_settings(WorldPhysicsSettingsReset(world_uid="w", expected_ref=current.ref), current)
        self.assertEqual(noop_reset.proposed_ref, current.ref)

    def test_stale_or_other_world_expectations_never_produce_changes(self):
        current = build_settings_view("w", WorldPhysicsSettings())
        stale = build_settings_view("w", WorldPhysicsSettings(gravity_acceleration_m_s2=2))
        operations = (
            (prepare_reset_world_physics_settings, WorldPhysicsSettingsReset(world_uid="w", expected_ref=stale.ref)),
            (prepare_replace_world_physics_settings, WorldPhysicsSettingsReplace(world_uid="w", expected_ref=stale.ref, value=current.settings)),
            (prepare_reset_world_physics_settings, WorldPhysicsSettingsReset(world_uid="other", expected_ref=build_settings_view("other", current.settings).ref)),
        )
        for operation, request in operations:
            result = operation(request, current)
            self.assertIsInstance(result, PhysicsSettingsChangeRefused)
            self.assertEqual(result.reason, PhysicsSettingsChangeReason.STALE_SETTINGS)
        with self.assertRaises(ValidationError):
            WorldPhysicsSettingsReset(world_uid="other", expected_ref=current.ref)

    def test_damaged_nested_settings_are_rejected_before_defaults_restore(self):
        current = build_settings_view("w", WorldPhysicsSettings(gravity_acceleration_m_s2=0))
        damaged = current.settings.model_copy()
        object.__delattr__(damaged, "gravity_acceleration_m_s2")
        with self.assertRaises(ValidationError):
            WorldPhysicsSettings.model_validate(damaged)
        with self.assertRaises(ValidationError):
            WorldPhysicsSettingsReplace(world_uid="w", expected_ref=current.ref, value=damaged)
        with self.assertRaises(ValidationError):
            PreparedPhysicsSettingsChange(world_uid="w", expected_ref=current.ref,
                                          proposed=damaged, proposed_ref=current.ref)
        self.assertEqual(current.settings.gravity_acceleration_m_s2, 0)
        # Actual missing authoring input still receives the declared default.
        self.assertEqual(WorldPhysicsSettings.model_validate({}).gravity_acceleration_m_s2, 9.80665)

    def test_prepared_change_rejects_content_mismatch_on_all_decode_boundaries(self):
        earth = build_settings_view("w", WorldPhysicsSettings())
        zero = build_settings_view("w", WorldPhysicsSettings(gravity_acceleration_m_s2=0))
        fields = dict(world_uid="w", expected_ref=earth.ref, proposed=zero.settings, proposed_ref=earth.ref)
        with self.assertRaises(ValidationError):
            PreparedPhysicsSettingsChange(**fields)
        invalid = PreparedPhysicsSettingsChange.model_construct(**fields)
        with self.assertRaises(ValidationError):
            PreparedPhysicsSettingsChange.model_validate(invalid)
        with self.assertRaises(ValidationError):
            PreparedPhysicsSettingsChange.model_validate(invalid.model_dump())
        with self.assertRaises(ValidationError):
            PreparedPhysicsSettingsChange.model_validate_json(invalid.model_dump_json())
        fields["proposed_ref"] = zero.ref
        valid = PreparedPhysicsSettingsChange(**fields)
        self.assertEqual(PreparedPhysicsSettingsChange.model_validate_json(valid.model_dump_json()), valid)

    def test_view_rejects_mismatched_content_and_schema_during_construction(self):
        earth = build_settings_view("w", WorldPhysicsSettings())
        zero = WorldPhysicsSettings(gravity_acceleration_m_s2=0)
        with self.assertRaises(ValidationError):
            WorldPhysicsSettingsView(settings=zero, ref=earth.ref)
        wire = earth.model_dump(mode="json")
        wire["settings"]["gravity_acceleration_m_s2"] = 0
        with self.assertRaises(ValidationError):
            WorldPhysicsSettingsView.model_validate_json(json.dumps(wire))
        wire = earth.model_dump(mode="json")
        wire["ref"]["schema_version"] = 2
        with self.assertRaises(ValidationError):
            WorldPhysicsSettingsView.model_validate(wire)


if __name__ == "__main__":
    unittest.main()
