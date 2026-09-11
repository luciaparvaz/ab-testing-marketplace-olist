# Phase 2 — Data Understanding

> CRISP-DM · Phase 2 of 6
> Reproducible script: `src/profiling_phase2.py` → `outputs/tables/phase2_summary.json`
> Figures: `outputs/figures/f2_01…03.png`

---

## 2.1 Provenance, license and structure

| | |
|---|---|
| **Source** | Brazilian E-Commerce Public Dataset by Olist — Kaggle (`olistbr/brazilian-ecommerce`) |
| **Publisher** | Olist Store (Brazilian marketplace) |
| **License** | **CC BY-NC-SA 4.0** — verified on download via the Kaggle CLI (`License(s): CC-BY-NC-SA-4.0`). Non-commercial use, attribution, and *share-alike*. Compatible with portfolio use; the raw CSVs are **not versioned** in the repo. |
| **Download** | `kaggle datasets download -d olistbr/brazilian-ecommerce` (42.6 MB compressed) |
| **Format** | 9 relational CSVs, joined by keys (`order_id`, `customer_id`, `product_id`, `seller_id`) |

### Tables and volumes

| Table | Rows | Columns | Use in the experiment |
|---|---:|---:|---|
| `olist_orders_dataset` | 99,441 | 8 | backbone: 1 row/order, status, timestamps |
| `olist_order_items_dataset` | 112,650 | 7 | **primary metric**: `price`, `freight_value` per item |
| `olist_order_payments_dataset` | 103,886 | 5 | amount robustness (`payment_value`), payment method |
| `olist_order_reviews_dataset` | 99,224 | 7 | **guardrail G1**: `review_score` |
| `olist_customers_dataset` | 99,441 | 5 | **randomization unit**: `customer_unique_id`, `customer_state` |
| `olist_products_dataset` | 32,951 | 9 | segmentation by category |
| `olist_sellers_dataset` | 3,095 | 4 | marketplace context |
| `olist_geolocation_dataset` | ~1M | 5 | not used (noise, does not inform the question) |
| `product_category_name_translation` | 71 | 2 | PT→EN category translation |

---

## 2.2 Period and analysis window

- **Raw range:** 2016-09-04 to 2018-10-17.
- **Dataset reality:** 2016-09/10 are token months (4 + 324 orders), 2016-11 is **empty**, and
  2018-09/10 have 16 + 4 orders (export cutoff). The bulk sits between **2017-01 and 2018-08**.
- **Decision (confirmed):** restrict to the **stable window 2017-01 → 2018-08** to (i) remove the
  sparse start and the incomplete tail and (ii) make the volume and duration resemble those of a
  real experiment. Impact on n: less than 1% of valid orders is lost and the mean AOV changes from
  R$ 137.42 to R$ 137.37 (audit §B6) → this is an adjustment **for realism, not a bias correction**.
- Since the assignment will be **random per customer**, *treatment* and *control* will cover the
  same date range → **seasonality is balanced by design** (see `f2_01_monthly_volume.png`).

---

## 2.3 Primary metric: AOV profiling

`merch_value` = Σ `price` of the items per `order_id` (excludes freight). Valid orders = status in
{delivered, shipped, invoiced, approved, processing} and with at least one item → **n = 98,199
orders / 94,983 unique customers**.

| Statistic | `merch_value` (primary) | `merch + freight` | `log(merch_value)` |
|---|---:|---:|---:|
| n | 98,199 | 98,199 | 98,199 |
| mean | **R$ 137.42** | R$ 160.24 | 4.443 |
| median | R$ 86.90 | R$ 105.28 | 4.465 |
| std. dev. | R$ 209.31 | R$ 219.11 | 0.932 |
| **CV (σ/μ)** | **1.523** | 1.367 | 0.210 |
| p95 / p99 | R$ 400 / R$ 995 | R$ 449 / R$ 1,055 | 5.99 / 6.90 |
| max | R$ 13,440 | R$ 13,664 | 9.51 |
| **skew** | **9.77** | 9.26 | **0.24** |
| kurtosis (excess) | 271.4 | 244.1 | 0.33 |

**Key readings (they shape Phase 4):**

1. **The raw AOV is extremely skewed and leptokurtic** (skew ≈ 9.8; tail up to R$ 13,440 versus a
   median of R$ 87). See `f2_02_aov_distribution.png`.
2. **The log transform brings the skewness and kurtosis into a robust range** (skew 9.8 → 0.24;
   kurtosis 271 → 0.33). It **still is formally not normal** (D'Agostino K² p ≈ 8·10⁻²⁴ at n =
   5,000 — audit §B1), but that is irrelevant: at large n the mean is normal by the CLT. **The
   t-test on `log(AOV)` is NOT the primary test**: it tests the **ratio of geometric means** (≈
   median), which is a different business question, not a "more powerful" version of the AOV
   (audit §B2). It is included as a **robustness check**.
3. With **n ≈ 47-48k per group** (after dedup to 1 order/customer and the time window), the
   Central Limit Theorem makes the **sampling distribution of the mean normal despite the skew**,
   so **Welch's t on the raw value is the primary test** (the business wants the mean, because
   revenue = mean × volume). This is confirmed empirically with Phase 4's A/A test.
4. **Tail outliers** (max R$ 13,440) inflate the variance. **Decision (audit §B4):** **p99.5
   winsorization only for the significance test** (clips 0.50% of observations, brings the CV
   from 1.52 to 1.28); the **descriptive base AOV is reported WITHOUT winsorization** (R$ 137.42),
   because winsorizing shifts the mean by -2.4%. The test is reported **with and without**
   winsorization.

### Power preview (preliminary — not the validation)

With `TTestIndPower` (normal approximation), n ≈ 49k/group, α = 0.05 two-sided, power 0.80:

| Scenario | CV | Detectable relative lift |
|---|---:|---:|
| Raw AOV | 1.523 | **+2.72%** |
| p99.5 winsorized AOV | 1.278 | **+2.28%** |

→ Both below the **+3% relevance MDE**, but with a **narrow margin**. This figure is a
**worst-case upper bound** and is **not** the basis for the "powered sample" conclusion: the real
validation is the **empirical power at the injected diluted effect** (§1.7b), measured by repeated
simulation in Phase 4. With a **diluted** effect the real power will be **lower** than the nominal
one — an expected project result, not a failure.

---

## 2.4 Guardrail metrics: profiling

| Guardrail | Base value | Notes |
|---|---|---|
| **G1 — `review_score`** | mean **4.12** / 5 · σ 1.32 · **99.3%** coverage | Skewed inverted-U distribution: 58% are 5★, 11% are 1★ (`f2_03_guardrails.png`). Not normal → Mann-Whitney or a "≥ 4" proportion test as a complement to the t-test. |
| **G2 — cancellation rate** | **0.63%** overall (625 / 99,441) | Rare event → proportion (z) or Fisher test; low power, will be reported with a wide CI. |
| **G3 — `freight_value`** | mean **R$ 22.82** / order · CV 0.95 | Watch that an AOV rise does not come with higher absorbed freight. |
| **G4 — orders per customer** | see §2.5 | That the AOV does not rise at the cost of lower frequency. |

---

## 2.5 Randomization unit: orders per customer

| | |
|---|---:|
| Unique customers (valid) | 94,983 |
| With exactly 1 order | 92,096 (**96.96%**) |
| With 2 or more orders | 2,887 (3.04%) |
| % of orders from repeat customers | **6.21%** |
| Max. orders from one customer | 16 |

→ Randomizing by `customer_unique_id` is **almost equivalent** to randomizing by order (avoids
contamination). **Decision (audit §B3):** deduplicate to **1 order per customer** (the first one
in the window). Verified: it shifts the mean AOV by only **-0.35%** (R$ 137.42 → 137.90), and in
exchange **randomization unit = analysis unit** (no need for clustered SE). Resulting analysis n
≈ 94k customers (before applying the time window). Robustness: analysis with all orders +
customer-clustered SE.

---

## 2.6 Data quality (findings that Phase 3 must handle)

| Finding | Magnitude | Planned treatment (Phase 3) |
|---|---|---|
| Orders with no items | 775 (mostly `unavailable` / `canceled`) | Exclude from the primary metric; counted in G2. |
| Duplicate `review_id` | 814 | Deduplicate. |
| `order_id` with >1 review | 551 | Keep the review with the **most recent `review_answer_timestamp`** (not by row order — affects 100 orders, audit §B5). |
| Null `order_approved_at` | 160 | Does not affect the primary metric; documented. |
| Null `order_delivered_customer_date` | 2,965 | Only affects delivery metrics (not the main guardrail). |
| Missing `payment_value` on a valid order | 1 | Documented; the primary metric comes from `order_items`, not from payments (audit §B7). |
| Non-final statuses (`shipped`, `invoiced`, `processing`, `approved`) | ~1,700 | Included as "completed purchase"; sensitivity analysis restricting to `delivered`. |
| AOV outliers (heavy tail) | p99 = R$ 995; max R$ 13,440 | Declared **p99.5** winsorization only for the significance test; descriptive base AOV unwinsorized; reported with and without. |
| `payment_type = not_defined` | 3 | Dropped. |

---

## 2.7 Limitations affecting the experiment's validity

1. **No real randomization or traffic layer.** The dataset starts at the order: there are no
   sessions, visits, or carts → **conversion cannot be measured**. The primary metric is the AOV
   (§1.2). The control/treatment assignment is **simulated** (§1.7); the A/B effect is **injected
   in a declared way** with a **diluted** model (20% of treated units respond with +25%; ATE =
   +5%). As a consequence, the project demonstrates **design and analysis rigor**, not a genuine
   business finding.
2. **Treatment effect not observed in covariates.** By simulating, the redesign can only act on the
   metric we perturb; in reality it would also affect the category mix, the return rate, etc. The
   scope is limited to AOV + observable guardrails.
3. **2-year historical window, not a 2-4 week experiment.** Mitigated by restricting to
   2017-01/2018-08 and balancing seasonality by design, but the "time in experiment" is not
   realistic. The restriction is cosmetic, not corrective: the mean AOV barely changes (§B6).
4. **Very low repeat purchase (3% of customers).** Prevents a primary retention metric with
   reasonable power; retention is out of scope.
5. **Survivorship bias in reviews.** `review_score` only exists for orders that went on to generate
   a review (99.3% coverage, acceptable) and is subject to customer self-selection.
6. **Single market (Brazil, 2016-2018).** No external validity outside that context.

---

## 2.8 Closing Phase 2 and handoff to Phase 3

- [x] Provenance, license (CC BY-NC-SA 4.0 **verified**), size and structure documented.
- [x] Primary metric profiled: **mean AOV R$ 137.42 · CV 1.523 · skew 9.8**; `log(AOV)` skew 0.24
  / kurtosis 0.33 (robust range; formally not normal but irrelevant thanks to the CLT at large n).
- [x] The numerical baseline missing from Phase 1 → **fixed** (feeds Phase 4's power analysis).
- [x] Guardrails profiled (G1 4.12/5 · G2 0.63% · G3 R$ 22.82).
- [x] Randomization unit characterized (97% of customers with 1 order).
- [x] Power preview: detectable effect ~+2.7% (raw) / ~+2.3% (winsor.) — **upper bound**, not the
  validation; the validation is Phase 4's empirical power.
- [x] Validity limitations listed.
- [x] **Independent audit** of Phases 1-2 passed: no calculation errors, 7 refinements applied
  (see `docs/audit_phase1_phase2.md`).
- **Next (Phase 3):** apply the 2017-01/2018-08 time window, deduplicate reviews by timestamp,
  deduplicate to 1 order/customer, apply p99.5 winsorization (significance test only), build the
  analytical table `1 row = 1 customer-order`, simulate the assignment, and run the *covariate
  balance check*.
