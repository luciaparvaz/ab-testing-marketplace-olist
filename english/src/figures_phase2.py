"""Phase 2 — profiling figures for the portfolio."""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from config import OUT_FIGURES as FIG, RAW, VALID_STATUS, WINDOW_END, WINDOW_START, apply_plot_style

apply_plot_style()


def main():
    orders = pd.read_csv(RAW / "olist_orders_dataset.csv", parse_dates=["order_purchase_timestamp"])
    items = pd.read_csv(RAW / "olist_order_items_dataset.csv")
    reviews = pd.read_csv(RAW / "olist_order_reviews_dataset.csv")
    customers = pd.read_csv(RAW / "olist_customers_dataset.csv")

    merch = items.groupby("order_id")["price"].sum().rename("merch_value")
    o = orders.merge(merch, on="order_id", how="left")
    o = o[o["order_status"].isin(VALID_STATUS) & o["merch_value"].notna()]

    # --- Fig 1: monthly order volume ---
    monthly = o.set_index("order_purchase_timestamp").resample("MS").size()
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.bar(monthly.index, monthly.values, width=20, color="#3b6ea5")
    ax.axvspan(pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END), color="#f2c14e", alpha=0.18,
               label=f"stable window ({WINDOW_START} to 2018-08)")
    ax.set_title("Monthly volume of valid orders — Olist FD (Phase 2 profiling)")
    ax.set_ylabel("orders")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "f2_01_monthly_volume.png")
    plt.close(fig)

    # --- Fig 2: AOV (primary metric) distribution, raw vs log ---
    mv = o["merch_value"].values
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    axes[0].hist(np.clip(mv, 0, 800), bins=80, color="#3b6ea5")
    axes[0].axvline(np.mean(mv), color="#c1121f", ls="--", lw=1.3, label=f"mean = R$ {np.mean(mv):.0f}")
    axes[0].axvline(np.median(mv), color="#264653", ls=":", lw=1.3, label=f"median = R$ {np.median(mv):.0f}")
    axes[0].set_title(f"Raw AOV (clipped to R$800)  ·  skew={pd.Series(mv).skew():.1f}")
    axes[0].set_xlabel("merchandise value per order (R$)")
    axes[0].legend(fontsize=8)
    axes[1].hist(np.log(np.clip(mv, 0.01, None)), bins=80, color="#2a9d8f")
    axes[1].set_title(f"log(AOV)  ·  skew={pd.Series(np.log(np.clip(mv,0.01,None))).skew():.2f} "
                      f"(robust range for the t-test; CLT at large n)")
    axes[1].set_xlabel("log(merchandise value)")
    fig.suptitle("Distribution of the primary metric — input for the power analysis (Phase 4)", y=1.03)
    fig.tight_layout()
    fig.savefig(FIG / "f2_02_aov_distribution.png", bbox_inches="tight")
    plt.close(fig)

    # --- Fig 3: guardrails (review score + orders per customer) ---
    rev = reviews.drop_duplicates("order_id", keep="last")
    rs = o.merge(rev[["order_id", "review_score"]], on="order_id", how="left")["review_score"].dropna()
    cu = o.merge(customers[["customer_id", "customer_unique_id"]], on="customer_id", how="left")
    per_cust = cu.groupby("customer_unique_id").size()
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
    vc = rs.value_counts().sort_index()
    axes[0].bar(vc.index.astype(int), vc.values, color="#e76f51")
    axes[0].set_title(f"G1 · review_score  (mean {rs.mean():.2f}, 99% coverage)")
    axes[0].set_xlabel("score (1-5)")
    pc = per_cust.value_counts().sort_index()
    axes[1].bar(pc.index[:6], pc.values[:6], color="#8d99ae")
    axes[1].set_yscale("log")
    axes[1].set_title(f"Orders per customer  ({(per_cust==1).mean()*100:.1f}% with just 1)")
    axes[1].set_xlabel("number of orders per customer_unique_id")
    axes[1].yaxis.set_major_formatter(mticker.ScalarFormatter())
    fig.suptitle("Guardrails and randomization unit (Phase 2)", y=1.03)
    fig.tight_layout()
    fig.savefig(FIG / "f2_03_guardrails.png", bbox_inches="tight")
    plt.close(fig)

    print("figures written to", FIG)
    for p in sorted(FIG.glob("f2_*.png")):
        print(" -", p.name)


if __name__ == "__main__":
    main()
