# Judge regression gate

Decision: **FAIL**

PASS concerns judge alignment on this sample under this policy; it is not a model release or deployment approval.

Limits: false-pass rate <= 0.2; absolute differential bias <= 0.1. Minimum per scope: 60 pairs and 15 reference failures per version.

Positive means pass. False-pass rate = false passes / reference failures. Intervals are marginal 95% Wilson score intervals.

| Scope | Pairs | Version | Agreement | False passes / failures | Rate [interval] |
|---|---:|---|---:|---:|---|
| overall | 680 | baseline | 1.0000 | 0 / 380 | 0.0000 [0.0000, 0.0100] |
| overall | 680 | candidate | 0.9706 | 20 / 340 | 0.0588 [0.0384, 0.0891] |
| slice:format | 600 | baseline | 1.0000 | 0 / 350 | 0.0000 [0.0000, 0.0109] |
| slice:format | 600 | candidate | 1.0000 | 0 / 300 | 0.0000 [0.0000, 0.0126] |
| slice:lookup | 80 | baseline | 1.0000 | 0 / 30 | 0.0000 [0.0000, 0.1135] |
| slice:lookup | 80 | candidate | 0.7500 | 20 / 40 | 0.5000 [0.3520, 0.6480] |

Deltas are candidate minus baseline in pass-rate units. Bias is judge delta minus reference delta. Intervals use a paired case percentile bootstrap (2000 draws; seed 2026).

| Scope | Reference delta [interval] | Judge delta [interval] | Differential bias [interval] | Status |
|---|---|---|---|---|
| overall | 0.0588 [0.0382, 0.0809] | 0.0882 [0.0676, 0.1088] | 0.0294 [0.0162, 0.0426] | pass |
| slice:format | 0.0833 [0.0633, 0.1050] | 0.0833 [0.0633, 0.1050] | 0.0000 [0.0000, 0.0000] | pass |
| slice:lookup | -0.1250 [-0.2000, -0.0625] | 0.1250 [0.0625, 0.2000] | 0.2500 [0.1625, 0.3500] | fail |

## Gate reasons

- slice:lookup / false_pass_rate: FAIL — candidate: Wilson lower bound exceeds limit.
- slice:lookup / direction_reversal: FAIL — observed reference and judge deltas have opposite signs.
- slice:lookup / differential_bias: FAIL — bootstrap interval lies outside bias tolerance.

Intervals describe the observed sample; they do not correct for selection bias, dependent cases, label error, or multiple slices. A degenerate bootstrap cannot reveal unseen errors. An observed sign reversal fails by policy, without a statistical significance claim.
