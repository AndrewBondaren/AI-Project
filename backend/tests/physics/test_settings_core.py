import unittest

from pydantic import ValidationError

from app.application.physics.settings.capture import build_settings_view, validate_settings_view
from app.application.physics.settings.legacyImport import normalise_legacy_gravity
from app.application.physics.settings.prepare import (
    prepare_replace_world_physics_settings, prepare_reset_world_physics_settings,
)
from app.dataModel.physics.settings.settingsChange import (
    PreparedPhysicsSettingsChange, WorldPhysicsSettingsReplace, WorldPhysicsSettingsReset,
)
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

    def test_legacy_factor_is_explicit_and_finite(self):
        for factor, expected in ((1, 9.80665), (0.38, 3.726527), (0, 0.0)):
            self.assertEqual(normalise_legacy_gravity(factor).gravity_acceleration_m_s2, expected)
        for invalid in (None, True, "1", -1, float("inf"), 1e308):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                normalise_legacy_gravity(invalid)


if __name__ == "__main__":
    unittest.main()
