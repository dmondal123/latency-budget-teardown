"""Regression checks for the frozen contract and evaluation-suite verifier."""

from __future__ import annotations

import subprocess
import sys
import unittest
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class VerifyEvalSuiteTest(unittest.TestCase):
    def test_environment_manifest_is_pinned_and_transparent(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/verify_environment.py"],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Qwen3-VL-4B-Instruct-4bit@2fd8dac", result.stdout)
        self.assertNotIn("runtime revision pending feasibility gate", result.stdout)

    def test_versioned_case_schema_is_present(self) -> None:
        schema_path = REPOSITORY_ROOT / "eval/v1/case.schema.json"
        with schema_path.open(encoding="utf-8") as stream:
            schema = json.load(stream)

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["title"], "Multimodal RAG evaluation case v1")

    def test_repository_contract_and_eval_suite_verify(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/verify_eval.py",
                "--repo-root",
                str(REPOSITORY_ROOT),
            ],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validated 30 cases", result.stdout)
        self.assertIn("sealed 6 holdouts", result.stdout)


if __name__ == "__main__":
    unittest.main()
