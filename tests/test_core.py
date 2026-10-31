from __future__ import annotations

import json
import math
import random
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from judge_gate.core import InputError, Pair, Policy, evaluate, load_pairs, paired_metrics, wilson

POLICY = Policy(("lookup",), 1, 1, 1.0, 1.0, 100, 17)


def records() -> list[dict]:
    return [
        {
            "case_id": "a",
            "version": version,
            "slice": "lookup",
            "reference_pass": False,
            "judge_pass": False,
        }
        for version in ("baseline", "candidate")
    ]


class InputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "input.jsonl"

    def load(self, rows: list[dict], policy: Policy = POLICY) -> list[Pair]:
        self.path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return load_pairs(self.path, policy)

    def test_complete_pairs_are_sorted(self) -> None:
        rows = [{**row, "case_id": name} for name in ("b", "a") for row in records()]
        self.assertEqual([pair.case_id for pair in self.load(rows)], ["a", "b"])

    def test_rejects_bad_records(self) -> None:
        mutations = [
            lambda row: row.update(extra=1),
            lambda row: row.pop("slice"),
            lambda row: row.update(reference_pass=1),
            lambda row: row.update(judge_pass="false"),
            lambda row: row.update(reference_pass=None),
            lambda row: row.update(version="latest"),
            lambda row: row.update(version=[]),
            lambda row: row.update(slice="undeclared"),
            lambda row: row.update(case_id=" a"),
            lambda row: row.update(case_id="x\n"),
            lambda row: row.update(case_id=""),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                rows = records()
                mutate(rows[0])
                with self.assertRaises(InputError):
                    self.load(rows)

    def test_rejects_missing_duplicate_and_inconsistent_pairs(self) -> None:
        for rows in (records()[:1], records() + records()[:1]):
            with self.subTest(rows=rows), self.assertRaises(InputError):
                self.load(rows)
        rows = records()
        rows[1]["slice"] = "format"
        with self.assertRaisesRegex(InputError, "inconsistent slice"):
            self.load(rows, replace(POLICY, slices=("lookup", "format")))

    def test_rejects_empty_blank_nonobject_and_duplicate_json_keys(self) -> None:
        texts = (
            "",
            "\n",
            "[]\n",
            "{}\n",
            "null\n",
            "{bad\n",
            '{"case_id":"a","case_id":"b"}\n',
            '{"extra":NaN}\n',
            '{"extra":Infinity}\n',
        )
        for text in texts:
            with self.subTest(text=text):
                self.path.write_text(text, encoding="utf-8")
                with self.assertRaises(InputError):
                    load_pairs(self.path, POLICY)

    def test_policy_strictness(self) -> None:
        original = {
            "slices": ["lookup"],
            "min_cases": 1,
            "min_reference_failures": 1,
            "max_false_pass_rate": 0.2,
            "max_abs_differential_bias": 0.1,
            "bootstrap_samples": 100,
            "seed": 17,
        }
        self.path.write_text(json.dumps(original), encoding="utf-8")
        self.assertEqual(Policy.load(self.path).slices, ("lookup",))
        changes = (
            {"extra": 1},
            {"slices": []},
            {"slices": ["lookup", "lookup"]},
            {"slices": "lookup"},
            {"min_cases": True},
            {"min_cases": 0},
            {"min_reference_failures": 0},
            {"bootstrap_samples": 99},
            {"bootstrap_samples": 100_001},
            {"seed": -1},
            {"seed": 2**32},
            {"max_false_pass_rate": True},
            {"max_false_pass_rate": float("nan")},
            {"max_false_pass_rate": 10**1000},
            {"max_abs_differential_bias": float("inf")},
            {"max_abs_differential_bias": -0.1},
        )
        for change in changes:
            with self.subTest(change=change):
                self.path.write_text(json.dumps(original | change), encoding="utf-8")
                with self.assertRaises(InputError):
                    Policy.load(self.path)
        self.path.write_text(json.dumps(original)[:-1] + ',"seed":18}', encoding="utf-8")
        with self.assertRaisesRegex(InputError, "duplicate JSON key"):
            Policy.load(self.path)
        del original["seed"]
        self.path.write_text(json.dumps(original), encoding="utf-8")
        with self.assertRaises(InputError):
            Policy.load(self.path)
        self.path.write_text('{"huge":' + "9" * 5000 + "}", encoding="utf-8")
        with self.assertRaises(InputError):
            Policy.load(self.path)


class StatisticsTests(unittest.TestCase):
    def test_wilson_hand_calculation_and_boundaries(self) -> None:
        lower, upper = wilson(5, 10)
        self.assertAlmostEqual(lower, 0.236593090512564, places=12)
        self.assertAlmostEqual(upper, 0.763406909487436, places=12)
        self.assertEqual(wilson(0, 20)[0], 0.0)
        self.assertAlmostEqual(wilson(0, 20)[1], 0.161125158052819, places=12)
        self.assertAlmostEqual(wilson(20, 20)[0], 1 - wilson(0, 20)[1])
        self.assertEqual(wilson(20, 20)[1], 1.0)
        self.assertIsNone(wilson(0, 0))

    def test_wilson_endpoints_are_exact_without_floating_cancellation(self) -> None:
        for trials in (1, 20, 300, 1000):
            with self.subTest(trials=trials):
                self.assertEqual(wilson(0, trials)[0], 0.0)
                self.assertEqual(wilson(trials, trials)[1], 1.0)

    def test_confusion_and_paired_hand_calculation(self) -> None:
        pairs = [
            Pair("a", "lookup", True, True, True, True),
            Pair("b", "lookup", False, True, True, False),
            Pair("c", "lookup", False, False, False, True),
            Pair("d", "lookup", True, False, False, False),
        ]
        report = evaluate(pairs, POLICY)["overall"]
        self.assertEqual(
            report["versions"]["baseline"]["confusion"],
            {"true_pass": 1, "false_pass": 1, "true_fail": 1, "false_fail": 1},
        )
        for version in ("baseline", "candidate"):
            metrics = report["versions"][version]
            self.assertEqual(metrics["agreement"], 0.5)
            self.assertEqual(metrics["false_pass_rate"]["estimate"], 0.5)
        self.assertEqual(report["paired"]["reference_delta"]["estimate"], 0)
        self.assertEqual(report["paired"]["judge_delta"]["estimate"], 0)
        self.assertEqual(report["paired"]["differential_bias"]["estimate"], 0)

    def test_bootstrap_preserves_all_four_labels_and_version_pairing(self) -> None:
        pairs = [
            Pair(str(i), "lookup", i % 2 == 0, i % 2 == 0, i % 3 == 0, i % 3 == 0)
            for i in range(12)
        ]
        report = paired_metrics(pairs, 200, "paired")
        self.assertEqual(report["reference_delta"], report["judge_delta"])
        self.assertEqual(report["differential_bias"]["interval"], [0, 0])
        self.assertTrue(report["differential_bias"]["degenerate"])
        same_versions = [
            Pair(str(i), "lookup", i % 2 == 0, i % 3 == 0, i % 2 == 0, i % 3 == 0)
            for i in range(12)
        ]
        for metric in paired_metrics(same_versions, 100, "versions").values():
            self.assertEqual(metric["interval"], [0, 0])

    def test_small_bootstrap_matches_independent_draw_calculation(self) -> None:
        pairs = [
            Pair("a", "lookup", False, False, True, False),
            Pair("b", "lookup", False, True, False, True),
        ]
        rng = random.Random("known")
        reference_draws = sorted(
            sum(rng.randrange(2) == 0 for _ in range(2)) / 2 for _ in range(100)
        )
        self.assertEqual(reference_draws[0], 0)
        self.assertEqual(reference_draws[-1], 1)
        metric = paired_metrics(pairs, 100, "known")["reference_delta"]
        self.assertEqual(metric["estimate"], 0.5)
        self.assertEqual(metric["interval"], [0, 1])

    def test_record_and_policy_slice_permutation_invariance(self) -> None:
        pairs = [
            Pair(str(i), "lookup" if i % 2 else "format", False, i % 3 == 0, i % 4 == 0, False)
            for i in range(20)
        ]
        policy = replace(POLICY, slices=("lookup", "format"))
        expected = evaluate(pairs, policy)
        random.Random(3).shuffle(pairs)
        self.assertEqual(evaluate(pairs, policy), expected)
        other = evaluate(pairs, replace(policy, slices=("format", "lookup")))
        self.assertEqual(other["slices"], expected["slices"])


class GateTests(unittest.TestCase):
    def test_zero_false_pass_tolerance_distinguishes_zero_and_positive_counts(self) -> None:
        policy = replace(POLICY, max_false_pass_rate=0)
        for error_cases, expected in ((0, "inconclusive"), (1, "fail")):
            with self.subTest(error_cases=error_cases):
                pairs = [
                    Pair(str(i), "lookup", False, i < error_cases, False, i < error_cases)
                    for i in range(300)
                ]
                report = evaluate(pairs, policy)
                self.assertEqual(report["status"], expected)
                self.assertTrue(
                    all(
                        reason["check"] == "false_pass_rate" and reason["status"] == expected
                        for reason in report["overall"]["reasons"]
                    )
                )

    def test_zero_failures_and_missing_declared_slice_are_inconclusive(self) -> None:
        pairs = [Pair("a", "lookup", True, True, True, True)]
        report = evaluate(pairs, replace(POLICY, slices=("lookup", "missing")))
        self.assertEqual(report["status"], "inconclusive")
        for version in report["overall"]["versions"].values():
            self.assertIsNone(version["false_pass_rate"]["estimate"])
            self.assertIsNone(version["false_pass_rate"]["interval"])
        missing = report["slices"]["missing"]
        self.assertEqual(missing["n_cases"], 0)
        self.assertEqual(missing["status"], "inconclusive")
        self.assertIsNone(missing["paired"]["reference_delta"]["interval"])

    def test_sparse_failures_cannot_pass_even_with_perfect_agreement(self) -> None:
        pairs = [Pair(str(i), "lookup", False, False, False, False) for i in range(2)]
        report = evaluate(pairs, replace(POLICY, min_reference_failures=3))
        self.assertEqual(report["status"], "inconclusive")

    def test_reversal_fails_even_with_sparse_support(self) -> None:
        report = evaluate([Pair("a", "lookup", False, True, True, False)], POLICY)
        self.assertEqual(report["status"], "fail")
        self.assertIn("direction_reversal", [r["check"] for r in report["overall"]["reasons"]])

    def test_interval_inside_crossing_and_outside_policy(self) -> None:
        pairs = [Pair(str(i), "lookup", False, i < 5, False, i < 5) for i in range(10)]
        for limit, expected in ((0.8, "pass"), (0.5, "inconclusive"), (0.2, "fail")):
            with self.subTest(limit=limit):
                self.assertEqual(
                    evaluate(pairs, replace(POLICY, max_false_pass_rate=limit))["status"], expected
                )

    def test_differential_bias_outside_and_crossing_policy(self) -> None:
        pairs = [Pair(str(i), "lookup", False, False, False, i < 10) for i in range(20)]
        self.assertEqual(
            evaluate(pairs, replace(POLICY, max_abs_differential_bias=0.1))["status"], "fail"
        )
        self.assertEqual(
            evaluate(pairs, replace(POLICY, max_abs_differential_bias=0.5))["status"],
            "inconclusive",
        )

    def test_all_numeric_outputs_are_finite_or_unknown(self) -> None:
        report = evaluate([Pair("a", "lookup", False, False, True, True)], POLICY)

        def walk(value: object) -> None:
            if isinstance(value, dict):
                for child in value.values():
                    walk(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    walk(child)
            elif isinstance(value, float):
                self.assertTrue(math.isfinite(value))

        walk(report)


if __name__ == "__main__":
    unittest.main()
