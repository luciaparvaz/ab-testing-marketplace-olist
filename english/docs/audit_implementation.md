# Implementation audit — does the code do what the documents say?

> Fourth round of self-review. Complements the three previous audits (`audit_phase1_phase2.md`,
> `audit_phase5.md`, `audit_global.md`), which focused on the **numbers** and the
> **methodological decisions**. None of the three compared, line by line, the text of a `.md` file
> against the code that is supposed to produce it. This one does: a full read of `params.yaml`,
> `run_all.py`, the modules in `src/`, and the tests in `tests/`, checking every design claim
> against its actual implementation.
>
> **Verdict:** the experimental design remains sound. **Two real implementation defects** were
> found that the previous audits did not catch, because they did not audit code — neither changed
> the final decision (LAUNCH), but both contradicted guarantees the project explicitly states.
> Both are fixed, with a regression test added for each.

---

## Finding 1 (high severity, fixed) — G2 was recomputing the control/treatment assignment

**Problem.** The design requires a **single** control/treatment assignment, computed once per
`customer_unique_id` and persisted in `analytical_table.parquet` (§1.3). `modeling.py ::
g2_cancellation_guardrail()` recomputed it from scratch with `rng.choice(size=len(o))` on a table
that **does not preserve the same row order** as the analytical table (G2 does not apply
`VALID_STATUS`, because it needs to keep the `canceled` orders, which is exactly what it measures).
With a position-indexed assignment and different row orderings, a given customer's group in G2
could fail to match their real group.

With the current parameters this went unnoticed (no effect is injected into guardrails, so both
splits are interchangeable), but it was a verifiable internal inconsistency: the control/treatment
partition was not the same at every point in the pipeline, contradicting §1.3.

**Fix applied.** `g2_cancellation_guardrail()` now reads the `group` persisted in
`analytical_table.parquet` and does a `merge` on `customer_unique_id` (as
`clustered_se_robustness()` in the same file already correctly did), instead of reassigning by
position. G2's `n` drops to the customers present in the analytical table — correct, since they are
the only ones the experiment actually assigned to a group.

**Effect on the reported number — why this is not a simple label swap.** G2's cancellation rate
drops from 0.54%/0.57% (buggy version) to 0.02%/0.04% (fixed version): a drop of an order of
magnitude, not a simple relabeling of groups. The reason is that the `inner join` against
`analytical_table.parquet` now excludes customers whose only order in the window was canceled —
they never had a valid order, so they were never really assigned to a group, and should not count
in an experiment guardrail. Before, the guardrail measured cancellation over **everyone who bought
in the window** (a figure close to the Phase 2 global cancellation rate, 0.63%,
`phase2_summary.json :: global_cancellation_rate_pct`); it now measures cancellation over **whoever
was actually assigned to the experiment**, which by construction excludes anyone who only
canceled. These are different populations by design — mixing in people the experiment never
touched would artificially inflate the base rate and dilute any real degradation signal — and this
is the methodologically correct definition for an experiment guardrail, not an inconsistency
between the old and new version. It is documented in `phase4_summary.json`'s own `guardrails_note`
field so that anyone comparing both numbers has the context without having to read the code.

*(Field names below are the ones used in `english/src/`, which are the English translations of
the Spanish field names in `src/` — e.g. `significant_after_BH` corresponds to
`significativo_tras_BH` in the Spanish codebase. Both versions are functionally identical; see
`docs/audit_implementation.md` for the Spanish field names.)*

**Regression test:** `tests/test_outputs.py :: test_g2_uses_same_assignment_as_analytical_table`
independently recomputes control/treatment (a direct customer→group merge) and compares it against
what the real function returns.

---

## Finding 2 (high severity, fixed) — the two-gate rule never reached the decision code

**Problem.** The global audit (D19) correctly identified that at n≈47k/group, any minimal
regression in a guardrail comes out significant, and corrected the rule to "significant **AND**
magnitude ≥ threshold". That fix was demonstrated in `guardrail_regression_scenarios()` — an
isolated, purely illustrative function. The real evaluation, `run_ab_test()` →
`guard[k]["significant_after_BH"]`, and `run_all.py`'s reproducibility report
(`guard_ok = all(not g["significant_after_BH"] ...)`), **never applied any magnitude criterion**.
The "AND" rule was demonstrated in a JSON that no one read to make the decision.

**Fix applied.**
- `params.yaml` declares the §1.4 business thresholds (`guardrail_thresholds`): G1 review_score
  0.05 pts, G2 cancellation 0.2 pp, G3 freight ≥ 20% of the AOV increase. **G4 (frequency) has no
  quantified magnitude threshold in the original design** ("relevant magnitude" with no number) —
  it is explicitly left with only the significance criterion, declared as a known limitation
  instead of inventing an unfounded threshold.
- `config.py` exposes `GUARDRAIL_THRESHOLDS`, following the single-source-of-truth rule.
- `run_ab_test()` computes `magnitude_exceeds_threshold` and `blocks = significant_after_BH AND
  magnitude_exceeds_threshold` for each guardrail — this is now the field any consumer of the
  decision must read.
- `run_all.py::reproducibility_report()` checks `not g["blocks"]` instead of
  `not g["significant_after_BH"]`.

**Regression test:** `test_guardrail_blocks_is_two_gate_and` verifies that `blocks` is exactly the
declared AND; `test_guardrails_not_degraded` was updated to check `blocks` (the field that
actually governs the decision) instead of bare significance.

---

## Medium findings (fixed)

- **Balance check via raw-text parsing** in `run_all.py::reproducibility_report()`
  (`"False" not in bal.split("balanced")[1]`) — replaced with a `pandas` read and
  `bal["balanced"].all()`, identical to the equivalent check in `test_outputs.py`.
- **Outdated caption** in `figures_phase2.py` ("log(AOV) ... nearly normal"), which did not reflect
  the nuance already applied to the text in `audit_phase1_phase2.md` — corrected to "robust range
  for the t-test; CLT at large n".
- **Magic number `20`** (window length in months) hardcoded in `evaluation.py::main()` to annualize
  the economic impact — replaced with the same calculation derived from `WINDOW_START`/`WINDOW_END`
  that `tests/test_config.py::test_window_is_20_months` was already using to verify it indirectly.

## Low-impact findings (not fixed, documented as a known limitation)

- Order loading/filtering logic duplicated across 5–6 places in `src/` (the root cause of Finding
  1). A refactor (`src/data_loading.py::load_orders(...)`) is desirable but not urgent; left as
  future work.
- The "guardrail with injected effect" improvement (D19) only covers G1; G2–G4 have no equivalent
  power check.
- The cost model (`mde_cost_model.py`) does not discount future cash flows — reasonable for a model
  already declared illustrative (§1.5).

---

## Verification

Full pipeline re-run with `python run_all.py` after applying the two high-severity fixes: the
decision is still **LAUNCH**, with the same primary effect (+5.67%, 95% CI [3.99%, 7.34%]) and all
10 checks in the reproducibility report green, including the new
`guardrails: none blocks the launch (two-gate rule)`. Full `pytest` suite (30 fast tests + 3 slow
tests) green, including the 4 regression tests added by this audit.
