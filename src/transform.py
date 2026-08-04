from datetime import datetime
from typing import Dict

import pandas as pd


def drop_duplicate_rows(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Remove exact duplicate rows (every column identical).

    Rows that share a key but differ in other columns are left alone -
    validation.py's uniqueness checks catch those as a real data quality issue.
    """
    before = len(df)
    deduped = df.drop_duplicates(keep="first").reset_index(drop=True)
    removed = before - len(deduped)
    if removed > 0:
        print(f"  Deduped {table_name}: removed {removed} exact duplicate row(s)")
    return deduped


def flatten_orders(orders_df: pd.DataFrame) -> pd.DataFrame:
    """Flatten nested orders into order-item-level rows."""
    flattened_rows = []

    for _, order_row in orders_df.iterrows():
        order_id = order_row["order_id"]
        customer_id = order_row["customer_id"]
        delivery_method_id = order_row["delivery_method_id"]
        order_date = order_row["order_date"]

        metadata = order_row.get("metadata", {})
        source = metadata.get("source", "unknown")
        processed_at = metadata.get("processed_at", None)

        items = order_row.get("items", [])
        if not isinstance(items, list):
            continue

        for item in items:
            flattened_rows.append({
                "order_id": order_id,
                "customer_id": customer_id,
                "delivery_method_id": delivery_method_id,
                "order_date": order_date,
                "item_id": item.get("item_id"),
                "product_id": item.get("product_id"),
                "product_name_from_order": item.get("product_name"),
                "quantity": item.get("quantity"),
                "special_instructions": item.get("special_instructions"),
                "source": source,
                "processed_at": processed_at,
            })

    flattened_df = pd.DataFrame(flattened_rows)
    print(f"  Flattened {len(orders_df)} orders into {len(flattened_df)} items")
    return flattened_df


def create_dim_customers(customers_df: pd.DataFrame) -> pd.DataFrame:
    """Create customers dimension, enriched with a derived full_name."""
    dim = customers_df[["id", "first_name", "last_name", "city"]].copy()
    dim.columns = ["customer_id", "first_name", "last_name", "city"]
    dim["full_name"] = dim["first_name"].str.cat(dim["last_name"], sep=" ")
    return dim


def create_dim_categories(categories_df: pd.DataFrame) -> pd.DataFrame:
    """Create categories dimension."""
    dim = categories_df[["id", "category_name"]].copy()
    dim.columns = ["category_id", "category_name"]
    return dim


def create_dim_products(products_df: pd.DataFrame, dim_categories: pd.DataFrame) -> pd.DataFrame:
    """Create products dimension, enriched with category_name denormalized from
    dim_categories so reporting queries don't need an extra join."""
    dim = products_df[["id", "product_name", "manufacturer", "price", "category_id"]].copy()
    dim.columns = ["product_id", "product_name", "manufacturer", "price", "category_id"]
    dim["price"] = pd.to_numeric(dim["price"], errors="coerce")
    dim = dim.merge(dim_categories[["category_id", "category_name"]], on="category_id", how="left")
    return dim


def create_dim_delivery_methods(delivery_methods_df: pd.DataFrame) -> pd.DataFrame:
    """Create delivery methods dimension."""
    dim = delivery_methods_df[["id", "method_name", "courier_name", "shipping_days"]].copy()
    dim.columns = ["delivery_method_id", "method_name", "courier_name", "shipping_days"]
    return dim


def create_dim_date(order_dates_series: pd.Series) -> pd.DataFrame:
    """Create date dimension from order dates."""
    dates = pd.to_datetime(order_dates_series).dt.normalize().unique()
    dates = sorted(dates)

    rows = []
    for date in dates:
        rows.append({
            "date_key": int(date.strftime("%Y%m%d")),
            "date": date.strftime("%Y-%m-%d"),
            "year": date.year,
            "month": date.month,
            "day": date.day,
            "day_of_week": date.day_name(),
        })

    return pd.DataFrame(rows)


def create_fact_order_items(
    flattened_orders: pd.DataFrame,
    dim_products: pd.DataFrame,
    dim_delivery_methods: pd.DataFrame,
) -> pd.DataFrame:
    """Create fact table: one row per order item with calculated line_amount."""
    fact = flattened_orders.copy()

    # Join products for unit_price
    fact = fact.merge(
        dim_products[["product_id", "price"]],
        on="product_id",
        how="left",
    )
    fact.rename(columns={"price": "unit_price"}, inplace=True)
    fact["line_amount"] = fact["quantity"] * fact["unit_price"]

    # Select columns in order
    fact_columns = [
        "order_id", "item_id", "customer_id", "product_id", "delivery_method_id",
        "order_date", "quantity", "unit_price", "line_amount",
        "special_instructions", "source", "processed_at",
    ]
    fact = fact[fact_columns].copy()

    # Type conversions
    fact["order_id"] = fact["order_id"].astype("int32")
    fact["item_id"] = fact["item_id"].astype("int32")
    fact["customer_id"] = fact["customer_id"].astype("int32")
    fact["product_id"] = fact["product_id"].astype("int32")
    fact["delivery_method_id"] = fact["delivery_method_id"].astype("int32")
    fact["quantity"] = fact["quantity"].astype("int32")
    fact["unit_price"] = pd.to_numeric(fact["unit_price"], errors="coerce").astype("float64")
    fact["line_amount"] = pd.to_numeric(fact["line_amount"], errors="coerce").astype("float64")

    return fact


def transform_all(extracted: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Transform raw data into dimensional model."""
    customers = drop_duplicate_rows(extracted["customers"], "customers")
    categories = drop_duplicate_rows(extracted["categories"], "categories")
    products = drop_duplicate_rows(extracted["products"], "products")
    delivery_methods = drop_duplicate_rows(extracted["delivery_methods"], "delivery_methods")

    dim_customers = create_dim_customers(customers)
    dim_categories = create_dim_categories(categories)
    dim_products = create_dim_products(products, dim_categories)
    dim_delivery_methods = create_dim_delivery_methods(delivery_methods)

    flattened_orders = flatten_orders(extracted["orders"])
    flattened_orders = drop_duplicate_rows(flattened_orders, "flattened_orders")
    dim_date = create_dim_date(flattened_orders["order_date"])
    fact_order_items = create_fact_order_items(flattened_orders, dim_products, dim_delivery_methods)

    tables = {
        "dim_customers": dim_customers,
        "dim_categories": dim_categories,
        "dim_products": dim_products,
        "dim_delivery_methods": dim_delivery_methods,
        "dim_date": dim_date,
        "fact_order_items": fact_order_items,
    }
    dimension_count = len(tables) - 1
    print(f"  Created {dimension_count} dimensions + 1 fact table ({len(fact_order_items)} items total)")

    return tables
