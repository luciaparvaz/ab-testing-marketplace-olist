"""
Fase 4 — Modeling: diseño estadístico del experimento y ejecución del test.

Bloques:
  1. inject_diluted_effect  — efecto de tratamiento sintético declarado (modelo diluido, §1.7b)
  2. power_analysis         — potencia a priori: analítica (efecto uniforme) vs simulada (efecto diluido)
  3. check_assumptions      — normalidad de la media (TCL), homocedasticidad (Levene), independencia
  4. aa_calibration         — 1.000 particiones aleatorias: tasa de falsos positivos + KS de p-valores
  5. run_ab_test            — inyección del efecto en la asignación declarada + test primario + guardrails BH

Salida: outputs/tables/fase4_*.{json,csv}  ·  outputs/figures/f4_*.png
Todo con semillas fijas.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.power import TTestIndPower
from statsmodels.stats.multitest import multipletests

from config import (ALPHA, ANALYTICAL_TABLE, ATE, DELTA_RESP, EPS_SD, MDE_RELEVANCIA, N_BOOT, N_SIM_AA,
                    N_SIM_MULTISEED, N_SIM_POWER, OUT_FIGURES as FIG, OUT_TABLES as OUT_T,
                    P_RESP, PROC, RAW, SEED, TARGET_POWER, VALID_STATUS, WINDOW_END, WINDOW_START,
                    WINSOR_Q, apply_plot_style)
from effect_model import inject_diluted_effect

import matplotlib.pyplot as plt
apply_plot_style()


# ===========================================================================
# Power analysis
# ===========================================================================
def power_analysis(df: pd.DataFrame) -> dict:
    res = {}
    n1 = int((df.group == "control").sum())
    n2 = int((df.group == "treatment").sum())
    res["n_control"], res["n_treatment"] = n1, n2

    for label, col in [("crudo", "merch_value"), ("winsor_p99.5", "merch_value_w")]:
        x = df[col].values
        mu, sd = x.mean(), x.std(ddof=1)
        cv = sd / mu
        # (a) MDE detectable al 80 % con n fijo (efecto uniforme, aprox normal)
        d_det = TTestIndPower().solve_power(nobs1=n1, alpha=ALPHA, power=TARGET_POWER,
                                            alternative="two-sided")
        mde_rel = d_det * cv
        # (b) potencia analítica para un efecto UNIFORME de +ATE
        d_ate = ATE / cv
        pow_uniform = TTestIndPower().power(effect_size=d_ate, nobs1=n1, alpha=ALPHA,
                                            alternative="two-sided", ratio=n2 / n1)
        # (c) potencia SIMULADA con el efecto DILUIDO real
        rng = np.random.default_rng(1234)
        rejects = np.empty(N_SIM_POWER, dtype=bool)
        est = np.empty(N_SIM_POWER)
        for k in range(N_SIM_POWER):
            g = rng.random(len(x)) < 0.5                       # re-split 50/50
            xk = inject_diluted_effect(x, g, rng)
            a, b = xk[g], xk[~g]
            st, p = stats.ttest_ind(a, b, equal_var=False)
            rejects[k] = p < ALPHA
            est[k] = a.mean() / b.mean() - 1
        pow_diluted = float(rejects.mean())
        res[label] = {
            "mean": round(mu, 2), "sd": round(sd, 2), "cv": round(cv, 4),
            "mde_rel_detectable_80pct_pct": round(mde_rel * 100, 3),
            "power_efecto_uniforme_+5pct": round(float(pow_uniform), 4),
            "power_efecto_diluido_+5pct_ATE": round(pow_diluted, 4),
            "lift_medio_estimado_sim_pct": round(float(est.mean()) * 100, 3),
            "sesgo_estimador_pp": round((float(est.mean()) - ATE) * 100, 3),
            "penalizacion_potencia_por_dilucion_pp": round((float(pow_uniform) - pow_diluted) * 100, 2),
        }

    # --- curva potencia vs n: ¿penaliza el efecto diluido? ----------------
    x = df["merch_value"].values
    cv = x.std(ddof=1) / x.mean()
    grid = [400, 800, 1600, 3200, 6400, 12800, 25600, n1]
    curve = {"n_por_grupo": grid, "power_uniforme": [], "power_diluido": [], "penalizacion_pp": []}
    rng = np.random.default_rng(99)
    S = 500
    for n in grid:
        pu = float(TTestIndPower().power(effect_size=ATE / cv, nobs1=n, alpha=ALPHA,
                                         alternative="two-sided"))
        rej = 0
        for _ in range(S):
            samp = rng.choice(x, size=2 * n, replace=(2 * n > len(x)))
            g = rng.random(2 * n) < 0.5
            xk = inject_diluted_effect(samp, g, rng)
            _, p = stats.ttest_ind(xk[g], xk[~g], equal_var=False)
            rej += p < ALPHA
        pd_ = rej / S
        curve["power_uniforme"].append(round(pu, 4))
        curve["power_diluido"].append(round(pd_, 4))
        curve["penalizacion_pp"].append(round((pu - pd_) * 100, 2))
    res["curva_potencia_vs_n"] = curve

    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.plot(grid, curve["power_uniforme"], "o-", color="#c1121f",
            label="efecto uniforme (fórmula estándar)")
    ax.plot(grid, curve["power_diluido"], "s-", color="#3b6ea5", label="efecto diluido (simulado)")
    ax.axhline(0.80, color="#999", ls=":", lw=1, label="potencia 80 %")
    ax.axvline(n1, color="#2a9d8f", ls="--", lw=1, label=f"n del experimento ({n1:,})")
    ax.set_xscale("log")
    ax.set_xlabel("n por grupo")
    ax.set_ylabel("potencia (detectar ATE = +5 %)")
    ax.set_title("El efecto diluido apenas penaliza la potencia\n"
                 "(la varianza natural del AOV, CV≈1,5, domina la varianza que añade la dilución)")
    ax.legend(fontsize=7.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "f4_04_power_vs_n.png")
    plt.close(fig)
    return res


# ===========================================================================
# G2 — guardrail de cancelación (necesita la tabla de pedidos COMPLETA)
# ===========================================================================
def g2_cancellation_guardrail() -> dict:
    orders = pd.read_csv(RAW / "olist_orders_dataset.csv",
                         parse_dates=["order_purchase_timestamp"])
    customers = pd.read_csv(RAW / "olist_customers_dataset.csv")
    m = (orders["order_purchase_timestamp"] >= WINDOW_START) & \
        (orders["order_purchase_timestamp"] < WINDOW_END)
    o = orders[m].merge(customers[["customer_id", "customer_unique_id"]], on="customer_id", how="left")
    o = o.sort_values("order_purchase_timestamp").drop_duplicates("customer_unique_id", keep="first")
    rng = np.random.default_rng(SEED)
    o = o.assign(group=rng.choice(["control", "treatment"], size=len(o)))
    o["canceled"] = (o["order_status"] == "canceled").astype(int)
    tab = o.groupby("group")["canceled"].agg(["sum", "count"])
    from statsmodels.stats.proportion import proportions_ztest
    stat, p = proportions_ztest(tab["sum"].values, tab["count"].values)
    return {
        "control": {"cancelados": int(tab.loc["control", "sum"]), "n": int(tab.loc["control", "count"]),
                    "tasa_pct": round(tab.loc["control", "sum"] / tab.loc["control", "count"] * 100, 3)},
        "treatment": {"cancelados": int(tab.loc["treatment", "sum"]), "n": int(tab.loc["treatment", "count"]),
                      "tasa_pct": round(tab.loc["treatment", "sum"] / tab.loc["treatment", "count"] * 100, 3)},
        "z_stat": round(float(stat), 3), "p_value": round(float(p), 4),
        "nota": "tabla de pedidos completa (incluye canceled); sin efecto inyectado -> se espera no degradación",
    }


# ===========================================================================
# 3. Verificación de supuestos
# ===========================================================================
def check_assumptions(df: pd.DataFrame) -> dict:
    rng = np.random.default_rng(7)
    x = df["merch_value"].values
    n = len(x) // 2

    # (a) normalidad de la MEDIA (TCL) via bootstrap
    boot_means = np.array([rng.choice(x, size=n, replace=True).mean() for _ in range(5000)])
    k2_raw, p_raw = stats.normaltest(rng.choice(x, 5000, replace=False))
    k2_mean, p_mean = stats.normaltest(boot_means)

    # (b) homocedasticidad entre grupos (asignación declarada, SIN efecto)
    c = df.loc[df.group == "control", "merch_value"].values
    t = df.loc[df.group == "treatment", "merch_value"].values
    lev_stat0, lev_p0 = stats.levene(c, t, center="median")
    # (c) homocedasticidad DESPUÉS de inyectar el efecto diluido
    rng2 = np.random.default_rng(SEED)
    is_t = (df.group == "treatment").values
    xe = inject_diluted_effect(x, is_t, rng2)
    lev_stat1, lev_p1 = stats.levene(xe[~is_t], xe[is_t], center="median")

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
    ax[0].hist(np.clip(rng.choice(x, 5000), 0, 800), bins=60, color="#3b6ea5")
    ax[0].set_title(f"Datos brutos (muestra)  ·  D'Agostino p={p_raw:.1e}")
    ax[0].set_xlabel("merch_value (R$)")
    ax[1].hist(boot_means, bins=60, color="#2a9d8f")
    ax[1].set_title(f"Media bootstrap (n={n})  ·  D'Agostino p={p_mean:.3f}")
    ax[1].set_xlabel("media de merch_value (R$)")
    fig.suptitle("Supuesto de normalidad: no lo cumplen los datos, sí la media (TCL)", y=1.03)
    fig.tight_layout()
    fig.savefig(FIG / "f4_01_tcl_normalidad.png", bbox_inches="tight")
    plt.close(fig)

    return {
        "normalidad_datos_brutos": {"DAgostino_K2": round(k2_raw, 1), "p": float(f"{p_raw:.2e}"),
                                    "veredicto": "no normal (esperado)"},
        "normalidad_de_la_media_bootstrap": {"DAgostino_K2": round(k2_mean, 3), "p": round(p_mean, 4),
                                             "veredicto": "compatible con normal -> Welch-t válido"},
        "homocedasticidad_sin_efecto": {"Levene_stat": round(lev_stat0, 3), "p": round(lev_p0, 4),
                                        "veredicto": "varianzas iguales (esperado en A/A)"},
        "homocedasticidad_con_efecto_diluido": {"Levene_stat": round(lev_stat1, 2), "p": float(f"{lev_p1:.2e}"),
                                                "veredicto": "el efecto diluido INFLA la varianza del "
                                                             "treatment -> usar Welch, NO Student"},
        "independencia": "por diseño: asignación aleatoria + dedup a 1 pedido/cliente elimina "
                         "correlación intra-cliente. SUTVA asumido (sin interferencia entre clientes).",
    }


# ===========================================================================
# 4. Calibración A/A — 1.000 particiones
# ===========================================================================
def aa_calibration(df: pd.DataFrame) -> dict:
    rng = np.random.default_rng(2024)
    out = {}
    for label, col in [("merch_value", "merch_value"), ("merch_value_w", "merch_value_w"),
                       ("log_merch", "merch_value")]:
        x = df[col].values
        if label == "log_merch":
            x = np.log(x)
        pvals = np.empty(N_SIM_AA)
        for k in range(N_SIM_AA):
            g = rng.random(len(x)) < 0.5
            st, p = stats.ttest_ind(x[g], x[~g], equal_var=False)
            pvals[k] = p
        ks_stat, ks_p = stats.kstest(pvals, "uniform")
        fpr = float((pvals < 0.05).mean())
        half = 1.96 * np.sqrt(0.05 * 0.95 / N_SIM_AA)
        fpr_ci_ok = (fpr - half) <= 0.05 <= (fpr + half)
        out[label] = {
            "tasa_falsos_positivos_alpha_0.05": round(fpr, 4),
            "tasa_esperada": 0.05,
            "IC95_tasa": [round(fpr - half, 4), round(fpr + half, 4)],
            "IC95_contiene_0.05": bool(fpr_ci_ok),
            "KS_vs_uniforme_stat": round(float(ks_stat), 4),
            "KS_vs_uniforme_p": round(float(ks_p), 4),
            # KS se aplica a 3 métricas -> se usa un umbral corregido (0.05/3) para "catastrófico"
            "veredicto": "calibrado" if (fpr_ci_ok and ks_p > 0.0167) else "REVISAR",
        }

    # figura: histograma de p-valores del A/A (métrica primaria)
    rng = np.random.default_rng(2024)
    x = df["merch_value"].values
    pv = np.array([stats.ttest_ind(*(lambda g: (x[g], x[~g]))(rng.random(len(x)) < 0.5),
                                   equal_var=False)[1] for _ in range(N_SIM_AA)])
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    ax.hist(pv, bins=20, color="#8d99ae", edgecolor="white")
    ax.axhline(N_SIM_AA / 20, color="#c1121f", ls="--", lw=1.2, label="uniforme esperada")
    ax.set_title(f"A/A · distribución de p-valores ({N_SIM_AA} particiones)\n"
                 f"falsos positivos = {(pv < 0.05).mean()*100:.1f}%  (esperado 5%)")
    ax.set_xlabel("p-valor (Welch-t sobre merch_value, sin efecto)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "f4_02_aa_pvalores.png")
    plt.close(fig)
    return out


# ===========================================================================
# 5. A/B test — efecto inyectado en la asignación declarada
# ===========================================================================
def _welch_ci(a, b, alpha=ALPHA):
    ma, mb = a.mean(), b.mean()
    va, vb = a.var(ddof=1), b.var(ddof=1)
    se = np.sqrt(va / a.size + vb / b.size)
    dfw = se**4 / ((va / a.size)**2 / (a.size - 1) + (vb / b.size)**2 / (b.size - 1))
    tcrit = stats.t.ppf(1 - alpha / 2, dfw)
    diff = ma - mb
    return diff, (diff - tcrit * se, diff + tcrit * se), dfw


def _bootstrap_ratio_ci(a, b, rng, n=N_BOOT, alpha=ALPHA):
    r = np.empty(n)
    for i in range(n):
        r[i] = rng.choice(a, a.size, replace=True).mean() / rng.choice(b, b.size, replace=True).mean() - 1
    return np.percentile(r, [100 * alpha / 2, 100 * (1 - alpha / 2)])


def run_ab_test(df: pd.DataFrame) -> dict:
    rng = np.random.default_rng(SEED)
    is_t = (df.group == "treatment").values

    # --- inyección del efecto en la métrica primaria (declarada, SEED=42) ---
    df = df.copy()
    df["mv_effect"] = inject_diluted_effect(df["merch_value"].values, is_t, rng)
    cap = df["merch_value_w"].max()
    df["mv_effect_w"] = np.minimum(df["mv_effect"], cap)

    t = df[is_t]; c = df[~is_t]
    res = {"n_control": len(c), "n_treatment": len(t), "ATE_declarado_pct": ATE * 100}

    # --- primario y robustez ---
    primary = {}
    for label, col in [("Welch_crudo", "mv_effect"), ("Welch_winsor_p99.5", "mv_effect_w")]:
        diff, (lo, hi), dfw = _welch_ci(t[col].values, c[col].values)
        st, p = stats.ttest_ind(t[col].values, c[col].values, equal_var=False)
        base = c[col].mean()
        primary[label] = {
            "control": round(base, 2), "treatment": round(t[col].mean(), 2),
            "diff_abs_R$": round(diff, 2),
            "lift_rel_pct": round(diff / base * 100, 3),
            "IC95_lift_pct": [round(lo / base * 100, 3), round(hi / base * 100, 3)],
            "p_value": float(f"{p:.3e}"), "welch_df": round(dfw, 0),
            "ATE_5pct_en_IC": bool(lo / base * 100 <= 5.0 <= hi / base * 100),
        }
    # log (cociente de medias geométricas)
    st, p = stats.ttest_ind(np.log(t["mv_effect"]), np.log(c["mv_effect"]), equal_var=False)
    gm_ratio = np.exp(np.log(t["mv_effect"]).mean() - np.log(c["mv_effect"]).mean()) - 1
    primary["log_geom_ratio"] = {"lift_geom_pct": round(gm_ratio * 100, 3), "p_value": float(f"{p:.3e}"),
                                 "nota": "cociente de medias geométricas (~mediana), NO el AOV"}
    # Mann-Whitney
    u, p = stats.mannwhitneyu(t["mv_effect"], c["mv_effect"], alternative="two-sided")
    primary["mann_whitney"] = {"U": float(u), "p_value": float(f"{p:.3e}"),
                               "nota": "dominancia estocástica"}
    # bootstrap
    boot = _bootstrap_ratio_ci(t["mv_effect"].values, c["mv_effect"].values, rng)
    primary["bootstrap_ratio"] = {"IC95_lift_pct": [round(boot[0] * 100, 3), round(boot[1] * 100, 3)],
                                  "nota": "sin supuesto distribucional"}
    res["primario"] = primary

    # --- guardrails (SIN efecto inyectado: deben salir planos) ---
    guard = {}
    raw_p = {}
    # G1 review_score (Welch + Mann-Whitney)
    g1c = c["review_score"].dropna(); g1t = t["review_score"].dropna()
    st, p1 = stats.ttest_ind(g1t, g1c, equal_var=False)
    guard["G1_review_score"] = {"control": round(g1c.mean(), 4), "treatment": round(g1t.mean(), 4),
                                "diff": round(g1t.mean() - g1c.mean(), 4), "p_welch": p1,
                                "umbral_alarma": "caída >= 0.05 pts"}
    raw_p["G1_review_score"] = p1
    # G2 tasa de cancelación (tabla de pedidos completa)
    g2 = g2_cancellation_guardrail()
    guard["G2_cancelacion"] = {"control_pct": g2["control"]["tasa_pct"],
                               "treatment_pct": g2["treatment"]["tasa_pct"],
                               "z_stat": g2["z_stat"], "p_welch": g2["p_value"],
                               "umbral_alarma": "subida significativa"}
    raw_p["G2_cancelacion"] = g2["p_value"]
    # G3 freight_value
    st, p3 = stats.ttest_ind(t["freight_value"], c["freight_value"], equal_var=False)
    guard["G3_freight_value"] = {"control": round(c["freight_value"].mean(), 3),
                                 "treatment": round(t["freight_value"].mean(), 3),
                                 "diff": round(t["freight_value"].mean() - c["freight_value"].mean(), 3),
                                 "p_welch": p3, "umbral_alarma": "subida significativa"}
    raw_p["G3_freight_value"] = p3
    # G4 n_items
    st, p4 = stats.ttest_ind(t["n_items"], c["n_items"], equal_var=False)
    guard["G4_n_items"] = {"control": round(c["n_items"].mean(), 4), "treatment": round(t["n_items"].mean(), 4),
                           "diff": round(t["n_items"].mean() - c["n_items"].mean(), 4),
                           "p_welch": p4, "umbral_alarma": "caída significativa"}
    raw_p["G4_n_items"] = p4

    # --- corrección Benjamini-Hochberg sobre la familia de guardrails ---
    keys = list(raw_p.keys())
    pv = [raw_p[k] for k in keys]
    rej, p_adj, _, _ = multipletests(pv, alpha=ALPHA, method="fdr_bh")
    for k, pa, r in zip(keys, p_adj, rej):
        guard[k]["p_ajustado_BH"] = float(f"{pa:.4f}")
        guard[k]["significativo_tras_BH"] = bool(r)
    res["guardrails"] = guard
    res["guardrails_nota"] = ("G2 (cancelación) se evalúa sobre la tabla de pedidos completa, no la "
                              "analítica (que ya filtra estados). Sin efecto inyectado en guardrails "
                              "-> se espera no degradación.")

    # --- figura resumen del A/B ---
    fig, ax = plt.subplots(figsize=(7, 3))
    labels = ["Welch crudo", "Welch winsor", "bootstrap"]
    lifts = [primary["Welch_crudo"]["lift_rel_pct"], primary["Welch_winsor_p99.5"]["lift_rel_pct"],
             np.mean(primary["bootstrap_ratio"]["IC95_lift_pct"])]
    cis = [primary["Welch_crudo"]["IC95_lift_pct"], primary["Welch_winsor_p99.5"]["IC95_lift_pct"],
           primary["bootstrap_ratio"]["IC95_lift_pct"]]
    y = np.arange(len(labels))
    for i, (l, ci) in enumerate(zip(lifts, cis)):
        ax.plot(ci, [i, i], color="#3b6ea5", lw=2)
        ax.plot(l, i, "o", color="#3b6ea5")
    ax.axvline(5.0, color="#2a9d8f", ls="--", lw=1.3, label="ATE declarado (+5%)")
    ax.axvline(3.0, color="#c1121f", ls=":", lw=1.3, label="MDE relevancia (+3%)")
    ax.axvline(0.0, color="#999", lw=0.8)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.set_xlabel("lift del AOV (%)  ·  IC 95 %")
    ax.set_title("A/B · efecto sobre la métrica primaria (efecto diluido inyectado)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "f4_03_ab_efecto.png")
    plt.close(fig)
    return res



def decision_scenarios(df: pd.DataFrame) -> dict:
    """Aplica la regla de decisión (§1.5) a varios tamaños de efecto inyectado.
    Muestra que el diseño alcanza las tres ramas: lanzar / iterar / no lanzar."""
    is_t = (df.group == "treatment").values
    x_raw = df["merch_value"].values        # inyectar sobre crudo, winsorizar DESPUÉS (igual que run_ab_test)
    cap = df["merch_value_w"].max()
    base = np.minimum(x_raw, cap)[~is_t].mean()
    rows = []
    for ate_pct in [0, 1, 2, 3, 4, 5, 8]:
        rng = np.random.default_rng(SEED)
        dr = ate_pct / 100 / P_RESP         # delta_resp para ese ATE
        xe = np.minimum(inject_diluted_effect(x_raw, is_t, rng, delta_resp=dr), cap)
        diff, (lo, hi), _ = _welch_ci(xe[is_t], xe[~is_t])
        _, p = stats.ttest_ind(xe[is_t], xe[~is_t], equal_var=False)
        lift, lo_p, hi_p = diff / base * 100, lo / base * 100, hi / base * 100
        if p >= ALPHA or lift <= 0:
            dec = "NO LANZAR"
        elif lo_p > MDE_RELEVANCIA:
            dec = "LANZAR"
        else:
            dec = "ITERAR"
        rows.append({"ATE_inyectado_pct": ate_pct, "lift_observado_pct": round(lift, 2),
                     "IC95_pct": [round(lo_p, 2), round(hi_p, 2)], "p_value": float(f"{p:.2e}"),
                     "decision": dec})
    return {"nota": f"regla §1.5 · MDE relevancia = +{MDE_RELEVANCIA}% · guardrails no inyectados "
                    f"(siempre OK) · este split tiene +1,2% de desbalance basal",
            "escenarios": rows}


# ===========================================================================
# Mejoras de la auditoría global
# ===========================================================================
def guardrail_regression_scenarios(df: pd.DataFrame) -> dict:
    """Auditoría §D19 / mejora nº1: inyectar una regresión en G1 (review_score) y comprobar que
    el test de guardrail (a) tiene potencia para detectarla y (b) con una regla de dos puertas
    (significativo Y magnitud >= umbral) no bloquea el lanzamiento por ruido sub-umbral."""
    is_t = (df.group == "treatment").values
    rs = df["review_score"].values.astype(float)
    base = np.nanmean(rs[~is_t])
    THRESH = 0.05
    rows = []
    for delta in [0.0, -0.03, -0.05, -0.08]:
        y = rs.copy()
        y[is_t] = y[is_t] + delta                     # regresión aditiva en el treatment
        a, b = y[is_t], y[~is_t]
        a, b = a[~np.isnan(a)], b[~np.isnan(b)]
        st, p = stats.ttest_ind(a, b, equal_var=False)
        obs = a.mean() - b.mean()
        sig = p < ALPHA
        mag = abs(obs) >= THRESH and obs < 0
        rows.append({
            "regresion_inyectada_pts": delta,
            "diff_observada_pts": round(obs, 4),
            "p_value": float(f"{p:.2e}"),
            "significativo": bool(sig),
            "magnitud_>=_0.05": bool(mag),
            "regla_OR_(significativo O magnitud)": bool(sig or mag),   # regla original §1.4
            "regla_AND_(significativo Y magnitud)": bool(sig and mag),  # regla corregida
        })
    return {
        "base_review_control": round(base, 4), "umbral_magnitud_pts": THRESH,
        "escenarios": rows,
        "hallazgo": ("A n≈47k CUALQUIER regresión real es significativa (incluso −0,03). La regla "
                     "original 'significativo O magnitud≥0,05' bloquearía el lanzamiento por ruido "
                     "sub-umbral -> se corrige a 'significativo Y magnitud≥0,05'. Con la regla "
                     "corregida: −0,03 NO bloquea (correcto), −0,08 SÍ bloquea (correcto). El test "
                     "de guardrail tiene potencia sobrada para detectar la regresión."),
    }


def heterogeneous_effect_variant(df: pd.DataFrame) -> dict:
    """Auditoría §D8 / mejora nº2: variante con efecto REALMENTE heterogéneo (concentrado en pedidos
    por debajo de un umbral hipotético de envío gratis) y comprobar que el análisis de segmentos lo
    DETECTA (a diferencia del efecto homogéneo del análisis principal)."""
    from statsmodels.regression.linear_model import OLS
    rng = np.random.default_rng(SEED)
    is_t = (df.group == "treatment").values
    x = df["merch_value"].values.astype(float)
    FREE_SHIP_THRESHOLD = 150.0                       # R$, hipotético
    band = (x >= FREE_SHIP_THRESHOLD - 60) & (x < FREE_SHIP_THRESHOLD)   # "cerca del umbral"

    # efecto SOLO en tratados dentro de la banda: +12% (para el ~28% de pedidos en banda -> ATE ~3.4%)
    y = x.copy()
    resp = is_t & band & (rng.random(len(x)) < 0.6)
    y[resp] = y[resp] * (1 + 0.12 + rng.normal(0, 0.05, resp.sum()))

    near = band.astype(float)
    treat = is_t.astype(float)
    ylog = np.log(y)
    X = np.column_stack([np.ones(len(y)), treat, near, treat * near])
    r = OLS(ylog, X).fit(cov_type="HC3")
    p_inter = float(r.pvalues[3])

    # efecto global vs efecto en la banda
    def lift(mask):
        tt, cc = y[mask & is_t], y[mask & ~is_t]
        return (tt.mean() / cc.mean() - 1) * 100
    return {
        "umbral_envio_gratis_R$": FREE_SHIP_THRESHOLD,
        "pct_pedidos_en_banda": round(band.mean() * 100, 1),
        "lift_global_pct": round(lift(np.ones(len(y), bool)), 2),
        "lift_en_banda_pct": round(lift(band), 2),
        "lift_fuera_de_banda_pct": round(lift(~band), 2),
        "p_interaccion_cerca_del_umbral_HC3": float(f"{p_inter:.2e}"),
        "heterogeneidad_detectada": bool(p_inter < ALPHA),
        "hallazgo": ("con un efecto realmente heterogéneo (concentrado bajo el umbral de envío "
                     "gratis), el test de interacción SÍ lo detecta (p muy pequeño). Contraste con "
                     "el análisis principal (efecto homogéneo -> ninguna interacción). El diseño "
                     "distingue heterogeneidad real de artefactos."),
    }


def ab_multiseed(df: pd.DataFrame, n_seeds: int = N_SIM_MULTISEED) -> dict:
    """Auditoría §4 punto 4 / mejora nº3: repetir el A/B COMPLETO sobre muchas semillas
    (re-split + re-inyección del efecto diluido) para medir la distribución del estimador y la
    cobertura real del IC 95 %. Cierra la debilidad del 'un solo split'.
    Se hace en CRUDO y en WINSOR para aislar el efecto de la winsorización sobre el sesgo."""
    x = df["merch_value"].values.astype(float)
    cap = df["merch_value_w"].max()

    def _run(winsor: bool) -> dict:
        rng = np.random.default_rng(777)
        lifts = np.empty(n_seeds); covers = np.empty(n_seeds, bool); rej = np.empty(n_seeds, bool)
        for k in range(n_seeds):
            g = rng.random(len(x)) < 0.5
            xe = inject_diluted_effect(x, g, rng)
            if winsor:
                xe = np.minimum(xe, cap)
            diff, (lo, hi), _ = _welch_ci(xe[g], xe[~g])
            base = xe[~g].mean()
            lifts[k] = diff / base * 100
            covers[k] = (lo / base * 100) <= 5.0 <= (hi / base * 100)
            rej[k] = stats.ttest_ind(xe[g], xe[~g], equal_var=False)[1] < ALPHA
        return {"lift_medio_pct": round(float(lifts.mean()), 3),
                "sesgo_pp": round(float(lifts.mean()) - ATE * 100, 3),
                "lift_sd_pp": round(float(lifts.std(ddof=1)), 3),
                "lift_p2.5_p97.5": [round(float(np.percentile(lifts, 2.5)), 2),
                                    round(float(np.percentile(lifts, 97.5)), 2)],
                "cobertura_IC95_del_+5pct": round(float(covers.mean()), 3),
                "potencia_empirica": round(float(rej.mean()), 3)}

    crudo, winsor = _run(False), _run(True)
    return {
        "n_semillas": n_seeds,
        "crudo": crudo,
        "winsor_p99.5": winsor,
        "hallazgo": (f"En CRUDO el estimador es INSESGADO (sesgo {crudo['sesgo_pp']} pp) y el IC 95% "
                     f"cubre el valor real el {crudo['cobertura_IC95_del_+5pct']:.0%} de las veces "
                     f"(nominal 95%). La WINSORIZACIÓN introduce un pequeño sesgo NEGATIVO "
                     f"({winsor['sesgo_pp']} pp) porque recorta más los valores altos del treatment "
                     f"(efecto multiplicativo) -> la cobertura baja a "
                     f"{winsor['cobertura_IC95_del_+5pct']:.0%}. Es el precio de la reducción de "
                     f"varianza; la decisión (LANZAR) es robusta porque ambos IC superan el +3%. "
                     f"El +5,7% del split SEED=42 está dentro del rango p2,5-p97,5."),
    }


def clustered_se_robustness() -> dict:
    """Auditoría §D3 / mejora nº5: repetir el primario con TODOS los pedidos (sin dedup) y errores
    estándar agrupados por cliente; confirmar que coincide con la versión deduplicada."""
    from statsmodels.regression.linear_model import OLS
    orders = pd.read_csv(RAW / "olist_orders_dataset.csv", parse_dates=["order_purchase_timestamp"])
    items = pd.read_csv(RAW / "olist_order_items_dataset.csv")
    customers = pd.read_csv(RAW / "olist_customers_dataset.csv")
    mw = (orders.order_purchase_timestamp >= WINDOW_START) & (orders.order_purchase_timestamp < WINDOW_END)
    valid = VALID_STATUS
    merch = items.groupby("order_id")["price"].sum().rename("mv")
    o = (orders[mw & orders.order_status.isin(valid)]
         .merge(merch, on="order_id").dropna(subset=["mv"])
         .merge(customers[["customer_id", "customer_unique_id"]], on="customer_id"))
    # MISMA asignación que el análisis principal: mapa cliente->grupo de la tabla analítica
    at = pd.read_parquet(ANALYTICAL_TABLE)[["customer_unique_id", "group"]]
    cmap = at.set_index("customer_unique_id")["group"].map({"control": 0, "treatment": 1})
    o = o[o["customer_unique_id"].isin(cmap.index)].copy()
    o["treat"] = o["customer_unique_id"].map(cmap).astype(float)
    # mismo efecto diluido (SEED) a nivel pedido sobre los tratados
    rng = np.random.default_rng(SEED)
    is_t = o["treat"].values.astype(bool)
    o["mv_e"] = inject_diluted_effect(o["mv"].values, is_t, rng)
    cap = o["mv_e"].quantile(WINSOR_Q)
    o["mv_e"] = np.minimum(o["mv_e"], cap)
    base = o.loc[~is_t, "mv_e"].mean()

    X = np.column_stack([np.ones(len(o)), o["treat"].values])
    r_iid = OLS(o["mv_e"].values, X).fit(cov_type="HC1")
    r_cl = OLS(o["mv_e"].values, X).fit(cov_type="cluster",
                                       cov_kwds={"groups": o["customer_unique_id"].values})
    return {
        "n_pedidos_sin_dedup": len(o), "n_clientes": int(o.customer_unique_id.nunique()),
        "lift_pct_todos_los_pedidos": round(r_cl.params[1] / base * 100, 3),
        "lift_pct_dedup_1_pedido_cliente_ref": 5.666,
        "SE_robusto_sin_clustering_R$": round(r_iid.bse[1], 4),
        "SE_cluster_por_cliente_R$": round(r_cl.bse[1], 4),
        "inflacion_SE_por_clustering_pct": round((r_cl.bse[1] / r_iid.bse[1] - 1) * 100, 2),
        "hallazgo": ("con TODOS los pedidos + SE por clúster de cliente, el SE es prácticamente "
                     "idéntico al de la versión deduplicada (el 97% de clientes tiene 1 pedido -> el "
                     "clustering apenas infla el SE, ~1%). El lift puntual difiere un poco porque "
                     "incluye ~3.200 pedidos extra de clientes recurrentes, pero la conclusión "
                     "(significativo, IC sobre el MDE) no cambia. Deduplicar fue la opción simple y "
                     "correcta."),
    }


# ===========================================================================
def main():
    df = pd.read_parquet(ANALYTICAL_TABLE)
    report = {
        "parametros": {"SEED": SEED, "ALPHA": ALPHA, "P_RESP": P_RESP, "DELTA_RESP": DELTA_RESP,
                       "EPS_SD": EPS_SD, "ATE_pct": ATE * 100, "N_SIM_AA": N_SIM_AA,
                       "N_SIM_POWER": N_SIM_POWER, "N_BOOT": N_BOOT},
        "1_power_analysis": power_analysis(df),
        "2_supuestos": check_assumptions(df),
        "3_aa_calibracion": aa_calibration(df),
        "4_ab_test": run_ab_test(df),
        "5_decision_scenarios": decision_scenarios(df),
        "6_guardrail_regression": guardrail_regression_scenarios(df),
        "7_efecto_heterogeneo": heterogeneous_effect_variant(df),
        "8_ab_multiseed": ab_multiseed(df),
        "9_clustered_se": clustered_se_robustness(),
    }
    (OUT_T / "fase4_resumen.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
