"""
Phase 2 — Data Understanding: profiling aimed at the experimental question.

This is not generic EDA: only what is needed is computed for (a) defining the primary metric
and its variance -> input for the Phase 4 power analysis, (b) sizing the sample,
(c) documenting limitations that affect the experiment's validity.

Output: outputs/tables/fase2_*.csv  and  a summary via stdout.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats

from config import OUT_TABLES as OUT_T, RAW

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

    # ---- 1. Size and period -------------------------------------------------
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
    report["orders_per_month"] = {str(k.date()): int(v) for k, v in monthly.items()}

    # ---- 2. Order status -----------------------------------------
    report["order_status"] = orders["order_status"].value_counts().to_dict()

    # ---- 3. Relevant nulls -----------------------------------------------
    report["nulls_orders"] = orders.isna().sum().to_dict()

    # ---- 4. Duplicates ---------------------------------------------------
    report["dup_order_id_in_orders"] = int(orders["order_id"].duplicated().sum())
    report["dup_review_id"] = int(reviews["review_id"].duplicated().sum())
    report["dup_order_id_in_reviews"] = int(reviews["order_id"].duplicated().sum())

    # ---- 5. Primary metric: merchandise value per order ---------------
    # merchandise value = sum of price from order_items per order_id (excludes freight)
    merch = items.groupby("order_id")["price"].sum().rename("merch_value")
    freight = items.groupby("order_id")["freight_value"].sum().rename("freight_value")
    n_items = items.groupby("order_id").size().rename("n_items")

    # only delivered or in-transit orders count as a "completed purchase"
    from config import VALID_STATUS as valid_status
    o = orders[["order_id", "customer_id", "order_status", "order_purchase_timestamp"]].copy()
    o = o.merge(merch, on="order_id", how="left").merge(freight, on="order_id", how="left")
    o = o.merge(n_items, on="order_id", how="left")
    o = o.merge(customers[["customer_id", "customer_unique_id", "customer_state"]],
                on="customer_id", how="left")

    report["orders_without_items"] = int(o["merch_value"].isna().sum())
    report["orders_without_items_by_status"] = (
        o.loc[o["merch_value"].isna(), "order_status"].value_counts().to_dict()
    )

    o_valid = o[o["order_status"].isin(valid_status) & o["merch_value"].notna()].copy()
    report["n_valid_orders"] = int(o_valid.shape[0])
    report["n_unique_valid_customers"] = int(o_valid["customer_unique_id"].nunique())

    report["AOV_merch_value"] = describe_series(o_valid["merch_value"])
    report["AOV_with_freight"] = describe_series(o_valid["merch_value"] + o_valid["freight_value"])
    report["freight_value"] = describe_series(o_valid["freight_value"])
    report["n_items_per_order"] = describe_series(o_valid["n_items"])

    # log-transform (to assess symmetry)
    report["AOV_log_merch"] = describe_series(np.log(o_valid["merch_value"].clip(lower=0.01)))

    # ---- 6. Orders per customer (randomization unit) ----------------
    per_cust = o_valid.groupby("customer_unique_id").size()
    report["orders_per_customer"] = {
        "customers": int(per_cust.size),
        "with_1_order": int((per_cust == 1).sum()),
        "with_2+_orders": int((per_cust >= 2).sum()),
        "pct_customers_1_order": float((per_cust == 1).mean() * 100),
        "pct_orders_from_repeat_customers": float(
            o_valid.duplicated("customer_unique_id", keep=False).mean() * 100
        ),
        "max_orders_one_customer": int(per_cust.max()),
    }

    # ---- 7. Reviews (guardrail G1) ---------------------------------------
    rev = reviews.drop_duplicates("order_id", keep="last")
    rev_valid = o_valid[["order_id"]].merge(rev[["order_id", "review_score"]], on="order_id", how="left")
    report["review_coverage_pct"] = float(rev_valid["review_score"].notna().mean() * 100)
    report["review_score_dist"] = rev_valid["review_score"].value_counts().sort_index().to_dict()
    report["review_score_stats"] = describe_series(rev_valid["review_score"])

    # ---- 8. Cancellation (guardrail G2) ---------------------------------
    report["global_cancellation_rate_pct"] = float((orders["order_status"] == "canceled").mean() * 100)

    # ---- 9. Payments -----------------------------------------------------
    pay_by_order = payments.groupby("order_id")["payment_value"].sum()
    report["payment_value_stats"] = describe_series(
        o_valid[["order_id"]].merge(pay_by_order, on="order_id", how="left")["payment_value"]
    )
    report["payment_types"] = payments["payment_type"].value_counts().to_dict()

    # ---- 10. Power analysis preview: available n vs MDE ----------------
    # with n fixed per group, which relative delta is detectable at 80% power, alpha=0.05 two-tailed
    n_per_group = report["n_valid_orders"] // 2
    cv = report["AOV_merch_value"]["cv"]
    # Cohen's d needed for 80% power, 0.05 two-tailed, approx.
    from statsmodels.stats.power import TTestIndPower
    analysis = TTestIndPower()
    d_detectable = analysis.solve_power(nobs1=n_per_group, alpha=0.05, power=0.80, alternative="two-sided")
    # d = (mu_T - mu_C) / sigma ; relative_lift = d * sigma / mu = d * cv
    lift_detectable = d_detectable * cv
    report["power_preview"] = {
        "n_valid_orders": report["n_valid_orders"],
        "n_per_group_50_50": int(n_per_group),
        "cv_AOV_merch": cv,
        "cohen_d_detectable_80pct": float(d_detectable),
        "relative_lift_detectable_80pct_pct": float(lift_detectable * 100),
        "note": "preliminary, using a normal-approximation t-test; Phase 4 uses bootstrap/Welch over the real distribution",
    }

    # ---- save ----
    (OUT_T / "fase2_resumen.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # useful CSV tables
    pd.Series(report["orders_per_month"]).to_csv(OUT_T / "fase2_orders_por_mes.csv", header=["n_orders"])
    pd.DataFrame([report["AOV_merch_value"], report["AOV_with_freight"], report["freight_value"],
                  report["n_items_per_order"], report["AOV_log_merch"]],
                 index=["merch_value", "merch+freight", "freight", "n_items", "log(merch)"]
                 ).to_csv(OUT_T / "fase2_distribuciones.csv")

    # ---- print ----
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
