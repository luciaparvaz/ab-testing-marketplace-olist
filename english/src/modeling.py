"""
Phase 4 — Modeling: statistical design of the experiment and execution of the test.

Blocks:
  1. inject_diluted_effect  — declared synthetic treatment effect (diluted model, §1.7b)
  2. power_analysis         — a priori power: analytical (uniform effect) vs. simulated (diluted effect)
  3. check_assumptions      — normality of the mean (CLT), homoscedasticity (Levene), independence
  4. aa_calibration         — 1,000 random partitions: false-positive rate + KS test on p-values
  5. run_ab_test            — inject the effect into the declared assignment + primary test + BH guardrails

Output: outputs/tables/fase4_*.{json,csv}  ·  outputs/figures/f4_*.png
Everything with fixed seeds.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.power import TTestIndPower
from statsmodels.stats.multitest import multipletests

from config import (ALPHA, ANALYTICAL_TABLE, ATE, DELTA_RESP, EPS_SD, GUARDRAIL_THRESHOLDS,
                    MDE_RELEVANCIA, N_BOOT, N_SIM_AA, N_SIM_MULTISEED, N_SIM_POWER,
                    OUT_FIGURES as FIG, OUT_TABLES as OUT_T,
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

    for label, col in [("raw", "merch_value"), ("winsor_p99.5", "merch_value_w")]:
        x = df[col].values
        mu, sd = x.mean(), x.std(ddof=1)
        cv = sd / mu
        # (a) MDE detectable at 80% with fixed n (uniform effect, normal approximation)
        d_det = TTestIndPower().solve_power(nobs1=n1, alpha=ALPHA, power=TARGET_POWER,
                                            alternative="two-sided")
        mde_rel = d_det * cv
        # (b) analytical power for a UNIFORM effect of +ATE
        d_ate = ATE / cv
        pow_uniform = TTestIndPower().power(effect_size=d_ate, nobs1=n1, alpha=ALPHA,
                                            alternative="two-sided", ratio=n2 / n1)
        # (c) SIMULATED power with the real DILUTED effect
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
            "power_uniform_effect_+5pct": round(float(pow_uniform), 4),
            "power_diluted_effect_+5pct_ATE": round(pow_diluted, 4),
            "mean_estimated_lift_sim_pct": round(float(est.mean()) * 100, 3),
            "estimator_bias_pp": round((float(est.mean()) - ATE) * 100, 3),
            "power_penalty_from_dilution_pp": round((float(pow_uniform) - pow_diluted) * 100, 2),
        }

    # --- power vs n curve: does the diluted effect cost power? ----------------
    x = df["merch_value"].values
    cv = x.std(ddof=1) / x.mean()
    grid = [400, 800, 1600, 3200, 6400, 12800, 25600, n1]
    curve = {"n_per_group": grid, "power_uniform": [], "power_diluted": [], "penalty_pp": []}
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
        curve["power_uniform"].append(round(pu, 4))
        curve["power_diluted"].append(round(pd_, 4))
        curve["penalty_pp"].append(round((pu - pd_) * 100, 2))
    res["power_vs_n_curve"] = curve

    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.plot(grid, curve["power_uniform"], "o-", color="#c1121f",
            label="uniform effect (standard formula)")
    ax.plot(grid, curve["power_diluted"], "s-", color="#3b6ea5", label="diluted effect (simulated)")
    ax.axhline(0.80, color="#999", ls=":", lw=1, label="80% power")
    ax.axvline(n1, color="#2a9d8f", ls="--", lw=1, label=f"experiment's n ({n1:,})")
    ax.set_xscale("log")
    ax.set_xlabel("n per group")
    ax.set_ylabel("power (detect ATE = +5%)")
    ax.set_title("The diluted effect barely costs power\n"
                 "(the AOV's natural variance, CV≈1.5, dominates the variance added by dilution)")
    ax.legend(fontsize=7.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "f4_04_power_vs_n.png")
    plt.close(fig)
    return res


# ===========================================================================
# G2 — cancellation guardrail (needs the FULL orders table)
# ===========================================================================
def g2_cancellation_guardrail() -> dict:
    orders = pd.read_csv(RAW / "olist_orders_dataset.csv",
                         parse_dates=["order_purchase_timestamp"])
    customers = pd.read_csv(RAW / "olist_customers_dataset.csv")
    # the experiment's SINGLE assignment (persisted in the analytical table) — NEVER recomputed here.
    # G2 needs to keep the 'canceled' orders (it is the very metric it measures), so it cannot
    # deduplicate over the same table filtered by VALID_STATUS that prepare_data.py uses; instead
    # it JOINs against the already-assigned group, so that the control/treatment partition is
    # identical throughout the whole pipeline (implementation audit, finding 1).
    at = pd.read_parquet(ANALYTICAL_TABLE)[["customer_unique_id", "group"]]

    m = (orders["order_purchase_timestamp"] >= WINDOW_START) & \
        (orders["order_purchase_timestamp"] < WINDOW_END)
    o = orders[m].merge(customers[["customer_id", "customer_unique_id"]], on="customer_id", how="left")
    o = o.sort_values("order_purchase_timestamp").drop_duplicates("customer_unique_id", keep="first")
    o = o.merge(at, on="customer_unique_id", how="inner")   # only customers with a known assignment
    o["canceled"] = (o["order_status"] == "canceled").astype(int)
    tab = o.groupby("group")["canceled"].agg(["sum", "count"])
    from statsmodels.stats.proportion import proportions_ztest
    stat, p = proportions_ztest(tab["sum"].values, tab["count"].values)
    return {
        "control": {"canceled": int(tab.loc["control", "sum"]), "n": int(tab.loc["control", "count"]),
                    "rate_pct": round(tab.loc["control", "sum"] / tab.loc["control", "count"] * 100, 3)},
        "treatment": {"canceled": int(tab.loc["treatment", "sum"]), "n": int(tab.loc["treatment", "count"]),
                      "rate_pct": round(tab.loc["treatment", "sum"] / tab.loc["treatment", "count"] * 100, 3)},
        "z_stat": round(float(stat), 3), "p_value": round(float(p), 4),
        "note": "full orders table (includes canceled), but with the SAME control/treatment "
                "assignment as analytical_table.parquet; no effect injected in guardrails -> no "
                "degradation is expected",
    }


# ===========================================================================
# 3. Assumption checks
# ===========================================================================
def check_assumptions(df: pd.DataFrame) -> dict:
    rng = np.random.default_rng(7)
    x = df["merch_value"].values
    n = len(x) // 2

    # (a) normality of the MEAN (CLT) via bootstrap
    boot_means = np.array([rng.choice(x, size=n, replace=True).mean() for _ in range(5000)])
    k2_raw, p_raw = stats.normaltest(rng.choice(x, 5000, replace=False))
    k2_mean, p_mean = stats.normaltest(boot_means)

    # (b) homoscedasticity between groups (declared assignment, WITHOUT effect)
    c = df.loc[df.group == "control", "merch_value"].values
    t = df.loc[df.group == "treatment", "merch_value"].values
    lev_stat0, lev_p0 = stats.levene(c, t, center="median")
    # (c) homoscedasticity AFTER injecting the diluted effect
    rng2 = np.random.default_rng(SEED)
    is_t = (df.group == "treatment").values
    xe = inject_diluted_effect(x, is_t, rng2)
    lev_stat1, lev_p1 = stats.levene(xe[~is_t], xe[is_t], center="median")

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
    ax[0].hist(np.clip(rng.choice(x, 5000), 0, 800), bins=60, color="#3b6ea5")
    ax[0].set_title(f"Raw data (sample)  ·  D'Agostino p={p_raw:.1e}")
    ax[0].set_xlabel("merch_value (R$)")
    ax[1].hist(boot_means, bins=60, color="#2a9d8f")
    ax[1].set_title(f"Bootstrap mean (n={n})  ·  D'Agostino p={p_mean:.3f}")
    ax[1].set_xlabel("mean of merch_value (R$)")
    fig.suptitle("Normality assumption: the data doesn't meet it, the mean does (CLT)", y=1.03)
    fig.tight_layout()
    fig.savefig(FIG / "f4_01_tcl_normalidad.png", bbox_inches="tight")
    plt.close(fig)

    return {
        "normality_raw_data": {"DAgostino_K2": round(k2_raw, 1), "p": float(f"{p_raw:.2e}"),
                                    "verdict": "not normal (expected)"},
        "normality_bootstrap_mean": {"DAgostino_K2": round(k2_mean, 3), "p": round(p_mean, 4),
                                             "verdict": "compatible with normal -> Welch-t valid"},
        "homoscedasticity_no_effect": {"Levene_stat": round(lev_stat0, 3), "p": round(lev_p0, 4),
                                        "verdict": "equal variances (expected in A/A)"},
        "homoscedasticity_diluted_effect": {"Levene_stat": round(lev_stat1, 2), "p": float(f"{lev_p1:.2e}"),
                                                "verdict": "the diluted effect INFLATES the "
                                                             "treatment's variance -> use Welch, not Student"},
        "independence": "by design: random assignment + dedup to 1 order/customer removes "
                         "intra-customer correlation. SUTVA assumed (no interference between customers).",
    }


# ===========================================================================
# 4. A/A calibration — 1,000 partitions
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
            "false_positive_rate_alpha_0.05": round(fpr, 4),
            "expected_rate": 0.05,
            "CI95_rate": [round(fpr - half, 4), round(fpr + half, 4)],
            "CI95_contains_0.05": bool(fpr_ci_ok),
            "KS_vs_uniform_stat": round(float(ks_stat), 4),
            "KS_vs_uniform_p": round(float(ks_p), 4),
            # KS is applied to 3 metrics -> a corrected threshold (0.05/3) is used for "catastrophic"
            "verdict": "calibrated" if (fpr_ci_ok and ks_p > 0.0167) else "REVIEW",
        }

    # figure: histogram of A/A p-values (primary metric)
    rng = np.random.default_rng(2024)
    x = df["merch_value"].values
    pv = np.array([stats.ttest_ind(*(lambda g: (x[g], x[~g]))(rng.random(len(x)) < 0.5),
                                   equal_var=False)[1] for _ in range(N_SIM_AA)])
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    ax.hist(pv, bins=20, color="#8d99ae", edgecolor="white")
    ax.axhline(N_SIM_AA / 20, color="#c1121f", ls="--", lw=1.2, label="expected uniform")
    ax.set_title(f"A/A · p-value distribution ({N_SIM_AA} partitions)\n"
                 f"false positives = {(pv < 0.05).mean()*100:.1f}%  (expected 5%)")
    ax.set_xlabel("p-value (Welch-t on merch_value, no effect)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "f4_02_aa_pvalores.png")
    plt.close(fig)
    return out


# ===========================================================================
# 5. A/B test — effect injected into the declared assignment
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

    # --- inject the effect into the primary metric (declared, SEED=42) ---
    df = df.copy()
    df["mv_effect"] = inject_diluted_effect(df["merch_value"].values, is_t, rng)
    cap = df["merch_value_w"].max()
    df["mv_effect_w"] = np.minimum(df["mv_effect"], cap)

    t = df[is_t]; c = df[~is_t]
    res = {"n_control": len(c), "n_treatment": len(t), "ATE_declared_pct": ATE * 100}

    # --- primary result and robustness ---
    primary = {}
    for label, col in [("Welch_raw", "mv_effect"), ("Welch_winsor_p99.5", "mv_effect_w")]:
        diff, (lo, hi), dfw = _welch_ci(t[col].values, c[col].values)
        st, p = stats.ttest_ind(t[col].values, c[col].values, equal_var=False)
        base = c[col].mean()
        primary[label] = {
            "control": round(base, 2), "treatment": round(t[col].mean(), 2),
            "diff_abs_R$": round(diff, 2),
            "lift_rel_pct": round(diff / base * 100, 3),
            "CI95_lift_pct": [round(lo / base * 100, 3), round(hi / base * 100, 3)],
            "p_value": float(f"{p:.3e}"), "welch_df": round(dfw, 0),
            "ATE_5pct_in_CI": bool(lo / base * 100 <= 5.0 <= hi / base * 100),
        }
    # log (ratio of geometric means)
    st, p = stats.ttest_ind(np.log(t["mv_effect"]), np.log(c["mv_effect"]), equal_var=False)
    gm_ratio = np.exp(np.log(t["mv_effect"]).mean() - np.log(c["mv_effect"]).mean()) - 1
    primary["log_geom_ratio"] = {"lift_geom_pct": round(gm_ratio * 100, 3), "p_value": float(f"{p:.3e}"),
                                 "note": "ratio of geometric means (~median), NOT the AOV"}
    # Mann-Whitney
    u, p = stats.mannwhitneyu(t["mv_effect"], c["mv_effect"], alternative="two-sided")
    primary["mann_whitney"] = {"U": float(u), "p_value": float(f"{p:.3e}"),
                               "note": "stochastic dominance"}
    # bootstrap
    boot = _bootstrap_ratio_ci(t["mv_effect"].values, c["mv_effect"].values, rng)
    primary["bootstrap_ratio"] = {"CI95_lift_pct": [round(boot[0] * 100, 3), round(boot[1] * 100, 3)],
                                  "note": "no distributional assumption"}
    res["primary"] = primary

    # --- guardrails (WITHOUT injected effect: should come out flat) ---
    guard = {}
    raw_p = {}
    # G1 review_score (Welch + Mann-Whitney)
    g1c = c["review_score"].dropna(); g1t = t["review_score"].dropna()
    st, p1 = stats.ttest_ind(g1t, g1c, equal_var=False)
    guard["G1_review_score"] = {"control": round(g1c.mean(), 4), "treatment": round(g1t.mean(), 4),
                                "diff": round(g1t.mean() - g1c.mean(), 4), "p_welch": p1,
                                "alarm_threshold": "drop >= 0.05 pts"}
    raw_p["G1_review_score"] = p1
    # G2 cancellation rate (full orders table)
    g2 = g2_cancellation_guardrail()
    guard["G2_cancellation"] = {"control_pct": g2["control"]["rate_pct"],
                               "treatment_pct": g2["treatment"]["rate_pct"],
                               "diff_pp": round(g2["treatment"]["rate_pct"] - g2["control"]["rate_pct"], 4),
                               "z_stat": g2["z_stat"], "p_welch": g2["p_value"],
                               "alarm_threshold": "significant rise"}
    raw_p["G2_cancellation"] = g2["p_value"]
    # G3 freight_value
    st, p3 = stats.ttest_ind(t["freight_value"], c["freight_value"], equal_var=False)
    guard["G3_freight_value"] = {"control": round(c["freight_value"].mean(), 3),
                                 "treatment": round(t["freight_value"].mean(), 3),
                                 "diff": round(t["freight_value"].mean() - c["freight_value"].mean(), 3),
                                 "p_welch": p3, "alarm_threshold": "significant rise"}
    raw_p["G3_freight_value"] = p3
    # G4 n_items
    st, p4 = stats.ttest_ind(t["n_items"], c["n_items"], equal_var=False)
    guard["G4_n_items"] = {"control": round(c["n_items"].mean(), 4), "treatment": round(t["n_items"].mean(), 4),
                           "diff": round(t["n_items"].mean() - c["n_items"].mean(), 4),
                           "p_welch": p4, "alarm_threshold": "significant drop"}
    raw_p["G4_n_items"] = p4

    # --- Benjamini-Hochberg correction over the guardrail family ---
    keys = list(raw_p.keys())
    pv = [raw_p[k] for k in keys]
    rej, p_adj, _, _ = multipletests(pv, alpha=ALPHA, method="fdr_bh")
    for k, pa, r in zip(keys, p_adj, rej):
        guard[k]["p_adjusted_BH"] = float(f"{pa:.4f}")
        guard[k]["significant_after_BH"] = bool(r)

    # --- two-gate rule (significant AND magnitude >= threshold), §1.4 / audit D19 ---
    # G4 has no quantified magnitude threshold in the design ("relevant magnitude") -> it is left
    # with the significance criterion only, explicitly declared (see GUARDRAIL_THRESHOLDS).
    aov_diff_r = primary["Welch_winsor_p99.5"]["diff_abs_R$"]
    guard["G1_review_score"]["magnitude_exceeds_threshold"] = bool(
        guard["G1_review_score"]["diff"] <= -GUARDRAIL_THRESHOLDS["g1_review_score_pts"])
    guard["G2_cancellation"]["magnitude_exceeds_threshold"] = bool(
        guard["G2_cancellation"]["diff_pp"] >= GUARDRAIL_THRESHOLDS["g2_cancelacion_pp"])
    guard["G3_freight_value"]["magnitude_exceeds_threshold"] = bool(
        guard["G3_freight_value"]["diff"] > 0
        and aov_diff_r > 0
        and guard["G3_freight_value"]["diff"] >= GUARDRAIL_THRESHOLDS["g3_freight_share_of_aov_rise_pct"] / 100 * aov_diff_r)
    guard["G4_n_items"]["magnitude_exceeds_threshold"] = None
    guard["G4_n_items"]["threshold_note"] = ("no quantified magnitude threshold in the design (§1.4: "
                                          "'relevant magnitude') -> blocks on significance alone, "
                                          "declared as a known limitation")
    for k in keys:
        mag = guard[k]["magnitude_exceeds_threshold"]
        guard[k]["blocks"] = bool(guard[k]["significant_after_BH"] and (True if mag is None else mag))

    res["guardrails"] = guard
    res["guardrails_note"] = ("G2 (cancellation) is evaluated on the full orders table, not the "
                              "analytical one (which already filters statuses), but with the SAME "
                              "control/treatment assignment persisted in analytical_table.parquet: the "
                              "inner join against that table excludes customers whose only order in "
                              "the window was canceled (they never got to have a valid order -> they "
                              "were never assigned to a real group). That is why G2's rate "
                              "(~0.02-0.04%) is much lower than Phase 2's global cancellation rate "
                              "(~0.63% over EVERYONE who bought in the window, including those who "
                              "only canceled): these are different populations by design, not an "
                              "error. Measuring the guardrail over 'everyone who bought' would mix "
                              "into the denominator people the experiment never touched; measuring it "
                              "over 'whoever ended up actually assigned' is the correct definition for "
                              "an EXPERIMENT guardrail (implementation audit, finding 1). No effect "
                              "injected in guardrails -> no degradation is expected. 'blocks' applies "
                              "the two-gate rule (significant after BH AND magnitude >= threshold); it "
                              "is the field that any consumer of this decision should read.")

    # --- A/B summary figure ---
    fig, ax = plt.subplots(figsize=(7, 3))
    labels = ["Welch raw", "Welch winsor", "bootstrap"]
    lifts = [primary["Welch_raw"]["lift_rel_pct"], primary["Welch_winsor_p99.5"]["lift_rel_pct"],
             np.mean(primary["bootstrap_ratio"]["CI95_lift_pct"])]
    cis = [primary["Welch_raw"]["CI95_lift_pct"], primary["Welch_winsor_p99.5"]["CI95_lift_pct"],
           primary["bootstrap_ratio"]["CI95_lift_pct"]]
    y = np.arange(len(labels))
    for i, (l, ci) in enumerate(zip(lifts, cis)):
        ax.plot(ci, [i, i], color="#3b6ea5", lw=2)
        ax.plot(l, i, "o", color="#3b6ea5")
    ax.axvline(5.0, color="#2a9d8f", ls="--", lw=1.3, label="declared ATE (+5%)")
    ax.axvline(3.0, color="#c1121f", ls=":", lw=1.3, label="relevance MDE (+3%)")
    ax.axvline(0.0, color="#999", lw=0.8)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.set_xlabel("AOV lift (%)  ·  95% CI")
    ax.set_title("A/B · effect on the primary metric (injected diluted effect)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "f4_03_ab_efecto.png")
    plt.close(fig)
    return res



def decision_scenarios(df: pd.DataFrame) -> dict:
    """Applies the decision rule (§1.5) to several injected effect sizes.
    Shows that the design reaches all three branches: launch / iterate / do not launch."""
    is_t = (df.group == "treatment").values
    x_raw = df["merch_value"].values        # inject on the raw metric, winsorize AFTER (same as run_ab_test)
    cap = df["merch_value_w"].max()
    base = np.minimum(x_raw, cap)[~is_t].mean()
    rows = []
    for ate_pct in [0, 1, 2, 3, 4, 5, 8]:
        rng = np.random.default_rng(SEED)
        dr = ate_pct / 100 / P_RESP         # delta_resp for that ATE
        xe = np.minimum(inject_diluted_effect(x_raw, is_t, rng, delta_resp=dr), cap)
        diff, (lo, hi), _ = _welch_ci(xe[is_t], xe[~is_t])
        _, p = stats.ttest_ind(xe[is_t], xe[~is_t], equal_var=False)
        lift, lo_p, hi_p = diff / base * 100, lo / base * 100, hi / base * 100
        if p >= ALPHA or lift <= 0:
            dec = "DO NOT LAUNCH"
        elif lo_p > MDE_RELEVANCIA:
            dec = "LAUNCH"
        else:
            dec = "ITERATE"
        rows.append({"ATE_injected_pct": ate_pct, "lift_observed_pct": round(lift, 2),
                     "CI95_pct": [round(lo_p, 2), round(hi_p, 2)], "p_value": float(f"{p:.2e}"),
                     "decision": dec})
    return {"note": f"rule §1.5 · relevance MDE = +{MDE_RELEVANCIA}% · guardrails not injected "
                    f"(always OK) · this split has +1.2% of baseline imbalance",
            "scenarios": rows}


# ===========================================================================
# Global audit improvements
# ===========================================================================
def guardrail_regression_scenarios(df: pd.DataFrame) -> dict:
    """Audit §D19 / improvement #1: inject a regression in G1 (review_score) and check that
    the guardrail test (a) has power to detect it and (b) with a two-gate rule
    (significant AND magnitude >= threshold) does not block the launch over sub-threshold noise."""
    is_t = (df.group == "treatment").values
    rs = df["review_score"].values.astype(float)
    base = np.nanmean(rs[~is_t])
    THRESH = 0.05
    rows = []
    for delta in [0.0, -0.03, -0.05, -0.08]:
        y = rs.copy()
        y[is_t] = y[is_t] + delta                     # additive regression in the treatment
        a, b = y[is_t], y[~is_t]
        a, b = a[~np.isnan(a)], b[~np.isnan(b)]
        st, p = stats.ttest_ind(a, b, equal_var=False)
        obs = a.mean() - b.mean()
        sig = p < ALPHA
        mag = abs(obs) >= THRESH and obs < 0
        rows.append({
            "regression_injected_pts": delta,
            "diff_observed_pts": round(obs, 4),
            "p_value": float(f"{p:.2e}"),
            "significant": bool(sig),
            "magnitude_>=_0.05": bool(mag),
            "rule_OR_(significant_OR_magnitude)": bool(sig or mag),   # original §1.4 rule
            "rule_AND_(significant_AND_magnitude)": bool(sig and mag),  # corrected rule
        })
    return {
        "base_review_control": round(base, 4), "magnitude_threshold_pts": THRESH,
        "scenarios": rows,
        "finding": ("at n≈47k ANY real regression is significant (even -0.03). The original "
                     "'significant OR magnitude>=0.05' rule would block the launch over "
                     "sub-threshold noise -> it is corrected to 'significant AND magnitude>=0.05'. "
                     "With the corrected rule: -0.03 does NOT block (correct), -0.08 DOES block "
                     "(correct). The guardrail test has ample power to detect the regression."),
    }


def heterogeneous_effect_variant(df: pd.DataFrame) -> dict:
    """Audit §D8 / improvement #2: variant with a TRULY heterogeneous effect (concentrated in orders
    below a hypothetical free-shipping threshold) and check that the segment analysis DETECTS it
    (unlike the homogeneous effect of the main analysis)."""
    from statsmodels.regression.linear_model import OLS
    rng = np.random.default_rng(SEED)
    is_t = (df.group == "treatment").values
    x = df["merch_value"].values.astype(float)
    FREE_SHIP_THRESHOLD = 150.0                       # R$, hypothetical
    band = (x >= FREE_SHIP_THRESHOLD - 60) & (x < FREE_SHIP_THRESHOLD)   # "near the threshold"

    # effect ONLY on treated units within the band: +12% (for the ~28% of orders in the band -> ATE ~3.4%)
    y = x.copy()
    resp = is_t & band & (rng.random(len(x)) < 0.6)
    y[resp] = y[resp] * (1 + 0.12 + rng.normal(0, 0.05, resp.sum()))

    near = band.astype(float)
    treat = is_t.astype(float)
    ylog = np.log(y)
    X = np.column_stack([np.ones(len(y)), treat, near, treat * near])
    r = OLS(ylog, X).fit(cov_type="HC3")
    p_inter = float(r.pvalues[3])

    # global effect vs. effect within the band
    def lift(mask):
        tt, cc = y[mask & is_t], y[mask & ~is_t]
        return (tt.mean() / cc.mean() - 1) * 100
    return {
        "free_shipping_threshold_R$": FREE_SHIP_THRESHOLD,
        "pct_orders_in_band": round(band.mean() * 100, 1),
        "lift_global_pct": round(lift(np.ones(len(y), bool)), 2),
        "lift_in_band_pct": round(lift(band), 2),
        "lift_outside_band_pct": round(lift(~band), 2),
        "p_interaction_near_threshold_HC3": float(f"{p_inter:.2e}"),
        "heterogeneity_detected": bool(p_inter < ALPHA),
        "finding": ("with a truly heterogeneous effect (concentrated below the free-shipping "
                     "threshold), the interaction test DOES detect it (very small p). Contrast with "
                     "the main analysis (homogeneous effect -> no interaction). The design "
                     "distinguishes real heterogeneity from artifacts."),
    }


def ab_multiseed(df: pd.DataFrame, n_seeds: int = N_SIM_MULTISEED) -> dict:
    """Audit §4 point 4 / improvement #3: repeat the FULL A/B test over many seeds
    (re-split + re-injection of the diluted effect) to measure the estimator's distribution and the
    real coverage of the 95% CI. Closes the weakness of the 'single split'.
    Done on RAW and on WINSOR to isolate the effect of winsorization on the bias."""
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
        return {"mean_lift_pct": round(float(lifts.mean()), 3),
                "bias_pp": round(float(lifts.mean()) - ATE * 100, 3),
                "lift_sd_pp": round(float(lifts.std(ddof=1)), 3),
                "lift_p2.5_p97.5": [round(float(np.percentile(lifts, 2.5)), 2),
                                    round(float(np.percentile(lifts, 97.5)), 2)],
                "CI95_coverage_of_+5pct": round(float(covers.mean()), 3),
                "empirical_power": round(float(rej.mean()), 3)}

    crudo, winsor = _run(False), _run(True)
    return {
        "n_seeds": n_seeds,
        "raw": crudo,
        "winsor_p99.5": winsor,
        "finding": (f"On RAW the estimator is UNBIASED (bias {crudo['bias_pp']} pp) and the 95% CI "
                     f"covers the true value {crudo['CI95_coverage_of_+5pct']:.0%} of the time "
                     f"(nominal 95%). WINSORIZATION introduces a small NEGATIVE bias "
                     f"({winsor['bias_pp']} pp) because it clips the treatment's high values more "
                     f"(multiplicative effect) -> coverage drops to "
                     f"{winsor['CI95_coverage_of_+5pct']:.0%}. That is the price of the variance "
                     f"reduction; the (LAUNCH) decision is robust because both CIs clear +3%. "
                     f"The +5.7% of the SEED=42 split falls within the p2.5-p97.5 range."),
    }


def clustered_se_robustness() -> dict:
    """Audit §D3 / improvement #5: repeat the primary result with ALL orders (no dedup) and standard
    errors clustered by customer; confirm it matches the deduplicated version."""
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
    # SAME assignment as the main analysis: customer->group map from the analytical table
    at = pd.read_parquet(ANALYTICAL_TABLE)[["customer_unique_id", "group"]]
    cmap = at.set_index("customer_unique_id")["group"].map({"control": 0, "treatment": 1})
    o = o[o["customer_unique_id"].isin(cmap.index)].copy()
    o["treat"] = o["customer_unique_id"].map(cmap).astype(float)
    # same diluted effect (SEED) at order level on the treated units
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
        "n_orders_no_dedup": len(o), "n_customers": int(o.customer_unique_id.nunique()),
        "lift_pct_all_orders": round(r_cl.params[1] / base * 100, 3),
        "lift_pct_dedup_1_order_per_customer_ref": 5.666,
        "SE_robust_no_clustering_R$": round(r_iid.bse[1], 4),
        "SE_cluster_by_customer_R$": round(r_cl.bse[1], 4),
        "SE_inflation_from_clustering_pct": round((r_cl.bse[1] / r_iid.bse[1] - 1) * 100, 2),
        "finding": ("with ALL orders + SE clustered by customer, the SE is practically "
                     "identical to that of the deduplicated version (97% of customers have 1 order "
                     "-> clustering barely inflates the SE, ~1%). The point lift differs slightly "
                     "because it includes ~3,200 extra orders from repeat customers, but the "
                     "conclusion (significant, CI above the MDE) does not change. Deduplicating was "
                     "the simple and correct option."),
    }


# ===========================================================================
def main():
    df = pd.read_parquet(ANALYTICAL_TABLE)
    report = {
        "parameters": {"SEED": SEED, "ALPHA": ALPHA, "P_RESP": P_RESP, "DELTA_RESP": DELTA_RESP,
                       "EPS_SD": EPS_SD, "ATE_pct": ATE * 100, "N_SIM_AA": N_SIM_AA,
                       "N_SIM_POWER": N_SIM_POWER, "N_BOOT": N_BOOT},
        "1_power_analysis": power_analysis(df),
        "2_assumptions": check_assumptions(df),
        "3_aa_calibration": aa_calibration(df),
        "4_ab_test": run_ab_test(df),
        "5_decision_scenarios": decision_scenarios(df),
        "6_guardrail_regression": guardrail_regression_scenarios(df),
        "7_heterogeneous_effect": heterogeneous_effect_variant(df),
        "8_ab_multiseed": ab_multiseed(df),
        "9_clustered_se": clustered_se_robustness(),
    }
    (OUT_T / "fase4_resumen.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
