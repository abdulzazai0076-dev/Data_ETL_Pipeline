"""Integration test: full pipeline end-to-end."""

import tempfile
from pathlib import Path
import pandas as pd
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
    
    # Validate
    validate_all(transformed)  # Should not raise
    
    # Load
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        written = load_all(transformed, output_dir)
        
        # Verify files were written
        assert len(written) == 6  # 5 dimensions + 1 fact
        fact_file = output_dir / "fact_order_items.csv"
        assert fact_file.exists()
        
        # Verify data in fact file
        fact_df = pd.read_csv(fact_file)
        assert len(fact_df) == 10, "Should have 10 order items"
        assert "line_amount" in fact_df.columns
