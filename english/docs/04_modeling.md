# Phase 4 — Modeling (statistical design of the experiment)

> CRISP-DM · Phase 4 of 6
> Reproducible scripts: `src/modeling.py` · `src/mde_cost_model.py` (fixed seeds)
> → `outputs/tables/fase4_resumen.json`, `mde_cost_model.csv`
> Figures: `outputs/figures/f4_01…04.png`, `f_mde_breakeven.png`

In CRISP-DM, "Modeling" here = **the design and execution of the statistical test**: a priori
power analysis, assumption checks, A/A calibration, and the A/B test with the declared effect.
§§4.6-4.9 are the **global audit improvements** (multi-seed, guardrail regression, heterogeneous
effect, clustered SE).

Declared parameters (identical to §1.7b): `SEED=42`, two-sided `α=0.05`, diluted effect
`p_resp=0.20`, `δ_resp=0.25` → **ATE = +5%**, `ε ~ N(0, 0.05)`.
Analytical n: **control 47,280 · treatment 47,423**.

---

## 4.1 A priori power analysis

### Minimum detectable effect with fixed n (80% power, α = 0.05 two-sided)

| Metric | mean | CV | **Detectable MDE** |
|---|---:|---:|---:|
| Raw AOV | R$ 137.85 | 1.531 | **+2.79%** |
| p99.5 winsorized AOV | R$ 134.49 | 1.282 | **+2.34%** |

Both below the **+3% relevance MDE** (§1.5). Winsorization gains ~0.45 pp of sensitivity by
compressing the tail.

### Power for the declared effect (ATE = +5%)

| | uniform effect (formula) | diluted effect (simulated, 1,000 replicates) |
|---|---:|---:|
| Power (raw AOV) | 0.999 | **1.000** |
| Power (winsor AOV) | 1.000 | **1.000** |
| Estimated mean lift | — | **4.999%** (raw) / **5.006%** (winsor) |
| Estimator bias | — | **≈ 0 pp** |

→ The design is **amply powered** for +5% and the estimator is **unbiased**.

### Does the diluted effect cost power? (`f4_04_power_vs_n.png`)

Prediction from §1.7b: concentrating the effect in 20% inflates the *treatment* group's variance
and lowers power. **Verified by simulation over a grid of n (400 → 47,280 per group):**

| n / group | uniform power | diluted power | penalty |
|---:|---:|---:|---:|
| 400 | 0.08 | 0.11 | ~0 pp (noise) |
| 3,200 | 0.26 | 0.25 | +0.7 pp |
| 12,800 | 0.74 | 0.74 | +0.5 pp |
| 47,280 | 1.00 | 1.00 | −0.1 pp |

**Conclusion:** the penalty is **< 1 pp across the whole range** — negligible. Reason: the
variance added by dilution (≈ `p·(1−p)·δ_resp²·E[X²]` ≈ 1.4% of the total variance) is tiny
compared to the **AOV's natural variance** (CV ≈ 1.5). The intuition is correct in direction but
**irrelevant in magnitude** here. *Project finding: quantifying beats assuming.*

---

## 4.2 Assumption checks (`f4_01_tcl_normalidad.png`)

| Assumption | Test | Result | Verdict |
|---|---|---|---|
| Normality of the **data** | D'Agostino K² | K² = 5,453, p ≈ 0 | **Not normal** (expected — skew 9.8) |
| Normality of the **mean** (CLT) | D'Agostino K² over 5,000 bootstrap means (n = 47k) | K² = 0.38, **p = 0.826** | **Compatible with normal → Welch-t valid** |
| Homoscedasticity **without effect** (A/A) | Levene (median-centered) | stat = 1.61, p = 0.205 | Equal variances (expected) |
| Homoscedasticity **with diluted effect** | Levene | stat = 22.97, **p = 1.6·10⁻⁶** | The effect **inflates the treatment's variance** → **use Welch, NOT Student** |
| Independence | by design | random assignment + dedup to 1 order/customer | No intra-customer correlation; SUTVA assumed |

**The primary test is Welch's t** (not Student's): the check shows that under H1 the group
variances are **not** equal, exactly the case Welch is designed for.

---

## 4.3 A/A calibration — 2,000 random partitions

For each of 2,000 50/50 partitions (no effect), Welch-t on the metric and the p-value is logged.
Criterion: the 95% CI of the false-positive rate contains 0.05 **and** the p-values are uniform
(Kolmogorov-Smirnov).

| Metric | False positives (α = 0.05) | 95% CI | KS vs. uniform (p) | Verdict |
|---|---:|---:|---:|:--:|
| Raw AOV | **4.95%** | [3.99%; 5.91%] | 0.53 | ✅ calibrated |
| p99.5 winsor AOV | **5.00%** | [4.04%; 5.96%] | 0.93 | ✅ calibrated |
| log(AOV) | **5.00%** | [4.04%; 5.96%] | 0.72 | ✅ calibrated |

See `f4_02_aa_pvalores.png` (flat p-value histogram). **The pipeline does not generate false
positives and the p-values are calibrated.** (Note: an earlier run at 1,000 replicates gave a KS
p = 0.044 for the winsorized variant; it was verified over multiple seeds to be noise —the
false-positive rate stays at ~5%— and it disappears at 2,000 replicates.)

---

## 4.4 A/B test — diluted effect injected into the declared assignment (SEED = 42)

`f4_03_ab_efecto.png`

| Test | AOV lift | 95% CI | p-value | +5% within CI? |
|---|---:|---:|---:|:--:|
| **Welch · p99.5 winsor AOV (primary)** | **+5.67%** | **[+3.99%; +7.34%]** | **3.1·10⁻¹¹** | ✅ |
| Welch · raw AOV | +6.11% | [+4.09%; +8.13%] | 3.1·10⁻⁹ | ✅ |
| Bootstrap (10,000, no assumptions) | — | [+4.05%; +8.19%] | — | ✅ |
| log · ratio of geometric means | +4.79% | — | 1.4·10⁻¹⁴ | (different metric) |
| Mann-Whitney (stochastic dominance) | — | — | 1.8·10⁻¹⁵ | (different metric) |

**All intervals contain the true effect (+5%).** The point estimate lands above 5% because **this
particular split has +1.2% of baseline imbalance** (Phase 3, not significant, p = 0.235): the
effect injected on the *treatment* group is +4.86%, and +4.86% × (1 + 1.2%) ≈ +6.1%. Over 1,000
replicates the estimator is **unbiased** (mean 5.00%) — any single experiment carries the noise of
its own assignment, which is why the decision anchors on the **CI**, not on the point estimate.

### Guardrails (Welch / proportion z-test · Benjamini-Hochberg correction · no effect injected)

| Guardrail | control | treatment | raw p | **adjusted p (BH)** | Degraded? |
|---|---:|---:|---:|---:|:--:|
| G1 · review_score | 4.114 | 4.116 | 0.80 | 0.80 | ❌ no |
| G2 · cancellation rate | 0.541% | 0.570% | 0.56 | 0.77 | ❌ no |
| G3 · freight_value | R$ 22.74 | R$ 22.89 | 0.30 | 0.77 | ❌ no |
| G4 · number of items | 1.140 | 1.138 | 0.58 | 0.77 | ❌ no |

**No guardrail is degraded** (no adjusted p < 0.05). This is the expected result: the design only
injects an effect into the primary metric. The guardrail tests' real ability to **catch** a
regression is verified in §4.7.

---

## 4.5 Decision sweep — the three branches of the §1.5 rule

Applying the launch / iterate / do-not-launch rule to different injected effect sizes (winsorized
primary metric, guardrails OK, `SEED = 42` split with +1.2% of baseline imbalance):

| Injected ATE | observed lift | 95% CI | p-value | **Decision** |
|---:|---:|---:|---:|:--:|
| 0% | +1.01% | [−0.63%; +2.65%] | 0.227 | **DO NOT LAUNCH** |
| 1% | +1.95% | [+0.30%; +3.60%] | 0.020 | **ITERATE** |
| 2% | +2.89% | [+1.23%; +4.54%] | 6·10⁻⁴ | **ITERATE** |
| 3% | +3.82% | [+2.16%; +5.48%] | 6·10⁻⁶ | **ITERATE** |
| 4% | +4.75% | [+3.08%; +6.41%] | 2·10⁻⁸ | **LAUNCH** |
| **5% (declared)** | **+5.67%** | **[+3.99%; +7.34%]** | **3·10⁻¹¹** | **LAUNCH** |
| 8% | +8.40% | [+6.71%; +10.09%] | 2·10⁻²² | **LAUNCH** |

The design **reaches all three decisions**: a real effect below the relevance threshold (ATE ≤ 3%)
produces "ITERATE" —significant but with the CI touching the MDE—, and only from a clearly
relevant effect onward does "LAUNCH" trigger.

---

## 4.6 Multi-seed A/B — is a single split's result reliable? (improvement #3)

The **full A/B test** is repeated (re-split 50/50 + re-injection of the diluted effect + Welch)
over **500 seeds**, on raw and on winsorized data, to measure the estimator's distribution and the
**real coverage** of the 95% CI.

| | mean lift | bias | sd (pp) | p2.5-p97.5 | 95% CI coverage of the real +5% | power |
|---|---:|---:|---:|---:|---:|---:|
| **Raw AOV** | +4.97% | **−0.03 pp** | 1.05 | [+2.9%; +7.1%] | **0.94** | 1.00 |
| **p99.5 winsor AOV** | +4.64% | **−0.36 pp** | 0.87 | [+2.9%; +6.2%] | **0.92** | 1.00 |

**Findings:**

1. **On raw data the estimator is unbiased** (−0.03 pp) and the 95% CI has **nominal coverage**
   (0.94 ≈ 0.95). The +6.1% result from the `SEED=42` split falls within [+2.9%; +7.1%] — it is a
   normal realization, not an artifact.
2. **Winsorization introduces a small negative bias** (−0.36 pp) because the effect is
   multiplicative and the p99.5 clip bites more into the *treatment* group's high values. In
   exchange it reduces the estimator's spread (0.87 vs. 1.05) — **MSE is lower with winsor** (0.88
   vs. 1.11), but the CI **slightly under-covers** (0.92).
3. **Implication:** for the **significance test** (is there an effect? does it clear the MDE?),
   winsorization is preferable (more power, less MSE). For the **point estimate of the effect
   size**, raw is unbiased. Both are reported; the (LAUNCH) decision is identical under both.

This **closes the "single split" weakness** (global audit #4): the estimator is reliable under
repetition and the CIs are (almost) well calibrated.

---

## 4.7 Regression injected into a guardrail — does the design catch it? (improvement #1)

An additive regression is injected into `review_score` (G1) only in the *treatment* group, and the
**two-gate rule** is applied (significant **AND** magnitude ≥ 0.05 pts, global audit §D19):

| Injected regression | observed diff | p-value | Significant? | Magnitude ≥ 0.05? | "OR" rule (original) | **"AND" rule (corrected)** |
|---:|---:|---:|:--:|:--:|:--:|:--:|
| 0.00 | +0.002 | 0.80 | ❌ | ❌ | does not block | **does not block** ✅ |
| −0.03 | −0.028 | 0.001 | ✅ | ❌ | **blocks (false)** | **does not block** ✅ |
| −0.05 | −0.048 | 3·10⁻⁸ | ✅ | ❌ (just below) | blocks | does not block (borderline) |
| −0.08 | −0.078 | 2·10⁻¹⁹ | ✅ | ✅ | blocks | **blocks** ✅ |

**Findings:**

- At n ≈ 47k/group, **any real regression is statistically significant** (even −0.03 pts gives p
  ≈ 0.001). The guardrail test has **ample power**.
- The original rule ("significant **OR** magnitude") **would block the launch over sub-threshold
  noise**. The corrected rule ("significant **AND** magnitude") lets −0.03 through (correct) and
  catches −0.08 (correct). → **§1.4 updated.**

---

## 4.8 Variant with a truly heterogeneous effect (improvement #2)

The main analysis injects a **homogeneous** effect (random responders). Here a variant is tested
where the effect is **concentrated in orders below a hypothetical free-shipping threshold
(R$ 150)** — more realistic for the progress bar.

| | value |
|---|---|
| Orders in the band [R$ 90, R$ 150) | 22.4% |
| Lift **within the band** | **+7.05%** |
| Lift **outside the band** | +1.52% |
| `treatment × band` interaction test (log, HC3) | **p = 2·10⁻¹⁵** |

**The design detects the real heterogeneity** (tiny p), unlike the main analysis (homogeneous
effect → no interaction, §5.4). → The segment analysis **does work** when there is something to
find; its null result in the main analysis is not a lack of power.

---

## 4.9 Robustness: all orders + customer-clustered SE (improvement #5)

| | lift | SE (R$) |
|---|---:|---:|
| Dedup to 1 order/customer (main analysis) | +5.67% | 1.14 (Welch) |
| **All orders + customer-clustered SE** | **+5.71%** | **1.14 (cluster)** |
| All orders + robust SE without clustering | +5.71% | 1.12 |

Clustering **inflates the SE by only 1.1%** (97% of customers have a single order) and the lift is
practically the same. **Deduplicating was the simple and correct option**; it changes no
conclusion.

---

## 4.10 Closing Phase 4 and handoff to Phase 5

- [x] A priori power analysis: detectable MDE +2.79% / +2.34%; power ~100% for +5%; **dilution
  penalty < 1 pp (negligible, quantified)**.
- [x] Assumptions verified: normality of the mean via CLT (p = 0.83), heteroscedasticity under H1
  → **Welch justified**, independence by design.
- [x] A/A calibration (2,000 partitions): 5.0% false positives, uniform p-values (KS p ≥ 0.5).
- [x] A/B test: **+5.67% [+3.99%; +7.34%], p = 3·10⁻¹¹** (winsor) / **+6.11% [+4.09%; +8.13%]**
  (raw); both contain the real +5%.
- [x] Guardrails with BH: **none degraded**; rule corrected to "significant AND magnitude".
- [x] Decision sweep: all three branches of the rule are reachable.
- [x] **Multi-seed A/B** (500): raw unbiased and with nominal coverage; winsor with −0.36 pp of
  bias and lower MSE. The `SEED=42` split is a normal realization.
- [x] **Guardrail regression / heterogeneous effect / clustered SE / SRM / MDE cost model**
  (global audit improvements) executed.
- **Next (Phase 5 — Evaluation):** significance vs. relevance, segments with p-hacking control,
  decision.
