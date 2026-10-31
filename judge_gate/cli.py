"""Machine-readable and reviewable reports with distinct process exit codes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from judge_gate.core import InputError, Policy, evaluate, load_pairs

EXIT_CODES = {"pass": 0, "fail": 1, "inconclusive": 2}


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _number(value: float | None) -> str:
    return "unknown" if value is None else f"{value:.4f}"


def _interval(metric: dict[str, Any]) -> str:
    bounds = metric["interval"]
    interval = "unknown" if bounds is None else f"[{bounds[0]:.4f}, {bounds[1]:.4f}]"
    return f"{_number(metric['estimate'])} {interval}"


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("|", "&#124;")
        .replace("`", "&#96;")
    )


def render_markdown(report: dict[str, Any]) -> str:
    policy = report["policy"]
    scopes = [
        ("overall", report["overall"]),
        *((f"slice:{name}", scope) for name, scope in report["slices"].items()),
    ]
    lines = [
        "# Judge regression gate",
        "",
        f"Decision: **{report['status'].upper()}**",
        "",
        "PASS concerns judge alignment on this sample under this policy; it is not a model "
        "release or deployment approval.",
        "",
        f"Limits: false-pass rate <= {policy['max_false_pass_rate']}; absolute differential "
        f"bias <= {policy['max_abs_differential_bias']}. Minimum per scope: "
        f"{policy['min_cases']} pairs and {policy['min_reference_failures']} reference failures "
        "per version.",
        "",
        "Positive means pass. False-pass rate = false passes / reference failures. "
        "Intervals are marginal 95% Wilson score intervals.",
        "",
        "| Scope | Pairs | Version | Agreement | False passes / failures | Rate [interval] |",
        "|---|---:|---|---:|---:|---|",
    ]
    for name, scope in scopes:
        for version, metrics in scope["versions"].items():
            rate = metrics["false_pass_rate"]
            lines.append(
                f"| {_escape(name)} | {scope['n_cases']} | {version} | "
                f"{_number(metrics['agreement'])} | {metrics['confusion']['false_pass']} / "
                f"{rate['reference_failures']} | {_interval(rate)} |"
            )
    lines.extend(
        [
            "",
            "Deltas are candidate minus baseline in pass-rate units. Bias is judge delta "
            "minus reference delta. Intervals use a paired case percentile bootstrap "
            f"({policy['bootstrap_samples']} draws; seed {policy['seed']}).",
            "",
            "| Scope | Reference delta [interval] | Judge delta [interval] | "
            "Differential bias [interval] | Status |",
            "|---|---|---|---|---|",
        ]
    )
    for name, scope in scopes:
        metrics = scope["paired"]
        lines.append(
            f"| {_escape(name)} | {_interval(metrics['reference_delta'])} | "
            f"{_interval(metrics['judge_delta'])} | "
            f"{_interval(metrics['differential_bias'])} | {scope['status']} |"
        )
    reasons = [(name, reason) for name, scope in scopes for reason in scope["reasons"]]
    lines.extend(["", "## Gate reasons", ""])
    if reasons:
        lines.extend(
            f"- {_escape(name)} / {reason['check']}: "
            f"{reason['status'].upper()} — {_escape(reason['message'])}."
            for name, reason in reasons
        )
    else:
        lines.append("All declared scopes satisfy the policy.")
    lines.extend(
        [
            "",
            "Intervals describe the observed sample; they do not correct for selection "
            "bias, dependent cases, label error, or multiple slices. A degenerate bootstrap "
            "cannot reveal unseen errors. An observed sign reversal fails by policy, "
            "without a statistical significance claim.",
            "",
        ]
    )
    return "\n".join(lines)


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(64, f"{self.prog}: error: {message}\n")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    parser = Parser(description="Validate paired binary judge ratings against reference labels.")
    parser.add_argument("input", type=Path, help="strict paired JSONL records")
    parser.add_argument("--policy", type=Path, required=True, help="strict policy JSON")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        policy = Policy.load(args.policy)
        report = evaluate(load_pairs(args.input, policy), policy)
    except (InputError, OSError, UnicodeError) as exc:
        print(f"judge-gate: {exc}", file=sys.stderr)
        return 64
    sys.stdout.write(render_json(report) if args.format == "json" else render_markdown(report))
    return EXIT_CODES[report["status"]]
