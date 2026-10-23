"""PC-3 config IO and lazy container resource admission."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.core.appSettings import AppSettings, app_settings
from app.core.configManager import ConfigManager
from app.core.container import Container
from app.dataModel.planning.policy.planningRuntimeSettings import PlanningRuntimeSettings


def configured():
    return PlanningRuntimeSettings.model_validate({
        "cache": {"max_retained_bytes": 20000, "max_entry_bytes": 10000},
        "execution": {"max_workers": 2, "max_pending_builds": 4},
    })


class PlanningResourceTests(unittest.TestCase):
    def test_settings_update_validates_and_is_atomic_on_invalid_planning(self):
        settings = AppSettings()
        self.assertIsNone(settings.planning)
        settings.update(planning=configured().model_dump(mode="json"))
        self.assertEqual(settings.planning, configured())
        for invalid in ({}, {"cache": {}}, {"cache": configured().cache.model_dump()},
                        configured().model_dump() | {"execution": {"max_workers": True, "max_pending_builds": 1}},
                        configured().model_dump() | {"cache": {"max_retained_bytes": 1, "max_entry_bytes": 2}}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                settings.update(language="en", planning=invalid)
            self.assertEqual(settings.planning, configured())
            self.assertEqual(settings.language, AppSettings().language)
        settings.update(planning=None)
        self.assertIsNone(settings.planning)

    def test_toml_round_trip_and_absence_no_null_or_automatic_numeric_limits(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            manager = ConfigManager(path)
            loaded = manager.load()
            self.assertNotIn("planning", loaded)
            self.assertNotIn("[planning", path.read_text(encoding="utf-8"))
            settings = AppSettings(planning=configured())
            manager.save(settings)
            text = path.read_text(encoding="utf-8")
            self.assertIn("[planning.cache]", text)
            self.assertIn("[planning.execution]", text)
            self.assertNotIn("ttl_seconds", text)
            self.assertEqual(manager.load()["planning"], configured())
            # Migration of unrelated defaults must preserve the planning policy.
            path.write_text(text.replace('max_passes = 3\n', ''), encoding="utf-8")
            self.assertEqual(manager.load()["planning"], configured())
            manager.save(AppSettings())
            self.assertNotIn("planning", manager.load())

    def test_incomplete_or_invalid_toml_fails_without_migrating_fake_limits(self):
        for fragment in ("[planning]\n", "[planning.cache]\nmax_retained_bytes = 100\n",
                         "[planning.cache]\nmax_retained_bytes = true\nmax_entry_bytes = 1\n"
                         "[planning.execution]\nmax_workers = 1\nmax_pending_builds = 1\n"):
            with TemporaryDirectory() as directory:
                path = Path(directory) / "config.toml"
                path.write_text(fragment, encoding="utf-8")
                with self.assertRaises(ValidationError):
                    ConfigManager(path).load()
                self.assertEqual(path.read_text(encoding="utf-8"), fragment)

    def test_container_requires_policies_and_owns_one_cache_even_under_concurrent_access(self):
        with patch.object(app_settings, "planning", None):
            container = Container(None, None)
            with self.assertRaisesRegex(ValueError, "explicit.*planning.cache"):
                container.planning_cache_service()
        with patch.object(app_settings, "planning", configured()):
            container = Container(None, None)
            with ThreadPoolExecutor(max_workers=8) as pool:
                services = list(pool.map(lambda _: container.planning_cache_service(), range(32)))
            self.assertTrue(all(service is services[0] for service in services))
            self.assertIs(container.planning_memory_cache(), container.planning_memory_cache())
            self.assertEqual(container.planning_resources(), configured())
            other = Container(None, None)
            self.assertIsNot(other.planning_memory_cache(), container.planning_memory_cache())
        # Process resources retain their captured immutable configuration.
        self.assertEqual(container.planning_resources(), configured())


if __name__ == "__main__":
    unittest.main()
