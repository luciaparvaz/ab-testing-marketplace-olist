"""
Efecto de tratamiento sintético — modelo diluido (docs/01 §1.7b).

Módulo sin efectos secundarios al importar (a diferencia de los scripts de fase). Lo comparten
`modeling.py` y `evaluation.py`, que antes lo duplicaban / se importaban entre sí.
"""
from __future__ import annotations

import numpy as np

from config import DELTA_RESP, EPS_SD, P_RESP


def inject_diluted_effect(values: np.ndarray, is_treat: np.ndarray, rng: np.random.Generator,
                          p_resp: float = P_RESP, delta_resp: float = DELTA_RESP,
                          eps_sd: float = EPS_SD) -> np.ndarray:
    """Devuelve `values` con el efecto aplicado SOLO a los tratados.

    Para cada tratado i:  R_i ~ Bernoulli(p_resp);
        si R_i = 1:  v_i *= (1 + delta_resp + eps_i),  eps_i ~ N(0, eps_sd)
        si R_i = 0:  v_i sin cambio
    Efecto medio (ATE) = p_resp * delta_resp.
    """
    out = values.astype(float).copy()
    tr = np.where(is_treat)[0]
    responders = rng.random(tr.size) < p_resp
    eps = rng.normal(0.0, eps_sd, tr.size)
    factor = np.where(responders, 1.0 + delta_resp + eps, 1.0)
    out[tr] = out[tr] * factor
    return out
