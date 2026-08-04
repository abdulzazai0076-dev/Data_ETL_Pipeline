"""Tests for aggregate.py."""

import pandas as pd
import pytest
from aggregate import aggregate_all, create_agg_sales_by_category, validate_agg_sales_by_category
from validation import ValidationError


def make_fact_and_dims():
    dim_categories = pd.DataFrame({
        "category_id": [1, 2],
        "category_name": ["Televisions", "Audio"],
    })
    dim_products = pd.DataFrame({
        "product_id": [10, 11, 20],
        "product_name": ["TV A", "TV B", "Speaker"],
        "manufacturer": ["X", "Y", "Z"],
        "price": [100.0, 200.0, 50.0],
        "category_id": [1, 1, 2],
        "category_name": ["Televisions", "Televisions", "Audio"],
    })
    fact_order_items = pd.DataFrame({
        "order_id": [1, 1, 2],
        "item_id": [1, 2, 1],
        "customer_id": [1, 1, 2],
        "product_id": [10, 11, 20],
        "delivery_method_id": [100, 100, 100],
        "order_date": ["2021-01-01", "2021-01-01", "2021-01-02"],
        "quantity": [1, 2, 3],
        "unit_price": [100.0, 200.0, 50.0],
        "line_amount": [100.0, 400.0, 150.0],
        "special_instructions": [None, None, None],
        "source": ["pos", "pos", "pos"],
        "processed_at": ["2021-01-01T00:00:00Z", "2021-01-01T00:00:00Z", "2021-01-02T00:00:00Z"],
    })
    return fact_order_items, dim_products, dim_categories


def test_create_agg_sales_by_category_totals():
    fact, dim_products, dim_categories = make_fact_and_dims()

    agg = create_agg_sales_by_category(fact, dim_products, dim_categories)

    assert len(agg) == 2

    tv_row = agg[agg["category_name"] == "Televisions"].iloc[0]
    assert tv_row["total_quantity"] == 3  # 1 + 2
    assert tv_row["total_revenue"] == 500.0  # 100 + 400
    assert tv_row["line_item_count"] == 2
    assert tv_row["distinct_order_count"] == 1  # both TV items are on order_id 1

    audio_row = agg[agg["category_name"] == "Audio"].iloc[0]
    assert audio_row["total_quantity"] == 3
    assert audio_row["total_revenue"] == 150.0
    assert audio_row["line_item_count"] == 1
    assert audio_row["distinct_order_count"] == 1


def test_agg_sales_by_category_reconciles_with_fact_table():
    """The sum of total_revenue across categories must equal the fact table total."""
    fact, dim_products, dim_categories = make_fact_and_dims()

    agg = create_agg_sales_by_category(fact, dim_products, dim_categories)

    assert agg["total_revenue"].sum() == pytest.approx(fact["line_amount"].sum())
    validate_agg_sales_by_category(agg, fact)  # should not raise


def test_validate_agg_sales_by_category_raises_on_mismatch():
    """If the aggregate total doesn't reconcile with the fact table, it's a real bug -
    e.g. a dropped row from a bad join - and must be caught, not silently shipped."""
    fact, dim_products, dim_categories = make_fact_and_dims()
    agg = create_agg_sales_by_category(fact, dim_products, dim_categories)

    agg.loc[0, "total_revenue"] = agg.loc[0, "total_revenue"] + 1000.0

    with pytest.raises(ValidationError, match="does not reconcile"):
        validate_agg_sales_by_category(agg, fact)


def test_aggregate_all_returns_expected_table():
    fact, dim_products, dim_categories = make_fact_and_dims()
    tables = {
        "fact_order_items": fact,
        "dim_products": dim_products,
        "dim_categories": dim_categories,
    }

    result = aggregate_all(tables)

    assert set(result.keys()) == {"agg_sales_by_category"}
    assert len(result["agg_sales_by_category"]) == 2
