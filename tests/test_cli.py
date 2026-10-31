from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from judge_gate.cli import render_json, render_markdown
from judge_gate.core import Pair, Policy, evaluate, load_pairs
from scripts.demo import comparison, comparison_markdown, fixture

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.policy = self.directory / "policy.json"
        self.source = self.directory / "pairs.jsonl"
        self.config = {
            "slices": ["lookup"],
            "min_cases": 1,
            "min_reference_failures": 1,
            "max_false_pass_rate": 1,
            "max_abs_differential_bias": 1,
            "bootstrap_samples": 100,
            "seed": 17,
        }

    def invoke(
        self,
        reference: tuple[bool, bool] = (False, False),
        judge: tuple[bool, bool] = (False, False),
        format_name: str = "json",
    ):
        self.policy.write_text(json.dumps(self.config), encoding="utf-8")
        rows = [
            {
                "case_id": "a",
                "slice": "lookup",
                "version": version,
                "reference_pass": reference[i],
                "judge_pass": judge[i],
            }
            for i, version in enumerate(("baseline", "candidate"))
        ]
        self.source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "judge_gate",
                str(self.source),
                "--policy",
                str(self.policy),
                "--format",
                format_name,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_pass_fail_and_inconclusive_exit_codes(self) -> None:
        passed = self.invoke()
        self.assertEqual(passed.returncode, 0)
        self.assertEqual(json.loads(passed.stdout)["status"], "pass")
        failed = self.invoke((False, True), (True, False))
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(json.loads(failed.stdout)["status"], "fail")
        self.config["min_cases"] = 10
        uncertain = self.invoke()
        self.assertEqual(uncertain.returncode, 2)
        self.assertEqual(json.loads(uncertain.stdout)["status"], "inconclusive")

    def test_invalid_input_and_arguments_have_exit_64_and_no_report(self) -> None:
        self.invoke()
        self.source.write_text('{"bad":NaN}\n', encoding="utf-8")
        for arguments in ([str(self.source), "--policy", str(self.policy)], []):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, "-m", "judge_gate", *arguments],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(result.returncode, 64)
                self.assertEqual(result.stdout, "")
                self.assertTrue(result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_json_and_markdown_repeat_exactly(self) -> None:
        for format_name in ("json", "markdown"):
            with self.subTest(format_name=format_name):
                first = self.invoke((False, True), (True, False), format_name)
                second = self.invoke((False, True), (True, False), format_name)
                self.assertEqual(first.stdout, second.stdout)
                self.assertEqual(first.stderr, "")
                if format_name == "markdown":
                    self.assertIn("Decision: **FAIL**", first.stdout)
                    self.assertIn("direction_reversal", first.stdout)

    def test_markdown_escapes_untrusted_slice_names(self) -> None:
        name = "<b>|`test`"
        policy = Policy((name,), 1, 1, 1, 1, 100, 17)
        report = evaluate([Pair("a", name, False, False, False, False)], policy)
        markdown = render_markdown(report)
        self.assertNotIn(name, markdown)
        self.assertIn("&lt;b&gt;&#124;&#96;test&#96;", markdown)
        self.assertTrue(render_json(report).endswith("\n"))

    def test_high_aggregate_agreement_hides_slice_failure(self) -> None:
        self.source.write_text(fixture("hidden-slice"), encoding="utf-8")
        policy = Policy(("format", "lookup"), 60, 15, 0.2, 0.1, 100, 2026)
        report = evaluate(load_pairs(self.source, policy), policy)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["overall"]["status"], "pass")
        self.assertEqual(report["slices"]["lookup"]["status"], "fail")
        versions = report["overall"]["versions"]
        agreement = sum(metric["agreement"] for metric in versions.values()) / 2
        self.assertGreater(agreement, 0.98)
        lookup = report["slices"]["lookup"]
        self.assertEqual(lookup["paired"]["reference_delta"]["estimate"], -0.125)
        self.assertEqual(lookup["paired"]["judge_delta"]["estimate"], 0.125)
        self.assertEqual(lookup["versions"]["candidate"]["false_pass_rate"]["estimate"], 0.5)

    def test_comparators_expose_reversal_support_and_coverage(self) -> None:
        policy = Policy(("format", "lookup"), 60, 15, 0.2, 0.1, 100, 2026)
        reports = {}
        for name in ("clean", "hidden-slice", "low-support", "missing-slice"):
            self.source.write_text(fixture(name), encoding="utf-8")
            reports[name] = evaluate(load_pairs(self.source, policy), policy)
        result = comparison(reports)
        rows = {row["scenario"]: row for row in result["scenarios"]}
        self.assertEqual(result["agreement_only_threshold"], 0.95)
        self.assertTrue(all(row["agreement_only"] == "pass" for row in rows.values()))
        self.assertEqual(rows["clean"]["full_gate"], "pass")
        hidden = rows["hidden-slice"]
        self.assertEqual((hidden["overall_only"], hidden["full_gate"]), ("pass", "fail"))
        self.assertAlmostEqual(hidden["pooled_agreement"], 1340 / 1360)
        self.assertEqual(
            {item["check"] for item in hidden["nonpassing_checks"]},
            {"direction_reversal", "false_pass_rate", "differential_bias"},
        )
        sparse = rows["low-support"]
        self.assertEqual(sparse["pooled_agreement"], 1)
        self.assertEqual(sparse["overall_only"], "inconclusive")
        self.assertEqual(sparse["full_gate"], "inconclusive")
        self.assertIn("failure_support", {item["check"] for item in sparse["nonpassing_checks"]})
        missing = rows["missing-slice"]
        self.assertEqual(missing["n_pairs"], 80)
        self.assertEqual(missing["pooled_agreement"], 1)
        self.assertEqual((missing["overall_only"], missing["full_gate"]), ("pass", "inconclusive"))
        self.assertTrue(
            all(item["scope"] == "slice:lookup" for item in missing["nonpassing_checks"])
        )
        self.assertIn("case_support", {item["check"] for item in missing["nonpassing_checks"]})
        markdown = comparison_markdown(result)
        self.assertIn("not Abridge's current methods", markdown)
        self.assertIn("98.53%", markdown)

    def test_agreement_comparator_threshold_is_inclusive(self) -> None:
        policy = Policy(("lookup",), 1, 1, 1, 1, 100, 17)
        for error_cases, expected in ((1, "pass"), (2, "fail")):
            with self.subTest(error_cases=error_cases):
                pairs = [
                    Pair(str(i), "lookup", False, i < error_cases, False, i < error_cases)
                    for i in range(20)
                ]
                report = evaluate(pairs, policy)
                row = comparison({"threshold": report})["scenarios"][0]
                self.assertEqual(row["pooled_agreement"], 1 - error_cases / 20)
                self.assertEqual(row["agreement_only"], expected)


if __name__ == "__main__":
    unittest.main()
