"""
Fase 2 — Data Understanding: perfilado dirigido a la pregunta experimental.

No es EDA genérica: solo se calcula lo necesario para (a) definir la métrica primaria
y su varianza -> input del power analysis de la Fase 4, (b) dimensionar la muestra,
(c) documentar limitaciones que afectan a la validez del experimento.

Salida: outputs/tables/fase2_*.csv  y  un resumen por stdout.
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

RAW = Path("data/raw")
OUT_T = Path("outputs/tables")
OUT_T.mkdir(parents=True, exist_ok=True)

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 40)


def load():
    orders = pd.read_csv(
        RAW / "olist_orders_dataset.csv",
        parse_dates=[
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )
    items = pd.read_csv(RAW / "olist_order_items_dataset.csv")
    payments = pd.read_csv(RAW / "olist_order_payments_dataset.csv")
    reviews = pd.read_csv(RAW / "olist_order_reviews_dataset.csv",
                          parse_dates=["review_creation_date", "review_answer_timestamp"])
    customers = pd.read_csv(RAW / "olist_customers_dataset.csv")
    products = pd.read_csv(RAW / "olist_products_dataset.csv")
    return orders, items, payments, reviews, customers, products


def describe_series(s: pd.Series) -> dict:
    s = s.dropna()
    return {
        "n": int(s.size),
        "mean": float(s.mean()),
        "std": float(s.std(ddof=1)),
        "cv": float(s.std(ddof=1) / s.mean()) if s.mean() else np.nan,
        "min": float(s.min()),
        "p1": float(s.quantile(0.01)),
        "p5": float(s.quantile(0.05)),
        "p25": float(s.quantile(0.25)),
        "median": float(s.median()),
        "p75": float(s.quantile(0.75)),
        "p95": float(s.quantile(0.95)),
        "p99": float(s.quantile(0.99)),
        "max": float(s.max()),
        "skew": float(stats.skew(s)),
        "kurtosis_excess": float(stats.kurtosis(s)),
    }


def main():
    orders, items, payments, reviews, customers, products = load()
    report: dict = {}

    # ---- 1. Tamaño y período -------------------------------------------------
    report["shapes"] = {
        "orders": list(orders.shape),
        "order_items": list(items.shape),
        "order_payments": list(payments.shape),
        "order_reviews": list(reviews.shape),
        "customers": list(customers.shape),
        "products": list(products.shape),
    }
    report["period"] = {
        "purchase_min": str(orders["order_purchase_timestamp"].min()),
        "purchase_max": str(orders["order_purchase_timestamp"].max()),
    }
    monthly = (orders.set_index("order_purchase_timestamp")
                     .resample("MS").size())
    report["orders_por_mes"] = {str(k.date()): int(v) for k, v in monthly.items()}

    # ---- 2. Estado de los pedidos -----------------------------------------
    report["order_status"] = orders["order_status"].value_counts().to_dict()

    # ---- 3. Nulos relevantes -----------------------------------------------
    report["nulos_orders"] = orders.isna().sum().to_dict()

    # ---- 4. Duplicados ---------------------------------------------------
    report["dup_order_id_en_orders"] = int(orders["order_id"].duplicated().sum())
    report["dup_review_id"] = int(reviews["review_id"].duplicated().sum())
    report["dup_order_id_en_reviews"] = int(reviews["order_id"].duplicated().sum())

    # ---- 5. Métrica primaria: valor de mercancía por pedido ---------------
    # valor de mercancia = suma de price de order_items por order_id (excluye flete)
    merch = items.groupby("order_id")["price"].sum().rename("merch_value")
    freight = items.groupby("order_id")["freight_value"].sum().rename("freight_value")
    n_items = items.groupby("order_id").size().rename("n_items")

    # solo pedidos entregados o en camino cuentan como "compra realizada"
    valid_status = {"delivered", "shipped", "invoiced", "approved", "processing"}
    o = orders[["order_id", "customer_id", "order_status", "order_purchase_timestamp"]].copy()
    o = o.merge(merch, on="order_id", how="left").merge(freight, on="order_id", how="left")
    o = o.merge(n_items, on="order_id", how="left")
    o = o.merge(customers[["customer_id", "customer_unique_id", "customer_state"]],
                on="customer_id", how="left")

    report["pedidos_sin_items"] = int(o["merch_value"].isna().sum())
    report["pedidos_sin_items_por_status"] = (
        o.loc[o["merch_value"].isna(), "order_status"].value_counts().to_dict()
    )

    o_valid = o[o["order_status"].isin(valid_status) & o["merch_value"].notna()].copy()
    report["n_pedidos_validos"] = int(o_valid.shape[0])
    report["n_clientes_unicos_validos"] = int(o_valid["customer_unique_id"].nunique())

    report["AOV_merch_value"] = describe_series(o_valid["merch_value"])
    report["AOV_con_flete"] = describe_series(o_valid["merch_value"] + o_valid["freight_value"])
    report["freight_value"] = describe_series(o_valid["freight_value"])
    report["n_items_por_pedido"] = describe_series(o_valid["n_items"])

    # log-transform (para evaluar simetria)
    report["AOV_log_merch"] = describe_series(np.log(o_valid["merch_value"].clip(lower=0.01)))

    # ---- 6. Pedidos por cliente (unidad de aleatorizacion) ----------------
    per_cust = o_valid.groupby("customer_unique_id").size()
    report["pedidos_por_cliente"] = {
        "clientes": int(per_cust.size),
        "con_1_pedido": int((per_cust == 1).sum()),
        "con_2+_pedidos": int((per_cust >= 2).sum()),
        "pct_clientes_1_pedido": float((per_cust == 1).mean() * 100),
        "pct_pedidos_de_clientes_recurrentes": float(
            o_valid.duplicated("customer_unique_id", keep=False).mean() * 100
        ),
        "max_pedidos_un_cliente": int(per_cust.max()),
    }

    # ---- 7. Reviews (guardrail G1) ---------------------------------------
    rev = reviews.drop_duplicates("order_id", keep="last")
    rev_valid = o_valid[["order_id"]].merge(rev[["order_id", "review_score"]], on="order_id", how="left")
    report["review_coverage_pct"] = float(rev_valid["review_score"].notna().mean() * 100)
    report["review_score_dist"] = rev_valid["review_score"].value_counts().sort_index().to_dict()
    report["review_score_stats"] = describe_series(rev_valid["review_score"])

    # ---- 8. Cancelacion (guardrail G2) ---------------------------------
    report["tasa_cancelacion_pct_global"] = float((orders["order_status"] == "canceled").mean() * 100)

    # ---- 9. Payments -----------------------------------------------------
    pay_by_order = payments.groupby("order_id")["payment_value"].sum()
    report["payment_value_stats"] = describe_series(
        o_valid[["order_id"]].merge(pay_by_order, on="order_id", how="left")["payment_value"]
    )
    report["payment_types"] = payments["payment_type"].value_counts().to_dict()

    # ---- 10. Power analysis preview: n disponible vs MDE ----------------
    # con n fijo por grupo, que delta (relativo) se detecta al 80% potencia, alpha=0.05 bilateral
    n_per_group = report["n_pedidos_validos"] // 2
    cv = report["AOV_merch_value"]["cv"]
    # d de Cohen necesaria para 80% potencia, 0.05 bilateral, aprox
    from statsmodels.stats.power import TTestIndPower
    analysis = TTestIndPower()
    d_detectable = analysis.solve_power(nobs1=n_per_group, alpha=0.05, power=0.80, alternative="two-sided")
    # d = (mu_T - mu_C) / sigma ; lift_relativo = d * sigma / mu = d * cv
    lift_detectable = d_detectable * cv
    report["power_preview"] = {
        "n_pedidos_validos": report["n_pedidos_validos"],
        "n_por_grupo_50_50": int(n_per_group),
        "cv_AOV_merch": cv,
        "cohen_d_detectable_80pct": float(d_detectable),
        "lift_relativo_detectable_80pct_pct": float(lift_detectable * 100),
        "nota": "preliminar con t-test normal-aproximado; la Fase 4 usa bootstrap/Welch sobre la distribucion real",
    }

    # ---- guardar ----
    (OUT_T / "fase2_resumen.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # tablas CSV utiles
    pd.Series(report["orders_por_mes"]).to_csv(OUT_T / "fase2_orders_por_mes.csv", header=["n_orders"])
    pd.DataFrame([report["AOV_merch_value"], report["AOV_con_flete"], report["freight_value"],
                  report["n_items_por_pedido"], report["AOV_log_merch"]],
                 index=["merch_value", "merch+freight", "freight", "n_items", "log(merch)"]
                 ).to_csv(OUT_T / "fase2_distribuciones.csv")

    # ---- print ----
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
