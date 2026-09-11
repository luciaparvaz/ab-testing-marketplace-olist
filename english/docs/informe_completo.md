# Full project report
## A/B testing in a marketplace — does a product page redesign increase the average order value?

> Portfolio project · **CRISP-DM** methodology · public **Brazilian E-Commerce by Olist** dataset
> Reference document: walks through every phase, every methodological decision, the results
> (written as a thesis-style report), and the limitations. Meant so that someone who has not done
> the project can understand **what** was done, **how**, and **why**.

---

## Table of contents

1. [Summary](#1-summary)
2. [Introduction](#2-introduction)
3. [Phase 1 — Business Understanding](#3-phase-1--business-understanding)
4. [Phase 2 — Data Understanding](#4-phase-2--data-understanding)
5. [Phase 3 — Data Preparation](#5-phase-3--data-preparation)
6. [Phase 4 — Modeling: statistical design of the experiment](#6-phase-4--modeling-statistical-design-of-the-experiment)
7. [Phase 5 — Evaluation](#7-phase-5--evaluation)
8. [Phase 6 — Deployment](#8-phase-6--deployment)
9. [Results](#9-results)
10. [Limitations](#10-limitations)
11. [Discussion and conclusions](#11-discussion-and-conclusions)
12. [Future work](#12-future-work)
13. [Appendices](#13-appendices)

---

## 1. Summary

This project reproduces, end to end, the work of a product experimentation team evaluating a
change in a marketplace: a **product page redesign** (*cross-sell* recommendations and a progress
bar toward free shipping) whose hypothesis is that it **increases the average order value (AOV)**
without harming customer satisfaction or the cancellation rate.

The work follows the six phases of **CRISP-DM** and uses the public *Brazilian E-Commerce by
Olist* dataset (~100,000 orders, 2017-2018). Since the dataset **does not contain a real
experiment**, the control/treatment assignment is **simulated** (50/50 per customer, fixed seed)
and the redesign's effect is **injected in a declared way** via a *diluted* model (20% of treated
users respond with a +25% lift, for a mean effect of +5%). As a consequence, **the project does
not claim to discover anything about Olist**: it demonstrates that the **design, analysis, and
decision process** is correct —it controls false positives, recovers an effect of known size
without bias, separates statistical significance from business relevance, and withstands
*p-hacking*—.

**Main result.** The A/B test estimates an AOV increase of **+5.7%** (winsorized primary metric;
95% CI [+4.0%; +7.3%]; p ≈ 3·10⁻¹¹) or **+6.1%** on the unwinsorized metric (95% CI [+4.1%;
+8.1%]). Both intervals contain the true injected effect (+5%) and lie **entirely above** the
business relevance threshold (+3%). No guardrail is degraded and the effect is homogeneous across
segments. The decision rule returns **LAUNCH**.

**Methodological findings** (byproducts of the exercise, not of Olist):

- **Effect heterogeneity barely costs power** in this case (< 0.2 pp): the AOV's natural variance
  (CV ≈ 1.5) dominates the variance added by concentrating the effect in 20% of users.
- **Under H1 the group variances are not equal** (the multiplicative effect inflates the
  *treatment* group's variance; Levene p = 1.6·10⁻⁶) → the primary test is **Welch's t, not
  Student's**.
- **Winsorization, chosen to reduce variance, introduces a point bias of −0.36 pp** in the lift
  estimator; both the raw (unbiased) and the winsorized versions are reported.
- **At large n, any real regression is significant** → the guardrail rule needs **two gates**
  (significant **AND** magnitude ≥ threshold), not one.
- **Correcting for multiple comparisons does not save a badly posed estimand**: measuring the
  effect in absolute value (R$) over cuts correlated with basket size fabricates false "winning
  segments" that survive even Bonferroni; on the correct scale (percentage) nothing remains.

---

## 2. Introduction

### 2.1 Motivation and goal

The goal is to build a portfolio project on **A/B testing in an e-commerce/marketplace context**
that reflects the language and competencies of Data / Product Analyst postings: SQL, Python,
experimental design, stakeholder communication, and business metrics (conversion, retention,
revenue). The project is deliberately different from a prior A/B testing project in a gaming
context, both in domain and in the depth of the statistical design.

### 2.2 Methodology: CRISP-DM

The whole project is organized into the six phases of CRISP-DM, without merging them and keeping
traceability:

| Phase | Content in this project |
|---|---|
| 1 · Business Understanding | Problem, hypothesis, primary metric, guardrails, MDE, decision rule, simulation design |
| 2 · Data Understanding | Provenance and license, profiling aimed at the question, validity limitations |
| 3 · Data Preparation | Cleaning aimed at the question, analytical table, simulated assignment, *balance check* |
| 4 · Modeling | Statistical design: *power analysis*, assumption checks, A/A calibration, test execution |
| 5 · Evaluation | Significance vs. relevance, economic impact, segment analysis, decision |
| 6 · Deployment | Communication: executive summary, notebook, README, LinkedIn draft |

### 2.3 The central constraint: the experiment is simulated

The Olist dataset **starts at the order already placed**: it contains no sessions, visits, or
carts, and of course it contains no experiment with control and treatment groups. Given this, two
decisions run through the whole project:

1. **The primary metric is the AOV**, not conversion, because conversion would require a
   population of "non-buyers" that the dataset does not have and that **fabricating would be
   unacceptable**.
2. **The assignment is simulated and the effect is injected in a declared way.** The central
   parameter is δ (the mean effect), set at **+5%**. The analysis is run "blind" with respect to δ.

The project therefore reads as a **demonstration of method**: we know the truth (we put it there
ourselves) and we check that the statistical machinery recovers it. This note appears prominently
in every deliverable.

### 2.4 How the project is built and how it is reproduced

- **`params.yaml`** — single source of truth for all parameters (seed, α, effect, window, number
  of simulations, cost model).
- **`src/config.py`** — loads `params.yaml`, adds absolute paths and derived values. No other
  module defines constants (there is a test that verifies this).
- **`src/`** — one file per CRISP-DM phase (`profiling_fase2.py`, `figures_fase2.py`,
  `prepare_data.py`, `balance_check.py`, `mde_cost_model.py`, `modeling.py`, `evaluation.py`) plus
  `effect_model.py` (the synthetic effect, shared).
- **`run_all.py`** — single *entrypoint*: runs the six phases in order, verifies that each one
  generates its outputs, and finishes with a **reproducibility report** that checks 10 invariants
  (decision == LAUNCH, A/A false-positive rate in [3.5%; 6.5%], A/B CI above the MDE, no SRM,
  guardrails intact...). Exits with code ≠ 0 if something fails. ~2 min.
- **`notebooks/ab_test_olist.ipynb`** — **presentation** layer: only reads `outputs/` and shows
  figures and narrative; it computes nothing.
- **`tests/`** — `pytest` (fast) + `pytest -m slow` (re-runs and checks bit-for-bit idempotency).

```bash
pip install -r requirements.txt
python -m kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip
python run_all.py     # ~2 min
pytest
```

All the seeds are fixed → the result is deterministic.

---

## 3. Phase 1 — Business Understanding

> Source document: `docs/01_business_understanding.md`. All decisions in this phase are made
> **before looking at the data**.

### 3.1 Business context

Olist is a marketplace that connects small and medium Brazilian sellers with the country's large
online sales channels. The customer places an order —which may contain products from several
sellers— and, after delivery, leaves a review from 1 to 5. The dataset covers ~100,000 orders
between 2016 and 2018, across 9 relational tables.

### 3.2 The product lever evaluated

The Product team (the *Checkout & Conversion* squad) proposes a **product page redesign** that
combines:

1. A **"products often bought together" recommendations** module (*cross-sell*) on the page and
   in the cart.
2. A **progress bar toward free shipping**, activated above an amount threshold.

**Product hypothesis:** both elements push the customer to add items, so an **AOV increase** is
expected with no deterioration in satisfaction or cancellations.

### 3.3 Decision D1 — Primary metric = AOV, not conversion

| | |
|---|---|
| **Decision** | The success metric is the **merchandise value per order** (AOV) = Σ `order_items.price` per `order_id`, excluding freight. |
| **Rationale** | The dataset starts at the order: there is no traffic or "non-buyers", so conversion is not rigorously measurable. The AOV is, and it directly captures the cross-sell's expected effect. Also, revenue = AOV × volume, so it is a first-order business metric. |
| **Discarded alternatives** | (a) Simulating a traffic layer with non-buyers → rejected for **fabricating data**. (b) Switching to a dataset with real conversion (Criteo Uplift, Hillstrom) → discarded because its lever is a marketing send, not an *on-site* marketplace change. |
| **Cost** | The project does not demonstrate e-commerce's most typical funnel metric. Explicitly accepted. |

Freight is excluded from the metric because the redesign does not move it; it is monitored **as a
guardrail** (G3).

### 3.4 Decision D2 — Randomization unit = customer; analysis unit = 1 order/customer

| | |
|---|---|
| **Decision** | Randomize by `customer_unique_id`; in the main analysis keep each customer's **first order**. |
| **Rationale** | Randomizing by customer prevents two orders from the same person from falling into different groups (contamination; would violate SUTVA). Deduplicating to one order per customer makes **randomization unit = analysis unit**, which removes the need for clustered standard errors. Phase 3 verifies the cost is marginal (the mean AOV moves −0.35%; 3.3% of orders are lost). |
| **Alternative** | Keep all orders + customer-clustered SE. Equally valid; the simple one is chosen and the other is reported as robustness (Phase 4, §6.8). |
| **Ratio** | 50/50 (maximum power for a fixed total size). |

### 3.5 Decision D3 — Hypotheses, two-sided test, α = 0.05

| | Business formulation | Statistical formulation |
|---|---|---|
| **H0** | The redesign does not change the mean AOV | μ_T − μ_C = 0 |
| **H1** | The redesign changes the mean AOV | μ_T − μ_C ≠ 0 |

**Two-sided** —not one-sided, which would give more power— is chosen because the redesign *could
also lower* the AOV (e.g. if the "free shipping" focus makes the customer cap their spend at the
threshold), and that outcome must be formally detectable. α = 0.05 is the industry standard.

### 3.6 Decision D4 — Guardrails and the two-gate rule

Control metrics that **must not degrade**:

| Guardrail | Definition | Alarm threshold |
|---|---|---|
| **G1** — Satisfaction | mean `review_score` (1-5) | Significant drop **AND** magnitude ≥ 0.05 pts |
| **G2** — Cancellation | % of `order_status == 'canceled'` orders | Significant rise **AND** relevant magnitude |
| **G3** — Freight absorbed | mean `freight_value` per order | Significant rise absorbing part of the AOV increase |
| **G4** — Frequency | Number of items per order / orders per customer | Significant drop |

**Two-gate rule.** At n ≈ 47,000 per group, *any* real regression is statistically significant
(Phase 4, §6.8, shows that a −0.03 pt drop in `review_score` gives p ≈ 0.001). A rule of the type
"significant **OR** magnitude" would block the launch over sub-threshold noise. **Significant AND
magnitude ≥ threshold** is therefore required.

The guardrail family is tested with the **Benjamini-Hochberg (FDR) correction**, not Bonferroni:
the goal is to control the false discovery rate while keeping power over a set of monitoring
tests, not the strict FWER. The primary metric, being a single pre-specified test, **does not
enter** the correction.

### 3.7 Decision D5 — Relevance MDE = +3%, derived from a cost model

Statistical significance is not enough: it is necessary to fix **what effect size justifies the
cost** of building and maintaining the redesign. The relevance *minimum detectable effect* is set
at **+3% relative over the base AOV** and is **derived** (not asserted) from a *break-even* model
(`src/mde_cost_model.py`):

```
breakeven_lift = total_cost / (AOV · order_volume · commission · margin · years)
```

With illustrative assumptions (AOV R$ 137, commission 15%, net margin on commission 80%, build R$
250,000, maintain R$ 80,000/year, 2-year horizon), the *break-even* **falls as order volume
rises**:

| Orders/year | *Break-even* (2-year payback) |
|---:|---:|
| 58,700 (the dataset itself) | **+21.2%** |
| 250,000 | +5.0% |
| 1,000,000 | +1.25% |
| 5,000,000 | +0.25% |

Conclusion: the **+3% is valid for a marketplace with ≥ ~415,000 orders/year**. The project
assumes that scale (medium-large marketplace). Figure: `outputs/figures/f_mde_breakeven.png`.

### 3.8 Decision D6 — Product decision rule

| Result | Decision |
|---|---|
| Significant primary effect (p < 0.05) **and** 95% CI of the *lift* **entirely above** +3% **and** no guardrail degraded | **LAUNCH** |
| Positive and significant effect **but** the 95% CI includes values below +3% | **ITERATE** (the effect is real but not conclusively relevant) |
| Non-significant or negative effect, or any guardrail degraded | **DO NOT LAUNCH** |

The **ITERATE** branch avoids the binary launch/don't-launch and anchors the decision on the
**confidence interval** against the business threshold, not on the point estimate.

### 3.9 Decision D7 — Simulation design: A/A + diluted A/B

**Two experiments** are run:

**(a) A/A test** — random 50/50 assignment, **with no metric modified**. Purpose: empirically
demonstrate that the pipeline **does not generate false positives** before introducing any effect.
Repeated over **2,000 random partitions**: the H0 rejection rate at α = 0.05 should be around 5%
and the p-value distribution should be uniform (Kolmogorov-Smirnov test).

**(b) A/B test — diluted synthetic treatment effect.** **Partial adoption** model: for each order
`i` in the *treatment* group:

```
R_i  ~ Bernoulli(p_resp = 0.20)
if R_i = 1:  aov_T_i = aov_C_i · (1 + δ_resp + ε_i),   δ_resp = 0.25,  ε_i ~ N(0, 0.05)
if R_i = 0:  aov_T_i = aov_C_i   (no change)
```

| Parameter | Value | Meaning |
|---|---|---|
| `p_resp` | 0.20 | 20% of the treated units respond |
| `δ_resp` | 0.25 | responders spend +25% more |
| **ATE** (mean effect) | **`p_resp · δ_resp` = 0.05 → +5%** | matches the declared δ |
| Seed | `SEED = 42` | reproducibility |

Responders are drawn **at random, independent of the order's value** (keeps the ATE clean). The
diluted model (over a uniform multiplicative one) was chosen because **it is more realistic**: a
redesign only moves a fraction of users.

---

## 4. Phase 2 — Data Understanding

> Source document: `docs/02_data_understanding.md`. Script: `src/profiling_fase2.py`.

### 4.1 Provenance, license, and structure

| | |
|---|---|
| Source | *Brazilian E-Commerce Public Dataset by Olist* — Kaggle (`olistbr/brazilian-ecommerce`) |
| License | **CC BY-NC-SA 4.0** (verified on download). Non-commercial use; the raw CSVs **are not versioned** in the repository. |
| Size | 9 relational CSVs, ~42MB compressed; **99,441 orders** |

Tables and volumes:

| Table | Rows | Use in the experiment |
|---|---:|---|
| `olist_orders_dataset` | 99,441 | backbone: status, timestamps |
| `olist_order_items_dataset` | 112,650 | **primary metric** (`price`, `freight_value`) |
| `olist_order_payments_dataset` | 103,886 | payment type; amount robustness |
| `olist_order_reviews_dataset` | 99,224 | **guardrail G1** (`review_score`) |
| `olist_customers_dataset` | 99,441 | **randomization unit** (`customer_unique_id`) |
| `olist_products_dataset` | 32,951 | category (segmentation) |
| `olist_sellers`, `olist_geolocation`, `product_category_name_translation` | — | context / translation; geolocation not used |

### 4.2 Decision D8 — Time window 2017-01 → 2018-08

The raw range is 2016-09 to 2018-10, but 2016 is token (2016-11 is empty) and Sept-Oct 2018 have
few orders (export cutoff). It is restricted to the **stable window 2017-01 → 2018-08**. Phase 3
verifies this **does not change the mean AOV** (R$ 137.42 → R$ 137.37) and does not introduce
bias: it is an adjustment **for realism** (making the duration resemble an experiment), not
corrective. Figure: `f2_01_volumen_mensual.png`.

### 4.3 Primary metric profiling (AOV)

Valid orders (status in {delivered, shipped, invoiced, approved, processing} and with at least one
item): **n = 98,199 orders / 94,983 unique customers**.

| Statistic | `merch_value` (AOV) | `log(AOV)` |
|---|---:|---:|
| mean | **R$ 137.42** | 4.44 |
| median | R$ 86.90 | — |
| std. dev. | R$ 209.31 | 0.93 |
| **CV (σ/μ)** | **1.523** | 0.21 |
| p99 / max | R$ 995 / R$ 13,440 | — |
| **skew** | **9.77** | **0.24** |
| kurtosis (excess) | 271.4 | 0.34 |

**Key readings** (they shape Phase 4):

1. The raw AOV is **extremely skewed and leptokurtic** (tail up to R$ 13,440 versus a median of
   R$ 87). Figure: `f2_02_distribucion_aov.png`.
2. The log transform brings the skewness and kurtosis into a **robust range** (skew 0.24; kurtosis
   0.34). It is still formally not normal (D'Agostino p < 10⁻²⁰ at n = 5,000), but that is
   irrelevant: at large n the **mean** is normal by the Central Limit Theorem.
3. The t-test on `log(AOV)` tests the **ratio of geometric means** (≈ median), which is a
   *different* business question, not the AOV. It is included as **robustness**, not as the
   primary.

### 4.4 Guardrail profiling

| Guardrail | Base value | Notes |
|---|---|---|
| G1 · `review_score` | mean **4.12** / 5 · σ 1.32 · **99.3% coverage** | Inverted-U distribution (58% are 5★, 11% are 1★) → not normal |
| G2 · cancellation rate | **0.63%** overall | Rare event → proportion (z) test; low power |
| G3 · `freight_value` | mean **R$ 22.82** / order | Watch that an AOV rise does not come with more absorbed freight |

### 4.5 Randomization unit characterized

| | |
|---|---:|
| Unique customers (valid) | 94,983 |
| With exactly 1 order | **96.96%** |
| % of orders from repeat customers | 6.21% |
| Max. orders from one customer | 16 |

→ Randomizing by `customer_unique_id` is **almost equivalent** to randomizing by order;
deduplicating to one order per customer is a marginal-cost simplification.

### 4.6 Data quality (handled in Phase 3)

- 775 orders with no items (mostly `unavailable` / `canceled`) → excluded from the primary metric.
- 814 duplicate `review_id`; 551 orders with >1 review → the most recent by
  `review_answer_timestamp` is kept.
- 1 valid order with no payment record (irrelevant for the primary metric).
- AOV tail outliers → declared winsorization (§5.4).

### 4.7 Identified validity limitations

1. **No real randomization or traffic layer** → conversion is not measured; the effect is
   simulated.
2. **Treatment effect not observed in covariates:** by simulating, the redesign can only act on
   the metric we perturb; in reality it would also affect the category mix, the return rate, etc.
3. **2-year historical window**, not a 2-4 week experiment (mitigated by restricting the window
   and balancing seasonality by design).
4. **Very low repeat purchase (~3% of customers)** → no primary retention metric possible.
5. **Survivorship bias** in reviews (customer self-selection).
6. **Single market** (Brazil, 2017-2018) → no external validity outside that context.

---

## 5. Phase 3 — Data Preparation

> Source document: `docs/03_data_preparation.md`. Scripts: `src/prepare_data.py`,
> `src/balance_check.py`. Cleaning **aimed at the experimental question**, not generic EDA.

### 5.1 Chain of transformations (traced in `fase3_transformaciones.csv`)

| Step | n before | n after | Δ | Rationale |
|---|---:|---:|---:|---|
| Raw (`olist_orders`) | 99,441 | 99,441 | — | — |
| **Time window** [2017-01-01, 2018-09-01) | 99,441 | 99,092 | −349 | Removes the residual start-up and the incomplete tail (adjustment for realism, not corrective). |
| **Valid statuses** {delivered, shipped, invoiced, approved, processing} | 99,092 | 97,905 | −1,187 | A paid order is a "completed purchase"; `canceled` / `unavailable` / `created` are excluded. |
| **Orders with items** | 97,905 | 97,905 | 0 | Orders with no lines were already dropped with the invalid statuses. |
| **Dedup to 1 order/customer** (the first) | 97,905 | **94,703** | −3,202 | Randomization unit = analysis unit. |

**Final analytical table: 94,703 rows × 15 columns** (`data/processed/analytical_table.parquet`),
grain = 1 order-customer.

### 5.2 Enrichment (constructed variables)

| Column | Construction | Use |
|---|---|---|
| `merch_value` | Σ `order_items.price` per order | **primary metric** (descriptives) |
| `merch_value_w` | `merch_value` clipped at **p99.5** | **primary metric for the significance test** |
| `freight_value` · `n_items` | Σ / count per order | guardrails G3, G4 / covariate |
| `review_score` | most recent review by timestamp | guardrail G1 |
| `cat_dominante` | category (EN) of the most expensive item | covariate / segmentation |
| `payment_type` | type of the row with the highest `payment_value` | covariate / segmentation |
| `customer_state`, `mes_compra` | from `olist_customers` / truncated to month | balance covariates |
| `is_delivered` | `order_status == 'delivered'` | sensitivity analysis |
| `group` | see §5.6 | experiment arm |

`review_score` has 696 nulls (0.73%) → complete-case analysis for G1; the potential bias is
negligible at that percentage.

### 5.3 The Olist *gotcha* — resolved explicitly

`orders.customer_id` is **unique per order** (99,441 values for 99,441 rows); the real person is
`customers.customer_unique_id` (96,096 distinct values). The whole pipeline —dedup, assignment,
customer counting— uses `customer_unique_id`. It is the most common error when working with this
dataset and is verified in the audit.

### 5.4 Decision D9 — Winsorization at p99.5, only for the significance test

| | |
|---|---|
| **Decision** | `merch_value_w` clips the AOV at the 99.5th percentile (cap ≈ R$ 1,360; **473 orders, 0.50%**). The descriptive AOV is reported **unwinsorized** (R$ 137.42). The test is reported **with and without**. |
| **Rationale** | The extremely heavy tail (max R$ 13,440; kurtosis 271) inflates the variance and costs power. Winsorizing reduces the CV from 1.52 to 1.28. It is done **only for the significance test** because winsorizing shifts the mean by −2.4% and must not contaminate the descriptive statistics. |
| **How the researcher degree of freedom is managed** | The p99.5 threshold is **pre-specified in the audit before seeing results**, and the unwinsorized version is also reported (both give the same decision). Phase 4 (§6.8) finds that winsorization introduces a **−0.36 pp bias** in the estimator → both are reported. |

### 5.5 Decision — Review dedup by `review_answer_timestamp`

551 orders have >1 review. Deduplicating "by last CSV row" vs. "by most recent timestamp" changes
the score for 100 orders, with no impact on the mean (4.087 vs. 4.086). Even so, deduplication is
done **by timestamp** (the principled criterion).

### 5.6 Simulated random assignment

- **Mechanism:** `numpy.random.default_rng(SEED=42).choice(["control", "treatment"])` per row.
- **Result:** control = **47,280** · treatment = **47,423** (50.08% *treatment* — the expected
  deviation from 50% by chance).
- **The treatment effect is NOT injected at this phase.** The table comes out with the metric
  intact.

### 5.7 *Covariate balance check* + SRM (`src/balance_check.py`)

Criteria: **|SMD| < 0.10** per covariate and **omnibus test not significant**.

| Covariate | SMD | Test | p-value |
|---|---:|---|---:|
| `n_items` | −0.004 | Welch-t | 0.579 |
| `freight_value` | 0.007 | Welch-t | 0.305 |
| `customer_state` (27) | 0.013 | χ² (dof 26) | 0.919 |
| `cat_dominante` (72) | 0.020 | χ² (dof 71) | 0.320 |
| `payment_type` (4) | 0.009 | χ² (dof 3) | 0.623 |
| `mes_compra` (20) | 0.015 | χ² (dof 19) | 0.693 |

**All |SMD| ≤ 0.02** and **no omnibus test significant** (minimum p 0.32). Figure:
`f3_01_balance.png` (love-plot).

**SRM check (Sample Ratio Mismatch).** χ² of the observed split (47,280 / 47,423) against 50/50:
**χ² = 0.216; p = 0.642** → the split is compatible with 50/50, with no sign of differential unit
leakage.

**Point A/A check on the outcome.** With the declared seed, the mean AOV differs by +1.2% between
groups (Welch-t p = 0.235) — **sampling noise**. It is a reminder that a raw ~1% difference
between two random groups is normal, and that the decision must rest on the test and the CI, not
on the eye. This baseline imbalance of seed 42 propagates to the A/B point estimator (see §9).

---

## 6. Phase 4 — Modeling: statistical design of the experiment

> Source document: `docs/04_modeling.md`. Script: `src/modeling.py` (600 lines, 9 blocks).
> In CRISP-DM, "Modeling" here = **designing and executing the statistical test**.

### 6.1 A priori power analysis

With n ≈ 47,000 per group, α = 0.05 two-sided, target power 0.80:

| Metric | mean | CV | **Detectable MDE** |
|---|---:|---:|---:|
| Raw AOV | R$ 137.85 | 1.531 | **+2.79%** |
| p99.5 winsorized AOV | R$ 134.49 | 1.282 | **+2.34%** |

Both below the relevance MDE (+3%). The power for the declared effect (+5%) is **≈ 100%** on both
metrics, and the estimator is **unbiased** (mean of 1,000 simulated replicates: 4.999% raw,
5.006% winsor).

### 6.2 Does the diluted effect cost power? (finding)

Phase 1's prediction: concentrating the effect in 20% of users inflates the *treatment* group's
variance and could lower power. **Verified by simulation:** the penalty is **< 0.2 pp** at the
experiment's n and **< 1 pp** across the whole n grid tested (400 → 47,000 per group). Reason: the
variance added by dilution (≈ 1.4% of the total variance) is tiny compared to the AOV's natural
variance (CV ≈ 1.5). **The intuition is correct in direction but irrelevant in magnitude.** Figure:
`f4_04_power_vs_n.png`.

### 6.3 Assumption checks → Welch, not Student

| Assumption | Test | Result | Verdict |
|---|---|---|---|
| Normality of the **data** | D'Agostino K² | K² = 5,453; p ≈ 0 | **Not normal** (expected) |
| Normality of the **mean** (CLT) | D'Agostino over 5,000 bootstrap means | K² = 0.38; **p = 0.826** | **Compatible with normal → the t-test is valid** |
| Homoscedasticity **without effect** (A/A) | Levene (median-centered) | stat = 1.61; p = 0.205 | Equal variances (expected) |
| Homoscedasticity **with diluted effect** | Levene | stat = 22.97; **p = 1.6·10⁻⁶** | Variances **unequal** under H1 → **use Welch, NOT Student** |
| Independence | by design | random assignment + dedup to 1 order/customer | No intra-customer correlation; SUTVA assumed |

The primary test is **Welch's t**: the check shows that under H1 the group variances are not
equal, exactly the case Welch is designed for. Figure: `f4_01_tcl_normalidad.png`.

### 6.4 A/A calibration — 2,000 random partitions

For each of 2,000 50/50 partitions (no effect), Welch-t on the metric and the p-value is logged.
Criterion: a 95% CI of the false-positive rate that contains 0.05 **and** uniform p-values
(Kolmogorov-Smirnov).

| Metric | False positives (α = 0.05) | 95% CI | KS vs. uniform (p) | Verdict |
|---|---:|---:|---:|:--:|
| Raw AOV | **4.95%** | [3.99%; 5.91%] | 0.53 | ✅ calibrated |
| p99.5 winsor AOV | **5.00%** | [4.04%; 5.96%] | 0.93 | ✅ calibrated |
| log(AOV) | **5.00%** | [4.04%; 5.96%] | 0.72 | ✅ calibrated |

Figure: `f4_02_aa_pvalores.png` (flat p-value histogram). **The pipeline does not generate false
positives and the p-values are calibrated.**

### 6.5 A/B test — diluted effect injected (SEED = 42)

| Test | AOV lift | 95% CI | p-value |
|---|---:|---:|---:|
| **Welch · raw AOV** | **+6.11%** | [+4.09%; +8.13%] | 3.1·10⁻⁹ |
| **Welch · p99.5 winsor AOV** | **+5.67%** | [+3.99%; +7.34%] | 3.1·10⁻¹¹ |
| Bootstrap (10,000, no assumptions) | — | [+4.05%; +8.19%] | — |
| log · ratio of geometric means | +4.79% | — | 1.4·10⁻¹⁴ |
| Mann-Whitney (stochastic dominance) | — | — | 1.8·10⁻¹⁵ |

**All intervals contain the true effect (+5%).** The point estimate lands above 5% because this
particular *split* has the +1.2% of baseline imbalance described in §5.7. Figure:
`f4_03_ab_efecto.png`.

### 6.6 Guardrails (Benjamini-Hochberg, no effect injected)

| Guardrail | control | treatment | raw p | **adjusted p (BH)** | Degraded? |
|---|---:|---:|---:|---:|:--:|
| G1 · review_score | 4.114 | 4.116 | 0.80 | 0.80 | ❌ no |
| G2 · cancellation rate | 0.541% | 0.570% | 0.56 | 0.77 | ❌ no |
| G3 · freight_value | R$ 22.74 | R$ 22.89 | 0.30 | 0.77 | ❌ no |
| G4 · number of items | 1.140 | 1.138 | 0.58 | 0.77 | ❌ no |

**No guardrail degrades.** This is the expected result: the design only injects an effect into the
primary metric. The guardrail tests' real ability to **catch** a regression is verified separately
(§6.8).

### 6.7 Decision sweep — the three branches of the rule

Applying the LAUNCH / ITERATE / DO NOT LAUNCH rule to different injected effect sizes (winsorized
primary metric; guardrails OK; this *split* has +1.2% of baseline imbalance):

| Injected ATE | observed lift | 95% CI | p-value | **Decision** |
|---:|---:|---:|---:|:--:|
| 0% | +1.01% | [−0.63%; +2.65%] | 0.227 | **DO NOT LAUNCH** |
| 1% | +1.95% | [+0.30%; +3.60%] | 0.020 | **ITERATE** |
| 2% | +2.89% | [+1.23%; +4.54%] | 6·10⁻⁴ | **ITERATE** |
| 3% | +3.82% | [+2.16%; +5.48%] | 6·10⁻⁶ | **ITERATE** |
| 4% | +4.75% | [+3.08%; +6.41%] | 2·10⁻⁸ | **LAUNCH** |
| **5% (declared)** | **+5.67%** | **[+3.99%; +7.34%]** | **3·10⁻¹¹** | **LAUNCH** |
| 8% | +8.40% | [+6.71%; +10.09%] | 2·10⁻²² | **LAUNCH** |

The design **reaches all three decisions**.

### 6.8 Additional robustness

**Multi-seed A/B (500 replicates).** The full A/B test (re-*split* + re-injection) is repeated
over 500 seeds, on raw and on winsorized data:

| | mean lift | bias | p2.5-p97.5 | 95% CI coverage of the real +5% |
|---|---:|---:|---:|---:|
| Raw AOV | +4.97% | **−0.03 pp** | [+2.9%; +7.1%] | **0.94** |
| p99.5 winsor AOV | +4.64% | **−0.36 pp** | [+2.9%; +6.2%] | **0.92** |

On raw data the estimator is **unbiased** and the CI has nominal coverage. Winsorization
introduces a **small negative bias** (it clips more of the *treatment* group's high values, which
grew because of the multiplicative effect) in exchange for lower variance; its CI slightly
under-covers. The +5.7% of the SEED = 42 split falls within the p2.5-p97.5 range → it is a normal
realization.

**Regression injected into a guardrail.** An additive drop is injected into `review_score` only in
the *treatment* group, and the two-gate rule is applied:

| Injected regression | observed diff | p-value | Sig.? | Magnitude ≥ 0.05? | "OR" rule | **"AND" rule** |
|---:|---:|---:|:--:|:--:|:--:|:--:|
| 0.00 | +0.002 | 0.80 | ❌ | ❌ | does not block | **does not block** ✅ |
| −0.03 | −0.028 | 0.001 | ✅ | ❌ | blocks (false) | **does not block** ✅ |
| −0.05 | −0.048 | 3·10⁻⁸ | ✅ | ❌ (just below) | blocks | does not block (borderline) |
| −0.08 | −0.078 | 2·10⁻¹⁹ | ✅ | ✅ | blocks | **blocks** ✅ |

At large n any real regression is significant; the "OR" rule would block over sub-threshold noise,
the "AND" rule lets −0.03 through (correct) and catches −0.08 (correct).

**Variant with a truly heterogeneous effect.** Effect concentrated in orders below a hypothetical
free-shipping threshold (R$ 150; 22.4% of orders): lift **+7.05% within the band** vs. +1.52%
outside; `treatment × band` interaction test (log, HC3) **p = 2·10⁻¹⁵**. **The design detects the
real heterogeneity**, unlike the main analysis (homogeneous effect → no interaction).

**All orders + customer-clustered SE.** With the 97,905 non-deduplicated orders and
customer-clustered standard errors: lift **+5.71%** (vs. +5.67% deduplicated); clustering
**inflates the SE by only 1.1%** (97% of customers have one order). Deduplicating was the simple
and correct option.

---

## 7. Phase 5 — Evaluation

> Source document: `docs/05_evaluation.md`. Script: `src/evaluation.py`.

### 7.1 Statistical significance ≠ business relevance

| Question | Criterion | Result |
|---|---|---|
| Is it **statistically** significant? | p < 0.05 | **Yes** (p ≈ 3·10⁻¹¹) |
| Is it **relevant for the business**? | 95% CI of the *lift* **entirely above** the MDE (+3%) | **Yes** — CI [+3.99%; +7.34%] (winsor) and [+4.09%; +8.13%] (raw) |

With n ≈ 47,000 per group, even a trivial effect would come out "significant". What makes this
result **actionable** is that **the entire confidence interval is above the business relevance
threshold**, not just the point estimate.

### 7.2 Estimated economic impact

| | Value |
|---|---|
| Valid orders/year (historical extrapolation) | ≈ 58,700 |
| Annual merchandise GMV (base) | ≈ R$ 8.05M |
| **Annual GMV uplift** | **+R$ 456,000** · 95% CI [+R$ 322,000; +R$ 591,000] |
| Marketplace revenue uplift (assumed 15% commission) | ≈ +R$ 68,000/year |

Linear extrapolation of the per-order *lift* to the annual volume; real revenue depends on the
*take rate*.

### 7.3 Covariate-adjusted estimate (ANCOVA)

OLS `AOV_w ~ treatment + n_items + freight + category + macro-region + quarter` (HC3 errors):

| | Lift | 95% CI | SE (R$) |
|---|---:|---:|---:|
| Unadjusted | +5.67% | [+3.99%; +7.34%] | 1.141 |
| **Adjusted** | **+5.19%** | **[+3.71%; +6.68%]** | **1.013** |

The adjustment **reduces the standard error by 11.2%** (model R² ≈ 0.20) and brings the estimator
closer to the true +5%. The SE reduction is the robust benefit; the point shift is partly specific
to this sample and is not sold as a general property.

### 7.4 Segment analysis — pre-specified and corrected

**Segments declared BEFORE looking at results:** `cesta` (1 vs. 2+ items), `payment_type`,
`macro_region` (5 macro-regions), `trimestre`, `cat_grupo` (top 6 categories + rest).

> "New vs. repeat customer" is **out of scope**, declared: dedup to 1 order/customer leaves it
> degenerate (n_repeat ≈ 40) and repeat purchase at Olist is ~3%.

`treatment × segment` interaction test on **log(AOV)**, **HC3** Wald (relative effect):

| Segment | raw p | adjusted p (BH) | Heterogeneous? |
|---|---:|---:|:--:|
| cesta | 0.92 | 0.92 | ❌ |
| payment_type | 0.38 | 0.92 | ❌ |
| macro_region | 0.68 | 0.92 | ❌ |
| trimestre | 0.79 | 0.92 | ❌ |
| cat_grupo | 0.14 | 0.68 | ❌ |

**No interaction is significant.** The **relative** effect is homogeneous across segments,
consistent with the design (responders are drawn at random). Figure:
`f5_01_forest_segmentos.png`.

> **Why the test is run in `log` and not at the level scale:** the effect is multiplicative, so
> the **absolute** lift in R$ is mechanically larger in large baskets. A level-scale test would
> detect that "heterogeneity" which is not real — the business question is whether the
> **percentage** changes.

### 7.5 The risk of p-hacking — demonstrated

**38 arbitrary exploratory cuts** are tested (individual states, individual categories, freight
quartiles, quarters). Test: `treat × cut` interaction, HC3 Wald. Expected by pure chance at
α = 0.05: **≈ 1.9**.

| Test scale | Nominal p < 0.05 | After BH (FDR) | After Bonferroni |
|---|---:|---:|---:|
| **Level (R$)** | **5** (3 in freight quartiles) | **3** | **2** |
| **Log (relative effect, %)** | 2 | **0** | **0** |

**Lessons:**

1. At the **level** scale, several "segments where the effect differs" **survive even
   Bonferroni**. They are not chance: they are a **mechanical artifact** of the multiplicative
   effect (the *lift* in R$ is larger in large baskets), concentrated in the cuts correlated with
   size (freight quartiles).
2. At the **log** scale (the correct magnitude), only chance-level nominal findings remain and
   **none survives** the correction.
3. → **(a)** test the correct magnitude (%, not absolute R$); **(b)** pre-specify the segments;
   **(c)** correct for multiplicity. **Correcting is not enough if the estimand is wrong to begin
   with.**

### 7.6 Product decision

> # 🟢 LAUNCH

| Criterion | ✔ |
|---|---|
| Significant primary effect (p ≈ 3·10⁻¹¹) | ✅ |
| 95% CI of the *lift* entirely above the MDE (+3%) | ✅ [+3.99%; +7.34%] |
| Robust estimate (winsor, log, bootstrap, ANCOVA all agree) | ✅ |
| No guardrail degraded (G1-G4, Benjamini-Hochberg) | ✅ |
| Homogeneous relative effect across pre-specified segments | ✅ |
| Material economic impact (+R$ 456k/year GMV) | ✅ |

**Declared caveats:**

- The effect is **synthetic and known**: this decision **validates the decision process**, it does
  not constitute a real finding about Olist.
- With an injected ATE of +2% or +3%, the same rule would have returned **ITERATE**; with +0%,
  **DO NOT LAUNCH**. All three branches work.

**What to watch after a real launch:** the AOV at 4 weeks against the +3% minimum; the return and
complaint rate (not measurable in Olist); review again at 90 days to rule out the effect diluting
due to novelty.

---

## 8. Phase 6 — Deployment

> Source document: `docs/06_deployment.md`.

In a portfolio project, "deployment" is **communicating the result** to its audiences:

| Deliverable | File | Audience |
|---|---|---|
| Executive summary (1 page) | `docs/resumen_ejecutivo.md` | Non-technical stakeholder |
| Presentation notebook | `notebooks/ab_test_olist.ipynb` | Technical reviewer / recruiter |
| Repository README | `README.md` | GitHub visitor |
| LinkedIn post draft | `docs/linkedin_post.md` | Professional network |
| Per-phase documentation + audits | `docs/*.md` | Full trace of the reasoning |

**Reproducibility** (hardened after a review critique): `params.yaml` as the single source of
truth; `run_all.py` as the single *entrypoint* with a reproducibility report; the notebook reduced
to a read-only layer (no parallel execution path); a `pytest` suite with a bit-for-bit idempotency
test. Detail in section 2.4 and in `docs/06_deployment.md`.

**Chosen communication angle:** not "I ran an A/B test" (generic) but the **methodological
finding** that correcting for multiple comparisons does not protect against *p-hacking* if the
*estimand* is wrongly posed.

---

## 9. Results

> *Written as a thesis-style report: formal prose, past tense, with reference to tables and
> figures. All values come from `outputs/tables/*.json`, generated with a fixed seed.*

### 9.1 Sample description

After data preparation (section 5), the analytical sample consisted of **94,703 orders**, one per
customer, corresponding to the 2017-01-01 – 2018-08-31 time window. The random assignment produced
**47,280 units in the control group and 47,423 in the treatment group** (50.08%), a split
compatible with the 50/50 target ratio (χ² = 0.216; p = 0.642), with no sign of *Sample Ratio
Mismatch*. Covariate balance between groups was excellent: the six covariates considered (number
of items, freight value, customer state, dominant category, payment type, and purchase month)
showed standardized mean differences below 0.02 in absolute value, well under the conventional
0.10 threshold, and no omnibus test was significant (minimum p = 0.32). On the unperturbed primary
metric, a raw difference of +1.2% between groups was observed (Welch's t, p = 0.235), attributable
to the partition's sampling noise.

### 9.2 Validation of the experimental design

Before introducing any effect, an **A/A calibration** was performed, consisting of repeating the
test over 2,000 random 50/50 partitions of the sample. The false-positive rate at α = 0.05 was
4.95% for the raw AOV, 5.00% for the winsorized AOV, and 5.00% for the AOV on the log scale, in
all cases with a 95% confidence interval containing the nominal value of 0.05. The distribution of
the p-values was indistinguishable from a uniform one (Kolmogorov-Smirnov test, p ≥ 0.53 across
the three metrics; Figure `f4_02_aa_pvalores.png`). It is concluded that the analysis procedure
**does not generate false positives** and that its p-values are correctly calibrated.

The **a priori power analysis** determined that, with the available sample size (n ≈ 47,000 per
group), the minimum relative effect detectable at 80% power and α = 0.05 two-sided is +2.79% over
the raw AOV and +2.34% over the winsorized AOV, both below the business relevance threshold (+3%).
The power to detect the declared effect (+5%) was practically 100%. Through simulation (1,000
replicates) it was verified that **effect heterogeneity**, expected as a source of power loss, has
a negligible impact in this context: the power penalty from the diluted effect relative to a
uniform effect of the same mean size was below 0.2 percentage points at the experiment's size and
below 1 percentage point across the whole range of sample sizes examined (Figure
`f4_04_power_vs_n.png`). The effect estimator was unbiased in the simulation (mean of 1,000
replicates: 4.999% on the raw metric and 5.006% on the winsorized one).

In addition, the full A/B experiment —including the random re-partition and the re-injection of
the effect— was repeated over 500 seeds. On the raw metric the estimator was unbiased (mean bias
of −0.03 percentage points) and the 95% confidence interval covered the true effect in 94% of the
replicates, consistent with its nominal coverage. On the winsorized metric a **negative bias of
−0.36 percentage points** was detected and coverage dropped to 92%, because winsorization is more
likely to clip the treatment group's high values, inflated by the multiplicative effect. This bias
is the price of the variance reduction that winsorization provides, and it does not change the
decision, since both confidence intervals clear the relevance threshold. The point result obtained
with the main analysis's seed (+5.7%) falls within the extended interquartile range [p2.5; p97.5]
= [+2.9%; +7.1%] of the replicate distribution.

### 9.3 Test assumption checks

The AOV shows a strongly skewed (skewness coefficient = 9.77) and leptokurtic (excess kurtosis =
271.4) distribution, so the normality assumption for the observations is decisively rejected
(D'Agostino test, p ≈ 0). However, the **sampling distribution of the mean** is compatible with
normality (D'Agostino test on 5,000 bootstrap means of size n ≈ 47,000: K² = 0.38; p = 0.826), a
consequence of the Central Limit Theorem at this sample size. Levene's test for homogeneity of
variances between groups was not significant in the absence of an effect (p = 0.205) but **was
significant after the diluted effect was injected** (p = 1.6·10⁻⁶), reflecting that a
multiplicative effect applied to a fraction of the orders increases the treatment group's
variance. As a result, **Welch's t** was adopted as the primary test, instead of Student's t, for
its robustness to heteroscedasticity. Independence of the observations is guaranteed by design
(random assignment and deduplication to one order per customer), assuming no interference between
customers (SUTVA).

### 9.4 Main result

The primary test —Welch's t on the AOV winsorized at the 99.5th percentile— found an increase in
the mean order value in the treatment group of **+5.67%** (an absolute difference of R$ 7.58 per
order), with a 95% confidence interval of **[+3.99%; +7.34%]** and a p-value of **3.1·10⁻¹¹**
(t = 6.64; Welch degrees of freedom ≈ 94,405; n_control = 47,280, n_treatment = 47,423). On the
unwinsorized metric the estimated increase was **+6.11%** (95% CI [+4.09%; +8.13%]; p = 3.1·10⁻⁹).
The true injected effect (+5.0%) is **contained in both confidence intervals**. The point estimate
exceeds the injected value as a consequence of the partition's baseline imbalance described in
9.1 (+1.2%, not significant); the multi-seed analysis (9.2) confirms that the estimator is
unbiased under repetition.

The robustness analyses agreed: the bootstrap confidence interval (10,000 replicates, no
distributional assumption) was [+4.05%; +8.19%]; the test on the ratio of geometric means (log
scale) estimated a +4.79% (p = 1.4·10⁻¹⁴); and the Mann-Whitney test for stochastic dominance was
equally significant (p = 1.8·10⁻¹⁵). The **covariate adjustment** via ANCOVA (regression with
robust HC3 errors, R² ≈ 0.20) reduced the estimator's standard error by 11.2% and placed the
estimate at **+5.19%** (95% CI [+3.71%; +6.68%]), closer to the true value. Figure
`f4_03_ab_efecto.png` summarizes the point and interval estimates.

### 9.5 Guardrail metrics

None of the four control metrics showed degradation. After the Benjamini-Hochberg correction, the
mean review score (4.114 in control versus 4.116 in treatment; adjusted p = 0.80), the
cancellation rate (0.541% versus 0.570%; adjusted p = 0.77), the mean freight value (R$ 22.74
versus R$ 22.89; adjusted p = 0.77), and the mean number of items per order (1.140 versus 1.138;
adjusted p = 0.77) were statistically indistinguishable between groups. This result is expected,
given that the design injects the effect exclusively into the primary metric. The guardrail
tests' ability to detect a real regression was verified independently: the injection of a −0.08
point drop in the review score was correctly identified as degradation under the two-gate rule
(p = 2·10⁻¹⁹; magnitude ≥ 0.05), while a sub-threshold −0.03 point drop —statistically significant
at this sample size (p = 0.001) but below the relevance threshold— did not trigger the alarm, the
desired behavior.

### 9.6 Segment analysis

The effect heterogeneity analysis was carried out over five pre-specified segments (basket size,
payment type, macro-region, quarter, and category group), via `treatment × segment` interaction
tests on the log scale with robust HC3 errors and the Benjamini-Hochberg correction. **No test was
significant** (minimum raw p = 0.14; all adjusted p ≥ 0.68), indicating that the relative effect is
homogeneous across segments, consistent with the simulation design. Figure
`f5_01_forest_segmentos.png` shows the per-level estimates, all compatible with the global effect.

As a demonstration of the p-hacking risk, an exploratory sweep of 38 arbitrary sample cuts was then
performed. On the level scale (R$), five cuts showed a nominally significant interaction —versus
the ≈ 1.9 expected by chance— and three of them survived the Benjamini-Hochberg correction, two
even Bonferroni's; the affected cuts were concentrated in the freight-value quartiles, a variable
correlated with order size. These findings **are not the product of chance but an artifact of the
multiplicative effect**, which produces a larger absolute increase in higher-value orders.
Repeating the analysis on the log scale —the relevant magnitude for the business question— only
two nominal findings were observed, none of which survived the multiplicity correction.

### 9.7 Translation into a product decision

The primary effect is **statistically significant** (p ≈ 3·10⁻¹¹) and, above all, **materially
relevant**: the 95% confidence interval of the AOV increase lies entirely above the business
relevance threshold (+3%), derived from the break-even model. The estimate is robust to the
specification (winsorization, log scale, bootstrap, and covariate adjustment produce consistent
conclusions), no control metric degrades, and the effect is homogeneous across the pre-specified
segments. The estimated economic impact, under linear extrapolation to the historical annual
volume, amounts to **+R$ 456,000 per year of merchandise value** (95% CI [+R$ 322,000; +R$
591,000]). As a result, the decision rule returns **LAUNCH**. A sweep of the rule over different
effect sizes confirms that all three possible decisions (DO NOT LAUNCH, ITERATE, LAUNCH) are
reachable, and that an effect of +2% or +3% would have led to "ITERATE".

---

## 10. Limitations

Consolidated synthesis of the project's three audits (`docs/auditoria_fase1_fase2.md`,
`docs/auditoria_fase5.md`, `docs/auditoria_global.md`).

| # | Limitation | Severity | Intrinsic to the dataset? | Status |
|---|---|---|---|---|
| 1 | **The experiment is simulated** → zero external validity. The project describes nothing real about Olist. | High (it is the premise) | **Yes** | Declared in every deliverable; the project validates the *process*. |
| 2 | **The effect model shapes results.** Two choices matter: (a) responders are drawn at random → the homogeneity across segments is partly "baked into" the design; (b) the effect is multiplicative → it generates the artifact the p-hacking demo exploits. A model of the free-shipping bar would concentrate the effect below a threshold (a real heterogeneous effect). | Medium | Partial | Consequences explicitly analyzed; §6.8 adds a heterogeneous variant and shows the design detects it. |
| 3 | **Relevance MDE = +3%.** | Medium | No | **Resolved**: `src/mde_cost_model.py` derives it from a *break-even*; valid for volume ≥ ~415,000 orders/year. |
| 4 | **A single analysis split** (SEED 42), with +1.2% of baseline imbalance that inflates the point estimator. | Low-Medium | No | **Resolved**: §6.8 multi-seed A/B (500) → raw unbiased, CI coverage 0.94. |
| 5 | **Guardrails with no injected effect** → "no degradation" trivially true; would not by itself demonstrate that the tests would catch a real regression. | Medium | No | **Resolved**: §6.8 injects regressions into G1 and verifies the two-gate rule. |
| 6 | **No retention / LTV metric.** Olist's repeat purchase (~3%) and the window prevent it. | Low | **Yes** | Declared; out of scope. |

**Additional limitations:**

- **Linear economic extrapolation.** The GMV *uplift* assumes the per-order *lift* holds when
  scaled to the full volume and over time; it ignores novelty, saturation, and seasonality. The
  15% commission is an illustrative assumption (Olist does not publish its *take rate*).
- **Winsorization bias.** Winsorization, chosen to reduce variance, introduces a point bias of
  −0.36 pp in the *lift* estimator and an under-coverage of the CI (0.92 versus 0.95). Mitigated
  by also reporting the raw metric (unbiased, nominal coverage).
- **2-year time window**, not a 2-4 week experiment: the "time in experiment" is not realistic,
  although seasonality is balanced by the randomization.
- **Observational segments.** The segment analysis uses pre-treatment covariates; *new vs.
  returning* is not explored because of the degeneracy described in 7.4.

**No limitation invalidates the work.** #1 and #6 are an unavoidable consequence of choosing a
public e-commerce dataset with no experiment; #3, #4, and #5 were addressed in a second pass; a
residue of #2 persists (the effect's functional form is a declared choice).

### 10.1 Are these limitations solvable?

Of the eight limitations, **two are structural** (not removable with this dataset and this
scenario) and **six are solvable or already resolved**.

| # | Limitation | Solvable? | How / why not |
|---|---|:--:|---|
| 1 | Simulated experiment → zero external validity | ❌ **No**, without changing the premise | The only way to fix it is a dataset with **real randomization** (Criteo Uplift, Hillstrom, X5 RetailHero). But then the lever stops being an *on-site* checkout change and becomes a marketing send (email/SMS) → one limitation is traded for another. Real product experiments **are proprietary and are not published**. Possible mitigation: run the same pipeline over Hillstrom as an annex → validates the machinery with real data, without making the Olist analysis real. |
| 6 | No retention / LTV metric | ❌ **No**, with Olist | Repeat purchase at Olist is ~3% and the window is short. It would need a domain with natural repeat purchase (subscription, telco) or a dataset like *DunnHumby — The Complete Journey* (2 years, households) — but that one has *targeted*, not randomized, campaigns. It is a scope decision, declared. |
| 3 | Relevance MDE = +3% | ✅ **Already resolved** | It went from asserted to **derived** from a break-even model (`src/mde_cost_model.py`). Only improvable with real cost data, which does not exist publicly. |
| 4 | A single split (SEED 42) | ✅ **Already resolved** | The multi-seed A/B (500 replicates) demonstrates the estimator is unbiased and the CI has 0.94 coverage. The mean of the 500 could be presented as the headline instead of the seed-42 split. |
| 5 | Guardrails with no injected effect | ✅ **Already resolved (for G1)** | §6.8 injects regressions into `review_score` and verifies that the two-gate rule catches −0.08 and lets −0.03 through. Extensible to G2/G3/G4 in ~1h. |
| 2 | The effect model shapes results (homogeneity, p-hacking artifact) | 🟡 **Yes, with work** | Promote the heterogeneous variant of §6.8 to the main scenario; run the analysis under 2-3 effect models (multiplicative / additive / diluted) and show which conclusions are sensitive to the model. Turns it into a **transparent sensitivity analysis** instead of a hidden choice. Residue: any synthetic effect remains a choice. |
| — | Linear economic extrapolation · invented 15% commission | 🟡 **Improvable** | Use published *take rate* ranges (Olist ~10-20%) and a sensitivity table instead of a point. No real Olist figures exist. |
| — | Winsorization bias −0.36 pp | ✅ **Solvable** | Use an unbiased robust estimator (trimmed mean + bootstrap-BCa CI, or Hodges-Lehmann) instead of winsorizing; or present the raw metric (already unbiased) as the headline. |
| — | 2-year window ≠ 2-4 week experiment | 🟡 **Solvable at a cost** | Restrict to a 3-week span and re-run → n drops from 94k to ~5k, the detectable MDE rises to ~10%. Shows the realistic-duration scenario but power is lost. |

**Reading for a portfolio.** The current state is good: a reviewer values "knows its limitations
and states them" more than "hides them". The pending improvements have diminishing returns, and
making limitation #1 disappear would require proprietary data (not available) or a weaker
scenario.

---

## 11. Discussion and conclusions

### 11.1 What the project demonstrates

The project runs the full cycle of a product experimentation analysis with senior-level judgment:

1. **Pre-specification discipline.** Hypothesis, a single primary metric, guardrails, MDE, and the
   decision rule are written **before** looking at the data, and the order is kept throughout the
   documentation.
2. **Separation of significance and relevance** with an operational rule (CI vs. MDE), not just
   talk.
3. **Assumption checks that change the decision** (Welch instead of Student because of
   heteroscedasticity under H1): not a decorative check.
4. **A/A calibration** over 2,000 partitions — the correct way to certify a new experimentation
   pipeline — and **multi-seed A/B** for the confidence interval's coverage.
5. **Quantification of one's own prediction and its refutation** (the dilution penalty turned out
   negligible), and an honest report of the bias introduced by winsorization.
6. **P-hacking control**: pre-specification, multiplicity correction, and a demonstration that the
   wrong scale for the estimand fabricates findings that not even Bonferroni removes.
7. **Traceability and reproducibility**: parameters in a single file, a single *entrypoint* with a
   reproducibility report, a read-only notebook, and a test suite with an idempotency check.
8. **Documented self-criticism**: three audits that found and fixed real problems (F-test → Wald
   HC3; "nearly normal" → qualified; duplicated parameter → `config.py`).

### 11.2 Methodological findings

- **Effect heterogeneity does not appreciably cost power** when the metric's natural variance is
  high (CV ≈ 1.5). The opposite intuition is correct in direction but not in magnitude, and it is
  only discovered by quantifying it.
- **At large sample sizes, any real guardrail regression is significant.** The guardrail rule must
  combine **significance and magnitude** (two gates); a significance-only rule blocks launches
  over irrelevant noise.
- **Winsorization is not free.** Applied to a metric acted on by a multiplicative effect, it
  introduces a negative bias in the *lift* estimator. It reduces the mean squared error (lower
  variance offsets the bias) but degrades the confidence interval's coverage. The practical
  recommendation is to report both versions.
- **Correcting for multiple comparisons does not save a badly posed estimand.** Testing the effect
  in absolute value (R$) instead of in percentage, over cuts correlated with basket size, produces
  "winning segments" that survive even Bonferroni. The correct defense is threefold: correct
  magnitude, pre-specification, and correction.

### 11.3 Conclusion

For the stated goal —a portfolio project demonstrating competency in designing and analyzing
product experiments in a marketplace domain— the work more than delivers. The decisions are
justified, the alternatives considered, and, above all, **the limitations are declared rather than
hidden**. The underlying limitation (the experiment is simulated) is unavoidable with a public
e-commerce dataset and is handled with transparency: the project does not claim to have discovered
anything about Olist, but to demonstrate that it knows how to **design, execute, audit, and
decide** an experiment.

---

## 12. Future work

1. **Guardrail with a graded sub-threshold regression:** extend §6.8 with a sweep of regression
   magnitudes across several guardrails and detection power curves.
2. **Realistic heterogeneous effect as the main scenario:** turn the §6.8 variant (effect
   concentrated below the free-shipping threshold) into a full analysis, with power to detect the
   heterogeneity and per-band effect estimation.
3. **Design with a synthetic pre-treatment period** to apply CUPED and compare the variance
   reduction against ANCOVA.
4. **Calibrated cost model** with real marketplace data (or published ranges) to set the relevance
   MDE without illustrative assumptions.
5. **Sequential analysis / *always-valid* p-values** to simulate the real practice of peeking at
   results early.
6. **Replication on a dataset with real randomization** (Hillstrom, Criteo Uplift) as external
   validation of the pipeline, accepting that the lever would be a marketing send.

---

## 13. Appendices

### Appendix A — Experiment parameters (`params.yaml`)

| Parameter | Value | Meaning |
|---|---|---|
| `seed` | 42 | global seed |
| `alpha` | 0.05 | significance level (two-sided) |
| `effect.p_resp` | 0.20 | fraction of treated units that responds |
| `effect.delta_resp` | 0.25 | multiplicative effect among responders |
| `effect.eps_sd` | 0.05 | Gaussian noise on the effect |
| *ATE* (derived) | 0.05 | mean effect = `p_resp · delta_resp` |
| `mde_relevancia_pct` | 3.0 | minimum relevant *lift* (derived from the *break-even*) |
| `target_power` | 0.80 | target power |
| `window_start` / `window_end` | 2017-01-01 / 2018-09-01 (excl.) | time window |
| `winsor_q` | 0.995 | winsorization percentile (significance test only) |
| `n_sim_aa` | 2,000 | partitions for the A/A calibration |
| `n_sim_power` | 1,000 | replicates of the simulated power analysis |
| `n_sim_multiseed` | 500 | replicates of the full A/B test |
| `n_bootstrap` | 10,000 | resamples of the bootstrap CI |
| `cost_model.*` | see `params.yaml` | assumptions of the MDE break-even model |

### Appendix B — Glossary

| Term | Definition |
|---|---|
| **AOV** | *Average Order Value*, the mean order value. Here, merchandise value (Σ `price`), excluding freight. |
| **ATE** | *Average Treatment Effect*, the mean effect of the treatment. Here, +5% by construction. |
| **MDE** | *Minimum Detectable Effect*. Used in two senses: (a) the minimum effect the design detects at 80% power; (b) the *relevance MDE*, the minimum effect that justifies the change's cost. |
| **Guardrail** | A control metric that must not degrade even if the primary one improves. |
| **SMD** | *Standardized Mean Difference*. Balance criterion: \|SMD\| < 0.10. |
| **SRM** | *Sample Ratio Mismatch*, a deviation of the unit split from the target ratio (here 50/50). |
| **A/A test** | An experiment with no effect: control against control. Used to verify the pipeline does not generate false positives. |
| **Diluted effect** | A model in which only a fraction of the treated units responds. |
| **Winsorization** | Clipping a variable's extreme values at a given percentile. |
| **Welch's t** | A variant of Student's t that does not assume equal variances between groups. |
| **Benjamini-Hochberg (BH)** | A procedure that controls the false discovery rate (FDR) in multiple tests. |
| **Bonferroni** | A stricter correction: controls the probability of *any* false positive (FWER). |
| **ANCOVA** | Analysis of covariance: regression of the outcome on the treatment plus predictive covariates, to reduce variance. |
| **HC3** | A heteroscedasticity-robust standard-error estimator. |
| **CLT** | Central Limit Theorem: the sample mean tends to normal even if the data is not. |
| **SUTVA** | *Stable Unit Treatment Value Assumption*: no interference between units. |
| **CUPED** | *Controlled-experiment Using Pre-Experiment Data*: a variance-reduction technique using prior data. |

### Appendix C — How to reproduce

```bash
pip install -r requirements.txt

# data (not versioned, due to the CC BY-NC-SA 4.0 license)
python -m kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip

python run_all.py        # ~2 min · 6 phases + reproducibility report (fails with code !=0 if something doesn't check out)
pytest                   # fast tests
pytest -m slow           # + bit-for-bit idempotency

jupyter notebook notebooks/ab_test_olist.ipynb   # presentation layer (only reads outputs/)
```

### Appendix D — Figure index

| Figure | Phase | Content |
|---|---|---|
| `f2_01_volumen_mensual.png` | 2 | Monthly order volume; stable window |
| `f2_02_distribucion_aov.png` | 2 | AOV distribution: raw (skew 9.8) vs. log (nearly normal) |
| `f2_03_guardrails.png` | 2 | `review_score` and orders per customer |
| `f3_01_balance.png` | 3 | Covariate balance *love-plot* |
| `f4_01_tcl_normalidad.png` | 4 | Non-normal data; normal mean (CLT) |
| `f4_02_aa_pvalores.png` | 4 | A/A: flat p-value histogram |
| `f4_03_ab_efecto.png` | 4 | A/B effect with 95% CI (several methods) |
| `f4_04_power_vs_n.png` | 4 | Power vs. n: uniform vs. diluted effect |
| `f5_01_forest_segmentos.png` | 5 | *Forest plot* of the effect by segment |
| `f_mde_breakeven.png` | 4 | Relevance MDE derived from costs |

### Appendix E — History of audited decisions

| ID | Decision | Section | Audit outcome |
|---|---|---|---|
| D1 | Primary metric = AOV | 3.3 | Correct; the honest alternative was this or switching datasets |
| D2 | Randomize by customer; dedup to 1 order/customer | 3.4 | Correct and verified (impact −0.35%) |
| D3 | Two-sided test, α = 0.05 | 3.5 | Correct and conservative |
| D4 | Guardrails + two-gate rule + BH | 3.6 | Rule corrected from "OR" to "AND" after the audit |
| D5 | Relevance MDE = +3% | 3.7 | Went from asserted to **derived** from a cost model |
| D6 | LAUNCH/ITERATE/DO NOT LAUNCH rule | 3.8 | Excellent; all three branches verified |
| D7 | A/A + diluted A/B simulation | 3.9 | Well documented; the effect's functional form remains a declared choice |
| D8 | Time window 2017-01/2018-08 | 4.2 | Cosmetic, not corrective; correctly not oversold |
| D9 | p99.5 winsorization only for the significance test | 5.4 | Well managed; found to introduce −0.36 pp of bias → both are reported |
| — | Interaction tests: homoscedastic F → Wald HC3 | 7.4-7.5 | Corrected after the Phase 5 audit; reinforces the p-hacking demo |

---

*Document generated as part of the project. For the executable version and all intermediate data,
see the repository.*
