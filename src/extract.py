from pathlib import Path
from typing import Dict

import pandas as pd


def load_csv(file_path: Path) -> pd.DataFrame:
    """Load CSV file."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    df = pd.read_csv(file_path, encoding="utf-8")
    print(f"  Loaded {len(df)} rows from {file_path.name}")
    return df


def load_json_orders(file_path: Path) -> pd.DataFrame:
    """Load orders from JSON file."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = pd.read_json(f)
    print(f"  Loaded {len(data)} orders from {file_path.name}")
    return data


def extract_all(source_dir: Path) -> Dict[str, pd.DataFrame]:
    """Extract all source data files."""
    extracted = {
        "customers": load_csv(source_dir / "customers.csv"),
        "products": load_csv(source_dir / "products.csv"),
        "categories": load_csv(source_dir / "categories.csv"),
        "delivery_methods": load_csv(source_dir / "delivery_methods.csv"),
        "orders": load_json_orders(source_dir / "orders.json"),
    }
    return extracted
