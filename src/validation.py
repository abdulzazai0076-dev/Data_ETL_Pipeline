import re
from typing import Dict, List

import pandas as pd


class ValidationError(Exception):
    """Raised when one or more data quality checks fail."""
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

# fact table -> dimension foreign key relationships
FK_CHECKS = [
    ("fact_order_items", "customer_id", "dim_customers", "customer_id"),
    ("fact_order_items", "product_id", "dim_products", "product_id"),
    ("fact_order_items", "delivery_method_id", "dim_delivery_methods", "delivery_method_id"),
]

# dimension -> dimension foreign key relationships
DIM_FK_CHECKS = [
    ("dim_products", "category_id", "dim_categories", "category_id"),
]

# Business-rule lower bounds (inclusive) for fact table measures
FACT_MEASURE_RULES = {
    "quantity": 1,      # must order at least 1 unit
    "unit_price": 0,    # price cannot be negative
    "line_amount": 0,   # amount cannot be negative
}

# Business-rule lower bounds (inclusive) for dimension attributes
DIMENSION_BOUNDS = {
    "dim_products": {"price": 0},
    "dim_delivery_methods": {"shipping_days": 0},
}

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_FORMAT_COLUMNS = [
    ("fact_order_items", "order_date"),
    ("dim_date", "date"),
]


def validate_no_nulls(df: pd.DataFrame, columns: List[str], table_name: str) -> List[str]:
    """Check that none of the given columns contain nulls. Returns a list of error messages."""
    errors = []
    for col in columns:
        if col not in df.columns:
            continue
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            errors.append(f"{table_name}: {null_count} null value(s) found in '{col}'")
    return errors


def validate_dimension_uniqueness(df: pd.DataFrame, key_column: str, table_name: str) -> List[str]:
    """Check no duplicate primary keys in a dimension table."""
    if key_column not in df.columns:
        return [f"{table_name}: missing column '{key_column}'"]
    duplicate_count = int(df.duplicated(subset=[key_column], keep=False).sum())
    if duplicate_count > 0:
        return [f"{table_name}: {duplicate_count} row(s) with duplicate '{key_column}' values"]
    return []


def validate_composite_key_uniqueness(df: pd.DataFrame, key_columns: List[str], table_name: str) -> List[str]:
    """Check no duplicate rows for a composite key (e.g. order_id + item_id)."""
    missing = [c for c in key_columns if c not in df.columns]
    if missing:
        return [f"{table_name}: missing key column(s) {missing}"]
    duplicate_count = int(df.duplicated(subset=key_columns, keep=False).sum())
    if duplicate_count > 0:
        return [f"{table_name}: {duplicate_count} row(s) with duplicate composite key {key_columns}"]
    return []


def validate_foreign_key(source_df: pd.DataFrame, fk_col: str, dim_df: pd.DataFrame,
                          dim_key: str, relation_name: str) -> List[str]:
    """Check referential integrity: every non-null fk value exists in the dimension.

    Null fk values are intentionally not flagged here - use validate_no_nulls
    separately so null-key and orphan-key issues are reported distinctly.
    """
    if fk_col not in source_df.columns or dim_key not in dim_df.columns:
        return []
    valid_keys = set(dim_df[dim_key].dropna().unique())
    fact_keys = source_df[source_df[fk_col].notna()][fk_col].unique()
    orphans = set(fact_keys) - valid_keys
    if orphans:
        return [f"{relation_name}: invalid foreign key value(s) {sorted(orphans)}"]
    return []


def validate_measures_numeric(df: pd.DataFrame, measure_cols: List[str], table_name: str) -> List[str]:
    """Check measures have a numeric dtype."""
    errors = []
    for col in measure_cols:
        if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
            errors.append(f"{table_name}: '{col}' is not numeric")
    return errors


def validate_measure_bounds(df: pd.DataFrame, rules: Dict[str, float], table_name: str) -> List[str]:
    """Check numeric columns respect an inclusive lower bound (e.g. no negative prices)."""
    errors = []
    for col, min_value in rules.items():
        if col not in df.columns:
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        violation_count = int((numeric < min_value).sum())
        if violation_count > 0:
            errors.append(
                f"{table_name}: {violation_count} value(s) in '{col}' below the allowed minimum ({min_value})"
            )
    return errors


def validate_fact_calculated_fields(fact_df: pd.DataFrame) -> List[str]:
    """Check line_amount = quantity * unit_price, flagging both mismatches and
    missing/non-numeric inputs that would otherwise hide a bad calculation."""
    required = {"quantity", "unit_price", "line_amount"}
    if not required.issubset(fact_df.columns):
        return []

    quantity = pd.to_numeric(fact_df["quantity"], errors="coerce")
    unit_price = pd.to_numeric(fact_df["unit_price"], errors="coerce")
    line_amount = pd.to_numeric(fact_df["line_amount"], errors="coerce")

    expected = quantity * unit_price
    diff = line_amount - expected

    unresolvable = int(diff.isna().sum())
    errors = []
    if unresolvable > 0:
        errors.append(
            f"fact_order_items: {unresolvable} row(s) have missing/non-numeric quantity, "
            f"unit_price, or line_amount so line_amount could not be verified"
        )

    tolerance = 0.01
    mismatch_count = int(((diff.abs() > tolerance) & diff.notna()).sum())
    if mismatch_count > 0:
        errors.append(f"fact_order_items: {mismatch_count} row(s) where line_amount != quantity * unit_price")

    return errors


def validate_date_format(df: pd.DataFrame, column: str, table_name: str) -> List[str]:
    """Check date-like column values match YYYY-MM-DD (per project assumptions)."""
    if column not in df.columns:
        return []
    values = df[column].dropna().astype(str)
    if len(values) == 0:
        return []
    bad_count = int((~values.str.match(DATE_PATTERN)).sum())
    if bad_count > 0:
        return [f"{table_name}: {bad_count} value(s) in '{column}' are not in YYYY-MM-DD format"]
    return []


def validate_all(tables: Dict[str, pd.DataFrame]) -> None:
    """Run all data quality checks and raise ValidationError listing every issue found.

    Unlike a fail-fast approach, all checks run regardless of earlier failures so a
    single validation run surfaces the full picture of data quality problems.
    """
    print("  Validating data quality...")
    errors: List[str] = []

    required_tables = list(DIMENSIONS.keys()) + ["fact_order_items"]
    missing_tables = [t for t in required_tables if t not in tables]
    if missing_tables:
        raise ValidationError(f"Missing required table(s): {missing_tables}")

    for name, df in tables.items():
        if df is None or len(df) == 0:
            errors.append(f"{name}: table is empty")

    # Dimension checks
    for table_name, columns in DIMENSIONS.items():
        df = tables[table_name]
        if len(df) == 0:
            continue  # already flagged as empty above

        missing_cols = sorted(set(columns) - set(df.columns))
        if missing_cols:
            errors.append(f"{table_name}: missing column(s) {missing_cols}")
            continue  # remaining checks depend on these columns

        pk_col = columns[0]
        errors += validate_no_nulls(df, [pk_col], table_name)
        errors += validate_dimension_uniqueness(df, pk_col, table_name)

    for table_name, column in DATE_FORMAT_COLUMNS:
        if table_name == "dim_date" and len(tables.get("dim_date", [])) > 0:
            errors += validate_date_format(tables["dim_date"], column, table_name)

    for table_name, rules in DIMENSION_BOUNDS.items():
        df = tables.get(table_name)
        if df is not None and len(df) > 0:
            errors += validate_measure_bounds(df, rules, table_name)

    # dimension -> dimension foreign keys (e.g. dim_products.category_id)
    for src_name, fk_col, dim_name, dim_key in DIM_FK_CHECKS:
        src_df = tables.get(src_name)
        dim_df = tables.get(dim_name)
        if src_df is not None and dim_df is not None and len(src_df) > 0:
            errors += validate_no_nulls(src_df, [fk_col], src_name)
            errors += validate_foreign_key(src_df, fk_col, dim_df, dim_key, f"{src_name}.{fk_col} -> {dim_name}.{dim_key}")

    # Fact table checks
    fact = tables["fact_order_items"]
    if len(fact) > 0:
        missing_cols = sorted(set(FACT_SCHEMA["columns"]) - set(fact.columns))
        if missing_cols:
            errors.append(f"fact_order_items: missing column(s) {missing_cols}")
        else:
            fk_cols = [fk_col for _, fk_col, _, _ in FK_CHECKS]
            not_null_cols = FACT_SCHEMA["keys"] + fk_cols
            errors += validate_no_nulls(fact, not_null_cols, "fact_order_items")
            errors += validate_composite_key_uniqueness(fact, FACT_SCHEMA["keys"], "fact_order_items")
            errors += validate_measures_numeric(fact, FACT_SCHEMA["measures"], "fact_order_items")
            errors += validate_no_nulls(fact, FACT_SCHEMA["measures"], "fact_order_items")
            errors += validate_measure_bounds(fact, FACT_MEASURE_RULES, "fact_order_items")
            errors += validate_fact_calculated_fields(fact)
            errors += validate_date_format(fact, "order_date", "fact_order_items")

            # fact -> dimension foreign keys
            for fact_name, fk_col, dim_name, dim_key in FK_CHECKS:
                dim_df = tables.get(dim_name)
                if dim_df is not None and len(dim_df) > 0:
                    errors += validate_foreign_key(
                        fact, fk_col, dim_df, dim_key, f"{fact_name}.{fk_col} -> {dim_name}.{dim_key}"
                    )

    if errors:
        formatted = "\n".join(f"    - {e}" for e in errors)
        print(f"  \u2717 Validation failed with {len(errors)} issue(s):\n{formatted}")
        raise ValidationError(f"{len(errors)} validation issue(s) found:\n{formatted}")

    print("  \u2713 All validations passed")
