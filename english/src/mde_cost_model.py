"""
Improvement #4 of the global audit — derive the relevance MDE from a cost model,
instead of asserting it.

The "relevance MDE" is the AOV lift below which the annual incremental margin does NOT cover
the total cost of ownership of the redesign (build + maintain). Everything here is DECLARED
assumptions for illustrative purposes; the Olist dataset does not come with costs or a take rate.

Output: outputs/tables/mde_cost_model.csv  +  outputs/figures/f_mde_breakeven.png
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from config import COST_MODEL, OUT_FIGURES as FIG, OUT_TABLES as OUT_T

# ---- declared assumptions (from params.yaml -> config.COST_MODEL) --------
AOV_BASE = COST_MODEL["aov_base"]
COMMISSION = COST_MODEL["commission"]
NET_MARGIN_ON_COMMISSION = COST_MODEL["net_margin_on_commission"]
BUILD_COST = COST_MODEL["build_cost"]
MAINT_COST_YEAR = COST_MODEL["maint_cost_year"]
PAYBACK_YEARS = COST_MODEL["payback_years"]

# annual order volume: range. The dataset gives ~58,700; a medium-large marketplace, much more.
VOLUME_GRID = [58_700, 250_000, 1_000_000, 5_000_000, 20_000_000]


def breakeven_lift(volume: float,
                   build=BUILD_COST, maint=MAINT_COST_YEAR, years=PAYBACK_YEARS) -> float:
    """Relative AOV lift (fraction) that equates cumulative incremental margin and total cost."""
    margin_per_lift_year = AOV_BASE * volume * COMMISSION * NET_MARGIN_ON_COMMISSION
    total_cost = build + maint * years
    total_margin_per_lift = margin_per_lift_year * years
    return total_cost / total_margin_per_lift


def required_volume_for_mde(mde_pct: float,
                            build=BUILD_COST, maint=MAINT_COST_YEAR, years=PAYBACK_YEARS) -> float:
    """Inverse of `breakeven_lift`: minimum volume (orders/year) at which an `mde_pct` lift
    (in %, e.g. 3.0) is exactly break-even. Used by evaluation.py (portfolio review, priority 2)
    to compare the REAL volume used in the impact extrapolation against the volume the declared
    MDE actually requires -- before this fix, that comparison only existed as a number printed by
    this script's `main()`, never as a reusable value or checked against the final decision."""
    total_cost = build + maint * years
    mde_frac = mde_pct / 100
    return total_cost / (AOV_BASE * COMMISSION * NET_MARGIN_ON_COMMISSION * years * mde_frac)


def main():
    rows = []
    for v in VOLUME_GRID:
        for yrs in (1, 2, 3):
            bl = breakeven_lift(v, years=yrs)
            rows.append({"pedidos_anio": v, "horizonte_payback_anios": yrs,
                         "MDE_breakeven_pct": round(bl * 100, 3)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT_T / "mde_cost_model.csv", index=False)

    print("=== Relevance MDE derived from costs ===")
    print(f"assumptions: AOV R$ {AOV_BASE:.0f} · commission {COMMISSION:.0%} · net margin on commission "
          f"{NET_MARGIN_ON_COMMISSION:.0%}")
    print(f"            build R$ {BUILD_COST:,} · maintain R$ {MAINT_COST_YEAR:,}/year\n")
    piv = df.pivot(index="pedidos_anio", columns="horizonte_payback_anios", values="MDE_breakeven_pct")
    piv.columns = [f"payback {c}y  (MDE %)" for c in piv.columns]
    print(piv.to_string())

    v_data = 58_700
    v_mid = 1_000_000
    print(f"\nReading:")
    print(f"  · At the dataset's own volume (~{v_data:,} orders/year) the break-even is "
          f"~+{breakeven_lift(v_data)*100:.1f}%  ->  the +3% MDE would NOT be justified at that scale.")
    print(f"  · At medium marketplace scale (~{v_mid:,} orders/year) the break-even is "
          f"~+{breakeven_lift(v_mid)*100:.2f}%  ->  +3% is CONSERVATIVE (leaves margin).")
    print(f"  · The project implicitly assumes that second scale. The +3% is kept as the threshold "
          f"but is conditioned on volume >= ~{ (BUILD_COST+MAINT_COST_YEAR*PAYBACK_YEARS)/(AOV_BASE*COMMISSION*NET_MARGIN_ON_COMMISSION*PAYBACK_YEARS*0.03):,.0f} orders/year.")

    fig, ax = plt.subplots(figsize=(7, 3.8))
    vols = np.logspace(np.log10(40_000), np.log10(20_000_000), 60)
    for yrs, col in zip((1, 2, 3), ("#c1121f", "#3b6ea5", "#2a9d8f")):
        ax.plot(vols, [breakeven_lift(v, years=yrs) * 100 for v in vols], color=col,
                label=f"payback {yrs} year(s)")
    ax.axhline(3.0, color="#666", ls="--", lw=1, label="MDE used (+3%)")
    ax.axvline(58_700, color="#999", ls=":", lw=1)
    ax.axvline(415_000, color="#2a9d8f", ls=":", lw=1)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("orders / year"); ax.set_ylabel("break-even MDE (%)")
    ax.set_title("Relevance MDE derived from costs\n"
                 "+3% is break-even from ~415k orders/year onward  ·  at the dataset's scale "
                 "(~59k) it would be ~+21%", fontsize=9)
    ax.legend(fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(FIG / "f_mde_breakeven.png", dpi=130)
    print(f"\nfigure -> {FIG / 'f_mde_breakeven.png'}")


if __name__ == "__main__":
    main()
