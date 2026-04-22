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

## Tests

```bash
PYTHONPATH=src python -m pytest tests/
```

4 tests covering:
- Order flattening (nested items → item-level rows)
- Line amount calculation (quantity × unit_price)
- Dimension creation
- Full pipeline integration

## Assumptions

- Grain: one row per order item (not per order)
- line_amount = quantity × unit_price
- Dates: YYYY-MM-DD strings
- Foreign keys exist in dimensions (customers, products, delivery_methods)
- No duplicate primary keys in dimensions

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
  test_core.py     # Unit tests
  test_pipeline.py # Integration test
```
| `transform.py` | Create dimensional model (flatten, join, calculate) |
| `load.py` | Write CSV output files |
| `validation.py` | Enforce data quality checks |
| `model.py` | Define model structure and constraints |
| `utils.py` | Logging and path utilities |
| `main.py` | Orchestrate full pipeline |

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| FileNotFoundError | Run from project root or use `--source` flag |
| ValidationError | Check source data for nulls in keys or mismatched FKs |
| ImportError: pandas | `pip install -r requirements.txt` |
| ModuleNotFoundError in tests | Run from project root: `PYTHONPATH=src pytest tests/` |

---

## 📚 References

- **Kimball Dimensional Modeling:** "The Data Warehouse Toolkit" by Ralph Kimball & Margy Ross
- **Pandas Documentation:** https://pandas.pydata.org/docs/
- **Pytest Guide:** https://docs.pytest.org/

---

**Status:** Production Ready ✓  
**Version:** 1.0  
**Last Updated:** 2026-04-21
* **Execute the code** to demonstrate that it works successfully.

---

## 5. Technical Notes
* **Libraries:** You are free to use any Python libraries or frameworks (e.g., Pandas, PySpark, SQLAlchemy, etc.).
* **Testing:** Automated testing is not mandatory for this exercise, but be prepared to explain your **testing strategy** and how you would ensure data quality in a production environment.