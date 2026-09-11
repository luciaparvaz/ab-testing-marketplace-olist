# Phase 1 — Business Understanding

> CRISP-DM · Phase 1 of 6
> Project: A/B testing in a marketplace (Brazilian E-Commerce by Olist dataset)
> Status: **closed** — AOV baseline fixed in Phase 2; refined after the audit (see `docs/auditoria_fase1_fase2.md`).

---

## 1.1 Business context

Olist is a Brazilian **marketplace** that connects small and medium sellers with the country's
large online sales channels. The end customer browses a catalog, places an order (which may
contain products from several sellers) and, after delivery, leaves a review scored 1 to 5.

The public dataset covers **~100,000 orders placed between September 2016 and October 2018**,
spread across 9 relational tables (orders, order items, payments, reviews, customers, sellers,
products, geolocation, and category translation).

### Product lever evaluated

The Product team (the *Checkout & Conversion* squad) proposes a **redesign of the product block**
on the item page that combines two elements:

1. A **"products often bought together" recommendations** module (cross-sell) on the product page
   and in the cart.
2. A **progress bar toward free shipping** that activates above an amount threshold.

**Product hypothesis:** both elements push the customer to add extra items to the order, so an
increase in the **Average Order Value (AOV)** is expected, without harming satisfaction or driving
up cancellations.

### Why an experiment and not an observational analysis

The change affects purchasing behavior in a potentially subtle way and is confounded with
seasonality, category mix, and customer profile. Only **random assignment** allows causally
attributing the AOV difference to the redesign. Hence the A/B design.

---

## 1.2 Structural limitation of the dataset and how the scope is bounded

**The Olist dataset starts at the order already placed: it contains no sessions, visits, or
abandoned carts.** As a consequence:

| Typical e-commerce metric | Measurable with Olist? | Reason |
|---|---|---|
| Visit → order conversion rate | ❌ No | There is no population of "non-buyers" |
| Cart abandonment rate | ❌ No | No cart events |
| **Average Order Value (AOV)** | ✅ Yes | `order_items.price` aggregated per order |
| **Mean review score** | ✅ Yes | `order_reviews.review_score` |
| **Cancellation rate** | ✅ Yes | `orders.order_status == 'canceled'` |
| Items per order | ✅ Yes | Count of `order_items` per order |
| Repeat purchase within the window | ⚠️ Limited | `customer_unique_id` allows identifying it, but repeat purchase is very low (~3%) |

**Scope decision:** the primary metric will be the **AOV**, not conversion. It is the metric the
dataset supports rigorously and the one that directly captures the expected effect of cross-sell +
free shipping. A traffic/non-buyer layer will not be simulated because that would mean
**fabricating data**, which the project's quality standards prohibit. What WILL be injected — in a
declared way — is a treatment effect on real observations (see §1.7).

---

## 1.3 Randomization unit and analysis unit

- **Randomization unit:** the customer (`customer_unique_id`). Assigning per customer rather than
  per order prevents two orders from the same customer from falling into different groups
  (contamination) and respects the SUTVA assumption.
- **Analysis unit: the order, deduplicated to 1 order per customer** (the first one in the window).
  Rationale (audit §B3): 96.96% of customers have only one order, and keeping each customer's
  first one shifts the mean AOV by only **-0.35%** (R$ 137.42 → 137.90). In exchange,
  **randomization unit = analysis unit**, which removes the need for clustered standard errors and
  makes the analysis more transparent for a stakeholder. As a robustness check, the analysis with
  **all orders + customer-clustered SE** will also be reported.
- **Assignment ratio:** 50/50 (maximum power for a fixed total size).

---

## 1.4 Hypotheses

### Primary metric — AOV

| | Business formulation | Statistical formulation |
|---|---|---|
| **H0** | The redesign does not change the mean order value. | μ_T − μ_C = 0 |
| **H1** | The redesign changes the mean order value. | μ_T − μ_C ≠ 0 |

- **Two-sided test, α = 0.05.** Two-sided — rather than one-sided — is chosen because a redesign
  can also *reduce* the AOV (e.g. if the focus on "free shipping" makes the customer cap their
  spend at the threshold), and that outcome must be formally detectable, not only via guardrails.
- μ = mean merchandise value per order (`sum(order_items.price)` per `order_id`; freight is
  excluded because the redesign does not move it — it is monitored as a guardrail).

### Guardrail metrics (must not degrade)

| Guardrail | Definition | Alarm threshold | Test |
|---|---|---|---|
| G1 — Satisfaction | mean `review_score` (1-5) | Significant drop **AND** magnitude ≥ 0.05 pts | t-test / Mann-Whitney |
| G2 — Cancellation | % of orders with `order_status == 'canceled'` | Significant rise **AND** magnitude ≥ 0.2 pp | Proportion (z) test |
| G3 — Freight absorbed | mean `freight_value` per order | Significant rise **AND** absorbing ≥ 20% of the AOV increase | t-test |
| G4 — Frequency | Orders per customer in the window | Significant drop **AND** relevant magnitude | Proportion test / t-test |

**Two-gate rule (corrected after the global audit §D19):** at n ≈ 47k/group, *any* real regression
is statistically significant (even -0.03 pts in `review_score` gives p ≈ 0.001). A "significant
**OR** magnitude" rule would block the launch over sub-threshold noise. **Significant AND
magnitude ≥ threshold** is required — verified in Phase 4 (`modeling.py::
guardrail_regression_scenarios`): with the corrected rule a -0.03 regression does not block
(correct) and a -0.08 one does (correct).

The guardrail metrics are tested with **multiple-comparison correction** (see §1.6).

---

## 1.5 Business decision criterion (MDE and launch rule)

### Relevance Minimum Detectable Effect (MDE)

Statistical significance is not enough: it is necessary to set **what effect size justifies the
cost** of building and maintaining the redesign (engineering effort + design + maintenance of the
recommendation engine).

- The relevance MDE is set **in relative terms: +3% over the base AOV**.
- Rationale (cost model in `src/mde_cost_model.py`, global audit improvement #4): the break-even
  is `lift = total_cost / (AOV · volume · commission · margin · years)`. With illustrative
  assumptions (AOV R$ 137, commission 15%, net margin 80%, build R$ 250k, maintain R$ 80k/year,
  2-year payback), the break-even falls as order volume rises:
  - at ~58,700 orders/year (the dataset itself) → break-even **~+21%** (the +3% would **not** be
    justified at that scale);
  - at ~1,000,000 orders/year (medium marketplace) → break-even **~+1.25%** (the +3% is
    **conservative**).
  The project assumes the second scale. **The +3% is valid for a marketplace with ≥ ~415,000
  orders/year** (2-year payback). See `outputs/figures/f_mde_breakeven.png`.
- **Phase 4's power calculation** inverts the problem: with the **fixed** sample size the dataset
  imposes (~95k customers), it will compute **what MDE can be detected at 80% power and
  α = 0.05 two-sided**, and compare it with the +3% relevance threshold.
- **Warning (audit §C):** Phase 2's analytical preview gives a detectable effect of ~+2.7% (raw
  data) or ~+2.3% (p99.5 winsorized) — below +3%, but with a narrow margin. The conclusion that
  "the sample is sufficiently powered" **does not rest on that margin**, but on the **empirical
  power achieved at the injected δ** (§1.7), measured by repeated simulation in Phase 4.
- **Hypothesis to test in Phase 4:** that the **diluted** effect (§1.7b) reduces power relative to
  a uniform effect of the same mean size. It is a reasonable prediction —concentrating the effect
  in 20% inflates the *treatment* group's variance—, but **it must be quantified, not assumed**.
  (Phase 4 result: the penalty is **negligible** here, because the AOV's natural variance, CV ≈
  1.5, dominates; see `docs/04_modeling.md` §4.2.)

### Decision rule

| Result | Product decision |
|---|---|
| Significant primary effect (p < 0.05) **and** 95% CI of the *lift* **entirely above** +3% **and** no guardrail degraded | **Launch** |
| Positive and significant effect **but** the 95% CI includes values below +3% | **Iterate** (the effect is real but not conclusively relevant; refine the design or segment) |
| Non-significant or negative effect, or any guardrail significantly degraded | **Do not launch** |

---

## 1.6 Planned statistical design (detailed and executed in Phase 4)

- **Primary test:** **Welch's t on the raw AOV** (arithmetic mean between groups). It is the
  business metric: revenue = mean × volume. At n ≈ 47-48k per group the Central Limit Theorem
  makes the sampling distribution of the mean normal despite the skew of 9.8, so Welch is valid;
  this is confirmed empirically with the A/A test (§1.7a).
- **Robustness, NOT substitutes for the primary result** (audit §B2): (i) t-test on `log(AOV)` —
  tests the **ratio of geometric means** (≈ median), which is a *different* question, not a "more
  powerful" version of the AOV; (ii) Mann-Whitney — stochastic dominance; (iii) **bootstrap** of
  the mean difference with no distributional assumption; (iv) p99.5 winsorized mean. All are
  reported; the business decision anchors on Welch on the raw AOV.
- **Multiple-comparison correction:** **Benjamini-Hochberg (FDR)** over the guardrail family + any
  segment analysis. BH is chosen over Bonferroni because the goal is to control the false
  discovery rate while keeping reasonable power over a set of ~4-8 secondary tests, not the strict
  FWER. The primary metric does **not** enter the correction (it is a single pre-specified test).
- **Reporting:** for each metric — effect size (absolute and relative), 95% CI, p-value, and n per
  group. Never just the p-value.

---

## 1.7 Simulation design (declared and traceable)

Since the dataset does not come with groups, the assignment is **simulated**. Two experiments are run**:

### (a) A/A test — pipeline and Type I error validation

- Random 50/50 assignment by `customer_unique_id`, fixed seed.
- **No metric is modified.**
- Expected results if the pipeline is correct:
  - Covariate balance (`customer_state`, order's dominant category, purchase month, payment type,
    number of items) **not significant** (SMD < 0.1 and omnibus test not significant).
  - Repeating the A/A test over **many random partitions** (e.g. 1,000 seeds), the rejection rate
    of H0 at α = 0.05 should be around **5%**, and the distribution of p-values should be
    **uniform** (Kolmogorov-Smirnov test against the uniform).
- Purpose: to demonstrate that the design **does not generate false positives** and that the
  p-values are calibrated **before** introducing any effect.

### (b) A/B test — **diluted** and declared synthetic treatment effect

Model chosen (audit §D, option b): **partial adoption**. A real redesign only moves a fraction of
users; the rest do not change their behavior. For each order `i` in the *treatment* group:

```
R_i  ~ Bernoulli(p_resp)                          # does this user respond to the redesign?
if R_i = 1:  aov_T_i = aov_C_i · (1 + δ_resp + ε_i)
if R_i = 0:  aov_T_i = aov_C_i                     # no change
```

| Parameter | Declared value | Meaning |
|---|---|---|
| `p_resp` | **0.20** | 20% of treated orders respond |
| `δ_resp` | **0.25** | responders spend +25% more |
| `ε_i` | Normal(0, 0.05) | heterogeneity among responders (avoid inflating power with a deterministic effect) |
| **Mean effect (ATE)** | **`p_resp · δ_resp` = 0.05 → +5%** | matches the declared mean δ |
| Seed | fixed (`SEED = 42`), documented in the code | reproducibility |

- The responders are drawn **at random, independent of the order's value** (keeps the ATE clean).
  Optional variant for Phase 5: bias the responders toward an amount band below the free-shipping
  threshold (a more realistic effect of the progress bar).
- The analysis is run **blind** to `p_resp` and `δ_resp` and must **recover the 5% ATE within the
  95% CI**.
- **Prediction to verify:** concentrating the effect in 20% of the treated sample raises the
  *treatment* group's variance, which *could* reduce power relative to a uniform effect. Phase 4
  quantifies this by simulation. **Result:** the estimator is **unbiased** (mean of 1,000
  replicates = 5.00%) and the power penalty from dilution is **< 1 pp** across the whole n range —
  the intuition is correct in principle but **irrelevant in magnitude** here. It is a finding of
  the project: *verifying* beats *assuming*.

### Note on methodological honesty (will also go in the README and the notebook)

> The treatment effect is **known by construction**. The project's goal is **not** to "discover"
> whether the redesign works —we know it does, because we are the ones who introduce the effect—
> but to demonstrate that **the experimental design and the statistical analysis (a) control false
> positives and (b) recover an effect of known size without bias**, with its confidence interval
> and its power. That is exactly the competency being assessed in a product experimentation role.
> A dataset with real randomization (Criteo Uplift, Hillstrom) was discarded because its lever is a
> marketing send, not an on-site change in the marketplace.

---

## 1.8 Seasonality control and time window

- The assignment is **random per customer over the entire history**, so that *treatment* and
  *control* cover the **same date range** and seasonality is **balanced by design**.
- Phase 3 **restricts the window** to 2017-01 → 2018-08. This is an adjustment **for realism**
  (making the duration resemble a real experiment and removing residual months), **not a bias
  correction**: the audit (§B6) confirms that the mean AOV barely moves (R$ 137.42 → 137.37) and
  less than 1% of orders are lost.

---

## 1.9 Phase 1 deliverables

- [x] Business problem defined in product terms (product page redesign → AOV).
- [x] H0 / H1 in business and statistical language, with a single primary metric (AOV).
- [x] Guardrail metrics (G1-G4) with alarm thresholds.
- [x] Relevance MDE (+3% relative) and launch/iterate/do-not-launch decision rule.
- [x] Test approach, multiplicity correction (BH), and simulation design (A/A + diluted A/B,
  ATE = +5%).
- [x] Numerical AOV baseline and its variance → **closed in Phase 2**: mean AOV **R$ 137.42**,
  σ **R$ 209.31**, **CV 1.523**, skew 9.8. `log(AOV)` brings the skew to 0.24 and kurtosis to 0.33
  (robust range for the t-test; formally not normal, but irrelevant thanks to the CLT at large n).
  Power preview: detectable effect ~+2.7% (raw) / ~+2.3% (winsorized) — the real validation is
  Phase 4's empirical power.

---

## 1.10 Timeline risk (explicit warning)

The meta-prompt assigns *Business Understanding* + *Modeling (design)* to Block 3 (2.5h, Day 1).
The choice to run **both A/A and A/B** ("Both") adds work relative to A/B alone:

- Estimated incremental cost: **+1 to +1.5h**, concentrated in Phase 4 (the 1,000-seed A/A loop +
  the KS test for p-value uniformity) and in Phase 5 (writing up the validation).
- Most of the code is **shared** between A/A and A/B (same assignment, same tests, same power
  analysis), so the effort is not duplicated.
- **Proposed absorption:** Block 6 (Contingency, 1.5h, Day 2). If it still overflows, the cut would
  be reducing the A/A loop from 1,000 to 500 seeds (still enough to estimate a ~5% false-positive
  rate with acceptable precision) — **never** cutting the power analysis or the assumption checks.
