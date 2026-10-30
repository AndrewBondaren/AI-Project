"""Use the existing Pyright toolchain to verify positive and negative contracts."""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path


class TypingGateTests(unittest.TestCase):
    def test_nominal_refs_keys_and_outcomes(self) -> None:
        root = Path(__file__).resolve().parents[4]
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node is required by the existing Pyright toolchain")
        cli = root / "node_modules" / "pyright" / "index.js"
        self.assertTrue(cli.is_file(), "Use the project-installed Pyright; no network install")
        fixtures = root / "backend" / "tests" / "typing" / "snapshotCore"
        assert node is not None
        positive = subprocess.run(
            [node, str(cli), "-p", str(fixtures / "pyrightconfig.valid.json"), "--outputjson"],
            cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(positive.returncode, 0, positive.stdout + positive.stderr)
        self.assertEqual(json.loads(positive.stdout)["generalDiagnostics"], [])

        negative = subprocess.run(
            [node, str(cli), "-p", str(fixtures / "pyrightconfig.invalid.json"), "--outputjson"],
            cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(negative.returncode, 1, negative.stdout + negative.stderr)
        fixture = fixtures / "invalid.py"
        expected = [
            (index, match.group(1))
            for index, line in enumerate(fixture.read_text(encoding="utf-8").splitlines())
            if (match := re.search(r"# EXPECT: (\w+)", line))
        ]
        self.assertTrue(expected)
        actual = []
        for diagnostic in json.loads(negative.stdout)["generalDiagnostics"]:
            self.assertEqual(Path(diagnostic["file"]).resolve(), fixture.resolve(), diagnostic)
            self.assertEqual(diagnostic["severity"], "error", diagnostic)
            actual.append((diagnostic["range"]["start"]["line"], diagnostic["rule"]))
        self.assertEqual(sorted(actual), sorted(expected), negative.stdout)


if __name__ == "__main__":
    unittest.main()
