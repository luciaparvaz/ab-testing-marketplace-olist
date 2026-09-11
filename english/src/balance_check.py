"""
Phase 3 — Covariate balance check on the simulated assignment.

Verifies that control and treatment are exchangeable BEFORE injecting any effect:
  - SMD (standardized mean difference) per covariate; criterion |SMD| < 0.10
  - Omnibus test per covariate (chi2 for categorical, Welch-t for continuous)
  - Point A/A check on the primary metric with the declared seed (SEED=42)

Output: outputs/tables/fase3_balance.csv  +  outputs/figures/f3_01_balance.png
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt

from config import ANALYTICAL_TABLE, OUT_FIGURES as FIG, OUT_TABLES as OUT_T

CAT_COVARS = ["customer_state", "cat_dominante", "payment_type", "mes_compra"]
NUM_COVARS = ["n_items", "freight_value"]


def smd_continuous(a: pd.Series, b: pd.Series) -> float:
    s = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return (a.mean() - b.mean()) / s if s else 0.0


def smd_binary(p1: float, p2: float) -> float:
    p = (p1 + p2) / 2
    denom = np.sqrt(p * (1 - p))
    return (p1 - p2) / denom if denom else 0.0


def main():
    df = pd.read_parquet(ANALYTICAL_TABLE)
    c = df[df.group == "control"]
    t = df[df.group == "treatment"]
    rows = []

    # --- continuous covariates ---
    for col in NUM_COVARS:
        smd = smd_continuous(t[col], c[col])
        st, p = stats.ttest_ind(t[col], c[col], equal_var=False)
        rows.append({"covariable": col, "tipo": "continuous",
                     "control": round(c[col].mean(), 4), "treatment": round(t[col].mean(), 4),
                     "SMD": round(smd, 4), "test": "Welch-t", "stat": round(st, 3), "p_value": round(p, 4)})

    # --- categorical covariates: max SMD across levels + omnibus chi2 ---
    for col in CAT_COVARS:
        ct = pd.crosstab(df[col], df.group)
        chi2, p, dof, _ = stats.chi2_contingency(ct)
        pc = c[col].value_counts(normalize=True)
        ptt = t[col].value_counts(normalize=True)
        levels = pc.index.union(ptt.index)
        smd_max = max(abs(smd_binary(ptt.get(l, 0.0), pc.get(l, 0.0))) for l in levels)
        rows.append({"covariable": col, "tipo": f"categorical ({ct.shape[0]} levels)",
                     "control": "-", "treatment": "-",
                     "SMD": round(smd_max, 4), "test": f"chi2 (dof={dof})",
                     "stat": round(chi2, 2), "p_value": round(p, 4)})

    bal = pd.DataFrame(rows)
    bal["balanceada"] = bal["SMD"].abs() < 0.10
    bal.to_csv(OUT_T / "fase3_balance.csv", index=False)
    print("=== Covariate balance check (SEED=42 assignment) ===")
    print(bal.to_string(index=False))
    print(f"\nAll |SMD| < 0.10: {bal['balanceada'].all()}")
    print(f"No omnibus test significant at 0.05: {(bal['p_value'] >= 0.05).all()}")

    # --- SRM check (Sample Ratio Mismatch) ---
    n_c, n_t = len(c), len(t)
    chi2_srm, p_srm = stats.chisquare([n_c, n_t], [(n_c + n_t) / 2] * 2)
    print(f"\n=== SRM check (is the split 50/50?) ===")
    print(f"  control={n_c}  treatment={n_t}  ratio_t={n_t/(n_c+n_t):.4f}")
    print(f"  chi2={chi2_srm:.3f}  p={p_srm:.4f}  ->  "
          f"{'OK, compatible with 50/50' if p_srm > 0.01 else 'ALERT: possible SRM, review the assignment'}")
    pd.DataFrame([{"n_control": n_c, "n_treatment": n_t, "ratio_treatment": round(n_t/(n_c+n_t), 5),
                   "chi2": round(chi2_srm, 4), "p_value": round(p_srm, 4),
                   "veredicto": "no SRM" if p_srm > 0.01 else "SRM"}]
                 ).to_csv(OUT_T / "fase3_srm.csv", index=False)

    # --- point A/A check on the primary metric ---
    st, p = stats.ttest_ind(t.merch_value, c.merch_value, equal_var=False)
    diff = t.merch_value.mean() - c.merch_value.mean()
    lift = diff / c.merch_value.mean() * 100
    print(f"\n=== Point A/A · primary metric (merch_value, no effect) ===")
    print(f"  control={c.merch_value.mean():.2f}  treatment={t.merch_value.mean():.2f}  "
          f"diff={diff:+.2f} R$ ({lift:+.2f}%)  Welch-t p={p:.4f}")
    print("  -> with SEED=42 the difference is sampling noise; the global calibration "
          "(1000 seeds) is validated in Phase 4.")

    # --- love-plot figure ---
    fig, ax = plt.subplots(figsize=(7, 3.2))
    b2 = bal.sort_values("SMD", key=lambda s: s.abs())
    ax.scatter(b2["SMD"].abs(), range(len(b2)), color="#3b6ea5", zorder=3)
    ax.axvline(0.10, color="#c1121f", ls="--", lw=1.2, label="threshold |SMD| = 0.10")
    ax.set_yticks(range(len(b2)))
    ax.set_yticklabels(b2["covariable"])
    ax.set_xlabel("|SMD| (standardized mean difference)")
    ax.set_title("Covariate balance after random assignment (Phase 3)")
    ax.set_xlim(0, max(0.12, b2["SMD"].abs().max() * 1.3))
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "f3_01_balance.png", dpi=130)
    print(f"\nfigure -> {FIG / 'f3_01_balance.png'}")


if __name__ == "__main__":
    main()
