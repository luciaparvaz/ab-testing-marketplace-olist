"""
Phase 3 — Data Preparation.

Builds the analytical table `1 row = 1 order-customer` from the 9 raw CSVs,
applying ONLY the transformations justified by the experimental question (not generic EDA).
Every step is logged and traced to `outputs/tables/fase3_transformaciones.csv`.

It also simulates the random control/treatment assignment (per customer, 50/50, fixed seed) and
saves the table ready for the statistical design of Phase 4. The treatment effect is NOT
injected here (that is Phase 4).

Output:
  data/processed/analytical_table.parquet
  outputs/tables/fase3_transformaciones.csv
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import (ANALYTICAL_TABLE, OUT_TABLES as OUT_T, RAW, SEED, VALID_STATUS,
                    WINDOW_END, WINDOW_START, WINSOR_Q)

_LOG: list[dict] = []


def step(name: str, n_before: int, n_after: int, rationale: str):
    _LOG.append({"paso": name, "n_antes": n_before, "n_despues": n_after,
                 "delta": n_after - n_before, "justificacion": rationale})
    print(f"[{name}] {n_before} -> {n_after} ({n_after - n_before:+d})  · {rationale}")


def build_order_table() -> pd.DataFrame:
    orders = pd.read_csv(RAW / "olist_orders_dataset.csv",
                         parse_dates=["order_purchase_timestamp", "order_delivered_customer_date"])
    items = pd.read_csv(RAW / "olist_order_items_dataset.csv")
    payments = pd.read_csv(RAW / "olist_order_payments_dataset.csv")
    reviews = pd.read_csv(RAW / "olist_order_reviews_dataset.csv",
                          parse_dates=["review_answer_timestamp"])
    customers = pd.read_csv(RAW / "olist_customers_dataset.csv")
    products = pd.read_csv(RAW / "olist_products_dataset.csv")
    cat_tr = pd.read_csv(RAW / "product_category_name_translation.csv")

    n0 = len(orders)
    print(f"\n=== Building the order table (raw: {n0} orders) ===")

    # --- 1. Time window ------------------------------------------------
    m = (orders["order_purchase_timestamp"] >= WINDOW_START) & \
        (orders["order_purchase_timestamp"] < WINDOW_END)
    orders = orders[m].copy()
    step("date_window", n0, len(orders),
         f"restrict to [{WINDOW_START}, {WINDOW_END}) for realism (does not fix bias, §B6)")

    # --- 2. Valid statuses ----------------------------------------------
    nb = len(orders)
    orders = orders[orders["order_status"].isin(VALID_STATUS)].copy()
    step("valid_statuses", nb, len(orders),
         f"keep {sorted(VALID_STATUS)} = purchase completed; exclude canceled/unavailable/created")

    # --- 3. Primary metric: merchandise value per order --------
    merch = items.groupby("order_id")["price"].sum().rename("merch_value")
    freight = items.groupby("order_id")["freight_value"].sum().rename("freight_value")
    n_items = items.groupby("order_id").size().rename("n_items")
    orders = orders.merge(merch, on="order_id", how="left") \
                   .merge(freight, on="order_id", how="left") \
                   .merge(n_items, on="order_id", how="left")
    nb = len(orders)
    orders = orders[orders["merch_value"].notna()].copy()
    step("orders_with_items", nb, len(orders),
         "exclude orders with no order_items lines (they have no primary metric)")

    # --- 4. Dominant category of the order (most expensive item) --------
    prod_cat = products[["product_id", "product_category_name"]].merge(
        cat_tr, on="product_category_name", how="left")
    it = items.merge(prod_cat, on="product_id", how="left")
    dom = (it.sort_values("price", ascending=False)
             .drop_duplicates("order_id")[["order_id", "product_category_name_english"]]
             .rename(columns={"product_category_name_english": "cat_dominante"}))
    orders = orders.merge(dom, on="order_id", how="left")
    orders["cat_dominante"] = orders["cat_dominante"].fillna("unknown")

    # --- 5. Main payment type (row with the highest payment_value) --------
    pay = (payments.sort_values("payment_value", ascending=False)
                   .drop_duplicates("order_id")[["order_id", "payment_type"]])
    orders = orders.merge(pay, on="order_id", how="left")
    orders["payment_type"] = orders["payment_type"].replace("not_defined", np.nan).fillna("unknown")

    # --- 6. Review: dedup by most recent review_answer_timestamp -----
    rev = (reviews.sort_values("review_answer_timestamp")
                  .drop_duplicates("order_id", keep="last")[["order_id", "review_score"]])
    orders = orders.merge(rev, on="order_id", how="left")

    # --- 7. Derived variables ----------------------------------------
    orders["mes_compra"] = orders["order_purchase_timestamp"].dt.to_period("M").astype(str)
    orders["is_delivered"] = (orders["order_status"] == "delivered").astype(int)
    orders = orders.merge(customers[["customer_id", "customer_unique_id", "customer_state"]],
                          on="customer_id", how="left")
    return orders


def dedup_one_order_per_customer(df: pd.DataFrame) -> pd.DataFrame:
    nb = len(df)
    out = (df.sort_values("order_purchase_timestamp")
             .drop_duplicates("customer_unique_id", keep="first")
             .reset_index(drop=True))
    step("dedup_1_order_per_customer", nb, len(out),
         "keep each customer's first order -> randomization unit = analysis unit (§B3)")
    return out


def add_winsor_and_assignment(df: pd.DataFrame) -> pd.DataFrame:
    cap = df["merch_value"].quantile(WINSOR_Q)
    df["merch_value_w"] = df["merch_value"].clip(upper=cap)
    df.attrs["winsor_cap"] = float(cap)
    df.attrs["winsor_q"] = WINSOR_Q
    n_capped = int((df["merch_value"] > cap).sum())
    print(f"[winsor] cap p{WINSOR_Q*100:.1f} = R$ {cap:,.2f}  ·  {n_capped} orders capped "
          f"({n_capped/len(df)*100:.2f}%)  ·  col `merch_value_w` (only for the significance test)")

    rng = np.random.default_rng(SEED)
    df["group"] = rng.choice(["control", "treatment"], size=len(df))
    n_t = int((df["group"] == "treatment").sum())
    print(f"[assignment] seed={SEED}  ·  control={len(df) - n_t}  treatment={n_t}  "
          f"({n_t/len(df)*100:.2f}% treatment)")
    return df


def main():
    orders = build_order_table()
    orders = dedup_one_order_per_customer(orders)
    orders = add_winsor_and_assignment(orders)

    keep = ["order_id", "customer_unique_id", "order_purchase_timestamp", "mes_compra",
            "order_status", "is_delivered", "customer_state", "cat_dominante", "payment_type",
            "n_items", "merch_value", "merch_value_w", "freight_value", "review_score", "group"]
    tab = orders[keep].copy()

    out_path = ANALYTICAL_TABLE
    tab.to_parquet(out_path, index=False)
    pd.DataFrame(_LOG).to_csv(OUT_T / "fase3_transformaciones.csv", index=False)

    print(f"\n=== Analytical table: {tab.shape[0]} rows x {tab.shape[1]} columns -> {out_path} ===")
    print(tab.dtypes)
    print("\nPrimary metric summary by group (WITHOUT injected effect — should be ~equal):")
    print(tab.groupby("group")["merch_value"].agg(["count", "mean", "median", "std"]).round(2))
    print("\nNulls per column:")
    print(tab.isna().sum())


if __name__ == "__main__":
    main()
