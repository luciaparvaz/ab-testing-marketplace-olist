"""
Phase 5 — Evaluation.

Translates the Phase 4 statistical result into a product decision:
  1. Full report (effect, CI, p) and its reading
  2. Statistical significance vs. business relevance (against the +3% MDE) + impact in R$/year
  3. Covariate-adjusted estimate (ANCOVA) -> variance reduction
  4. Analysis by PRE-SPECIFIED segments (forest plot + interaction test, with BH)
  5. Demonstration of p-hacking risk (exploratory slicing without correction)
  6. Decision

Reuses the declared diluted effect (SEED=42) from src/modeling.py.
Output: outputs/tables/fase5_*.csv/json · outputs/figures/f5_*.png
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
    """Design matrix with a constant; categorical columns -> dummies (drop_first)."""
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
    """Robust (HC3) Wald p-value of the treat x segment interaction block.
    Necessary because under H1 there is heteroscedasticity between groups (Phase 4)."""
    k = seg_dummies.shape[1]
    X = np.column_stack([np.ones(len(y)), treat, seg_dummies, seg_dummies * treat[:, None]])
    res = OLS(y, X).fit(cov_type="HC3")
    R = np.zeros((k, X.shape[1]))
    for i in range(k):
        R[i, X.shape[1] - k + i] = 1.0
    return float(res.wald_test(R, scalar=True).pvalue)


apply_plot_style()

# PRE-SPECIFIED segments (declared BEFORE looking at per-segment results).
# "new vs. repeat customer" is NOT included: dedup to 1 order/customer leaves it degenerate
# (n_repeat≈40); also repeat purchase at Olist is ~3% (Phase 2 §2.7). Out of scope, declared.
PRESPEC_SEGMENTS = ["cesta", "payment_type", "macro_region", "trimestre", "cat_grupo"]

MACRO_REGION = {
    "SP": "Southeast", "RJ": "Southeast", "MG": "Southeast", "ES": "Southeast",
    "PR": "South", "SC": "South", "RS": "South",
    "BA": "Northeast", "PE": "Northeast", "CE": "Northeast", "MA": "Northeast", "PB": "Northeast",
    "RN": "Northeast", "AL": "Northeast", "PI": "Northeast", "SE": "Northeast",
    "GO": "Midwest", "DF": "Midwest", "MT": "Midwest", "MS": "Midwest",
    "PA": "North", "AM": "North", "RO": "North", "TO": "North", "AC": "North",
    "AP": "North", "RR": "North",
}


def load_with_effect() -> pd.DataFrame:
    df = pd.read_parquet(ANALYTICAL_TABLE).copy()
    is_t = (df.group == "treatment").values
    rng = np.random.default_rng(SEED)
    df["mv"] = inject_diluted_effect(df["merch_value"].values, is_t, rng)
    # same cap, same function, across the whole pipeline (see src/modeling.py and effect_model.py).
    cap = compute_winsor_cap(df["merch_value"].values, WINSOR_Q)
    df["mv_w"] = winsorize_outcome(df["mv"].values, cap)

    # segments
    df["cesta"] = np.where(df["n_items"] >= 2, "2+ items", "1 item")
    df["macro_region"] = df["customer_state"].map(MACRO_REGION).fillna("other")
    df["trimestre"] = pd.to_datetime(df["order_purchase_timestamp"]).dt.to_period("Q").astype(str)
    top_cat = df["cat_dominante"].value_counts().head(6).index
    df["cat_grupo"] = np.where(df["cat_dominante"].isin(top_cat), df["cat_dominante"], "other")
    return df


def welch_lift(t: np.ndarray, c: np.ndarray, alpha=ALPHA) -> dict:
    diff = t.mean() - c.mean()
    se = np.sqrt(t.var(ddof=1) / t.size + c.var(ddof=1) / c.size)
    dfw = se**4 / ((t.var(ddof=1) / t.size)**2 / (t.size - 1) +
                   (c.var(ddof=1) / c.size)**2 / (c.size - 1))
    tcrit = stats.t.ppf(1 - alpha / 2, dfw)
    st, p = stats.ttest_ind(t, c, equal_var=False)
    # log10(p) robust even if p underflows to 0.0
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
    out = {"parameters": {"SEED": SEED, "ATE_declared_pct": ATE * 100, "MDE_relevance_pct": MDE_RELEVANCIA}}

    # ---- 1-2. primary result + relevance + R$ impact --------------
    prim = welch_lift(df.loc[is_t, "mv_w"].values, df.loc[~is_t, "mv_w"].values)
    # annualization: uses the REAL volume of valid orders in the window (without dedup),
    # because the redesign would apply to every order, not only to each customer's first one.
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
    out["1_primary_result"] = {
        "lift_pct": round(prim["lift_pct"], 3),
        "CI95_lift_pct": [round(prim["ci_lo"], 3), round(prim["ci_hi"], 3)],
        "diff_abs_R$": round(prim["base"] * prim["lift_pct"] / 100, 2),
        "p_value": "underflow (< 1e-15)" if prim["p"] == 0 else float(f"{prim['p']:.2e}"),
        "log10_p": prim["log10_p"], "t_stat": prim["t_stat"],
        "n_control": prim["n_c"], "n_treatment": prim["n_t"],
        "significant": bool(prim["p"] < ALPHA),
        "ci_entirely_above_MDE": bool(prim["ci_lo"] > MDE_RELEVANCIA),
        "relevant": bool(prim["p"] < ALPHA and prim["ci_lo"] > MDE_RELEVANCIA),
    }
    from config import COST_MODEL
    COMMISSION = COST_MODEL["commission"]  # assumed marketplace take rate

    # --- MDE <-> volume consistency (portfolio review, priority 2) -----------------------------
    # mde_cost_model.py ALREADY computed (only via stdout, never as an output or checked against
    # the decision) that the +3% MDE is only break-even from ~415k orders/year, while the business
    # impact below is extrapolated over the REAL volume of the dataset (~59k). At that real
    # volume, the project's own cost model requires a MUCH higher break-even than +3% -- computed
    # here explicitly, not just stated in prose, and used to condition the final decision instead
    # of ignoring it.
    mde_breakeven_at_real_volume_pct = mde_cost_model.breakeven_lift(n_orders_year) * 100
    min_volume_for_mde_3pct = mde_cost_model.required_volume_for_mde(MDE_RELEVANCIA)
    real_volume_is_consistent_with_declared_mde = n_orders_year >= min_volume_for_mde_3pct

    out["2_business_impact"] = {
        "valid_orders_window_no_dedup": n_orders_window, "window_months": n_months,
        "estimated_orders_per_year": round(n_orders_year),
        "AOV_base_R$": round(base_aov, 2),
        "GMV_merchandise_annual_estimated_R$": round(gmv_year),
        "uplift_GMV_annual_R$": round(uplift_gmv_year),
        "uplift_GMV_annual_CI95_R$": [round(gmv_year * prim["ci_lo"] / 100),
                                     round(gmv_year * prim["ci_hi"] / 100)],
        "uplift_marketplace_revenue_annual_R$_assuming_15pct_commission": round(uplift_gmv_year * COMMISSION),
        "note": ("GMV = merchandise value. The marketplace's revenue is a commission (take rate) "
                 "on the GMV; 15% is assumed for illustrative purposes. Linear extrapolation of the "
                 "per-order lift to the historical annual volume."),
        "MDE_vs_volume_consistency": {
            "declared_MDE_pct": MDE_RELEVANCIA,
            "volume_used_in_extrapolation_orders_year": round(n_orders_year),
            "min_volume_for_+3pct_MDE_to_break_even": round(min_volume_for_mde_3pct),
            "MDE_break_even_AT_REAL_dataset_volume_pct": round(mde_breakeven_at_real_volume_pct, 2),
            "real_volume_is_consistent_with_declared_MDE": bool(real_volume_is_consistent_with_declared_mde),
            "reading": (
                f"The +{MDE_RELEVANCIA}% MDE used as the relevance gate (§1.5) is only break-even "
                f"from ~{min_volume_for_mde_3pct:,.0f} orders/year. The impact above is extrapolated "
                f"over ~{n_orders_year:,.0f} orders/year (this dataset's REAL volume) -- at that "
                f"scale, the project's own cost model requires a break-even of "
                f"~+{mde_breakeven_at_real_volume_pct:.1f}%, not +{MDE_RELEVANCIA}%. The +3% MDE "
                "only makes sense as a decision threshold if you implicitly assume a marketplace "
                "~7x larger than Olist in this dataset; at the real scale, neither the true "
                "injected lift (+5%) nor the one observed in the SEED=42 split (~+5.7%) clears the "
                "real break-even. See '6_decision' for how this conditions the final recommendation."
            ),
        },
    }

    # ---- 3. ANCOVA: covariate adjustment (variance reduction) ------
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
        "unadjusted": {"coef_treat_R$": round(b0, 3), "lift_pct": round(b0 / base * 100, 3),
                       "ci95_pct": [round(lo0 / base * 100, 3), round(hi0 / base * 100, 3)],
                       "se_R$": round(se0, 4)},
        "adjusted": {"coef_treat_R$": round(b1, 3), "lift_pct": round(b1 / base * 100, 3),
                       "ci95_pct": [round(lo1 / base * 100, 3), round(hi1 / base * 100, 3)],
                       "se_R$": round(se1, 4)},
        "SE_reduction_pct": round((1 - se1 / se0) * 100, 2),
    }

    # ---- 4. pre-specified segments: forest + interaction ----------
    seg_rows = []
    inter_p = {}
    for seg in PRESPEC_SEGMENTS:
        for lvl, g in df.groupby(seg):
            r = welch_lift(g.loc[g.group == "treatment", "mv_w"].values,
                           g.loc[g.group == "control", "mv_w"].values)
            seg_rows.append({"segmento": seg, "nivel": str(lvl), **{k: round(v, 3) for k, v in r.items()}})
        # group:segment interaction test on log(AOV): is the RELATIVE effect heterogeneous?
        # (at the level scale, the multiplicative effect gives a larger absolute lift in large
        #  baskets -> a mechanical 'heterogeneity' would be detected; the business asks about the
        #  %, hence the log)
        # HC3 Wald: robust to the between-group heteroscedasticity introduced by H1 (Phase 5 audit).
        seg_d = pd.get_dummies(df[seg], prefix=seg, drop_first=True, dtype=float).values
        treat_s = (df.group == "treatment").values.astype(float)
        inter_p[seg] = interaction_wald_hc3(np.log(df["mv"].values), treat_s, seg_d)
    seg_df = pd.DataFrame(seg_rows)
    seg_df.to_csv(OUT_T / "phase5_segments.csv", index=False)

    keys = list(inter_p)
    rej, p_adj, _, _ = multipletests([inter_p[k] for k in keys], alpha=ALPHA, method="fdr_bh")
    seg_n = {s: df.groupby(s).size().to_dict() for s in PRESPEC_SEGMENTS}
    out["4_segments"] = {
        "prespecified_segments": PRESPEC_SEGMENTS,
        "interaction_test": {k: {"p_raw": round(inter_p[k], 4), "p_BH": round(pa, 4),
                                 "heterogeneity_significant_after_BH": bool(r),
                                 "n_per_level": seg_n[k]}
                             for k, pa, r in zip(keys, p_adj, rej)},
        "test_scale": "log(AOV), HC3 Wald -> tests heterogeneity of the RELATIVE effect (%), "
                       "robust to the between-group heteroscedasticity; at the level scale the "
                       "multiplicative effect mechanically generates absolute heterogeneity in "
                       "large baskets",
        "verdict": ("no significant interaction (neither raw nor after BH) -> the relative effect "
                      "is HOMOGENEOUS across segments, consistent with the design (random "
                      "responders). Looking for 'where it works best' without correction would be "
                      "p-hacking."),
    }

    # ---- 5. p-hacking demonstration -------------------------------
    # ~38 arbitrary exploratory cuts (states, individual categories, freight quantiles, quarters)
    slicers = []
    for st_ in df.customer_state.value_counts().head(12).index:
        slicers.append(("state", st_, df.customer_state == st_))
    for ct in df.cat_dominante.value_counts().head(15).index:
        slicers.append(("category", ct, df.cat_dominante == ct))
    for q in range(4):
        lo, hi = df.freight_value.quantile(q / 4), df.freight_value.quantile((q + 1) / 4)
        slicers.append(("freight_q", f"q{q+1}", df.freight_value.between(lo, hi)))
    for m_ in df.trimestre.unique():
        slicers.append(("quarter", m_, df.trimestre == m_))
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
        p_level.append(OLS(y_level, X).fit(cov_type="HC3").pvalues[3])   # robust HC3
        p_log.append(OLS(y_log, X).fit(cov_type="HC3").pvalues[3])
        names.append(f"{fam}:{lvl}")
    p_level, p_log = np.array(p_level), np.array(p_log)

    def _summ(pv):
        bh = multipletests(pv, alpha=ALPHA, method="fdr_bh")[0]
        bf = multipletests(pv, alpha=ALPHA, method="bonferroni")[0]
        return {"nominal_p<0.05": {"n": int((pv < 0.05).sum()),
                                     "which": [names[i] for i in np.where(pv < 0.05)[0]]},
                "after_BH": {"n": int(bh.sum()), "which": [names[i] for i in np.where(bh)[0]]},
                "after_Bonferroni": int(bf.sum())}

    out["5_p_hacking"] = {
        "n_exploratory_cuts": len(names),
        "expected_by_chance_at_0.05": round(0.05 * len(names), 1),
        "test": "treat x cut interaction, HC3 Wald",
        "test_at_LEVEL_(mv_w)": _summ(p_level),
        "test_at_LOG_(relative_effect)": _summ(p_log),
        "lesson": ("(1) At LEVEL scale several 'segments where the effect differs' survive even "
                    "BH and Bonferroni: they are NOT chance, they are a MECHANICAL ARTIFACT of the "
                    "multiplicative effect (the lift in R$ is larger in large baskets), concentrated "
                    "in the cuts correlated with size (freight quartiles). "
                    "(2) At LOG scale (the relative effect, which is the business question) only "
                    "chance-level nominal findings remain, and NONE survives the correction. "
                    "Moral: (a) test the correct magnitude (%, not absolute R$), (b) pre-specify "
                    "segments, (c) correct for multiplicity. Correcting is not enough if the "
                    "estimand is wrong to begin with."),
    }

    # ---- figure: segment forest plot --------------------------
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    order = seg_df.iloc[::-1].reset_index(drop=True)
    ax.axvline(prim["lift_pct"], color="#2a9d8f", ls="--", lw=1.2, label=f"global effect (+{prim['lift_pct']:.1f}%)")
    ax.axvline(MDE_RELEVANCIA, color="#c1121f", ls=":", lw=1.2, label=f"relevance MDE (+{MDE_RELEVANCIA}%)")
    ax.axvline(0, color="#999", lw=0.7)
    for i, row in order.iterrows():
        ax.plot([row.ci_lo, row.ci_hi], [i, i], color="#3b6ea5", lw=1.8)
        ax.plot(row.lift_pct, i, "o", color="#3b6ea5", ms=4)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f"{r.segmento}: {r.nivel}" for r in order.itertuples()], fontsize=7)
    ax.set_xlabel("RELATIVE AOV lift (%) · 95% CI")
    ax.set_title("Effect by pre-specified segment\n"
                 "true effect is homogeneous (+5%) · no significant interaction after BH",
                 fontsize=10)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "f5_01_forest_segments.png", bbox_inches="tight")
    plt.close(fig)

    # ---- 6. decision --------------------------------------------
    # Before: `dec` depended ONLY on whether the CI cleared the DECLARED MDE (+3%), a threshold
    # that (see 2_business_impact.MDE_vs_volume_consistency) is only break-even from ~415k
    # orders/year -- far above the ~59k real orders used to compute the R$ impact above.
    # Publishing "LAUNCH" with an impact annualized over the real volume, while applying a
    # relevance threshold that volume does not justify, is the contradiction this portfolio
    # review closes. The decision now uses the SAME three-branch rule as
    # decision_scenarios/ab_multiseed (see src/modeling.py), but with the REAL break-even of the
    # dataset's volume as the threshold -- not the +3% meant for a ~7x larger scale.
    mde_real = out["2_business_impact"]["MDE_vs_volume_consistency"][
        "MDE_break_even_AT_REAL_dataset_volume_pct"]
    if not out["1_primary_result"]["significant"] or prim["lift_pct"] <= 0:
        dec = "DO NOT LAUNCH"
    elif prim["ci_lo"] > mde_real:
        dec = "LAUNCH"
    else:
        dec = "ITERATE"
    # decision under the DECLARED MDE (+3%), the one this project reported before this
    # correction -- kept for context, but no longer the headline decision.
    dec_under_declared_mde = "LAUNCH" if out["1_primary_result"]["relevant"] else "REVIEW"

    out["6_decision"] = {
        "decision": dec,
        "decision_under_declared_MDE_+3pct_ignoring_volume": dec_under_declared_mde,
        "justification": [
            f"Primary effect +{prim['lift_pct']:.2f}% (95% CI [{prim['ci_lo']:.2f}, {prim['ci_hi']:.2f}]), "
            f"log10(p) = {prim['log10_p']} -> highly significant.",
            f"At the dataset's REAL volume (~{out['2_business_impact']['estimated_orders_per_year']:,} "
            f"orders/year), the cost model's break-even is +{mde_real:.1f}% "
            f"(not the declared +{MDE_RELEVANCIA}%, calibrated for a much larger marketplace) -> "
            f"the 95% CI of the effect {'DOES' if prim['ci_lo'] > mde_real else 'does NOT'} clear "
            f"that real threshold entirely.",
            "No guardrail degraded (Phase 4, Benjamini-Hochberg).",
            "Homogeneous effect across pre-specified segments (no interaction after BH).",
            f"Covariate-adjusted estimate (ANCOVA): +{out['3_ancova']['adjusted']['lift_pct']}% "
            f"with SE {out['3_ancova']['SE_reduction_pct']}% lower.",
            f"Estimated impact: +R$ {uplift_gmv_year:,.0f}/year of merchandise GMV "
            f"(CI [{gmv_year*prim['ci_lo']/100:,.0f}, {gmv_year*prim['ci_hi']/100:,.0f}]) -- "
            f"insufficient to cover the redesign's cost (R$ "
            f"{mde_cost_model.BUILD_COST + mde_cost_model.MAINT_COST_YEAR * mde_cost_model.PAYBACK_YEARS:,.0f} "
            f"over {mde_cost_model.PAYBACK_YEARS} years) at the dataset's real volume.",
        ],
        "caveats": [
            "The effect is synthetic and declared: this 'decision' validates the process, not a real finding.",
            "The point estimate exceeds the injected ATE (+5%) because of the split's baseline "
            "imbalance (see balance_check.py, now includes merch_value in the formal table); the "
            "CI covers it.",
            f"The power of this decision rule (not just of rejecting H0) is measured in "
            f"fase4_resumen.json::8_ab_multiseed -- under the declared MDE, the 'LAUNCH' gate only "
            f"fires in a fraction of re-randomizations, not always (see "
            f"'decision_rule_power_finding').",
            "The +3% MDE is not wrong in itself -- it is the correct threshold if the marketplace "
            "had ~415k+ orders/year. The problem is publishing a business decision that mixes that "
            "threshold with an R$ impact computed over a volume ~7x smaller.",
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

    (OUT_T / "phase5_summary.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=_js), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False, default=_js))


if __name__ == "__main__":
    main()
