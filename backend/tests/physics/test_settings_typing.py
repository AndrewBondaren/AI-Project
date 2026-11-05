"""Use the project Pyright toolchain for positive and negative contracts."""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path


class SettingsTypingTests(unittest.TestCase):
    def test_public_outcomes_and_concrete_causes(self):
        root = Path(__file__).resolve().parents[3]
        node = shutil.which("node")
        self.assertIsNotNone(node)
        assert node is not None
        cli = root / "node_modules/pyright/index.js"
        self.assertTrue(cli.is_file())
        fixtures = root / "backend/tests/typing/physics"
        for mode in ("valid", "invalid"):
            with self.subTest(mode=mode):
                run = subprocess.run(
                    [node, str(cli), "-p", str(fixtures / f"pyrightconfig.{mode}.json"), "--outputjson"],
                    cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=60,
                )
                diagnostics = json.loads(run.stdout)["generalDiagnostics"]
                if mode == "valid":
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                    self.assertEqual(diagnostics, [])
                else:
                    self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                    fixture = fixtures / "invalid.py"
                    expected = [
                        (index, match.group(1))
                        for index, line in enumerate(fixture.read_text(encoding="utf-8").splitlines())
                        if (match := re.search(r"# EXPECT: (\w+)", line))
                    ]
                    actual = []
                    for diagnostic in diagnostics:
                        self.assertEqual(Path(diagnostic["file"]).resolve(), fixture.resolve())
                        self.assertEqual(diagnostic["severity"], "error")
                        actual.append((diagnostic["range"]["start"]["line"], diagnostic["rule"]))
                    self.assertEqual(sorted(actual), sorted(expected), run.stdout)
