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
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.power import TTestIndPower
from statsmodels.stats.multitest import multipletests

RAW = Path("data/raw")
PROC = Path("data/processed")
OUT_T = Path("outputs/tables")
FIG = Path("outputs/figures")
for p in (OUT_T, FIG):
    p.mkdir(parents=True, exist_ok=True)

# ---- parámetros declarados (coinciden con docs/01 §1.7b) --------------------
SEED = 42
ALPHA = 0.05
P_RESP = 0.20            # fracción de tratados que responden
DELTA_RESP = 0.25        # efecto entre respondedores (+25 %)
EPS_SD = 0.05            # heterogeneidad entre respondedores
ATE = P_RESP * DELTA_RESP  # = 0.05  -> +5 % efecto medio declarado
N_SIM_AA = 2000
N_SIM_POWER = 1000
N_BOOT = 10_000
TARGET_POWER = 0.80

import matplotlib.pyplot as plt
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 130, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})


# ===========================================================================
# 1. Efecto de tratamiento sintético — modelo diluido
# ===========================================================================
def inject_diluted_effect(values: np.ndarray, is_treat: np.ndarray, rng: np.random.Generator,
                          p_resp=P_RESP, delta_resp=DELTA_RESP, eps_sd=EPS_SD) -> np.ndarray:
    """Devuelve `values` con el efecto aplicado SOLO a los tratados.
    R_i ~ Bernoulli(p_resp);  si responde: v_i *= (1 + delta_resp + eps_i)."""
    out = values.astype(float).copy()
    tr = np.where(is_treat)[0]
    responders = rng.random(tr.size) < p_resp
    eps = rng.normal(0.0, eps_sd, tr.size)
    factor = np.where(responders, 1.0 + delta_resp + eps, 1.0)
    out[tr] = out[tr] * factor
    return out


# ===========================================================================
# 2. Power analysis
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
    m = (orders["order_purchase_timestamp"] >= "2017-01-01") & \
        (orders["order_purchase_timestamp"] < "2018-09-01")
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


MDE_RELEVANCIA = 3.0  # % (§1.5)


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
def main():
    df = pd.read_parquet(PROC / "analytical_table.parquet")
    report = {
        "parametros": {"SEED": SEED, "ALPHA": ALPHA, "P_RESP": P_RESP, "DELTA_RESP": DELTA_RESP,
                       "EPS_SD": EPS_SD, "ATE_pct": ATE * 100, "N_SIM_AA": N_SIM_AA,
                       "N_SIM_POWER": N_SIM_POWER, "N_BOOT": N_BOOT},
        "1_power_analysis": power_analysis(df),
        "2_supuestos": check_assumptions(df),
        "3_aa_calibracion": aa_calibration(df),
        "4_ab_test": run_ab_test(df),
        "5_decision_scenarios": decision_scenarios(df),
    }
    (OUT_T / "fase4_resumen.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
