"""Test core transformations and calculations."""

import pandas as pd
from transform import (
    create_dim_customers,
    create_dim_products,
    create_fact_order_items,
    drop_duplicate_rows,
    flatten_orders,
)


def test_flatten_orders():
    """Test order flattening converts nested items to item-level rows."""
    orders_df = pd.DataFrame([{
        "order_id": 1,
        "customer_id": 100,
        "delivery_method_id": 5,
        "order_date": "2021-01-01",
        "items": [
            {"item_id": 10, "product_id": 20, "product_name": "A", "quantity": 2},
            {"item_id": 11, "product_id": 21, "product_name": "B", "quantity": 1},
        ],
        "metadata": {"source": "pos", "processed_at": "2021-01-02T10:00:00Z"},
    }])

    result = flatten_orders(orders_df)

    assert len(result) == 2, "Should have 2 items"
    assert result.iloc[0]["item_id"] == 10
    assert result.iloc[1]["item_id"] == 11


def test_line_amount_calculation():
    """Test fact table calculates line_amount = quantity * unit_price."""
    flattened = pd.DataFrame({
        "order_id": [1, 1],
        "item_id": [10, 11],
        "customer_id": [100, 100],
        "delivery_method_id": [5, 5],
        "order_date": ["2021-01-01", "2021-01-01"],
        "product_id": [20, 21],
        "quantity": [2, 1],
        "special_instructions": [None, None],
        "source": ["pos", "pos"],
        "processed_at": ["2021-01-02T10:00:00Z", "2021-01-02T10:00:00Z"],
    })

    products = pd.DataFrame({
        "product_id": [20, 21],
        "product_name": ["A", "B"],
        "manufacturer": ["X", "Y"],
        "price": [39.99, 99.99],
        "category_id": [1, 2],
    })

    delivery_methods = pd.DataFrame({
        "delivery_method_id": [5],
        "method_name": ["Standard"],
        "courier_name": ["FedEx"],
        "shipping_days": [3],
    })

    fact = create_fact_order_items(flattened, products, delivery_methods)

    assert fact.iloc[0]["line_amount"] == 79.98, "2 * 39.99 = 79.98"
    assert fact.iloc[1]["line_amount"] == 99.99, "1 * 99.99 = 99.99"


def test_products_dimension():
    """Test product dimension creates correctly, enriched with category_name."""
    products_df = pd.DataFrame({
        "id": [1, 2],
        "product_name": ["Widget", "Gadget"],
        "manufacturer": ["MfgA", "MfgB"],
        "price": ["19.99", "29.99"],
        "category_id": [10, 20],
    })
    dim_categories = pd.DataFrame({
        "category_id": [10, 20],
        "category_name": ["Hardware", "Electronics"],
    })

    result = create_dim_products(products_df, dim_categories)

    assert len(result) == 2
    assert set(result.columns) == {
        "product_id", "product_name", "manufacturer", "price", "category_id", "category_name",
    }
    assert result.iloc[0]["product_id"] == 1
    assert result.iloc[0]["product_name"] == "Widget"
    assert result.iloc[0]["category_name"] == "Hardware"
    assert result.iloc[1]["category_name"] == "Electronics"


def test_customers_dimension_full_name():
    """Test customers dimension is enriched with a derived full_name."""
    customers_df = pd.DataFrame({
        "id": [1, 2],
        "first_name": ["Ada", "Grace"],
        "last_name": ["Lovelace", "Hopper"],
        "city": ["London", "New York"],
    })

    result = create_dim_customers(customers_df)

    assert result.iloc[0]["full_name"] == "Ada Lovelace"
    assert result.iloc[1]["full_name"] == "Grace Hopper"


def test_drop_duplicate_rows_removes_exact_duplicates():
    """Exact duplicate rows (every column identical) should be removed, keeping the first."""
    df = pd.DataFrame({
        "id": [1, 2, 1],
        "name": ["A", "B", "A"],
    })

    result = drop_duplicate_rows(df, "test_table")

    assert len(result) == 2
    assert list(result["id"]) == [1, 2]


def test_drop_duplicate_rows_keeps_same_key_different_value_rows():
    """Rows that share a key but differ in other columns are NOT deduped - that's a
    real data conflict that validation.py should catch, not silently resolve here."""
    df = pd.DataFrame({
        "id": [1, 1],
        "name": ["A", "B"],
    })

    result = drop_duplicate_rows(df, "test_table")

    assert len(result) == 2
