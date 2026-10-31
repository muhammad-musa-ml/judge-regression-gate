"""Regenerate synthetic fixtures and checked reports; expected gate failures are success here."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"clean": (0, "pass"), "hidden-slice": (1, "fail"), "low-support": (2, "inconclusive")}


def fixture(name: str) -> str:
    rows = []
    for slice_name in ("format", "lookup"):
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


def persist(path: Path, content: str, check: bool) -> None:
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"stale or missing example: {path.relative_to(ROOT)}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def run(check: bool) -> None:
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
