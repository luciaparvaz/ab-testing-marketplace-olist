# Global project audit — review as an expert statistician

> Cross-cutting review of **all** the project's methodological decisions: what was decided, why,
> what alternatives existed, and what weakness remains. Complements the per-phase audits
> (`auditoria_fase1_fase2.md`, `auditoria_fase5.md`).
>
> **Overall verdict:** the project is **methodologically sound and honest**. The central
> limitation —the experiment is simulated— is declared everywhere. There are **6 residual
> weaknesses** that a demanding reviewer would flag; none invalidates the work, and 4 of them are
> intrinsic to doing an experimentation project on a dataset with no experiment.

---

## Part I — Design decisions (Phase 1)

### D1. Primary metric = AOV, not conversion

- **Decision:** the success metric is the merchandise value per order (AOV).
- **Rationale:** the Olist dataset starts at the order already placed — there are no sessions,
  visits, or carts. Conversion (visit→purchase) **is not measurable** because the population of
  "non-buyers" does not exist. The AOV is, and it directly captures the expected effect of the
  cross-sell.
- **Discarded alternatives:** (a) simulating a traffic layer with non-buyers → **rejected for
  fabricating data** (prohibited by the project's standards); (b) using a dataset with real
  conversion (Criteo Uplift, Hillstrom) → discarded because its lever is marketing, not an
  on-site change.
- **Residual weakness:** the project does not demonstrate e-commerce's most typical metric (funnel
  conversion). A recruiter looking for exactly that will notice. **Mitigation:** it is explicitly
  justified, and the AOV is a first-order business metric (revenue = AOV × volume).
- **Verdict:** correct. The honest alternative was this or switching datasets.

### D2. AOV = sum of `price`, excluding freight

- **Rationale:** the redesign (cross-sell + free-shipping bar) moves the merchandise purchased,
  not the shipping cost. Including freight would add noise unrelated to the lever. Freight is
  monitored **as a guardrail** (G3).
- **Verdict:** correct. `payment_value` (which includes freight and installments) was used only as
  a robustness check.

### D3. Randomization unit = customer; analysis unit = 1 order/customer

- **Decision:** assign by `customer_unique_id`; keep each customer's **first** order.
- **Rationale:** assigning per customer prevents two orders from the same person from falling into
  different groups (contamination, violates SUTVA). Deduplicating to 1 order/customer makes
  **randomization unit = analysis unit**, which removes the need for clustered standard errors.
  The Phase 3 audit verified that this shifts the mean AOV by only **−0.35%** and 3.3% of orders
  are lost.
- **Alternative:** keep all orders + customer-clustered SE. Equally valid; the simple one was
  chosen because the cost is trivial and it is easier to explain to a stakeholder. Reported as
  robustness.
- **Residual weakness:** "the first order" introduces a subtle left-truncation bias (customers who
  had already bought before the window enter with an order that is not really their first).
  Affects ~40 of 94,703 customers → **negligible**.
- **Verdict:** correct and well verified.

### D4. Two-sided test, α = 0.05

- **Rationale:** two-sided because the redesign **could also lower** the AOV (e.g. if the
  "free shipping" bar makes the customer cap their spend at the threshold). That outcome must be
  formally detectable. α = 0.05 is the industry standard.
- **Alternative:** one-sided (more power). Rejected: in product experimentation, two-sided is
  recommended unless there is a strong justification, and there is none here.
- **Verdict:** correct and conservative.

### D5. Relevance MDE = +3% relative

- **Decision:** the AOV must rise by ≥ +3% to justify the redesign's cost.
- **Declared rationale:** below ~+3% the annual incremental margin does not cover the cost of
  operating a recommendation engine.
- **Residual weakness — the project's weakest point:** the +3% is an **assumed business rule, not
  derived from a real cost model**. In a real project one would need to estimate engineering cost,
  model maintenance cost, and the per-order margin, and solve for the break-even. Here it is a
  number set by hand.
- **Mitigation:** (a) it is declared as an assumption; (b) Phase 4's decision sweep (§4.5) shows
  what would happen with different MDEs; (c) the effect found (+5.7%) clears the threshold
  comfortably, so the conclusion is not sensitive to moving the MDE between +3% and +4%.
- **Verdict:** acceptable for a portfolio, but it is the point I would reinforce first.

### D6. Multiplicity correction: Benjamini-Hochberg over guardrails; primary excluded

- **Rationale:** the primary is **a single pre-specified test** → it does not enter any
  correction (standard practice). Over the family of ~4 guardrails + segments, the **false
  discovery rate (FDR)** is controlled with BH, not the strict FWER (Bonferroni), because the goal
  is to not lose power over secondary monitoring tests.
- **Alternative:** Bonferroni. More conservative; it was used **in addition** to BH in the
  p-hacking demo to show the contrast.
- **Verdict:** correct. The BH vs. Bonferroni choice is justified by the goal (FDR vs. FWER),
  which is exactly the reasoning expected.

### D7. Decision rule: CI vs. MDE, not just the p-value

- **Decision:** LAUNCH only if (p < 0.05) **and** (95% CI of the lift entirely above +3%) **and**
  (no guardrail degraded). ITERATE if significant but the CI touches the MDE. DO NOT LAUNCH
  otherwise.
- **Rationale:** at n ≈ 47k/group, a trivial effect also comes out "significant". Anchoring the
  decision on whether **the entire confidence interval** clears the business threshold is what
  separates significance from relevance. The ITERATE branch avoids the binary launch/don't-launch.
- **Verdict:** excellent. It is the project's core and it is well posed. Phase 4 §4.5 verifies
  that all three branches are reachable.

### D8. Synthetic effect model: diluted, multiplicative, random responders

- **Decision:** `aov_T = aov_C · (1 + δ_resp + ε)` for the 20% of treated units that responds;
  δ_resp = 0.25; ATE = +5%. Responders drawn **independent of the order's value**.
- **Rationale:** partial adoption (only a fraction responds) is realistic; a redesign does not
  move everyone. The multiplicative form fits a % MDE.
- **Residual weakness (important):** two model choices **shape the results**:
  1. **Random responders** → the effect is homogeneous by construction. Phase 5's conclusion
     "the effect does not vary by segment" is partly **baked into the design**. A more realistic
     model of the free-shipping bar would concentrate the effect on orders just below the
     threshold (a real heterogeneous effect). Mentioned as an extension (§1.7b) but not run.
  2. **Multiplicative** → it automatically generates a larger absolute lift in large baskets,
     which is exactly the artifact the p-hacking demo (§5.5) exploits. With an additive effect,
     that demo would come out differently.
- **Mitigation:** both choices are **declared** and their consequences are **explicitly
  analyzed** (homogeneity is tested, not assumed; the multiplicative artifact is explained). The
  project does not hide that these results depend on the model.
- **Verdict:** defensible and well documented, but it is the decision with the most "researcher
  degrees of freedom". The honesty with which it is treated compensates for that.

---

## Part II — Data and preparation (Phases 2-3)

### D9. Valid statuses = {delivered, shipped, invoiced, approved, processing}

- **Rationale:** a paid order is a "completed purchase" even if it hasn't arrived yet. `canceled`,
  `unavailable`, `created` are excluded (they don't represent an effective purchase).
- **Robustness:** `is_delivered` is kept for an analysis restricted to delivered orders only.
- **Verdict:** correct; the sensitivity analysis is planned.

### D10. Time window 2017-01 → 2018-08

- **Rationale:** 2016 and Sept-Oct 2018 are residual (export cutoff). The Phase 2 audit verified
  that restricting **does not change the mean AOV** (137.42 → 137.37) → this is an adjustment
  **for realism** (making the duration resemble an experiment), not a bias correction.
- **Verdict:** correct and, above all, **not oversold** (it is explicitly stated to be cosmetic).

### D11. `log(AOV)` as a robustness path, not as the primary

- **Finding from the Phase 1-2 audit:** the t-test on `log(AOV)` tests the **ratio of geometric
  means** (≈ median), which is a **different business question**, not a "more powerful" version
  of the AOV. The business wants the arithmetic mean (revenue = mean × volume).
- **Verdict:** a subtle and correct distinction. Many portfolio projects confuse this.

### D12. Winsorization at p99.5, only in the significance-test column

- **Decision:** `merch_value_w` clips at p99.5 (473 orders, 0.50%); the **descriptive** AOV is
  reported unwinsorized (R$ 137.42); the test is reported **with and without**.
- **Rationale:** the extremely heavy tail (max R$ 13,440 vs. median R$ 87; kurtosis 271) inflates
  the variance and costs power. Winsorizing reduces the CV from 1.52 to 1.28. It is done **only
  for the significance test** because winsorizing shifts the mean by −2.4% and must not
  contaminate the descriptive statistics.
- **Residual weakness:** the p99.5 threshold is a **researcher degree of freedom**. It is
  **pre-specified in the audit before seeing results** and it is also reported unwinsorized (both
  give the same decision), which is the correct way to handle it, but it remains a choice.
- **Verdict:** well managed. The golden rule —pre-specify and report both— is followed.

### D13. Review deduplication by `review_answer_timestamp`

- **Rationale:** 551 orders have >1 review; keeping the most recent by timestamp (not by CSV row
  order) is the principled criterion. Impact on the mean: none (4.087 vs. 4.086), but it is done
  correctly regardless.
- **Verdict:** correct, though inconsequential.

### D14. Covariate balance check: |SMD| < 0.10 + omnibus test

- **Rationale:** the |SMD| < 0.10 threshold is the literature standard (Austin) for "balanced".
  Complemented with a χ²/Welch omnibus test per covariate.
- **Result:** all |SMD| ≤ 0.02; no omnibus test significant (minimum p 0.32).
- **Minor weakness:** with 6 covariates and 1 assignment, the balance is almost trivially good
  (randomization over n ≈ 95k). The check is correct but not very demanding in this context. What
  does add value is the **point A/A check on the outcome** (+1.2%, p = 0.235), which reveals this
  particular seed's baseline imbalance.
- **Verdict:** correct; the informative part is the A/A on the outcome, not the covariates' SMD.

---

## Part III — Statistical design and execution (Phase 4)

### D15. Primary test = Welch's t (not Student, not Mann-Whitney, not permutation)

- **Three-layer rationale:**
  1. The business wants the **mean** → this rules out Mann-Whitney (stochastic dominance) and the
     t-test on log (geometric mean) as primaries.
  2. At n ≈ 47k/group, the **CLT** makes the sampling distribution of the mean normal despite the
     skew of 9.8 → the t-test is valid. **Empirically verified**: D'Agostino on 5,000 bootstrap
     means gives p = 0.83; and the A/A test over 2,000 partitions gives 5.0% false positives.
  3. Welch and not Student because the assumption check shows that **under H1 the group variances
     differ** (the diluted effect inflates the treatment's variance; Levene p = 1.6·10⁻⁶).
- **Verdict:** **exemplary.** This kind of reasoning —checking the assumption, and having the
  check's result *change* the choice of test— is what distinguishes a rigorous analysis.

### D16. Power analysis: analytical + simulated

- **Rationale:** the analytical calculation (`TTestIndPower`) assumes a uniform effect; the
  simulated one (1,000 re-split + re-injection replicates) captures the real variance of the
  diluted effect.
- **Finding:** the power penalty from dilution is **< 1 pp** across the whole n range. Phase 1's
  prediction ("the diluted effect will lower power") was reasonable but **wrong in magnitude** —
  the AOV's natural variance (CV ≈ 1.5) dominates. And the estimator is **unbiased** (mean of
  1,000 replicates = 5.00%).
- **Verdict:** excellent. Quantifying one's own prediction and finding it wrong, and saying so, is
  exactly what is asked for.

### D17. A/A with 2,000 partitions + KS uniformity test

- **Rationale:** empirically validate that the pipeline **does not generate false positives**
  before introducing any effect. 2,000 (raised from 1,000 after seeing that the winsorized variant
  came close to a KS p = 0.044 by chance).
- **Result:** 5.0% false positives [4.0; 5.9] across the 3 metrics; uniform p-values (KS ≥ 0.5).
- **Verdict:** **the project's most valuable piece from the point of view of an experimentation
  role.** The A/A test is the correct way to certify a new experimentation engine.

### D18. Bootstrap (10,000) of the mean ratio

- **Rationale:** a CI with no distributional assumption, as a robustness check for Welch's CI.
- **Verdict:** correct; the bootstrap CI [4.05%; 8.19%] agrees with Welch's.

### D19. Guardrails with no injected effect

- **Decision:** no effect is injected into G1-G4; they come out flat by construction.
- **Residual weakness:** this makes the finding "no guardrail degrades" **trivially true**. The
  project **does not demonstrate that the guardrail tests would detect a real regression** — only
  the A/A calibration suggests it indirectly.
- **Mitigation:** declared as an extension ("inject a sub-threshold regression into G1 and see if
  the design catches it"). This would be improvement #2 I would make.
- **Verdict:** acceptable but a missed content opportunity.

### D20. G2 (cancellation) over the full orders table

- **Rationale:** the analytical table already filters out invalid statuses, so cancellation is
  evaluated over the full `olist_orders`, reassigning by customer with the same seed. Proportion
  z-test (rare event, 0.6%).
- **Verdict:** correct; it is the kind of detail a careless reviewer misses.

---

## Part IV — Evaluation (Phase 5)

### D21. ANCOVA / covariate adjustment with HC3 errors

- **Rationale:** regressing the outcome on `treatment` + predictive covariates (number of items,
  freight, category, region, quarter) reduces the residual variance without biasing the estimator
  (equivalent to CUPED when there is no pre-period). HC3 for the heteroscedasticity.
- **Result:** R² = 0.20 → **SE −11.2%**; the estimator moves from +5.67% to +5.19% (closer to the
  real +5%).
- **Honest nuance (from the Phase 5 audit):** the SE reduction is the **robust, generalizable**
  benefit; the point shift is partly specific to this sample and **is not sold as a general
  property**.
- **Verdict:** correct and with the right nuance.

### D22. Pre-specified segments (5), not exploratory

- **Decision:** `cesta`, `payment_type`, `macro_region`, `trimestre`, `cat_grupo`, declared
  **before** looking at per-segment results. "New vs. repeat customer" was **discarded** as
  degenerate (n_repeat ≈ 40, a consequence of the dedup) — declared, not hidden.
- **Verdict:** correct. Pre-specification is defense #1 against p-hacking.

### D23. Interaction tests on the log scale (relative effect), not at the level scale

- **Rationale:** the effect is multiplicative → the **absolute** lift in R$ is mechanically larger
  in large baskets. A level-scale test would detect "heterogeneity" that is an artifact. The
  business question is whether the **%** changes → log scale.
- **Verdict:** **subtle and correct.** This is the kind of decision that sets a senior analyst
  apart.

### D24. Switch to Wald HC3 (from the homoscedastic F-test) after the audit

- **Reason:** the interaction tests used the homoscedastic F-test, but under H1 there is
  heteroscedasticity (Levene level p = 8·10⁻⁸, log p = 0.019). Switched to Wald with HC3 errors.
- **Impact:** §5.4 unchanged in conclusion; §5.5 (p-hacking) **was reinforced** — with correct SE,
  the level-scale test's artifacts survive Bonferroni (3 after BH, 2 after Bonferroni), and
  nothing survives at the log scale.
- **Verdict:** the audit did its job. The corrected result is stronger, not weaker.

### D25. P-hacking demo: 38 cuts, level vs. log, BH vs. Bonferroni

- **Verdict:** **the project's most original piece.** It empirically demonstrates that
  **correcting for multiplicity does not save a badly posed estimand**: on the wrong scale, the
  false findings survive even Bonferroni. Rarely seen in portfolios.

### D26. Economic impact: linear extrapolation + 15% commission

- **Residual weaknesses:**
  1. **Linear extrapolation** of the per-order lift to the annual volume → ignores novelty,
     saturation, seasonality, and that the effect might not hold out of sample.
  2. The **15% commission** is an **invented** number (Olist does not publish its take rate in the
     dataset). It is labeled "for illustrative purposes".
  3. The AOV base comes from deduplicated orders and is applied to the non-deduplicated volume
     (−0.35% bias, documented).
- **Mitigation:** everything declared; the figure is presented as an "estimate" with a CI, not as
  a financial projection.
- **Verdict:** acceptable as an order of magnitude; it is not a business case.

---

## Part V — Project weaknesses (honest synthesis)

| # | Weakness | Severity | Intrinsic? | Status |
|---|---|---|---|---|
| 1 | **The experiment is simulated** → zero external validity | High (but it is the premise) | Yes | Declared in every document; the project validates the *process* |
| 2 | **The effect model** shapes the homogeneity and the p-hacking artifact | Medium | Partial | Consequences analyzed; **§4.8 adds a variant with a real heterogeneous effect** and shows the design detects it |
| 3 | **+3% relevance MDE** asserted | Medium | No | **RESOLVED** — `src/mde_cost_model.py` derives the break-even; the +3% is valid for volume ≥ ~415k orders/year (§1.5) |
| 4 | **A single analysis split** (SEED 42) | Low-Medium | No | **RESOLVED** — §4.6 multi-seed A/B (500): raw unbiased, CI coverage 0.94; the split is a normal realization |
| 5 | **Guardrails with no injected effect** → trivial "no degradation" | Medium | No | **RESOLVED** — §4.7 injects regressions into G1 and verifies the design catches −0.08 and lets −0.03 through; **guardrail rule corrected** to "significant AND magnitude" |
| 6 | **No retention / LTV metric** | Low | Yes (data) | Olist's 3% repeat purchase prevents it; declared |

**None is fatal.** After the applied improvements, the only ones remaining are #1 and #6, both an
unavoidable consequence of choosing Olist, and a residue of #2 (the effect's functional form
remains a declared choice). A side finding of improvement #3 (multi-seed): **winsorization
introduces a negative bias of −0.36 pp** in the point estimator — documented in §4.6, with raw
and winsor reported separately.

---

## Part VI — What is done especially well

1. **Pre-specification discipline.** H0/H1, a single metric, guardrails, MDE, and the decision
   rule written **before** touching the data. The notebook and the docs keep that order.
2. **Separating significance from relevance** with an operational rule (CI vs. MDE), not just talk.
3. **Assumption checks that change the decision** (Welch instead of Student because of
   heteroscedasticity under H1). Not decorative.
4. **A/A calibration** over 2,000 partitions — the correct way to certify a new experimentation
   pipeline.
5. **Quantifying one's own prediction and refuting it** (the dilution penalty turned out
   negligible) and saying so.
6. **The p-hacking demo** (correct vs. incorrect estimand; BH vs. Bonferroni).
7. **Traceability and reproducibility**: one commit per phase + audits; fixed seeds; byte-identical
   outputs after re-running. **Hardened after the user's criticism**: `params.yaml` as the single
   source of truth, `run_all.py` as the single entrypoint with a reproducibility report, the
   notebook reduced to a read-only layer (no parallel execution path), a `pytest` suite with a
   bit-for-bit idempotency test.
8. **Documented self-criticism**: 3 audits (this one included) that found and fixed real things
   (F-test → HC3; "nearly normal" → qualified; clustered SE → dedup; duplicated SEED →
   `config.py`).

---

## Part VII — Improvements applied (all of them)

The 6 improvements proposed in the first version of this audit **have been implemented** (2nd pass):

| # | Improvement | Where | Result |
|---|---|---|---|
| 1 | Regression injected into guardrail G1 + two-gate rule | `modeling.py :: guardrail_regression_scenarios` · §4.7 · §1.4 | The test catches −0.08 pts, lets −0.03 through; rule corrected to "significant **AND** magnitude" |
| 2 | Variant with a real heterogeneous effect (below the free-shipping threshold) | `modeling.py :: heterogeneous_effect_variant` · §4.8 | Interaction detected (p = 2·10⁻¹⁵); the segment analysis works when there is something to find |
| 3 | Multi-seed A/B (500 replicates), raw vs. winsor | `modeling.py :: ab_multiseed` · §4.6 | Raw unbiased (−0.03 pp), coverage 0.94; **winsor with −0.36 pp of bias** (new finding) |
| 4 | Cost model for the MDE | `src/mde_cost_model.py` · §1.5 · `f_mde_breakeven.png` | The +3% is break-even for volume ≥ ~415k orders/year (2-year payback) |
| 5 | All orders + customer-clustered SE | `modeling.py :: clustered_se_robustness` · §4.9 | Clustering inflates the SE by only 1.1%; lift +5.71% vs. +5.67% deduplicated |
| 6 | Formal SRM check | `balance_check.py` · §3.5 · `fase3_srm.csv` | χ² = 0.216, p = 0.642 → no SRM |

---

## Final verdict

**The project demonstrates senior-level statistical judgment in product experimentation.** The
decisions are justified, the alternatives considered, and — most importantly — the weaknesses
declared rather than hidden. The underlying limitation (simulated experiment) is unavoidable with
a public e-commerce dataset and is handled with exemplary honesty: the project does not claim to
have discovered anything about Olist, but to demonstrate that it knows how to **design, execute,
audit, and decide** an experiment. For a portfolio aimed at Product / Data Analyst roles, it more
than delivers.

The 6 improvements from Part VII have been applied in a second pass. None changed the decision
(**LAUNCH**); two brought new findings: (a) the guardrail rule needed two gates ("significant AND
magnitude") because at large n everything is significant; (b) winsorization, chosen to reduce
variance, introduces a point bias of −0.36 pp — raw and winsor are reported separately.
