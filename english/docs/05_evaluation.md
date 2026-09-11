# Phase 5 — Evaluation

> CRISP-DM · Phase 5 of 6
> Reproducible script: `src/evaluation.py` → `outputs/tables/phase5_summary.json`,
> `outputs/tables/phase5_segments.csv` · Figure: `outputs/figures/f5_01_forest_segments.png`

Translates Phase 4's statistical result into a **product decision**, separating significance from
relevance and controlling for p-hacking in the segment analysis.

---

## 5.1 Result with full reporting (not just the p-value)

| Primary metric — AOV (injected diluted effect) | Welch **p99.5 winsor** | Welch **raw** |
|---|---|---|
| Relative lift | **+5.67%** | **+6.11%** |
| 95% CI | [+3.99%; +7.34%] | [+4.09%; +8.13%] |
| p-value | 3.1·10⁻¹¹ | 3.1·10⁻⁹ |
| True injected effect (+5.0%) | **within the CI** | **within the CI** |

n = control 47,280 · treatment 47,423.

**Reading the point estimate:** both versions land above the injected +5% because of the
**baseline imbalance** of the `SEED=42` split (+1.2%, not significant, p = 0.235; Phase 3). The
multi-seed A/B test (Phase 4 §4.6) confirms that **on raw data the estimator is unbiased** (−0.03
pp over 500 replicates, CI coverage 0.94) and that **winsorization dampens it by −0.36 pp** (in
exchange for lower variance). Honest range of the effect size: **+5.7% to +6.1%**. The decision
anchors on the **CI**, not on the point — and both CIs clear the MDE.

---

## 5.2 Statistical significance ≠ business relevance

| Question | Criterion | Result |
|---|---|---|
| Is it **statistically** significant? | p < 0.05 | **Yes** (p ≈ 3·10⁻¹¹) |
| Is it **relevant for the business**? | 95% CI of the lift **entirely above** the relevance MDE (+3%) | **Yes** — CI [+3.99%; +7.34%] (winsor) and [+4.09%; +8.13%] (raw) |

With n ≈ 47k/group, even a trivial effect would also come out "significant". What makes this
result **actionable** is that **the entire confidence interval is above the business relevance
threshold**, not just the point estimate.

> The relevance MDE (+3%) is **derived from a break-even model** (`src/mde_cost_model.py`,
> `f_mde_breakeven.png`): it is the lift below which the incremental margin does not cover the
> redesign's cost of ownership. Valid for a marketplace with ≥ ~415k orders/year (2-year payback).

### Estimated economic impact

| | Value |
|---|---|
| Valid orders/year (historical extrapolation) | ≈ 58,700 |
| Annual merchandise GMV (base) | ≈ R$ 8.05M |
| **Annual GMV uplift** | **+R$ 456,000** · 95% CI [+R$ 322k; +R$ 591k] |
| Marketplace revenue uplift (assumed 15% commission) | ≈ +R$ 68,000/year |

*Linear extrapolation of the per-order lift to the annual volume; real revenue depends on the take rate.*

---

## 5.3 Covariate-adjusted estimate (ANCOVA) — variance reduction

OLS `AOV_w ~ treatment + n_items + freight + category + macro-region + quarter` (HC3 errors):

| | Lift | 95% CI | SE (R$) |
|---|---:|---:|---:|
| Unadjusted | +5.67% | [+3.99%; +7.34%] | 1.141 |
| **Adjusted** | **+5.19%** | **[+3.71%; +6.68%]** | **1.013** |

The covariate adjustment **reduces the standard error by 11.2%** (a tighter CI) and **brings the
estimator closer to the true +5%** — the covariates (mainly number of items and category) explain
part of the residual noise. This is the standard technique (CUPED / regression) for gaining
precision without bias.

---

## 5.4 Segment analysis — pre-specified and corrected

**Segments declared BEFORE looking at results:** `cesta` (1 vs. 2+ items), `payment_type`,
`macro_region` (5 macro-regions of Brazil), `trimestre`, `cat_grupo` (top 6 categories + rest).

> **"New vs. repeat customer" is out of scope**, declared: dedup to 1 order/customer leaves it
> degenerate (n_repeat ≈ 40) and repeat purchase at Olist is ~3% (Phase 2 §2.7). It would be
> analyzed on the robustness table with all orders.

### `treatment × segment` interaction test on **log(AOV)**, **HC3** Wald (relative effect)

> HC3 (heteroscedasticity-robust SE): necessary because under H1 the group variances differ
> (Phase 4; Phase 5 audit §A2). The homoscedastic F-test would give slightly different p's without
> changing the conclusion.

| Segment | raw p | adjusted p (BH) | Heterogeneous? |
|---|---:|---:|:--:|
| cesta | 0.92 | 0.92 | ❌ |
| payment_type | 0.38 | 0.92 | ❌ |
| macro_region | 0.68 | 0.92 | ❌ |
| trimestre | 0.79 | 0.92 | ❌ |
| cat_grupo | 0.14 | 0.68 | ❌ |

**No interaction is significant.** The **relative** effect is homogeneous across segments,
consistent with the design (responders are drawn at random). In the *forest plot* (`f5_01`) a
couple of small, noisy segments (e.g. `bed_bath_table`, `health_beauty`) visually drift away from
the global +5.7%, but they are the **expected outliers when looking at 25 levels at once** with
marginal (not simultaneous) CIs: the joint interaction test —the correct test— does not detect
heterogeneity, and `health_beauty` is precisely the only nominal finding that **does not survive
the correction** (§5.5).

> **Why the test is run in `log` and not at the level scale:** the effect is multiplicative, so
> the **absolute** lift in R$ is mechanically larger in large baskets. A level-scale test would
> detect that "heterogeneity" which is not real — the business question is whether the **%**
> changes, and that is tested on the log scale.

---

## 5.5 The risk of p-hacking — demonstrated

**38 arbitrary exploratory cuts** are tested (individual states, individual categories, freight
quartiles, quarters). Test: `treat × cut` interaction, **HC3** Wald. Expected by pure chance at
α = 0.05: **≈ 1.9**.

| Test scale | Nominal p < 0.05 | After BH (FDR) | After Bonferroni |
|---|---:|---:|---:|
| **Level (R$)** | **5** (3 in freight quartiles) | **3** (`flete_q1`, `flete_q4`, `bed_bath_table`) | **2** |
| **Log (relative effect, %)** | 2 | **0** | **0** |

**Lessons:**
1. At the **level** scale, several "segments where the effect differs" **survive even
   Bonferroni**. They are not chance: they are a **mechanical artifact** of the multiplicative
   effect (the lift in R$ is larger in large baskets), concentrated in the cuts correlated with
   size (freight quartiles).
2. At the **log** scale (the correct magnitude: the %), only chance-level nominal findings remain
   and **none survives** BH or Bonferroni.
3. → **(a)** test the correct magnitude (%, not absolute R$); **(b)** pre-specify the segments;
   **(c)** correct for multiplicity. **Correcting is not enough if the estimand is wrong to begin
   with.**

---

## 5.6 Product decision

# 🟢 LAUNCH

| Criterion | ✔ |
|---|---|
| Significant primary effect (p ≈ 3·10⁻¹¹) | ✅ |
| 95% CI of the lift entirely above the relevance MDE (+3%) | ✅ [+3.99%; +7.34%] |
| Robust estimate (winsor, log, bootstrap, ANCOVA all agree) | ✅ |
| No guardrail degraded (G1-G4, Benjamini-Hochberg) | ✅ |
| Homogeneous relative effect across pre-specified segments | ✅ |
| Material economic impact (+R$ 456k/year GMV) | ✅ |

**Declared caveats:**
- The effect is **synthetic and known**: this decision **validates the decision process**, it does
  not constitute a real finding about Olist.
- With an injected ATE of +2% or +3%, the same rule would have returned **ITERATE** (real effect
  but CI touching the MDE); with +0%, **DO NOT LAUNCH** (Phase 4 §4.5). All three branches work.

---

## 5.7 Limitations of the evaluation

1. **Simulated effect** (already discussed): no external validity; the goal is to demonstrate the
   method.
2. **Linear economic extrapolation**: the GMV uplift assumes the per-order lift holds when scaled
   to the full volume and over time; it ignores novelty, saturation, and seasonality.
3. **No retention / LTV metric**: Olist's window and low repeat purchase prevent it. A 90-day
   repeat-purchase guardrail would be desirable in a real experiment.
4. **Guardrails with no injected effect**: by design they come out flat. A real experiment would
   also monitor returns and complaints (not available in Olist).
5. **A single analysis split** (SEED = 42): the point estimate carries that assignment's baseline
   imbalance; mitigated with the CI, the ANCOVA, and the evidence of unbiasedness over 1,000
   replicates.

---

## 5.8 Closing Phase 5 and handoff to Phase 6

- [x] Full reporting: effect, CI, p, size, n — not just significance.
- [x] Significance (p ≈ 3·10⁻¹¹) **vs.** relevance (CI entirely above the +3% MDE) — both ✅.
- [x] Economic impact: +R$ 456k/year of GMV [CI +R$ 322k; +R$ 591k].
- [x] ANCOVA: −11.2% SE, estimator closer to the real value.
- [x] Pre-specified segments + BH: **no heterogeneity**.
- [x] p-hacking demonstrated (level vs. log; BH vs. Bonferroni).
- [x] **Decision: LAUNCH**, with all three branches of the rule verified.
- **Next (Phase 6 — Deployment):** 1-page executive summary, reproducible notebook with a
  narrative, GitHub README, LinkedIn post draft.
