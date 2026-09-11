# Phase 3 — Data Preparation

> CRISP-DM · Phase 3 of 6
> Reproducible scripts: `src/prepare_data.py` (analytical table + assignment) · `src/balance_check.py`
> Output: `data/processed/analytical_table.parquet` · `outputs/tables/fase3_transformaciones.csv`
> · `outputs/tables/fase3_balance.csv` · `outputs/figures/f3_01_balance.png`

Cleaning **aimed at the experimental question** (the redesign's effect on the AOV), not generic
EDA. Every transformation is logged with its count and its rationale.

---

## 3.1 Chain of transformations (full trace)

| Step | n before | n after | Δ | Rationale |
|---|---:|---:|---:|---|
| Raw (`olist_orders`) | 99,441 | 99,441 | — | — |
| **Time window** `[2017-01-01, 2018-09-01)` | 99,441 | 99,092 | −349 | Removes the residual 2016 start-up and the incomplete Sep-Oct 2018 tail. Adjustment **for realism**, not corrective: the mean AOV does not move (audit §B6). |
| **Valid statuses** {delivered, shipped, invoiced, approved, processing} | 99,092 | 97,905 | −1,187 | A paid order is a "completed purchase". `canceled` / `unavailable` / `created` are excluded (they don't represent an effective purchase). `is_delivered` is kept for the sensitivity analysis. |
| **Orders with items** | 97,905 | 97,905 | 0 | The 775 orders with no `order_items` lines were already dropped with the invalid statuses. |
| **Dedup to 1 order / customer** (the first one) | 97,905 | 94,703 | −3,202 | Randomization unit = analysis unit (audit §B3). Shifts the mean AOV by −0.35%; removes the need for clustered standard errors. |

**Final analytical table: 94,703 rows × 15 columns · grain = 1 order-customer.**

---

## 3.2 Enrichment (constructed variables)

| Column | Construction | Use |
|---|---|---|
| `merch_value` | Σ `order_items.price` per `order_id` | **primary metric (AOV)** — unwinsorized, for descriptives |
| `merch_value_w` | `merch_value` clipped at **p99.5 = R$ 1,360** (473 orders, 0.50%) | **primary metric for the significance test** (audit §B4); the test is reported with and without |
| `freight_value` | Σ `order_items.freight_value` per `order_id` | guardrail G3 + balance covariate |
| `n_items` | count of lines per `order_id` | balance covariate / diagnostic |
| `review_score` | review with the **most recent** `review_answer_timestamp` per order | guardrail G1 |
| `cat_dominante` | category (EN) of the order's **most expensive** item | balance covariate / exploratory segmentation |
| `payment_type` | type of the row with the highest `payment_value`; `not_defined` → `unknown` | balance covariate / segmentation |
| `customer_state` | from `olist_customers` via `customer_id` | balance covariate / segmentation |
| `mes_compra` | `order_purchase_timestamp` truncated to month | balance covariate (seasonality) |
| `is_delivered` | `order_status == 'delivered'` | sensitivity analysis |
| `group` | see §3.4 | experiment arm |

### Nulls in the final table

| Column | Nulls | Treatment |
|---|---:|---|
| `review_score` | 696 (0.73%) | Excluded from the G1 test (complete-case analysis); given the 0.7%, the potential bias is negligible. Sensitivity: median imputation. |
| all other columns | 0 | — |

---

## 3.3 *The Olist gotcha* — resolved explicitly

`orders.customer_id` is **unique per order** (one row per order); the real person is
`customers.customer_unique_id`. The whole pipeline (dedup, assignment, customer counting) uses
`customer_unique_id`. Verified in the audit (§A).

---

## 3.4 Simulated random assignment

- **Unit:** `customer_unique_id` (equivalent to order after the dedup).
- **Mechanism:** `numpy.random.default_rng(SEED=42).choice(["control", "treatment"])` per row.
- **Declared seed:** `SEED = 42` (fixed in `src/prepare_data.py`).
- **Result:** control = **47,280** · treatment = **47,423** (50.08% treatment — the expected
  deviation from 50% by chance at n ≈ 95k).
- **The treatment effect is NOT injected at this phase.** The table comes out with the primary
  metric intact; the perturbation (diluted model, §1.7b) is applied in Phase 4.

---

## 3.5 Covariate balance check (`src/balance_check.py`)

Criteria: **|SMD| < 0.10** per covariate and **omnibus test not significant** at α = 0.05.

| Covariate | Type | SMD | Test | p-value | Balanced? |
|---|---|---:|---|---:|:--:|
| `n_items` | continuous | −0.0036 | Welch-t | 0.579 | ✅ |
| `freight_value` | continuous | 0.0067 | Welch-t | 0.305 | ✅ |
| `customer_state` | categorical (27) | 0.0127 | χ² (dof 26) | 0.919 | ✅ |
| `cat_dominante` | categorical (72) | 0.0200 | χ² (dof 71) | 0.320 | ✅ |
| `payment_type` | categorical (4) | 0.0085 | χ² (dof 3) | 0.623 | ✅ |
| `mes_compra` | categorical (20) | 0.0153 | χ² (dof 19) | 0.693 | ✅ |

**All |SMD| ≤ 0.02** (well below 0.10) and **no omnibus test is significant** (minimum p 0.32).
See `f3_01_balance.png`. → **The groups are exchangeable.**

### SRM check (Sample Ratio Mismatch)

χ² of the observed split (47,280 / 47,423) against 50/50: **χ² = 0.216, p = 0.642** → the split is
compatible with 50/50, with no sign of differential unit leakage. (`outputs/tables/fase3_srm.csv`).

### Point A/A check on the primary metric (SEED = 42)

| | control | treatment | difference | Welch-t |
|---|---:|---:|---:|---:|
| `merch_value` | R$ 137.04 | R$ 138.67 | **+1.63 R$ (+1.19%)** | **p = 0.235** |

With the declared seed, the observed difference in the AOV is **sampling noise** (not
significant). It is a good reminder that **a raw ~1% difference between two random groups is
normal** — hence the need for the formal test rather than the eye. The **global calibration** (is
the false-positive rate really ~5%? are the p-values uniform?) is validated with **1,000 seeds
in Phase 4**.

---

## 3.6 Closing Phase 3 and handoff to Phase 4

- [x] Time window applied (2017-01 → 2018-08).
- [x] Valid statuses filtered; `is_delivered` kept for sensitivity.
- [x] Reviews deduplicated by `review_answer_timestamp`.
- [x] Dedup to 1 order/customer (94,703 rows).
- [x] p99.5 winsorization in a separate `merch_value_w` column (significance test only).
- [x] Simulated 50/50 assignment per customer, `SEED = 42`.
- [x] Covariate balance check **passed** (|SMD| ≤ 0.02; all omnibus tests not significant).
- [x] SRM check **passed** (χ² = 0.216, p = 0.642).
- [x] Analytical table persisted to `data/processed/analytical_table.parquet`.
- **Next (Phase 4 — Modeling):** power analysis (a priori, with the diluted effect), test
  assumption checks, A/A over 1,000 seeds (Type I error + p-value uniformity), injection of the
  diluted effect, and running the primary test + guardrails with the BH correction.
