# Phase 6 — Deployment (portfolio format)

> CRISP-DM · Phase 6 of 6

In a portfolio project, "deployment" is **communicating the result** to its different audiences.
Deliverables:

| Deliverable | File | Audience |
|---|---|---|
| **Executive summary (1 page)** | `docs/resumen_ejecutivo.md` | Non-technical stakeholder (Product Lead, management) |
| **Presentation notebook** | `notebooks/ab_test_olist.ipynb` (+ jupytext `.py` source) | Technical reviewer / Data recruiter |
| **Repository README** | `README.md` | GitHub visitor |
| **LinkedIn post draft** | `docs/linkedin_post.md` | Professional network |
| **Per-phase documentation + audits** | `docs/0X_*.md`, `docs/auditoria_*.md` | Full trace of the reasoning |

## Reproducibility

Refactored after the user's review ("it's not reproducible if it's all in a notebook"):

- **Single source of truth for the parameters:** `params.yaml`, loaded by `src/config.py`. No
  other module defines `SEED`, `ALPHA`, the time window, the cost model, etc. (`tests/
  test_config.py` verifies this with an AST analysis).
- **Single entrypoint:** `python run_all.py` runs the 6 phases in dependency order, checks that
  each one generates its outputs, and finishes with a **reproducibility report** (decision ==
  LAUNCH, A/A ~5%, A/B CI above the MDE, no SRM, guardrails intact, ...). It exits with code ≠ 0
  if something doesn't check out. ~2 min.
- **No parallel execution paths:** the `ab_test_olist.ipynb` notebook **only reads** `outputs/`
  and shows figures + narrative; it recomputes nothing. It used to have a second computation path
  (it called `modeling.main()` etc.), which was the valid criticism.
- **`inject_diluted_effect`** lives in `src/effect_model.py` (no side effects on import); it used
  to be imported by `evaluation.py` from `modeling.py`, coupling the phases.
- **Absolute paths** derived from the repo's location → works from any CWD.
- **Tests:** `pytest` (fast: config, synthetic effect, result invariants) and
  `pytest -m slow` (re-runs `modeling.main()` twice and checks that the JSON is identical).
- The raw Olist CSVs **are not versioned** (CC BY-NC-SA 4.0 license).
- `notebooks/ab_test_olist.py` (jupytext *percent*) is the version-controllable source of the notebook.

## Communication recommendation (LinkedIn)

The chosen angle is not "I ran an A/B test" (generic) but the **methodological finding**:
correcting for multiple comparisons does not protect against p-hacking if the *estimand* is
wrongly posed (measuring the effect in absolute value instead of in percentage, over cuts
correlated with basket size, fabricates "winning segments" that survive even Bonferroni). It is a
concrete, counterintuitive point, demonstrated with code.

## What is NOT delivered (and why)

- **There is no real technical deployment recommendation** (feature flags, progressive rollout,
  production monitoring): the effect is simulated and there is no system to deploy. The executive
  summary does include the list of metrics to monitor *if the experiment were real*.
- **There is no predictive model**: this is a causal inference / experimentation project, not an
  ML one.
