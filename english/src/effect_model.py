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
