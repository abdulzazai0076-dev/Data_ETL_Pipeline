from pathlib import Path
from typing import Dict

import pandas as pd


def write_table_csv(df: pd.DataFrame, output_dir: Path, table_name: str) -> Path:
    """Write a table to CSV file."""
    output_path = output_dir / f"{table_name}.csv"
    df.to_csv(output_path, index=False)
    print(f"  Wrote {len(df)} rows to {table_name}.csv")
    return output_path


def load_all(tables: Dict[str, pd.DataFrame], output_dir: Path) -> Dict[str, Path]:
    """Write all tables to CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    return {table_name: write_table_csv(df, output_dir, table_name) 
            for table_name, df in tables.items()}


def print_summary(tables: Dict[str, pd.DataFrame]) -> None:
    """Print table summary."""
    total_rows = sum(len(df) for df in tables.values())
    print("\nTable Summary:")
    for table_name in sorted(tables.keys()):
        df = tables[table_name]
        print(f"  {table_name:30s} {len(df):6d} rows")
    print(f"  {'Total':30s} {total_rows:6d} rows\n")
