#!/usr/bin/env python3
"""Retail ETL Pipeline - Load CSV + JSON into dimensional model."""

import argparse
from pathlib import Path

from extract import extract_all
from load import load_all, print_summary
from transform import transform_all
from validation import validate_all


def run_pipeline(source_dir: Path, output_dir: Path, skip_validation: bool = False):
    """Execute ETL pipeline: extract -> transform -> validate -> load."""
    print("\n" + "=" * 60)
    print("ETL PIPELINE")
    print("=" * 60)
    
    print("\n[1/4] EXTRACT")
    extracted = extract_all(source_dir)
    
    print("\n[2/4] TRANSFORM")
    transformed = transform_all(extracted)
    
    print("\n[3/4] VALIDATE")
    if not skip_validation:
        validate_all(transformed)
    else:
        print("  WARNING: Validation skipped")
    
    print("\n[4/4] LOAD")
    load_all(transformed, output_dir)
    
    print_summary(transformed)
    
    print("=" * 60)
    print("ETL COMPLETED SUCCESSFULLY")
    print("=" * 60 + "\n")


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Retail ETL Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source", type=Path, default=Path("source_data"), 
                       help="Source data directory")
    parser.add_argument("--output", type=Path, default=Path("output"),
                       help="Output directory")
    parser.add_argument("--skip-validation", action="store_true",
                       help="Skip validation checks")
    
    args = parser.parse_args()
    
    if not args.source.exists():
        print(f"ERROR: Source directory not found: {args.source}")
        return 1
    
    try:
        run_pipeline(args.source, args.output, args.skip_validation)
        return 0
    except Exception as e:
        print(f"ERROR: Pipeline failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
