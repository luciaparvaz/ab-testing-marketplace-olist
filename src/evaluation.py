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

try:
    import sys as _sys; _sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.multitest import multipletests
import matplotlib.pyplot as plt


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

from modeling import inject_diluted_effect, SEED, ALPHA, ATE, MDE_RELEVANCIA

RAW = Path("data/raw")
PROC = Path("data/processed")
OUT_T = Path("outputs/tables")
FIG = Path("outputs/figures")
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 130, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})

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
    df = pd.read_parquet(PROC / "analytical_table.parquet").copy()
    is_t = (df.group == "treatment").values
    rng = np.random.default_rng(SEED)
    df["mv"] = inject_diluted_effect(df["merch_value"].values, is_t, rng)
    cap = df["merch_value_w"].max()
    df["mv_w"] = np.minimum(df["mv"], cap)

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
    mw = (orders_full.order_purchase_timestamp >= "2017-01-01") & \
         (orders_full.order_purchase_timestamp < "2018-09-01")
    valid_ids = set(items_full.order_id)
    n_orders_window = int(((orders_full[mw].order_status.isin(
        ["delivered", "shipped", "invoiced", "approved", "processing"])) &
        (orders_full[mw].order_id.isin(valid_ids))).sum())
    n_orders_year = n_orders_window / 20 * 12
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
    COMMISSION = 0.15  # take rate asumida del marketplace
    out["2_impacto_negocio"] = {
        "pedidos_validos_ventana_sin_dedup": n_orders_window, "meses_ventana": 20,
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
    dec = "LANZAR" if out["1_resultado_primario"]["relevante"] else "REVISAR"
    out["6_decision"] = {
        "decision": dec,
        "justificacion": [
            f"Efecto primario +{prim['lift_pct']:.2f}% (IC95 [{prim['ci_lo']:.2f}, {prim['ci_hi']:.2f}]), "
            f"log10(p) = {prim['log10_p']} -> muy significativo.",
            f"IC 95 % completamente por encima del MDE de relevancia (+{MDE_RELEVANCIA}%) -> relevante para negocio.",
            "Ningún guardrail degradado (Fase 4, Benjamini-Hochberg).",
            "Efecto homogéneo entre segmentos pre-especificados (sin interacción tras BH).",
            f"Estimación ajustada por covariables (ANCOVA): +{out['3_ancova']['con_ajuste']['lift_pct']}% "
            f"con SE {out['3_ancova']['reduccion_SE_pct']}% menor.",
            f"Impacto estimado: +R$ {uplift_gmv_year:,.0f}/año de GMV de mercancía "
            f"(IC [{gmv_year*prim['ci_lo']/100:,.0f}, {gmv_year*prim['ci_hi']/100:,.0f}]).",
        ],
        "caveats": [
            "El efecto es sintético y declarado: esta 'decisión' valida el proceso, no un hallazgo real.",
            "El estimador puntual (+5,7%) supera el ATE inyectado (+5%) por el desbalance basal "
            "del split (+1,2%, no significativo); el IC lo cubre.",
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
