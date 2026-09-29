"""
Synthetic treatment effect — diluted model (docs/01 §1.7b).

Module with no side effects on import (unlike the phase scripts). Shared by
`modeling.py` and `evaluation.py`, which used to duplicate it / import each other.
"""
from __future__ import annotations

import numpy as np

from config import DELTA_RESP, EPS_SD, P_RESP


def inject_diluted_effect(values: np.ndarray, is_treat: np.ndarray, rng: np.random.Generator,
                          p_resp: float = P_RESP, delta_resp: float = DELTA_RESP,
                          eps_sd: float = EPS_SD) -> np.ndarray:
    """Returns `values` with the effect applied ONLY to the treated units.

    For each treated unit i:  R_i ~ Bernoulli(p_resp);
        if R_i = 1:  v_i *= (1 + delta_resp + eps_i),  eps_i ~ N(0, eps_sd)
        if R_i = 0:  v_i unchanged
    Mean effect (ATE) = p_resp * delta_resp.
    """
    out = values.astype(float).copy()
    tr = np.where(is_treat)[0]
    responders = rng.random(tr.size) < p_resp
    eps = rng.normal(0.0, eps_sd, tr.size)
    factor = np.where(responders, 1.0 + delta_resp + eps, 1.0)
    out[tr] = out[tr] * factor
    return out


def compute_winsor_cap(pre_effect_values: np.ndarray, q: float) -> float:
    """Winsorization cap, SINGLE source of truth (fixes audit §2.1/§2.2: there used to be 3
    different semantics -- pre-effect cap in 5 places via `merch_value_w.max()`, cap
    RE-COMPUTED on post-effect data in `clustered_se_robustness` -- which produced two
    incompatible "winsorization bias" figures in the same `fase4_resumen.json`).

    Always computed on `pre_effect_values`, i.e. on `merch_value` BEFORE the synthetic effect is
    injected (control + treatment together, neither yet treated). This is not "using the
    counterfactual of the treated": before injecting the effect there is no real difference
    between the two groups (both are the same historical Olist data with no experiment), so this
    cap is distributionally equivalent to deriving it from the control group alone, or from a
    historical period before the experiment -- exactly the good practice of fixing the
    winsorization threshold with data NOT influenced by the treatment being tested (the same
    principle behind the project's p-hacking demo: don't make design decisions by looking at the
    result under H1). This is why `clustered_se_robustness` (which used to recompute the cap on
    `mv_e`, already with the effect injected) gave a different figure: that cap did depend on how
    much the effect itself had inflated the treated units, and is therefore not replicable in a
    real experiment where the threshold must be fixed BEFORE seeing the result.
    """
    return float(np.quantile(pre_effect_values, q))


def winsorize_outcome(values: np.ndarray, cap: float) -> np.ndarray:
    """Applies the already-computed cap (from `compute_winsor_cap`) to any outcome series --
    effect injected or not. A single application point for the ~5 places that used to repeat
    `np.minimum(x, df["merch_value_w"].max())` independently."""
    return np.minimum(values, cap)
