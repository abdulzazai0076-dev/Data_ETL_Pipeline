"""Tests for validation.py - covers happy path plus data-quality edge cases."""

import pandas as pd
import pytest
from validation import ValidationError, validate_all


def make_valid_tables():
    """A minimal, fully-valid set of tables that satisfies every check."""
    dim_customers = pd.DataFrame({
        "customer_id": [1, 2],
        "first_name": ["Ada", "Grace"],
        "last_name": ["Lovelace", "Hopper"],
        "city": ["London", "New York"],
    })
    dim_categories = pd.DataFrame({
        "category_id": [1],
        "category_name": ["Widgets"],
    })
    dim_products = pd.DataFrame({
        "product_id": [10, 11],
        "product_name": ["Widget", "Gadget"],
        "manufacturer": ["Acme", "Acme"],
        "price": [9.99, 19.99],
        "category_id": [1, 1],
    })
    dim_delivery_methods = pd.DataFrame({
        "delivery_method_id": [100],
        "method_name": ["Standard"],
        "courier_name": ["FedEx"],
        "shipping_days": [3],
    })
    dim_date = pd.DataFrame({
        "date_key": [20210101],
        "date": ["2021-01-01"],
        "year": [2021],
        "month": [1],
        "day": [1],
        "day_of_week": ["Friday"],
    })
    fact_order_items = pd.DataFrame({
        "order_id": [1, 1],
        "item_id": [10, 11],
        "customer_id": [1, 1],
        "product_id": [10, 11],
        "delivery_method_id": [100, 100],
        "order_date": ["2021-01-01", "2021-01-01"],
        "quantity": [2, 1],
        "unit_price": [9.99, 19.99],
        "line_amount": [19.98, 19.99],
        "special_instructions": [None, None],
        "source": ["pos", "pos"],
        "processed_at": ["2021-01-02T00:00:00Z", "2021-01-02T00:00:00Z"],
    })
    return {
        "dim_customers": dim_customers,
        "dim_categories": dim_categories,
        "dim_products": dim_products,
        "dim_delivery_methods": dim_delivery_methods,
        "dim_date": dim_date,
        "fact_order_items": fact_order_items,
    }


def test_valid_data_passes():
    """A well-formed dataset should not raise."""
    tables = make_valid_tables()
    validate_all(tables)  # should not raise


def test_empty_table_raises():
    tables = make_valid_tables()
    tables["dim_customers"] = tables["dim_customers"].iloc[0:0]
    with pytest.raises(ValidationError, match="table is empty"):
        validate_all(tables)


def test_missing_column_in_dimension_raises():
    tables = make_valid_tables()
    tables["dim_customers"] = tables["dim_customers"].drop(columns=["city"])
    with pytest.raises(ValidationError, match="missing column"):
        validate_all(tables)


def test_duplicate_dimension_key_raises():
    tables = make_valid_tables()
    dupe_row = tables["dim_customers"].iloc[[0]]
    tables["dim_customers"] = pd.concat([tables["dim_customers"], dupe_row], ignore_index=True)
    with pytest.raises(ValidationError, match="duplicate 'customer_id'"):
        validate_all(tables)


def test_null_dimension_key_raises():
    tables = make_valid_tables()
    tables["dim_customers"].loc[0, "customer_id"] = None
    with pytest.raises(ValidationError, match="null value.*customer_id"):
        validate_all(tables)


def test_duplicate_composite_key_in_fact_raises():
    """order_id + item_id must be unique even if no single column repeats."""
    tables = make_valid_tables()
    dupe_row = tables["fact_order_items"].iloc[[0]]
    tables["fact_order_items"] = pd.concat([tables["fact_order_items"], dupe_row], ignore_index=True)
    with pytest.raises(ValidationError, match="duplicate composite key"):
        validate_all(tables)


def test_null_foreign_key_in_fact_raises():
    """A null product_id must be flagged, not silently skipped by the FK check."""
    tables = make_valid_tables()
    tables["fact_order_items"].loc[0, "product_id"] = None
    with pytest.raises(ValidationError, match="null value.*product_id"):
        validate_all(tables)


def test_orphan_foreign_key_raises():
    tables = make_valid_tables()
    tables["fact_order_items"].loc[0, "product_id"] = 9999
    with pytest.raises(ValidationError, match="invalid foreign key value"):
        validate_all(tables)


def test_orphan_dimension_to_dimension_fk_raises():
    """dim_products.category_id must point to a real dim_categories row."""
    tables = make_valid_tables()
    tables["dim_products"].loc[0, "category_id"] = 9999
    with pytest.raises(ValidationError, match="dim_products.category_id"):
        validate_all(tables)


def test_negative_quantity_raises():
    tables = make_valid_tables()
    tables["fact_order_items"].loc[0, "quantity"] = -1
    with pytest.raises(ValidationError, match="quantity.*below the allowed minimum"):
        validate_all(tables)


def test_zero_quantity_raises():
    """Quantity must be at least 1 - a zero-quantity line item makes no sense."""
    tables = make_valid_tables()
    tables["fact_order_items"].loc[0, "quantity"] = 0
    with pytest.raises(ValidationError, match="quantity.*below the allowed minimum"):
        validate_all(tables)


def test_negative_unit_price_raises():
    tables = make_valid_tables()
    tables["fact_order_items"].loc[0, "unit_price"] = -5
    tables["fact_order_items"].loc[0, "line_amount"] = -10
    with pytest.raises(ValidationError, match="unit_price.*below the allowed minimum"):
        validate_all(tables)


def test_negative_product_price_raises():
    tables = make_valid_tables()
    tables["dim_products"].loc[0, "price"] = -1
    with pytest.raises(ValidationError, match="dim_products.*price.*below the allowed minimum"):
        validate_all(tables)


def test_negative_shipping_days_raises():
    tables = make_valid_tables()
    tables["dim_delivery_methods"].loc[0, "shipping_days"] = -1
    with pytest.raises(ValidationError, match="dim_delivery_methods.*shipping_days.*below the allowed minimum"):
        validate_all(tables)


def test_line_amount_mismatch_raises():
    tables = make_valid_tables()
    tables["fact_order_items"].loc[0, "line_amount"] = 999.0
    with pytest.raises(ValidationError, match="line_amount != quantity \\* unit_price"):
        validate_all(tables)


def test_null_unit_price_does_not_silently_pass():
    """A null unit_price must be caught explicitly, not hidden by NaN arithmetic
    in the line_amount check."""
    tables = make_valid_tables()
    tables["fact_order_items"].loc[0, "unit_price"] = None
    with pytest.raises(ValidationError):
        validate_all(tables)


def test_non_numeric_measure_raises():
    tables = make_valid_tables()
    tables["fact_order_items"]["quantity"] = tables["fact_order_items"]["quantity"].astype(object)
    tables["fact_order_items"].loc[0, "quantity"] = "two"
    with pytest.raises(ValidationError, match="not numeric"):
        validate_all(tables)


def test_invalid_date_format_raises():
    tables = make_valid_tables()
    tables["fact_order_items"].loc[0, "order_date"] = "01/01/2021"
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        validate_all(tables)


def test_multiple_errors_reported_together():
    """Robustness: a single run should surface every issue at once, not just the first."""
    tables = make_valid_tables()
    tables["fact_order_items"].loc[0, "quantity"] = -1
    tables["fact_order_items"].loc[1, "product_id"] = 9999
    tables["dim_customers"].loc[0, "customer_id"] = tables["dim_customers"].loc[1, "customer_id"]

    with pytest.raises(ValidationError) as exc_info:
        validate_all(tables)

    message = str(exc_info.value)
    assert "quantity" in message
    assert "invalid foreign key" in message
    assert "duplicate 'customer_id'" in message
