"""Regenerate synthetic fixtures and checked reports; expected gate failures are success here."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "clean": (0, "pass"),
    "hidden-slice": (1, "fail"),
    "low-support": (2, "inconclusive"),
    "missing-slice": (2, "inconclusive"),
}
AGREEMENT_THRESHOLD = 0.95


def fixture(name: str) -> str:
    rows = []
    for slice_name in ("format", "lookup"):
        if name == "missing-slice" and slice_name == "lookup":
            continue
        if name == "hidden-slice" and slice_name == "format":
            size, base_cut, candidate_cut, judge_cut = 600, 250, 300, 300
        elif name == "hidden-slice":
            size, base_cut, candidate_cut, judge_cut = 80, 50, 40, 60
        elif name == "low-support":
            size, base_cut, candidate_cut, judge_cut = 12, 8, 9, 9
        else:
            size, base_cut, candidate_cut, judge_cut = 80, 50, 60, 60
        for i in range(size):
            for version in ("baseline", "candidate"):
                reference = i < (base_cut if version == "baseline" else candidate_cut)
                judge = reference if version == "baseline" else i < judge_cut
                rows.append(
                    json.dumps(
                        {
                            "case_id": f"{slice_name}-{i:04d}",
                            "version": version,
                            "slice": slice_name,
                            "reference_pass": reference,
                            "judge_pass": judge,
                        },
                        sort_keys=True,
                    )
                )
    return "\n".join(rows) + "\n"


def comparison(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compare reduced checks with the full gate, using computed reports only."""
    scenarios = []
    for name, report in reports.items():
        overall = report["overall"]
        versions = overall["versions"]
        total_ratings = overall["n_cases"] * len(versions)
        matches = sum(
            metric["confusion"]["true_pass"] + metric["confusion"]["true_fail"]
            for metric in versions.values()
        )
        agreement = matches / total_ratings
        scopes = {"overall": overall} | {
            f"slice:{slice_name}": scope for slice_name, scope in report["slices"].items()
        }
        scenarios.append(
            {
                "scenario": name,
                "n_pairs": overall["n_cases"],
                "pooled_agreement": agreement,
                "agreement_only": "pass" if agreement >= AGREEMENT_THRESHOLD else "fail",
                "overall_only": overall["status"],
                "full_gate": report["status"],
                "nonpassing_checks": [
                    {"scope": scope_name, "check": reason["check"], "status": reason["status"]}
                    for scope_name, scope in scopes.items()
                    for reason in scope["reasons"]
                ],
                "source_report": f"{name}.json",
            }
        )
    return {
        "schema_version": 1,
        "agreement_only_threshold": AGREEMENT_THRESHOLD,
        "comparator_scope": (
            "Deliberately reduced illustrative comparators, not Abridge's current methods. "
            "Agreement-only ignores uncertainty and support; overall-only retains the computed "
            "overall checks but omits every slice check."
        ),
        "scenarios": scenarios,
    }


def comparison_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Illustrative comparator evidence",
        "",
        result["comparator_scope"],
        "",
        f"Agreement-only passes at pooled agreement >= {result['agreement_only_threshold']}. "
        "Pooled agreement counts matching labels across both versions. The other decisions "
        "come directly from the same scenario report's overall and full statuses.",
        "",
        "| Synthetic scenario | Pairs | Pooled agreement | Agreement-only | "
        "Overall-only | Full gate |",
        "|---|---:|---:|---|---|---|",
    ]
    for row in result["scenarios"]:
        lines.append(
            f"| [{row['scenario']}]({row['scenario']}.md) | {row['n_pairs']} | "
            f"{row['pooled_agreement']:.2%} | {row['agreement_only'].upper()} | "
            f"{row['overall_only'].upper()} | {row['full_gate'].upper()} |"
        )
    lines.extend(
        [
            "",
            "## Why decisions differ",
            "",
        ]
    )
    for row in result["scenarios"]:
        checks = sorted({f"{item['scope']}/{item['check']}" for item in row["nonpassing_checks"]})
        detail = ", ".join(checks) if checks else "all full-gate checks satisfy the policy"
        lines.append(f"- {row['scenario']}: {detail}.")
    lines.extend(
        [
            "",
            "These are constructed label fixtures, not measurements of a deployed judge or "
            "an improvement in model quality. The evidence shows detection of the specified "
            "synthetic failures and withholding a pass for insufficient support or coverage. "
            "All statistical and sampling limitations in the scenario reports still apply.",
            "",
        ]
    )
    return "\n".join(lines)


def persist(path: Path, content: str, check: bool) -> None:
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"stale or missing example: {path.relative_to(ROOT)}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def run(check: bool) -> None:
    reports = {}
    for name, (code, status) in EXPECTED.items():
        source = ROOT / "examples" / f"{name}.jsonl"
        persist(source, fixture(name), check)
        for format_name, extension in (("json", "json"), ("markdown", "md")):
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "judge_gate",
                    str(source),
                    "--policy",
                    "examples/policy.json",
                    "--format",
                    format_name,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode != code:
                raise RuntimeError(
                    f"{name}: exit {result.returncode}, expected {code}: {result.stderr}"
                )
            if format_name == "json":
                report = json.loads(result.stdout)
                reports[name] = report
                if report["status"] != status:
                    raise RuntimeError(f"{name}: unexpected status")
                if name == "hidden-slice":
                    if report["overall"]["status"] != "pass":
                        raise RuntimeError("hidden-slice: aggregate was intended to pass")
                    if report["slices"]["lookup"]["status"] != "fail":
                        raise RuntimeError("hidden-slice: lookup was intended to fail")
                    versions = report["overall"]["versions"]
                    agreement = sum(metric["agreement"] for metric in versions.values()) / 2
                    print(
                        f"{name}: {status.upper()} (exit {code}); aggregate agreement "
                        f"{agreement:.2%}, aggregate gate PASS, lookup gate FAIL"
                    )
                else:
                    print(f"{name}: {status.upper()} (exit {code})")
            persist(ROOT / "examples" / "reports" / f"{name}.{extension}", result.stdout, check)
    result = comparison(reports)
    directory = ROOT / "examples" / "reports"
    persist(
        directory / "comparison.json",
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        check,
    )
    persist(directory / "comparison.md", comparison_markdown(result), check)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="verify committed examples without edits"
    )
    args = parser.parse_args()
    try:
        run(args.check)
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f"demo: {exc}\n")


if __name__ == "__main__":
    main()
