"""Run both static fixtures; unexpected diagnostics fail just like missing ones."""

import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


class TypeTests(unittest.TestCase):
    def test_unchanged_metadata_strict_baseline(self):
        root = Path(__file__).resolve().parents[4]
        record = root / "backend/app/dataModel/engine/dag/records.py"
        # Pydantic annotates FieldInfo.annotation as type | None, while the
        # existing admission code also handles a runtime TypeVar. Keep that
        # pre-existing strict diagnostic explicit, without suppressing new code.
        with tempfile.TemporaryDirectory(prefix="dag-typing-baseline-", dir=root) as temporary:
            config = Path(temporary) / "pyrightconfig.json"
            config.write_text(json.dumps({
                "include": ["../" + record.relative_to(root).as_posix()],
                "extraPaths": [str(root / "backend")],
                "venvPath": str(root), "venv": ".venv", "pythonVersion": "3.12",
                "typeCheckingMode": "strict",
            }), encoding="utf-8")
            result = subprocess.run(
                ["node", str(root / "node_modules/pyright/index.js"), "-p", str(config), "--outputjson"],
                cwd=root, capture_output=True, text=True, timeout=90,
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        diagnostics = json.loads(result.stdout)["generalDiagnostics"]
        actual = [
            (Path(item["file"]).resolve(), item["range"]["start"]["line"], item.get("rule"), item["severity"])
            for item in diagnostics
        ]
        self.assertEqual(actual, [(record.resolve(), 58, "reportUnnecessaryIsInstance", "error")], result.stdout)

    def test_positive_and_exact_negative_diagnostics(self):
        root = Path(__file__).resolve().parents[4]
        fixtures = root / "backend/tests/dag_typing/typing"
        cli = root / "node_modules/pyright/index.js"
        positive = subprocess.run(
            ["node", str(cli), "-p", str(fixtures / "pyrightconfig.json"), "--outputjson"],
            cwd=root, capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(positive.returncode, 0, positive.stdout + positive.stderr)
        self.assertEqual(json.loads(positive.stdout)["generalDiagnostics"], [])
        expected = []
        for index, line in enumerate((fixtures / "invalid.py").read_text(encoding="utf-8").splitlines()):
            match = re.search(r"# expect: (\w+)", line)
            if match:
                expected.append((index, match.group(1)))
        self.assertTrue(expected, "negative fixture must declare expected errors")
        negative = subprocess.run(
            ["node", str(cli), "-p", str(fixtures / "pyrightconfig.invalid.json"), "--outputjson"],
            cwd=root, capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(negative.returncode, 1, negative.stdout + negative.stderr)
        actual = []
        for diagnostic in json.loads(negative.stdout)["generalDiagnostics"]:
            self.assertEqual(Path(diagnostic["file"]).resolve(), (fixtures / "invalid.py").resolve(), diagnostic)
            self.assertEqual(diagnostic["severity"], "error", diagnostic)
            actual.append((diagnostic["range"]["start"]["line"], diagnostic.get("rule")))
        self.assertEqual(sorted(actual), sorted(expected), negative.stdout)
