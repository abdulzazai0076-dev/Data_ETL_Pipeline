from typing import Dict

import pandas as pd


class ValidationError(Exception):
    pass


# Schema definitions
DIMENSIONS = {
    "dim_customers": ["customer_id", "first_name", "last_name", "city"],
    "dim_categories": ["category_id", "category_name"],
    "dim_products": ["product_id", "product_name", "manufacturer", "price", "category_id"],
    "dim_delivery_methods": ["delivery_method_id", "method_name", "courier_name", "shipping_days"],
    "dim_date": ["date_key", "date", "year", "month", "day", "day_of_week"],
}

FACT_SCHEMA = {
    "columns": [
        "order_id", "item_id", "customer_id", "product_id", "delivery_method_id",
        "order_date", "quantity", "unit_price", "line_amount",
        "special_instructions", "source", "processed_at",
    ],
    "keys": ["order_id", "item_id"],
    "measures": ["quantity", "unit_price", "line_amount"],
}

FK_CHECKS = [
    ("fact_order_items", "customer_id", "dim_customers", "customer_id"),
    ("fact_order_items", "product_id", "dim_products", "product_id"),
    ("fact_order_items", "delivery_method_id", "dim_delivery_methods", "delivery_method_id"),
]


def validate_dimension_uniqueness(df: pd.DataFrame, key_column: str, table_name: str):
    """Check no duplicate keys."""
    if key_column not in df.columns:
        raise ValidationError(f"{table_name}: Missing column '{key_column}'")
    duplicates = df[df.duplicated(subset=[key_column], keep=False)]
    if len(duplicates) > 0:
        raise ValidationError(f"{table_name}: Duplicate keys found in '{key_column}'")


def validate_no_nulls_in_keys(df: pd.DataFrame, key_columns: list, table_name: str):
    """Check no nulls in keys."""
    for col in key_columns:
        if col in df.columns and df[col].isna().sum() > 0:
            raise ValidationError(f"{table_name}: Null values found in '{col}'")


def validate_foreign_key(fact_df: pd.DataFrame, fk_col: str, dim_df: pd.DataFrame, 
                         dim_key: str, relation_name: str):
    """Check referential integrity."""
    valid_keys = set(dim_df[dim_key].unique())
    fact_keys = fact_df[fact_df[fk_col].notna()][fk_col].unique()
    orphans = set(fact_keys) - valid_keys
    if orphans:
        raise ValidationError(f"{relation_name}: Invalid foreign key values {orphans}")


def validate_measures_numeric(df: pd.DataFrame, measure_cols: list, table_name: str):
    """Check measures are numeric."""
    for col in measure_cols:
        if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
            raise ValidationError(f"{table_name}: '{col}' is not numeric")


def validate_fact_calculated_fields(fact_df: pd.DataFrame):
    """Check line_amount = quantity * unit_price."""
    expected = fact_df["quantity"] * fact_df["unit_price"]
    tolerance = 0.01
    mismatches = ((fact_df["line_amount"] - expected).abs() > tolerance).sum()
    if mismatches > 0:
        raise ValidationError(f"fact_order_items: {mismatches} line_amount mismatches")


def validate_all(tables: Dict[str, pd.DataFrame]):
    """Run all validation checks."""
    print("  Validating data quality...")
    
    try:
        # Check no empty tables
        for name, df in tables.items():
            if len(df) == 0:
                raise ValidationError(f"{name}: Table is empty")

        # Validate dimensions
        for table_name, columns in DIMENSIONS.items():
            df = tables[table_name]
            pk_col = columns[0]
            
            # Check required columns
            missing = set(columns) - set(df.columns)
            if missing:
                raise ValidationError(f"{table_name}: Missing columns {missing}")
            
            # Check unique keys
            validate_dimension_uniqueness(df, pk_col, table_name)
            # Check no nulls in keys
            validate_no_nulls_in_keys(df, [pk_col], table_name)

        # Validate fact table
        fact = tables["fact_order_items"]
        missing = set(FACT_SCHEMA["columns"]) - set(fact.columns)
        if missing:
            raise ValidationError(f"fact_order_items: Missing columns {missing}")
        
        validate_no_nulls_in_keys(fact, FACT_SCHEMA["keys"], "fact_order_items")
        validate_measures_numeric(fact, FACT_SCHEMA["measures"], "fact_order_items")
        validate_fact_calculated_fields(fact)

        # Validate foreign keys
        for fact_name, fk_col, dim_name, dim_key in FK_CHECKS:
            validate_foreign_key(tables[fact_name], fk_col, tables[dim_name], dim_key,
                               f"{fact_name}.{fk_col} -> {dim_name}.{dim_key}")

        print("  ✓ All validations passed")
        
    except ValidationError as e:
        print(f"  ✗ Validation failed: {e}")
        raise
