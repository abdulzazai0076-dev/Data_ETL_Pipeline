"""Integration test: full pipeline end-to-end."""

import tempfile
from pathlib import Path
import pandas as pd
import pytest
from aggregate import aggregate_all
from extract import extract_all
from transform import transform_all
from validation import validate_all
from load import load_all


def test_end_to_end_pipeline():
    """Test complete pipeline from extract to load."""
    # Use actual source data
    source_dir = Path(__file__).parent.parent / "source_data"
    
    # Extract
    extracted = extract_all(source_dir)
    assert "customers" in extracted
    assert "orders" in extracted
    assert len(extracted["customers"]) > 0
    
    # Transform
    transformed = transform_all(extracted)
    assert "fact_order_items" in transformed
    assert "dim_customers" in transformed
    assert len(transformed["fact_order_items"]) > 0
    assert "full_name" in transformed["dim_customers"].columns
    assert "category_name" in transformed["dim_products"].columns
    
    # Validate
    validate_all(transformed)  # Should not raise
    
    # Aggregate
    aggregated = aggregate_all(transformed)
    assert "agg_sales_by_category" in aggregated
    assert len(aggregated["agg_sales_by_category"]) > 0
    
    # Load
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        all_tables = {**transformed, **aggregated}
        written = load_all(all_tables, output_dir)
        
        # Verify files were written
        assert len(written) == 7  # 5 dimensions + 1 fact + 1 aggregate
        fact_file = output_dir / "fact_order_items.csv"
        assert fact_file.exists()
        agg_file = output_dir / "agg_sales_by_category.csv"
        assert agg_file.exists()
        
        # Verify data in fact file
        fact_df = pd.read_csv(fact_file)
        assert len(fact_df) == 10, "Should have 10 order items"
        assert "line_amount" in fact_df.columns
        
        # Verify data in aggregate file
        agg_df = pd.read_csv(agg_file)
        assert agg_df["total_revenue"].sum() == pytest.approx(fact_df["line_amount"].sum())
