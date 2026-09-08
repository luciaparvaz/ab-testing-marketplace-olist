"""Fase 2 — figuras de perfilado para el portfolio."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

RAW = Path("data/raw")
FIG = Path("outputs/figures")
FIG.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 130, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})

orders = pd.read_csv(RAW / "olist_orders_dataset.csv", parse_dates=["order_purchase_timestamp"])
items = pd.read_csv(RAW / "olist_order_items_dataset.csv")
reviews = pd.read_csv(RAW / "olist_order_reviews_dataset.csv")
customers = pd.read_csv(RAW / "olist_customers_dataset.csv")

valid_status = {"delivered", "shipped", "invoiced", "approved", "processing"}
merch = items.groupby("order_id")["price"].sum().rename("merch_value")
o = orders.merge(merch, on="order_id", how="left")
o = o[o["order_status"].isin(valid_status) & o["merch_value"].notna()]

# --- Fig 1: volumen mensual de pedidos ---
monthly = o.set_index("order_purchase_timestamp").resample("MS").size()
fig, ax = plt.subplots(figsize=(9, 3.4))
ax.bar(monthly.index, monthly.values, width=20, color="#3b6ea5")
ax.axvspan(pd.Timestamp("2017-01-01"), pd.Timestamp("2018-09-01"), color="#f2c14e", alpha=0.18,
           label="ventana estable propuesta (2017-01 a 2018-08)")
ax.set_title("Volumen mensual de pedidos válidos — Olist FD (perfilado Fase 2)")
ax.set_ylabel("pedidos")
ax.legend(loc="upper left", fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "f2_01_volumen_mensual.png")
plt.close(fig)

# --- Fig 2: distribución del AOV (métrica primaria) raw vs log ---
mv = o["merch_value"].values
fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
axes[0].hist(np.clip(mv, 0, 800), bins=80, color="#3b6ea5")
axes[0].axvline(np.mean(mv), color="#c1121f", ls="--", lw=1.3, label=f"media = R$ {np.mean(mv):.0f}")
axes[0].axvline(np.median(mv), color="#264653", ls=":", lw=1.3, label=f"mediana = R$ {np.median(mv):.0f}")
axes[0].set_title(f"AOV bruto (clip a R$800)  ·  skew={pd.Series(mv).skew():.1f}")
axes[0].set_xlabel("valor de mercancía por pedido (R$)")
axes[0].legend(fontsize=8)
axes[1].hist(np.log(np.clip(mv, 0.01, None)), bins=80, color="#2a9d8f")
axes[1].set_title(f"log(AOV)  ·  skew={pd.Series(np.log(np.clip(mv,0.01,None))).skew():.2f} (casi normal)")
axes[1].set_xlabel("log(valor de mercancía)")
fig.suptitle("Distribución de la métrica primaria — input del power analysis (Fase 4)", y=1.03)
fig.tight_layout()
fig.savefig(FIG / "f2_02_distribucion_aov.png", bbox_inches="tight")
plt.close(fig)

# --- Fig 3: guardrails (review score + pedidos por cliente) ---
rev = reviews.drop_duplicates("order_id", keep="last")
rs = o.merge(rev[["order_id", "review_score"]], on="order_id", how="left")["review_score"].dropna()
cu = o.merge(customers[["customer_id", "customer_unique_id"]], on="customer_id", how="left")
per_cust = cu.groupby("customer_unique_id").size()
fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
vc = rs.value_counts().sort_index()
axes[0].bar(vc.index.astype(int), vc.values, color="#e76f51")
axes[0].set_title(f"G1 · review_score  (media {rs.mean():.2f}, cobertura 99%)")
axes[0].set_xlabel("puntuación (1–5)")
pc = per_cust.value_counts().sort_index()
axes[1].bar(pc.index[:6], pc.values[:6], color="#8d99ae")
axes[1].set_yscale("log")
axes[1].set_title(f"Pedidos por cliente  ({(per_cust==1).mean()*100:.1f}% con 1 solo)")
axes[1].set_xlabel("nº de pedidos por customer_unique_id")
axes[1].yaxis.set_major_formatter(mticker.ScalarFormatter())
fig.suptitle("Guardrails y unidad de aleatorización (Fase 2)", y=1.03)
fig.tight_layout()
fig.savefig(FIG / "f2_03_guardrails.png", bbox_inches="tight")
plt.close(fig)

print("figuras escritas en", FIG)
for p in sorted(FIG.glob("f2_*.png")):
    print(" -", p.name)
