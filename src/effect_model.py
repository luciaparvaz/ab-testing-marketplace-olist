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


def compute_winsor_cap(pre_effect_values: np.ndarray, q: float) -> float:
    """Cap de winsorización, ÚNICA fuente de verdad (corrige auditoría §2.1/§2.2: antes había 3
    semánticas distintas -- cap pre-efecto en 5 sitios vía `merch_value_w.max()`, cap RE-CALCULADO
    sobre datos post-efecto en `clustered_se_robustness` -- que producían dos cifras de "sesgo de
    winsorización" incompatibles en el mismo `fase4_resumen.json`).

    Se calcula SIEMPRE sobre `pre_effect_values`, es decir sobre `merch_value` ANTES de inyectar el
    efecto sintético (control + treatment juntos, pero ninguno de los dos aún tratado). Esto no es
    "usar el contrafactual de los tratados": antes de inyectar el efecto no hay ninguna diferencia
    real entre los dos grupos (ambos son el mismo Olist histórico sin experimento), así que este cap
    es equivalente en distribución a derivarlo solo del grupo de control, o de un periodo histórico
    anterior al experimento -- exactamente la buena práctica de fijar el umbral de winsorización con
    datos NO influidos por el propio tratamiento que se va a testear (el mismo principio que motiva
    la demo de p-hacking del proyecto: no tomar decisiones de diseño mirando el resultado bajo H1).
    Es la razón por la que `clustered_se_robustness` (que recalculaba el cap sobre `mv_e`, ya con el
    efecto inyectado) daba una cifra distinta: ese cap sí dependía de cuánto había inflado el propio
    efecto a los tratados, y por tanto no es replicable en un experimento real donde el umbral debe
    fijarse ANTES de ver el resultado.
    """
    return float(np.quantile(pre_effect_values, q))


def winsorize_outcome(values: np.ndarray, cap: float) -> np.ndarray:
    """Aplica el cap ya calculado (por `compute_winsor_cap`) a cualquier serie de outcome -- efecto
    inyectado o no. Un solo punto de aplicación para los ~5 sitios que antes repetían
    `np.minimum(x, df["merch_value_w"].max())` de forma independiente."""
    return np.minimum(values, cap)
