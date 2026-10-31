# Judge regression gate

Decision: **INCONCLUSIVE**

PASS concerns judge alignment on this sample under this policy; it is not a model release or deployment approval.

Limits: false-pass rate <= 0.2; absolute differential bias <= 0.1. Minimum per scope: 60 pairs and 15 reference failures per version.

Positive means pass. False-pass rate = false passes / reference failures. Intervals are marginal 95% Wilson score intervals.

| Scope | Pairs | Version | Agreement | False passes / failures | Rate [interval] |
|---|---:|---|---:|---:|---|
| overall | 24 | baseline | 1.0000 | 0 / 8 | 0.0000 [0.0000, 0.3244] |
| overall | 24 | candidate | 1.0000 | 0 / 6 | 0.0000 [0.0000, 0.3903] |
| slice:format | 12 | baseline | 1.0000 | 0 / 4 | 0.0000 [0.0000, 0.4899] |
| slice:format | 12 | candidate | 1.0000 | 0 / 3 | 0.0000 [0.0000, 0.5615] |
| slice:lookup | 12 | baseline | 1.0000 | 0 / 4 | 0.0000 [0.0000, 0.4899] |
| slice:lookup | 12 | candidate | 1.0000 | 0 / 3 | 0.0000 [0.0000, 0.5615] |

Deltas are candidate minus baseline in pass-rate units. Bias is judge delta minus reference delta. Intervals use a paired case percentile bootstrap (2000 draws; seed 2026).

| Scope | Reference delta [interval] | Judge delta [interval] | Differential bias [interval] | Status |
|---|---|---|---|---|
| overall | 0.0833 [0.0000, 0.2083] | 0.0833 [0.0000, 0.2083] | 0.0000 [0.0000, 0.0000] | inconclusive |
| slice:format | 0.0833 [0.0000, 0.2500] | 0.0833 [0.0000, 0.2500] | 0.0000 [0.0000, 0.0000] | inconclusive |
| slice:lookup | 0.0833 [0.0000, 0.2500] | 0.0833 [0.0000, 0.2500] | 0.0000 [0.0000, 0.0000] | inconclusive |

## Gate reasons

- overall / case_support: INCONCLUSIVE — 24 pairs &lt; 60 required.
- overall / failure_support: INCONCLUSIVE — baseline: 8 reference failures &lt; 15 required.
- overall / false_pass_rate: INCONCLUSIVE — baseline: Wilson interval crosses limit.
- overall / failure_support: INCONCLUSIVE — candidate: 6 reference failures &lt; 15 required.
- overall / false_pass_rate: INCONCLUSIVE — candidate: Wilson interval crosses limit.
- slice:format / case_support: INCONCLUSIVE — 12 pairs &lt; 60 required.
- slice:format / failure_support: INCONCLUSIVE — baseline: 4 reference failures &lt; 15 required.
- slice:format / false_pass_rate: INCONCLUSIVE — baseline: Wilson interval crosses limit.
- slice:format / failure_support: INCONCLUSIVE — candidate: 3 reference failures &lt; 15 required.
- slice:format / false_pass_rate: INCONCLUSIVE — candidate: Wilson interval crosses limit.
- slice:lookup / case_support: INCONCLUSIVE — 12 pairs &lt; 60 required.
- slice:lookup / failure_support: INCONCLUSIVE — baseline: 4 reference failures &lt; 15 required.
- slice:lookup / false_pass_rate: INCONCLUSIVE — baseline: Wilson interval crosses limit.
- slice:lookup / failure_support: INCONCLUSIVE — candidate: 3 reference failures &lt; 15 required.
- slice:lookup / false_pass_rate: INCONCLUSIVE — candidate: Wilson interval crosses limit.

Intervals describe the observed sample; they do not correct for selection bias, dependent cases, label error, or multiple slices. A degenerate bootstrap cannot reveal unseen errors. An observed sign reversal fails by policy, without a statistical significance claim.
