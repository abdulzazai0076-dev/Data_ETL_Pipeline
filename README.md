# Retail Data Warehouse ETL

Transforms raw operational data (CSV + JSON) into a dimensional data model. Outputs 6 CSV tables.

## Data Model

**Star Schema** with item-level fact table:

- **fact_order_items** — One row per order item (10 rows)  
  - Composite key: (order_id, item_id)
  - Measures: quantity, unit_price, line_amount (calculated)

- **Dimensions** (31 rows total):
  - dim_customers (4 rows)
  - dim_products (8 rows)
  - dim_categories (3 rows)
  - dim_delivery_methods (2 rows)
  - dim_date (4 rows)

## Pipeline

1. **Extract** — Load CSVs (customers, products, categories, delivery_methods) + JSON orders
2. **Transform** — Flatten nested items, create dimensions, join to fact, calculate line_amount
3. **Validate** — Check key uniqueness, referential integrity, business rules
4. **Load** — Write 6 CSVs to `output/`

## How to Run

```bash
python src/main.py                           # Basic run
python src/main.py --source ./data --output ./out  # Custom paths
python src/main.py --skip-validation         # Skip validation
```

## Validation Rules

`validation.py` runs a full data-quality sweep before anything is written to `output/`.
Every check runs on every call (it does not stop at the first problem), so a single
failed run reports **all** issues found, not just the first one.

| Check | Applies to |
|---|---|
| Table not empty | All 6 tables |
| Required columns present | All 6 tables |
| Primary key present & unique | Each dimension (e.g. `customer_id`, `product_id`) |
| Composite key present & unique | `fact_order_items` (`order_id` + `item_id`) |
| No nulls in keys / foreign keys | `fact_order_items` keys + FK columns |
| No nulls in measures | `quantity`, `unit_price`, `line_amount` |
| Measures are numeric | `quantity`, `unit_price`, `line_amount` |
| Business-rule bounds | `quantity` ≥ 1, `unit_price`/`line_amount`/`price` ≥ 0, `shipping_days` ≥ 0 |
| `line_amount = quantity × unit_price` | `fact_order_items` (also flags rows where the check itself can't run due to missing/non-numeric inputs) |
| Date format is `YYYY-MM-DD` | `fact_order_items.order_date`, `dim_date.date` |
| Foreign keys resolve | `fact_order_items` → `dim_customers` / `dim_products` / `dim_delivery_methods` |
| Foreign keys resolve | `dim_products.category_id` → `dim_categories.category_id` |

If any check fails, `validate_all` raises a `ValidationError` listing every issue found,
e.g.:

```
3 validation issue(s) found:
    - fact_order_items: 1 null value(s) found in 'product_id'
    - fact_order_items.product_id -> dim_products.product_id: invalid foreign key value(s) [9999]
    - dim_customers: 1 row(s) with duplicate 'customer_id' values
```

## Tests

```bash
PYTHONPATH=src python -m pytest tests/
```

23 tests covering:

- **`test_core.py`** — Order flattening (nested items → item-level rows), line amount
  calculation, dimension creation
- **`test_pipeline.py`** — Full pipeline integration (extract → transform → validate → load)
- **`test_validation.py`** — Validation edge cases: duplicate/null keys, duplicate
  composite keys, null and orphaned foreign keys (including dimension-to-dimension),
  negative/zero quantities and prices, mismatched or unverifiable `line_amount`,
  non-numeric measures, bad date formats, and multiple simultaneous failures being
  reported together

## Assumptions

- Grain: one row per order item (not per order)
- line_amount = quantity × unit_price
- Dates: `YYYY-MM-DD` strings (enforced by validation)
- Quantity must be at least 1; prices and amounts cannot be negative
- Foreign keys exist in dimensions (customers, products, delivery_methods, categories)
- No duplicate primary keys in dimensions, no duplicate (order_id, item_id) in the fact table

## Output

```
output/
├── dim_categories.csv           (3 rows)
├── dim_customers.csv            (4 rows)
├── dim_date.csv                 (4 rows)
├── dim_delivery_methods.csv     (2 rows)
├── dim_products.csv             (8 rows)
└── fact_order_items.csv         (10 rows)
```

## Design Rationale

- **Item-level grain**: Enables product-level analytics  
- **Denormalize category into products**: Eliminates extra joins in queries  
- **Calculate line_amount**: Ensures consistency and auditability  
- **CSV output**: Simple, portable, no external dependencies  

## Structure

```
src/
  main.py       # CLI entry, orchestrates pipeline
  extract.py    # Load CSV + JSON
  transform.py  # Create dimensional model
  validation.py # Data quality checks
  load.py       # Write CSVs

tests/
  test_core.py       # Unit tests (flatten, calculations, dimensions)
  test_pipeline.py   # Integration test (full pipeline)
  test_validation.py # Validation edge-case tests
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| FileNotFoundError | Run from project root or use `--source` flag |
| ValidationError | Check source data for nulls in keys, mismatched FKs, negative quantities/prices, or bad date formats |
| ImportError: pandas | `pip install -r requirements.txt` |
| ModuleNotFoundError in tests | Run from project root: `PYTHONPATH=src pytest tests/` |

## References

- **Kimball Dimensional Modeling:** "The Data Warehouse Toolkit" by Ralph Kimball & Margy Ross
- **Pandas Documentation:** https://pandas.pydata.org/docs/
- **Pytest Guide:** https://docs.pytest.org/
