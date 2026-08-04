from typing import Dict

import pandas as pd

from validation import ValidationError


def create_agg_sales_by_category(
    fact_df: pd.DataFrame,
    dim_products: pd.DataFrame,
    dim_categories: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate fact_order_items up to one row per category.

    Columns: category_id, category_name, total_quantity, total_revenue,
    line_item_count, distinct_order_count.
    """
    merged = fact_df.merge(
        dim_products[["product_id", "category_id"]],
        on="product_id",
        how="left",
    )
    merged = merged.merge(
        dim_categories[["category_id", "category_name"]],
        on="category_id",
        how="left",
    )

    agg = (
        merged.groupby(["category_id", "category_name"], dropna=False)
        .agg(
            total_quantity=("quantity", "sum"),
            total_revenue=("line_amount", "sum"),
            line_item_count=("item_id", "count"),
            distinct_order_count=("order_id", "nunique"),
        )
        .reset_index()
        .sort_values("category_id")
        .reset_index(drop=True)
    )
    agg["total_revenue"] = agg["total_revenue"].round(2)
    return agg


def validate_agg_sales_by_category(agg_df: pd.DataFrame, fact_df: pd.DataFrame) -> None:
    """Reconciliation check: total_revenue across all categories must equal the
    fact table's total line_amount. Catches join/grouping bugs (e.g. a dropped
    or duplicated row) that wouldn't be caught by any single-table check."""
    agg_total = float(agg_df["total_revenue"].sum())
    fact_total = float(fact_df["line_amount"].sum())
    # Each category's total_revenue is rounded to cents for display, so allow a small
    # tolerance that scales with the number of categories being summed.
    tolerance = 0.01 * max(1, len(agg_df))
    if abs(agg_total - fact_total) > tolerance:
        raise ValidationError(
            f"agg_sales_by_category: total_revenue ({agg_total}) does not reconcile "
            f"with fact_order_items.line_amount sum ({fact_total})"
        )


def aggregate_all(tables: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Build all aggregate tables from the validated star schema."""
    agg_sales_by_category = create_agg_sales_by_category(
        tables["fact_order_items"], tables["dim_products"], tables["dim_categories"]
    )
    validate_agg_sales_by_category(agg_sales_by_category, tables["fact_order_items"])

    print(f"  Created agg_sales_by_category ({len(agg_sales_by_category)} rows)")

    return {
        "agg_sales_by_category": agg_sales_by_category,
    }
