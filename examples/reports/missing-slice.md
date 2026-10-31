# Judge regression gate

Decision: **INCONCLUSIVE**

PASS concerns judge alignment on this sample under this policy; it is not a model release or deployment approval.

Limits: false-pass rate <= 0.2; absolute differential bias <= 0.1. Minimum per scope: 60 pairs and 15 reference failures per version.

Positive means pass. False-pass rate = false passes / reference failures. Intervals are marginal 95% Wilson score intervals.

| Scope | Pairs | Version | Agreement | False passes / failures | Rate [interval] |
|---|---:|---|---:|---:|---|
| overall | 80 | baseline | 1.0000 | 0 / 30 | 0.0000 [0.0000, 0.1135] |
| overall | 80 | candidate | 1.0000 | 0 / 20 | 0.0000 [0.0000, 0.1611] |
| slice:format | 80 | baseline | 1.0000 | 0 / 30 | 0.0000 [0.0000, 0.1135] |
| slice:format | 80 | candidate | 1.0000 | 0 / 20 | 0.0000 [0.0000, 0.1611] |
| slice:lookup | 0 | baseline | unknown | 0 / 0 | unknown unknown |
| slice:lookup | 0 | candidate | unknown | 0 / 0 | unknown unknown |

Deltas are candidate minus baseline in pass-rate units. Bias is judge delta minus reference delta. Intervals use a paired case percentile bootstrap (2000 draws; seed 2026).

| Scope | Reference delta [interval] | Judge delta [interval] | Differential bias [interval] | Status |
|---|---|---|---|---|
| overall | 0.1250 [0.0625, 0.2000] | 0.1250 [0.0625, 0.2000] | 0.0000 [0.0000, 0.0000] | pass |
| slice:format | 0.1250 [0.0625, 0.2000] | 0.1250 [0.0625, 0.2000] | 0.0000 [0.0000, 0.0000] | pass |
| slice:lookup | unknown unknown | unknown unknown | unknown unknown | inconclusive |

## Gate reasons

- slice:lookup / case_support: INCONCLUSIVE — 0 pairs &lt; 60 required.
- slice:lookup / failure_support: INCONCLUSIVE — baseline: 0 reference failures &lt; 15 required.
- slice:lookup / failure_support: INCONCLUSIVE — candidate: 0 reference failures &lt; 15 required.

Intervals describe the observed sample; they do not correct for selection bias, dependent cases, label error, or multiple slices. A degenerate bootstrap cannot reveal unseen errors. An observed sign reversal fails by policy, without a statistical significance claim.
