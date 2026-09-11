# Audit — Phase 5 (Evaluation)

> Critical review prior to closing the phase and moving to Phase 6.
> Method: independent re-derivation (`/tmp/audit_f5.py`), review of each test's assumptions.
> Verdict: **1 correction applied** (robust SE in the interaction tests). The rest of the numbers
> and the decision (**LAUNCH**) are confirmed unchanged.

---

## A. Correction applied — robust SE (HC3) in the interaction tests

### A1. The problem

The `treatment × segment` interaction tests (§5.4) and the p-hacking sweep (§5.5) used OLS's
**homoscedastic F-test**. But Phase 4 (§4.2) had already shown that **under H1 the group
variances are NOT equal** (the diluted effect inflates the *treatment* group's variance).

### A2. Verification

| Scale | Levene (equal variances between groups) |
|---|---|
| Level (`merch_value_w`) | p = 8·10⁻⁸ → **strong heteroscedasticity** |
| Log(`merch_value`) | p = 0.019 → **mild** heteroscedasticity (var 0.862 vs. 0.886) |

### A3. Correction

The homoscedastic F-test is replaced with a **Wald test with HC3 errors** in:
- `src/evaluation.py :: interaction_wald_hc3()` (§5.4)
- the p-hacking sweep (§5.5), `OLS(...).fit(cov_type="HC3")`

### A4. Impact on the results

**§5.4 — pre-specified segments:** the conclusion **does not change** (no significant
interaction). Only the p-values move:

| Segment | p (homosc. F, before) | p (Wald HC3, now) |
|---|---:|---:|
| cesta | 0.93 | 0.92 |
| payment_type | 0.41 | 0.38 |
| macro_region | 0.62 | 0.68 |
| trimestre | 0.80 | 0.79 |
| cat_grupo | 0.26 | 0.14 |

**§5.5 — p-hacking:** the result **is reinforced**. With correct SE, the LEVEL-scale test's
problem is **worse** than had been reported:

| Scale | Nominal | After BH | After Bonferroni |
|---|---:|---:|---:|
| Level — **homosc. F (previous report)** | 4 | 1 | 1 |
| Level — **Wald HC3 (corrected)** | **5** | **3** | **2** |
| Log — Wald HC3 | 2 | 0 | 0 |

The lesson is now sharper: on the wrong scale, the multiplicative effect's mechanical artifacts
**survive even Bonferroni**; on the correct scale (log), nothing survives. **Correcting for
multiplicity does not save a badly posed estimand.**

---

## B. Checks that pass unchanged

### B1. Primary result (§5.1)

Independently re-derived (effect injection with `SEED=42`, Welch by hand):

| | Reported | Re-derived |
|---|---|---|
| AOV lift (winsor) | +5.666% | +5.666% |
| 95% CI | [+3.994%; +7.337%] | [+3.994%; +7.337%] |
| Actual responders | — | 19.96% (declared 20%) |
| Mean treatment factor | — | 1.0496 (declared 1.05) |

### B2. ANCOVA (§5.3)

| | Value | Check |
|---|---|---|
| R² of the model with covariates | **0.204** | explains 20% of the AOV's variance |
| SE reduction | 1.141 → 1.013 = **−11.2%** | consistent: 1−√(1−0.204) ≈ 11% |
| Estimator | +5.67% → **+5.19%** | confirmed with an alternative 2-covariate model: +5.25% |

The **SE reduction is the robust, generalizable benefit**. The point shift (+5.67 → +5.19) is
consistent but partly specific to this sample; it is not sold as a general property.

### B3. Economic impact (§5.2)

| | Reported | Re-derived |
|---|---|---|
| Valid orders/year | ≈ 58,700 | 58,743 (97,905 / 20 × 12) |
| Annual merchandise GMV | R$ 8.05M | R$ 8.05M |
| Annual GMV uplift | +R$ 456k | +R$ 456k |

*Consistency note:* the AOV base comes from the deduplicated first orders and is applied to the
non-deduplicated volume; since dedup shifts the AOV by only −0.35% (Phase 2 audit §B3), the bias
is negligible. Documented.

### B4. Segment forest plot (§5.4)

Three levels recomputed by hand match `outputs/tables/phase5_segments.csv` exactly
(`cesta:1 item` +6.111%; `payment_type:credit_card` +6.027%; `cat_grupo:health_beauty` +12.317%).

### B5. Decision (§5.6)

**LAUNCH** is maintained: significant effect, CI entirely above the +3% MDE, guardrails intact,
homogeneous relative effect, material impact. All three branches of the rule (DO NOT LAUNCH /
ITERATE / LAUNCH) remain reachable (Phase 4 §4.5).

---

## C. Minor points logged (no action)

1. **`log(AOV)` mildly heteroscedastic (Levene p = 0.019):** covered by the move to HC3.
2. **Mixed winsor/no-winsor scale:** the forest plot uses `merch_value_w` (Welch, robust) and the
   interaction tests use unwinsorized `log(merch_value)`. This is not an inconsistency — the log
   already controls the tail; it is documented in the notebook.
3. **Primary `p_value` in the JSON:** scipy underflows to 0.0; it is reported via
   `log10(p) = −10.5` (equivalent to p ≈ 3·10⁻¹¹, identical to the Phase 4 value).

---

## D. Resolution

- Correction A applied to `src/evaluation.py`; `docs/05_evaluation.md` §5.4 and §5.5 updated.
- No re-run of the other phases.
- Proceed to commit the correction and start Phase 6.
