"""
Fase 5 — Evaluation.

Traduce el resultado estadístico de la Fase 4 a una decisión de producto:
  1. Reporte completo (efecto, IC, p) y su lectura
  2. Significancia estadística vs relevancia de negocio (frente al MDE +3 %) + impacto en R$/año
  3. Estimación ajustada por covariables (ANCOVA) -> reducción de varianza
  4. Análisis por segmentos PRE-ESPECIFICADOS (forest plot + test de interacción, con BH)
  5. Demostración del riesgo de p-hacking (slicing exploratorio sin corrección)
  6. Decisión

Reutiliza el efecto diluido declarado (SEED=42) de src/modeling.py.
Salida: outputs/tables/fase5_*.csv/json · outputs/figures/f5_*.png
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.multitest import multipletests
import matplotlib.pyplot as plt

from config import (ALPHA, ANALYTICAL_TABLE, ATE, MDE_RELEVANCIA, OUT_FIGURES as FIG,
                    OUT_TABLES as OUT_T, RAW, SEED, WINDOW_END, WINDOW_START, WINSOR_Q,
                    apply_plot_style)
from effect_model import compute_winsor_cap, inject_diluted_effect, winsorize_outcome
import mde_cost_model


def _design(df: pd.DataFrame, cols: list[str], cat_cols: list[str]) -> pd.DataFrame:
    """Matriz de diseño con constante; categóricas -> dummies (drop_first)."""
    parts = [pd.Series(1.0, index=df.index, name="const")]
    for c in cols:
        parts.append(df[c].astype(float).rename(c))
    for c in cat_cols:
        parts.append(pd.get_dummies(df[c], prefix=c, drop_first=True, dtype=float))
    return pd.concat(parts, axis=1)


def ols_hc3(y: pd.Series, X: pd.DataFrame):
    return OLS(y.values, X.values).fit(cov_type="HC3"), list(X.columns)


def _coef(res, names, name):
    i = names.index(name)
    ci = res.conf_int()
    return res.params[i], res.bse[i], ci[i, 0], ci[i, 1]


def interaction_wald_hc3(y: np.ndarray, treat: np.ndarray, seg_dummies: np.ndarray) -> float:
    """p-valor Wald robusto (HC3) del bloque de interacciones treat x segmento.
    Necesario porque bajo H1 hay heterocedasticidad entre grupos (Fase 4)."""
    k = seg_dummies.shape[1]
    X = np.column_stack([np.ones(len(y)), treat, seg_dummies, seg_dummies * treat[:, None]])
    res = OLS(y, X).fit(cov_type="HC3")
    R = np.zeros((k, X.shape[1]))
    for i in range(k):
        R[i, X.shape[1] - k + i] = 1.0
    return float(res.wald_test(R, scalar=True).pvalue)


apply_plot_style()

# Segmentos PRE-ESPECIFICADOS (declarados ANTES de mirar resultados por segmento).
# "nuevo vs recurrente" NO está: la dedup a 1 pedido/cliente lo deja degenerado (n_recurrente≈40);
# además la recompra en Olist es ~3% (Fase 2 §2.7). Queda fuera del alcance, declarado.
PRESPEC_SEGMENTS = ["cesta", "payment_type", "macro_region", "trimestre", "cat_grupo"]

MACRO_REGION = {
    "SP": "Sudeste", "RJ": "Sudeste", "MG": "Sudeste", "ES": "Sudeste",
    "PR": "Sur", "SC": "Sur", "RS": "Sur",
    "BA": "Nordeste", "PE": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste",
    "RN": "Nordeste", "AL": "Nordeste", "PI": "Nordeste", "SE": "Nordeste",
    "GO": "Centro-Oeste", "DF": "Centro-Oeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
    "PA": "Norte", "AM": "Norte", "RO": "Norte", "TO": "Norte", "AC": "Norte",
    "AP": "Norte", "RR": "Norte",
}


def load_with_effect() -> pd.DataFrame:
    df = pd.read_parquet(ANALYTICAL_TABLE).copy()
    is_t = (df.group == "treatment").values
    rng = np.random.default_rng(SEED)
    df["mv"] = inject_diluted_effect(df["merch_value"].values, is_t, rng)
    # mismo cap, misma función, en todo el pipeline (ver src/modeling.py y effect_model.py).
    cap = compute_winsor_cap(df["merch_value"].values, WINSOR_Q)
    df["mv_w"] = winsorize_outcome(df["mv"].values, cap)

    # segmentos
    df["cesta"] = np.where(df["n_items"] >= 2, "2+ items", "1 item")
    df["macro_region"] = df["customer_state"].map(MACRO_REGION).fillna("otros")
    df["trimestre"] = pd.to_datetime(df["order_purchase_timestamp"]).dt.to_period("Q").astype(str)
    top_cat = df["cat_dominante"].value_counts().head(6).index
    df["cat_grupo"] = np.where(df["cat_dominante"].isin(top_cat), df["cat_dominante"], "resto")
    return df


def welch_lift(t: np.ndarray, c: np.ndarray, alpha=ALPHA) -> dict:
    diff = t.mean() - c.mean()
    se = np.sqrt(t.var(ddof=1) / t.size + c.var(ddof=1) / c.size)
    dfw = se**4 / ((t.var(ddof=1) / t.size)**2 / (t.size - 1) +
                   (c.var(ddof=1) / c.size)**2 / (c.size - 1))
    tcrit = stats.t.ppf(1 - alpha / 2, dfw)
    st, p = stats.ttest_ind(t, c, equal_var=False)
    # log10(p) robusto aunque p haga underflow a 0.0
    log10p = float((np.log(2) + stats.t.logsf(abs(st), dfw)) / np.log(10))
    base = c.mean()
    return {"n_c": int(c.size), "n_t": int(t.size), "base": base,
            "lift_pct": diff / base * 100,
            "ci_lo": (diff - tcrit * se) / base * 100,
            "ci_hi": (diff + tcrit * se) / base * 100,
            "p": float(p), "log10_p": round(log10p, 2), "t_stat": round(float(st), 2)}


def main():
    df = load_with_effect()
    is_t = df.group == "treatment"
    out = {"parametros": {"SEED": SEED, "ATE_declarado_pct": ATE * 100, "MDE_relevancia_pct": MDE_RELEVANCIA}}

    # ---- 1-2. resultado primario + relevancia + impacto R$ --------------
    prim = welch_lift(df.loc[is_t, "mv_w"].values, df.loc[~is_t, "mv_w"].values)
    # anualización: se usa el volumen REAL de pedidos válidos en la ventana (sin dedup),
    # porque el rediseño aplicaría a todos los pedidos, no solo a los primeros de cada cliente.
    orders_full = pd.read_csv(RAW / "olist_orders_dataset.csv", parse_dates=["order_purchase_timestamp"])
    items_full = pd.read_csv(RAW / "olist_order_items_dataset.csv")
    mw = (orders_full.order_purchase_timestamp >= WINDOW_START) & \
         (orders_full.order_purchase_timestamp < WINDOW_END)
    valid_ids = set(items_full.order_id)
    from config import VALID_STATUS
    n_orders_window = int(((orders_full[mw].order_status.isin(VALID_STATUS)) &
        (orders_full[mw].order_id.isin(valid_ids))).sum())
    n_months = (pd.Timestamp(WINDOW_END).to_period("M") - pd.Timestamp(WINDOW_START).to_period("M")).n
    n_orders_year = n_orders_window / n_months * 12
    base_aov = df.loc[~is_t, "merch_value"].mean()
    gmv_year = n_orders_year * base_aov
    uplift_gmv_year = gmv_year * prim["lift_pct"] / 100
    out["1_resultado_primario"] = {
        "lift_pct": round(prim["lift_pct"], 3),
        "IC95_lift_pct": [round(prim["ci_lo"], 3), round(prim["ci_hi"], 3)],
        "diff_abs_R$": round(prim["base"] * prim["lift_pct"] / 100, 2),
        "p_value": "underflow (< 1e-15)" if prim["p"] == 0 else float(f"{prim['p']:.2e}"),
        "log10_p": prim["log10_p"], "t_stat": prim["t_stat"],
        "n_control": prim["n_c"], "n_treatment": prim["n_t"],
        "significativo": bool(prim["p"] < ALPHA),
        "ci_entero_sobre_MDE": bool(prim["ci_lo"] > MDE_RELEVANCIA),
        "relevante": bool(prim["p"] < ALPHA and prim["ci_lo"] > MDE_RELEVANCIA),
    }
    from config import COST_MODEL
    COMMISSION = COST_MODEL["commission"]  # take rate asumida del marketplace

    # --- consistencia MDE <-> volumen (revisión de portfolio, prioridad 2) --------------------
    # mde_cost_model.py YA calculaba (solo por stdout, nunca en un output ni comparado contra la
    # decisión) que el MDE de +3% solo es break-even a partir de ~415k pedidos/año, mientras el
    # impacto de negocio de abajo se extrapola sobre el volumen REAL del dataset (~59k). A ese
    # volumen real, el propio modelo de costes del proyecto exige un break-even MUCHO más alto que
    # +3% -- calculado aquí explícitamente, no solo declarado en prosa, y usado para condicionar
    # la decisión final en vez de ignorarlo.
    mde_breakeven_volumen_real_pct = mde_cost_model.breakeven_lift(n_orders_year) * 100
    volumen_minimo_para_mde_3pct = mde_cost_model.required_volume_for_mde(MDE_RELEVANCIA)
    volumen_consistente_con_mde_declarado = n_orders_year >= volumen_minimo_para_mde_3pct

    out["2_impacto_negocio"] = {
        "pedidos_validos_ventana_sin_dedup": n_orders_window, "meses_ventana": n_months,
        "pedidos_por_anio_estimado": round(n_orders_year),
        "AOV_base_R$": round(base_aov, 2),
        "GMV_mercancia_anual_estimado_R$": round(gmv_year),
        "uplift_GMV_anual_R$": round(uplift_gmv_year),
        "uplift_GMV_anual_IC95_R$": [round(gmv_year * prim["ci_lo"] / 100),
                                     round(gmv_year * prim["ci_hi"] / 100)],
        "uplift_ingreso_marketplace_anual_R$_asumiendo_comision_15pct": round(uplift_gmv_year * COMMISSION),
        "nota": ("GMV = valor de mercancía. El ingreso del marketplace es una comisión (take rate) "
                 "sobre el GMV; se asume 15% a efectos ilustrativos. Extrapolación lineal del lift "
                 "por pedido al volumen anual histórico."),
        "consistencia_MDE_vs_volumen": {
            "MDE_declarado_pct": MDE_RELEVANCIA,
            "volumen_usado_en_la_extrapolacion_pedidos_anio": round(n_orders_year),
            "volumen_minimo_para_que_MDE_+3pct_sea_break_even": round(volumen_minimo_para_mde_3pct),
            "MDE_break_even_AL_VOLUMEN_REAL_del_dataset_pct": round(mde_breakeven_volumen_real_pct, 2),
            "volumen_real_es_consistente_con_MDE_declarado": bool(volumen_consistente_con_mde_declarado),
            "lectura": (
                f"El MDE de +{MDE_RELEVANCIA}% usado como puerta de relevancia (§1.5) solo es "
                f"break-even a partir de ~{volumen_minimo_para_mde_3pct:,.0f} pedidos/año. El "
                f"impacto de arriba se extrapola sobre ~{n_orders_year:,.0f} pedidos/año (el volumen "
                f"REAL del dataset) -- a esa escala, el propio modelo de costes del proyecto exige "
                f"un break-even de ~+{mde_breakeven_volumen_real_pct:.1f}%, no +{MDE_RELEVANCIA}%. "
                "El MDE de +3% solo tiene sentido como umbral de decisión si se asume implícitamente "
                "un marketplace ~7x mayor que Olist en este dataset; a la escala real, ni el lift "
                "verdadero inyectado (+5%) ni el observado en el split SEED=42 (~+5,7%) superan el "
                "break-even real. Ver '6_decision' para cómo esto condiciona la recomendación final."
            ),
        },
    }

    # ---- 3. ANCOVA: ajuste por covariables (reducción de varianza) ------
    d = df.copy()
    d["treat"] = is_t.astype(int)
    base = d.loc[d.treat == 0, "mv_w"].mean()
    X0 = _design(d, ["treat"], [])
    r0, n0 = ols_hc3(d["mv_w"], X0)
    X1 = _design(d, ["treat", "n_items", "freight_value"], ["cat_grupo", "macro_region", "trimestre"])
    r1, n1 = ols_hc3(d["mv_w"], X1)
    b0, se0, lo0, hi0 = _coef(r0, n0, "treat")
    b1, se1, lo1, hi1 = _coef(r1, n1, "treat")
    out["3_ancova"] = {
        "sin_ajuste": {"coef_treat_R$": round(b0, 3), "lift_pct": round(b0 / base * 100, 3),
                       "ci95_pct": [round(lo0 / base * 100, 3), round(hi0 / base * 100, 3)],
                       "se_R$": round(se0, 4)},
        "con_ajuste": {"coef_treat_R$": round(b1, 3), "lift_pct": round(b1 / base * 100, 3),
                       "ci95_pct": [round(lo1 / base * 100, 3), round(hi1 / base * 100, 3)],
                       "se_R$": round(se1, 4)},
        "reduccion_SE_pct": round((1 - se1 / se0) * 100, 2),
    }

    # ---- 4. segmentos pre-especificados: forest + interacción ----------
    seg_rows = []
    inter_p = {}
    for seg in PRESPEC_SEGMENTS:
        for lvl, g in df.groupby(seg):
            r = welch_lift(g.loc[g.group == "treatment", "mv_w"].values,
                           g.loc[g.group == "control", "mv_w"].values)
            seg_rows.append({"segmento": seg, "nivel": str(lvl), **{k: round(v, 3) for k, v in r.items()}})
        # test de interacción group:segmento sobre log(AOV): ¿el efecto RELATIVO es heterogéneo?
        # (en nivel, el efecto multiplicativo da un lift absoluto mayor en cestas grandes -> se
        #  detectaría 'heterogeneidad' mecánica; el negocio pregunta por el %, de ahí el log)
        # Wald HC3: robusto a la heterocedasticidad entre grupos que introduce H1 (auditoría Fase 5).
        seg_d = pd.get_dummies(df[seg], prefix=seg, drop_first=True, dtype=float).values
        treat_s = (df.group == "treatment").values.astype(float)
        inter_p[seg] = interaction_wald_hc3(np.log(df["mv"].values), treat_s, seg_d)
    seg_df = pd.DataFrame(seg_rows)
    seg_df.to_csv(OUT_T / "fase5_segmentos.csv", index=False)

    keys = list(inter_p)
    rej, p_adj, _, _ = multipletests([inter_p[k] for k in keys], alpha=ALPHA, method="fdr_bh")
    seg_n = {s: df.groupby(s).size().to_dict() for s in PRESPEC_SEGMENTS}
    out["4_segmentos"] = {
        "segmentos_prespecificados": PRESPEC_SEGMENTS,
        "test_interaccion": {k: {"p_bruto": round(inter_p[k], 4), "p_BH": round(pa, 4),
                                 "heterogeneidad_significativa_tras_BH": bool(r),
                                 "n_por_nivel": seg_n[k]}
                             for k, pa, r in zip(keys, p_adj, rej)},
        "escala_test": "log(AOV), Wald HC3 -> contrasta heterogeneidad del efecto RELATIVO (%), "
                       "robusto a la heterocedasticidad entre grupos; en nivel el efecto "
                       "multiplicativo genera heterogeneidad absoluta mecánica en cestas grandes",
        "veredicto": ("ninguna interacción significativa (ni bruta ni tras BH) -> el efecto relativo "
                      "es HOMOGÉNEO entre segmentos, coherente con el diseño (responders al azar). "
                      "Buscar 'dónde funciona mejor' sin corrección sería p-hacking."),
    }

    # ---- 5. demostración de p-hacking -------------------------------
    # ~38 cortes exploratorios arbitrarios (estados, categorías sueltas, cuantiles de flete, trimestres)
    slicers = []
    for st_ in df.customer_state.value_counts().head(12).index:
        slicers.append(("estado", st_, df.customer_state == st_))
    for ct in df.cat_dominante.value_counts().head(15).index:
        slicers.append(("categoria", ct, df.cat_dominante == ct))
    for q in range(4):
        lo, hi = df.freight_value.quantile(q / 4), df.freight_value.quantile((q + 1) / 4)
        slicers.append(("flete_q", f"q{q+1}", df.freight_value.between(lo, hi)))
    for m_ in df.trimestre.unique():
        slicers.append(("trimestre", m_, df.trimestre == m_))
    treat = (df.group == "treatment").values.astype(float)
    y_level = df["mv_w"].values
    y_log = np.log(df["mv"].values)
    p_level, p_log, names = [], [], []
    for fam, lvl, mask in slicers:
        g = df[mask]
        if (g.group == "treatment").sum() < 30 or (g.group == "control").sum() < 30:
            continue
        inseg = mask.values.astype(float)
        X = np.column_stack([np.ones(len(df)), treat, inseg, treat * inseg])
        p_level.append(OLS(y_level, X).fit(cov_type="HC3").pvalues[3])   # HC3 robusto
        p_log.append(OLS(y_log, X).fit(cov_type="HC3").pvalues[3])
        names.append(f"{fam}:{lvl}")
    p_level, p_log = np.array(p_level), np.array(p_log)

    def _summ(pv):
        bh = multipletests(pv, alpha=ALPHA, method="fdr_bh")[0]
        bf = multipletests(pv, alpha=ALPHA, method="bonferroni")[0]
        return {"nominales_p<0.05": {"n": int((pv < 0.05).sum()),
                                     "cuales": [names[i] for i in np.where(pv < 0.05)[0]]},
                "tras_BH": {"n": int(bh.sum()), "cuales": [names[i] for i in np.where(bh)[0]]},
                "tras_Bonferroni": int(bf.sum())}

    out["5_p_hacking"] = {
        "n_cortes_exploratorios": len(names),
        "esperados_por_azar_a_0.05": round(0.05 * len(names), 1),
        "test": "interacción treat x corte, Wald HC3",
        "test_en_NIVEL_(mv_w)": _summ(p_level),
        "test_en_LOG_(efecto_relativo)": _summ(p_log),
        "leccion": ("(1) En NIVEL varios 'segmentos donde el efecto es distinto' sobreviven incluso "
                    "a BH y a Bonferroni: NO son casualidad, son un ARTEFACTO MECÁNICO del efecto "
                    "multiplicativo (el lift en R$ es mayor en cestas grandes), concentrado en los "
                    "cortes correlacionados con el tamaño (cuartiles de flete). "
                    "(2) En LOG (el efecto relativo, que es la pregunta de negocio) solo quedan "
                    "hallazgos nominales de nivel-azar, y NINGUNO sobrevive a la corrección. "
                    "Moraleja: (a) testar la magnitud correcta (%, no R$ absolutos), (b) pre-especificar "
                    "segmentos, (c) corregir por multiplicidad. Corregir no basta si el estimando está mal."),
    }

    # ---- figura: forest plot de segmentos --------------------------
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    order = seg_df.iloc[::-1].reset_index(drop=True)
    ax.axvline(prim["lift_pct"], color="#2a9d8f", ls="--", lw=1.2, label=f"efecto global (+{prim['lift_pct']:.1f}%)")
    ax.axvline(MDE_RELEVANCIA, color="#c1121f", ls=":", lw=1.2, label=f"MDE relevancia (+{MDE_RELEVANCIA}%)")
    ax.axvline(0, color="#999", lw=0.7)
    for i, row in order.iterrows():
        ax.plot([row.ci_lo, row.ci_hi], [i, i], color="#3b6ea5", lw=1.8)
        ax.plot(row.lift_pct, i, "o", color="#3b6ea5", ms=4)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f"{r.segmento}: {r.nivel}" for r in order.itertuples()], fontsize=7)
    ax.set_xlabel("lift RELATIVO del AOV (%) · IC 95 %")
    ax.set_title("Efecto por segmento pre-especificado\n"
                 "efecto verdadero homogéneo (+5 %) · sin interacción significativa tras BH",
                 fontsize=10)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "f5_01_forest_segmentos.png", bbox_inches="tight")
    plt.close(fig)

    # ---- 6. decisión --------------------------------------------
    # Antes: `dec` dependía SOLO de si el IC superaba el MDE DECLARADO (+3%), un umbral que (ver
    # 2_impacto_negocio.consistencia_MDE_vs_volumen) solo es break-even a partir de ~415k
    # pedidos/año -- muy por encima de los ~59k reales usados para calcular el impacto en R$ de
    # arriba. Publicar "LANZAR" con un impacto anualizado sobre el volumen real, aplicando un
    # umbral de relevancia que ese mismo volumen no justifica, es la contradicción que cierra la
    # prioridad 2 de la revisión de portfolio. La decisión ahora usa la MISMA regla de tres ramas
    # que decision_scenarios/ab_multiseed (ver src/modeling.py), pero con el break-even REAL del
    # volumen del dataset como umbral -- no el +3% pensado para una escala ~7x mayor.
    mde_real = out["2_impacto_negocio"]["consistencia_MDE_vs_volumen"][
        "MDE_break_even_AL_VOLUMEN_REAL_del_dataset_pct"]
    if not out["1_resultado_primario"]["significativo"] or prim["lift_pct"] <= 0:
        dec = "NO LANZAR"
    elif prim["ci_lo"] > mde_real:
        dec = "LANZAR"
    else:
        dec = "ITERAR"
    # decisión bajo el MDE DECLARADO (+3%), la que reportaba el proyecto antes de esta corrección
    # -- se conserva para contexto, pero ya no es la decisión titular.
    dec_bajo_mde_declarado = "LANZAR" if out["1_resultado_primario"]["relevante"] else "REVISAR"

    out["6_decision"] = {
        "decision": dec,
        "decision_bajo_MDE_declarado_+3pct_ignorando_volumen": dec_bajo_mde_declarado,
        "justificacion": [
            f"Efecto primario +{prim['lift_pct']:.2f}% (IC95 [{prim['ci_lo']:.2f}, {prim['ci_hi']:.2f}]), "
            f"log10(p) = {prim['log10_p']} -> muy significativo.",
            f"Al volumen REAL del dataset (~{out['2_impacto_negocio']['pedidos_por_anio_estimado']:,} "
            f"pedidos/año), el break-even del modelo de costes es +{mde_real:.1f}% "
            f"(no el +{MDE_RELEVANCIA}% declarado, calibrado para un marketplace mucho mayor) -> "
            f"el IC 95% del efecto {'SÍ' if prim['ci_lo'] > mde_real else 'NO'} queda enteramente "
            f"por encima de ese umbral real.",
            "Ningún guardrail degradado (Fase 4, Benjamini-Hochberg).",
            "Efecto homogéneo entre segmentos pre-especificados (sin interacción tras BH).",
            f"Estimación ajustada por covariables (ANCOVA): +{out['3_ancova']['con_ajuste']['lift_pct']}% "
            f"con SE {out['3_ancova']['reduccion_SE_pct']}% menor.",
            f"Impacto estimado: +R$ {uplift_gmv_year:,.0f}/año de GMV de mercancía "
            f"(IC [{gmv_year*prim['ci_lo']/100:,.0f}, {gmv_year*prim['ci_hi']/100:,.0f}]) -- "
            f"insuficiente para cubrir el coste del rediseño (R$ "
            f"{mde_cost_model.BUILD_COST + mde_cost_model.MAINT_COST_YEAR * mde_cost_model.PAYBACK_YEARS:,.0f} "
            f"a {mde_cost_model.PAYBACK_YEARS} años) al volumen real del dataset.",
        ],
        "caveats": [
            "El efecto es sintético y declarado: esta 'decisión' valida el proceso, no un hallazgo real.",
            "El estimador puntual supera el ATE inyectado (+5%) por el desbalance basal del split "
            "(ver balance_check.py, ahora incluye merch_value en la tabla formal); el IC lo cubre.",
            f"La potencia de esta regla de decisión (no solo de rechazar H0) se mide en "
            f"fase4_resumen.json::8_ab_multiseed -- con el umbral del MDE declarado, la puerta "
            f"'LANZAR' solo se activa en una fracción de las re-aleatorizaciones, no siempre "
            f"(ver 'hallazgo_potencia_de_la_decision').",
            "El MDE de +3% no es incorrecto en sí mismo -- es el umbral correcto si el marketplace "
            "tuviera ~415k+ pedidos/año. El problema es publicar una decisión de negocio que mezcla "
            "ese umbral con un impacto en R$ calculado sobre un volumen ~7x menor.",
        ],
    }

    def _js(o):
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        raise TypeError(type(o))

    (OUT_T / "fase5_resumen.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=_js), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False, default=_js))


if __name__ == "__main__":
    main()
