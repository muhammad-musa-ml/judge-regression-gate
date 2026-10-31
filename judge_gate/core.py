"""Strict inputs, descriptive uncertainty intervals, and an explicit policy gate."""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

VERSIONS = ("baseline", "candidate")
FIELDS = {"case_id", "version", "slice", "reference_pass", "judge_pass"}
Z95 = 1.959963984540054


class InputError(ValueError):
    """An input cannot be evaluated under this schema."""


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise InputError(f"nonfinite JSON number: {value}")


def _json(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON: {exc.msg}") from exc
    except InputError:
        raise
    except ValueError as exc:
        raise InputError(f"invalid JSON: {exc}") from exc


def _name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise InputError(f"{field} must be a nonempty string without surrounding whitespace")
    if any(ord(char) < 32 for char in value):
        raise InputError(f"{field} must not contain control characters")
    return value


@dataclass(frozen=True)
class Policy:
    slices: tuple[str, ...]
    min_cases: int
    min_reference_failures: int
    max_false_pass_rate: float
    max_abs_differential_bias: float
    bootstrap_samples: int
    seed: int

    def __post_init__(self) -> None:
        if not isinstance(self.slices, tuple) or not self.slices:
            raise InputError("slices must be a nonempty tuple of prespecified names")
        for name in self.slices:
            _name(name, "slice")
        if len(set(self.slices)) != len(self.slices):
            raise InputError("duplicate policy slice")
        for field in ("min_cases", "min_reference_failures", "bootstrap_samples", "seed"):
            if type(getattr(self, field)) is not int:
                raise InputError(f"{field} must be an integer")
        if self.min_cases < 1 or self.min_reference_failures < 1:
            raise InputError("minimum support counts must be positive")
        if not 100 <= self.bootstrap_samples <= 100_000:
            raise InputError("bootstrap_samples must be between 100 and 100000")
        if not 0 <= self.seed < 2**32:
            raise InputError("seed must be between 0 and 2**32 - 1")
        for field in ("max_false_pass_rate", "max_abs_differential_bias"):
            value = getattr(self, field)
            if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
                raise InputError(f"{field} must be a finite number between 0 and 1")

    @classmethod
    def load(cls, path: Path) -> Policy:
        data = _json(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != set(cls.__dataclass_fields__):
            raise InputError("policy must contain exactly the documented keys")
        if not isinstance(data["slices"], list):
            raise InputError("policy slices must be a JSON array")
        data["slices"] = tuple(data["slices"])
        return cls(**data)


@dataclass(frozen=True)
class Pair:
    case_id: str
    slice: str
    baseline_reference: bool
    baseline_judge: bool
    candidate_reference: bool
    candidate_judge: bool


def load_pairs(path: Path, policy: Policy) -> list[Pair]:
    cases: dict[str, dict[str, dict[str, Any]]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            row = _json(line)
            if not isinstance(row, dict) or set(row) != FIELDS:
                raise InputError("record must contain exactly the five documented keys")
            case_id = _name(row["case_id"], "case_id")
            slice_name = _name(row["slice"], "slice")
            if slice_name not in policy.slices:
                raise InputError(f"undeclared slice: {slice_name}")
            version = row["version"]
            if not isinstance(version, str) or version not in VERSIONS:
                raise InputError("version must be baseline or candidate")
            if any(type(row[field]) is not bool for field in ("reference_pass", "judge_pass")):
                raise InputError("reference_pass and judge_pass must be JSON booleans")
            group = cases.setdefault(case_id, {})
            if version in group:
                raise InputError(f"duplicate case/version: {case_id}/{version}")
            group[version] = row
        except InputError as exc:
            raise InputError(f"line {line_number}: {exc}") from exc
    if not cases:
        raise InputError("input must contain at least one complete pair")
    result = []
    for case_id, group in sorted(cases.items()):
        if set(group) != set(VERSIONS):
            raise InputError(f"incomplete version pair: {case_id}")
        base, candidate = (group[version] for version in VERSIONS)
        if base["slice"] != candidate["slice"]:
            raise InputError(f"inconsistent slice within pair: {case_id}")
        result.append(
            Pair(
                case_id,
                base["slice"],
                base["reference_pass"],
                base["judge_pass"],
                candidate["reference_pass"],
                candidate["judge_pass"],
            )
        )
    return result


def wilson(successes: int, trials: int) -> list[float] | None:
    """Two-sided 95% Wilson score interval; absent support is unknown."""
    if trials == 0:
        return None
    p = successes / trials
    z2 = Z95**2
    center = (p + z2 / (2 * trials)) / (1 + z2 / trials)
    radius = Z95 * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials**2)) / (1 + z2 / trials)
    # Exact analytical endpoints avoid cancellation at zero-tolerance policy boundaries.
    lower = 0.0 if successes == 0 else max(0.0, center - radius)
    upper = 1.0 if successes == trials else min(1.0, center + radius)
    return [lower, upper]


def _percentile(values: list[float], probability: float) -> float:
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def paired_metrics(pairs: list[Pair], samples: int, seed: str) -> dict[str, Any]:
    """Resample whole cases, keeping both versions and both labels together."""
    names = ("reference_delta", "judge_delta", "differential_bias")
    if not pairs:
        return {name: {"estimate": None, "interval": None, "degenerate": None} for name in names}
    contributions = []
    for pair in pairs:
        reference = int(pair.candidate_reference) - int(pair.baseline_reference)
        judge = int(pair.candidate_judge) - int(pair.baseline_judge)
        contributions.append((reference, judge, judge - reference))
    n = len(pairs)
    estimates = [sum(row[column] for row in contributions) / n for column in range(3)]
    draws: list[list[float]] = [[], [], []]
    rng = random.Random(seed)
    for _ in range(samples):
        totals = [0, 0, 0]
        for _ in range(n):
            row = contributions[rng.randrange(n)]
            for column in range(3):
                totals[column] += row[column]
        for column in range(3):
            draws[column].append(totals[column] / n)
    result = {}
    for column, name in enumerate(names):
        ordered = sorted(draws[column])
        result[name] = {
            "estimate": estimates[column],
            "interval": [_percentile(ordered, 0.025), _percentile(ordered, 0.975)],
            "degenerate": len({row[column] for row in contributions}) == 1,
        }
    return result


def version_metrics(pairs: list[Pair], version: str) -> dict[str, Any]:
    counts = dict.fromkeys(("true_pass", "false_pass", "true_fail", "false_fail"), 0)
    for pair in pairs:
        reference = getattr(pair, f"{version}_reference")
        judge = getattr(pair, f"{version}_judge")
        key = (
            ("true_pass" if reference else "false_pass")
            if judge
            else ("false_fail" if reference else "true_fail")
        )
        counts[key] += 1
    n = len(pairs)
    failures = counts["false_pass"] + counts["true_fail"]
    return {
        "confusion": counts,
        "agreement": (counts["true_pass"] + counts["true_fail"]) / n if n else None,
        "reference_pass_rate": (counts["true_pass"] + counts["false_fail"]) / n if n else None,
        "judge_pass_rate": (counts["true_pass"] + counts["false_pass"]) / n if n else None,
        "false_pass_rate": {
            "estimate": counts["false_pass"] / failures if failures else None,
            "interval": wilson(counts["false_pass"], failures),
            "reference_failures": failures,
        },
    }


def _scope(pairs: list[Pair], policy: Policy, seed: str) -> dict[str, Any]:
    versions = {version: version_metrics(pairs, version) for version in VERSIONS}
    paired = paired_metrics(pairs, policy.bootstrap_samples, seed)
    reasons: list[dict[str, str]] = []

    def add(status: str, check: str, message: str) -> None:
        reasons.append({"status": status, "check": check, "message": message})

    if len(pairs) < policy.min_cases:
        add("inconclusive", "case_support", f"{len(pairs)} pairs < {policy.min_cases} required")
    for version, metrics in versions.items():
        rate = metrics["false_pass_rate"]
        failures = rate["reference_failures"]
        if failures < policy.min_reference_failures:
            add(
                "inconclusive",
                "failure_support",
                f"{version}: {failures} reference failures "
                f"< {policy.min_reference_failures} required",
            )
        interval = rate["interval"]
        if interval is not None:
            if interval[0] > policy.max_false_pass_rate:
                add("fail", "false_pass_rate", f"{version}: Wilson lower bound exceeds limit")
            elif interval[1] > policy.max_false_pass_rate:
                add("inconclusive", "false_pass_rate", f"{version}: Wilson interval crosses limit")
    reference = paired["reference_delta"]["estimate"]
    judge = paired["judge_delta"]["estimate"]
    if reference is not None and reference * judge < 0:
        add(
            "fail", "direction_reversal", "observed reference and judge deltas have opposite signs"
        )
    interval = paired["differential_bias"]["interval"]
    tolerance = policy.max_abs_differential_bias
    if interval is not None:
        if interval[0] > tolerance or interval[1] < -tolerance:
            add("fail", "differential_bias", "bootstrap interval lies outside bias tolerance")
        elif interval[0] < -tolerance or interval[1] > tolerance:
            add("inconclusive", "differential_bias", "bootstrap interval crosses bias tolerance")
    status = (
        "fail"
        if any(reason["status"] == "fail" for reason in reasons)
        else ("inconclusive" if reasons else "pass")
    )
    return {
        "n_cases": len(pairs),
        "versions": versions,
        "paired": paired,
        "status": status,
        "reasons": reasons,
    }


def evaluate(pairs: list[Pair], policy: Policy) -> dict[str, Any]:
    """Evaluate loader-validated pairs. Input ordering never affects resampling."""
    ordered = sorted(pairs, key=lambda pair: pair.case_id)
    overall = _scope(ordered, policy, f"{policy.seed}:overall")
    slices = {
        name: _scope(
            [pair for pair in ordered if pair.slice == name], policy, f"{policy.seed}:slice:{name}"
        )
        for name in sorted(policy.slices)
    }
    statuses = [scope["status"] for scope in (overall, *slices.values())]
    status = (
        "fail"
        if "fail" in statuses
        else ("inconclusive" if "inconclusive" in statuses else "pass")
    )
    return {
        "schema_version": 1,
        "status": status,
        "policy": asdict(policy),
        "overall": overall,
        "slices": slices,
    }
