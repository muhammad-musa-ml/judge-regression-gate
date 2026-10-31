# Illustrative comparator evidence

Deliberately reduced illustrative comparators, not Abridge's current methods. Agreement-only ignores uncertainty and support; overall-only retains the computed overall checks but omits every slice check.

Agreement-only passes at pooled agreement >= 0.95. Pooled agreement counts matching labels across both versions. The other decisions come directly from the same scenario report's overall and full statuses.

| Synthetic scenario | Pairs | Pooled agreement | Agreement-only | Overall-only | Full gate |
|---|---:|---:|---|---|---|
| [clean](clean.md) | 160 | 100.00% | PASS | PASS | PASS |
| [hidden-slice](hidden-slice.md) | 680 | 98.53% | PASS | PASS | FAIL |
| [low-support](low-support.md) | 24 | 100.00% | PASS | INCONCLUSIVE | INCONCLUSIVE |
| [missing-slice](missing-slice.md) | 80 | 100.00% | PASS | PASS | INCONCLUSIVE |

## Why decisions differ

- clean: all full-gate checks satisfy the policy.
- hidden-slice: slice:lookup/differential_bias, slice:lookup/direction_reversal, slice:lookup/false_pass_rate.
- low-support: overall/case_support, overall/failure_support, overall/false_pass_rate, slice:format/case_support, slice:format/failure_support, slice:format/false_pass_rate, slice:lookup/case_support, slice:lookup/failure_support, slice:lookup/false_pass_rate.
- missing-slice: slice:lookup/case_support, slice:lookup/failure_support.

These are constructed label fixtures, not measurements of a deployed judge or an improvement in model quality. The evidence shows detection of the specified synthetic failures and withholding a pass for insufficient support or coverage. All statistical and sampling limitations in the scenario reports still apply.
