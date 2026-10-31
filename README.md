# judge-regression-gate

An offline regression harness for a binary LLM judge that rates two model versions
on the same cases. It compares judge ratings with reference labels, checks declared
slices, and returns **PASS**, **FAIL**, or **INCONCLUSIVE** with reproducible JSON
and Markdown evidence. Python 3.11+, standard library runtime, no model calls.

The motivating question comes from [Abridge's public article on validating LLM
judges](https://tech.abridge.com/blog/continual-monitoring-validating-and-using-llm-judges):
does agreement actually support the intended use, particularly comparing model
versions? Aggregate agreement can conceal missed failures and differing bias
between versions. This project explores that question with original, synthetic,
nonmedical label fixtures. It does not evaluate a company's systems or imply
affiliation, endorsement, clinical validity, or deployment readiness.

## Run the demo

From the repository root:

```sh
python scripts/demo.py
python -m unittest discover -v
python scripts/demo.py --check
```

The first command creates fixtures and reports in `examples/`, runs the real CLI,
and verifies all three expected outcomes. Its own exit code is zero when the demo
behaves as expected, including the intentionally failing gate.

Measured output with the checked policy, 2,000 bootstrap draws, and seed 2026:

```text
clean: PASS (exit 0)
hidden-slice: FAIL (exit 1); aggregate agreement 98.53%, aggregate gate PASS, lookup gate FAIL
low-support: INCONCLUSIVE (exit 2)
```

The hidden-slice case has 680 pairs. Within its 80-case `lookup` slice, the reference
pass rate decreases by 0.125 while the judge pass rate increases by 0.125. The
candidate's false-pass rate is 20/40 = 0.5000, with Wilson interval
[0.3520, 0.6480]. Its overall candidate false-pass rate is only 20/340 = 0.0588.
See the complete [failure report](examples/reports/hidden-slice.md),
[clean report](examples/reports/clean.md), and
[low-support report](examples/reports/low-support.md).

Run a single evaluation:

```sh
python -m judge_gate examples/hidden-slice.jsonl --policy examples/policy.json --format markdown
python -m judge_gate examples/clean.jsonl --policy examples/policy.json > report.json
```

Optional installation adds the equivalent `judge-gate` command:

```sh
python -m pip install .
judge-gate examples/clean.jsonl --policy examples/policy.json
```

## Input contract

Each UTF-8 JSONL row contains exactly these five keys:

```json
{"case_id":"lookup-001","version":"baseline","slice":"lookup","reference_pass":false,"judge_pass":true}
{"case_id":"lookup-001","version":"candidate","slice":"lookup","reference_pass":true,"judge_pass":true}
```

`true` means the output satisfies the evaluation criterion; `false` means it does
not. Reference labels are supplied observations, not inferred ground truth. In
the demo, both reference and judge labels are assigned by the fixture generator;
there are no model outputs, human annotations, prompts, or domain assessments.
`format` and `lookup` are neutral scenario names, not implemented task evaluators.

Each globally unique case ID needs exactly one row per version, with the same
slice. Unknown keys, duplicate JSON keys, missing/duplicate version pairs,
undeclared slices, blank lines, nonfinite numbers, numeric/string booleans, and
empty or padded identifiers are errors. A missing declared slice is valid input
but produces an inconclusive gate.

The strict [policy](examples/policy.json) prespecifies every required slice,
minimum pair and reference-failure counts, false-pass limit, absolute differential
bias tolerance, bootstrap draw count, and seed. Counts must be positive integers;
draws must be 100–100,000; seed must be an integer in [0, 2³²−1]; limits must be
finite numbers in [0, 1]. Booleans are not numeric settings. Demo thresholds are
illustrative, not recommended operational defaults.

## Metrics and decisions

All deltas use candidate minus baseline, in pass-rate units:

| Metric | Calculation |
|---|---|
| Confusion matrix | True pass, false pass, true fail, false fail; positive means pass |
| Agreement | Matching judge/reference labels divided by cases, per version |
| False-pass rate | False passes divided by reference failures, per version |
| Reference delta | Mean candidate reference label minus mean baseline reference label |
| Judge delta | Mean candidate judge label minus mean baseline judge label |
| Differential bias | Judge delta minus reference delta |

False-pass intervals use the two-sided 95% [Wilson score
method](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).
No reference failures means an unknown estimate and interval, never zero.

Delta intervals use a paired case percentile bootstrap: each draw samples `n`
whole cases with replacement, retaining both versions and both labels. The
2.5th and 97.5th percentiles use linear interpolation at `(draws - 1) * p`.
The [paired resampling and percentile
definitions](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
describe the method; SciPy is not a dependency. Overall cases are pooled, and each
slice is resampled separately. Cases are sorted by ID before resampling, with a
separate deterministic seed stream per scope. JSON records unrounded numbers,
policy, intervals, degenerate-distribution flags, and reasons; Markdown rounds to
four decimals. Both formats use UTF-8.

The overall scope **and every declared slice** must satisfy the policy:

1. Insufficient pairs or reference failures in either version is inconclusive.
2. A false-pass Wilson interval wholly above the limit fails; one crossing the
   limit is inconclusive; an upper bound at or below the limit satisfies it.
3. A differential-bias bootstrap interval wholly outside `[-tolerance, tolerance]`
   fails; overlap with an outside region is inconclusive; containment satisfies it.
4. Opposite nonzero observed reference/judge delta signs fail immediately. This
   is a conservative policy check, not a significance test. A zero delta is a tie.

FAIL takes precedence over INCONCLUSIVE; PASS requires no failing or inconclusive
checks. Agreement is descriptive. False-fail counts are reported but have no
separate policy threshold; common bias can cancel in a model comparison.

| Exit code | Meaning |
|---:|---|
| 0 | PASS: all selected judge-alignment checks satisfy this sample and policy |
| 1 | FAIL: at least one check fails |
| 2 | INCONCLUSIVE: support or interval precision is insufficient |
| 64 | Invalid input, policy, arguments, encoding, or unreadable file; no report |

A PASS does not approve the candidate model: the judge can track a deterioration
accurately and pass these checks. This is judge validation for a bounded
comparison use, not a pass@k estimator or a model release quality gate.

## Limits and verification

- Labels can be wrong; disagreements require review. No label-reliability model
  or automatic adjudication is included.
- Cases are assumed independent and the observed mix is unweighted. Enriched,
  clustered, reused, or adaptively selected samples need a different analysis;
  this tool does not correct sampling or selection bias.
- Intervals are marginal and unadjusted across metrics/slices. They do not give
  a simultaneous 95% guarantee. Choose slices and policy before inspecting data.
- Percentile bootstrap intervals can under-cover, especially with sparse or
  discrete data. Constant contributions give zero-width intervals, marked
  `degenerate` in JSON; resampling cannot discover unseen judge errors. The clean
  fixture deliberately has this limitation. Minimum support does not establish
  representativeness or sufficient statistical power.
- This is a small offline prototype: two fixed versions, one disjoint slice per
  case, binary labels, in-memory input, and fixed 95% intervals. It does not run
  judges, optimize prompts, monitor production, or validate clinical systems.

The unittest suite covers hand calculations, boundaries, malformed inputs,
pairing, input-order invariance, missing slices, sparse support, reversed rankings,
hidden slice failures, deterministic reports, and CLI exit codes. CI tests Python
3.11 and 3.13, checks formatting/lint, installs the CLI, and verifies that generated
examples match the saved evidence.

```sh
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
```

MIT licensed. See [LICENSE](LICENSE).
