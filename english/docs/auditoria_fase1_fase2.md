# Audit — Phases 1 and 2 (code, results, and interpretations)

> Critical review prior to closing the phases and committing.
> Method: independent re-derivation of all key numbers via a second path
> (`/tmp/audit_fase2.py`, reproducible), review of assumptions, and search for errors.
> Overall verdict: **no material calculation errors**. 7 interpretation/decision refinements
> before Phase 3. 1 simulation design decision remains open.

---

## A. Calculation verification — everything checks out

| Number (Phase 2) | Value in the doc | Independent re-derivation | OK? |
|---|---|---|---|
| n valid orders | 98,199 | 98,199 | ✅ |
| Mean / median AOV | R$ 137.42 / 86.90 | R$ 137.4189 / 86.90 | ✅ |
| AOV σ / CV | 209.31 / 1.523 | 209.3064 / 1.5231 | ✅ |
| AOV skew / kurtosis | 9.77 / 271 | 9.772 / 271.4 | ✅ |
| log(AOV) skew / kurtosis | 0.24 / 0.33 | 0.2424 / 0.3346 | ✅ |
| 80% detectable lift | +2.72% | +2.723% (statsmodels **and** closed-form formula agree) | ✅ |
| % customers with 1 order | 96.96% | 96.96% | ✅ |

**Integrity checks that pass:**

- `order_items.price` has no zeros or negatives (min R$ 0.85); 1 row = 1 unit → the sum per
  `order_id` is the correct merchandise value.
- **Olist's *gotcha* is resolved correctly:** `orders.customer_id` is unique per order (99,441),
  `customer_unique_id` identifies the person (96,096). The profiling uses `customer_unique_id` to
  count customers and for the randomization unit. Correct.
- `freight_value ≥ 0` always.

---

## B. Interpretation refinements (before Phase 3)

### B1. "log(AOV) nearly normal" — qualify it

The log transform brings the skew from 9.8 down to **0.24** and the kurtosis from 271 to **0.33**.
But the **D'Agostino test on `log(AOV)` (n = 5,000) rejects normality with p ≈ 8·10⁻²⁴**.

- **This is not an error**, it is a precision issue: at large n, any tiny deviation "is
  significant".
- **Corrected wording:** *"the log transform brings the skewness and kurtosis into a range (skew
  0.24; kurtosis 0.33) in which the t-test is robust; it is still formally not normal (D'Agostino
  p < 10⁻²⁰ at n = 5,000), but that is irrelevant because at n ≈ 49k/group the sampling
  distribution of the mean is normal by the CLT regardless of the skew"*.

### B2. The test on the log scale answers a **different** business question

- t-test on the **raw AOV** → tests the **arithmetic mean** → this is what determines total
  revenue (revenue = mean × volume). **It is the business metric.**
- t-test on **log(AOV)** → tests the mean of the logs → equivalent to the **ratio of geometric
  means** ≈ a shift of the **median**. **It is not** the AOV.
- **Consequence:** the log-scale analysis is included as **robustness**, not as a "more powerful
  version" of the primary test. That it detects +1.7% instead of +2.7% is not an advantage: it
  measures a different effect.
- The Phase 2 doc is corrected to not suggest that log = "free" extra power.

### B3. Repeat customers — simplify the design

The audit quantifies the real impact of customers with multiple orders:

| Approach | n | Mean AOV |
|---|---:|---:|
| All orders | 98,199 | R$ 137.42 |
| 1 order per customer (the first) | 94,983 | R$ 137.90 |

Mean difference: **−0.35%**. Insignificant.

- **Revised recommendation:** instead of "customer-clustered standard errors" (more complex),
  **deduplicate to 1 order per customer (the first one in the window)**. This way
  **randomization unit = analysis unit**, the need for clustered SE disappears, and the cost is
  3.3% of orders and 0.35% of bias in the mean. Cleaner and easier to explain to a stakeholder.
- Equally valid alternative: keep all orders + customer-clustered SE. The simple one is chosen.

### B4. Winsorization — quantified, with its side effect

| Cap | Threshold | % obs clipped | CV | 80% detectable lift | Resulting mean AOV |
|---|---:|---:|---:|---:|---:|
| no cap | R$ 13,440 | 0% | 1.523 | 2.72% | R$ 137.42 |
| **p99.5** | **R$ 1,350** | **0.50%** | **1.278** | **2.28%** | **R$ 134.11** |
| p99 | R$ 995 | 1.00% | 1.181 | 2.11% | R$ 131.55 |
| p97.5 | R$ 626 | 2.50% | 1.019 | 1.82% | R$ 125.63 |

- The power gain from winsorizing at p99.5 is **modest** (2.72 → 2.28%).
- **Side effect:** winsorizing at p99.5 **lowers the mean by 2.4%** (R$ 137.42 → 134.11). For a
  test of the **difference** between groups it does not matter (both groups are winsorized the
  same way), but the **descriptively reported base AOV** must be the **raw one (R$ 137.42)**.
- **Revised decision:** winsorize at **p99.5 only for the significance test**; report the
  descriptive base AOV **unwinsorized**; include the **unwinsorized** analysis as robustness.
  Criterion pre-registered here, before seeing any test result.

### B5. Review deduplication — by timestamp, not by row order

- 551 orders have >1 review. Deduplicating "by last CSV row" vs. "by the most recent
  `review_answer_timestamp`" **changes the score for 100 orders**.
- Impact on the global mean: **none** (4.0867 vs. 4.0864).
- Even so, Phase 3 will deduplicate **by timestamp** (a principled criterion). Phase 2's profiling
  is not redone: the G1 guardrail number (4.12 over valid orders) does not change materially.

### B6. Time window — it is cosmetic, it does not correct a bias

- Mean AOV, full window: R$ 137.42 · window 2017-01/2018-08: **R$ 137.37** (n 98,199 → 97,905).
- Restricting the window **does not change the mean** nor does it introduce/correct a bias. The
  restriction is kept **only for realism** (making the duration resemble a real experiment) and to
  remove residual months — not as a correction step. The Phase 2 doc is adjusted to not oversell
  this.
- Side note: 2017-01 has a high AOV (R$ 152) over only 787 orders (early adopters). Irrelevant
  after the random assignment.

### B7. Minor detail

- `payment_value` is available for 98,198 of 98,199 valid orders (1 `delivered` order with no
  payment record). Documented; it does not affect the primary metric (which comes from
  `order_items`).

---

## C. Audit of the high-level interpretations

| Claim in the docs | Audit verdict |
|---|---|
| "The sample has enough power to detect the +3% MDE" | **Fragile as stated.** The margin is +2.72% vs. +3%: 0.3 pp. With p99.5 winsorization it becomes +2.28% (more comfortable). **Correction:** frame the conclusion around the **power achieved at the injected δ = 5%** (Phase 4/5) and present the +2.7% as "worst-case upper bound of the detectable effect (raw data)". **Phase 4's A/A test is the real validation** of the calibration, not this analytical preview. |
| "Welch's t on the raw AOV is a defensible primary test" | **Correct**, by the CLT at n ≈ 49k/group. Reinforced by the A/A simulation (empirically checks the Type I error). |
| "Seasonality balanced by design" | **Correct** — random assignment per customer spreads the months evenly. Also confirmed that the mean AOV is stable across windows. |
| BH correction over guardrails, primary excluded | **Standard and correct.** Add: Phase 5's segment analyses are **exploratory/non-confirmatory** and are labeled as such (already covered in §1.6). |
| "The project demonstrates design rigor, not a business finding" | **Correct and clearly flagged** in §2.7 and §1.7. It is the central limitation and it is prominently declared. |

---

## D. OPEN design decision — functional form of the synthetic effect (Phase 4)

The user chose "declared synthetic effect". The **shape** of the effect is still unset. Options:

| Option | Model | Realism relative to "cross-sell + free-shipping bar" | Statistical implication |
|---|---|---|---|
| **(a) Uniform multiplicative** | `aov_T = aov_C · (1 + δ + ε)` | Low: assumes all orders grow by the same % | The simplest; fits directly with a % MDE |
| **(b) Diluted** | only a fraction `p` of the treated units responds (e.g. 25%), the rest unchanged | **High:** a redesign only moves part of the users | Stresses the power analysis (the mean effect gets diluted); more instructive |
| **(c) Additive per item** | with probability `q`, 1 recommended item is added with a value ~ the real distribution of `price` | **High** for the cross-sell | The absolute effect is not constant in % → interesting for comparing level vs. % tests |
| **(d) Concentrated at a threshold** | pushes up only orders in a band below the free-shipping threshold | **High** for the progress bar | Very heterogeneous effect; complex to calibrate |

**Recommendation:** **(b) diluted** with `δ_responders` such that the overall mean effect is 5%
(e.g. 20% respond with +25%). It is realistic, keeps the declared mean δ, and makes the power
analysis and the A/A test more informative. **(a)** if maximum simplicity and fitting the
timeline are prioritized.

---

## E. Changes to apply before Phase 3 (actionable summary)

1. Edit `docs/02_data_understanding.md`: qualify "nearly normal" (B1), remove the idea that log =
   more power (B2), reframe the repeat-customer approach toward dedup to 1/customer (B3), rewrite
   the winsorization decision with its effect on the mean (B4), soften the time-window rationale
   (B6), add the `payment_value` note (B7).
2. Edit `docs/01_business_understanding.md`: §1.3 (dedup 1/customer instead of clustered SE),
   §1.5 (frame power around the injected δ, not the +2.7/+3 margin), §1.7 (fix the effect's shape
   per decision D).
3. No re-run of the profiling is needed: the Phase 2 numbers are correct.
4. Phase 3 incorporates: review dedup by timestamp, dedup to 1 order/customer, declared p99.5
   winsorization, 2017-01/2018-08 window.

---

## F. Resolution (user decisions)

1. **Shape of the synthetic effect:** option **(b) diluted** — `p_resp = 0.20`, `δ_resp = 0.25`,
   ATE = +5%. Fixed in `docs/01_business_understanding.md` §1.7b.
2. **Repeat customers:** **dedup to 1 order/customer** (the first one in the window). Robustness
   with all orders + clustered SE. Fixed in §1.3 and §2.5.
3. Changes E1-E2 **applied** to the Phase 1 and 2 docs. Proceed to commit Phases 1 + 2 + the
   audit and start Phase 3.
