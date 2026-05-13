"""
Build the silver layer for CRLA and PhilIRI.

Reads bronze (raw CSV exports) and writes harmonized, typed parquets
to data/silver/crla/ and data/silver/philiri/.

Usage:
    cd /workspace/innovation-projects/project_crla
    ds python scripts/build_silver.py [--crla] [--philiri]

With no flags, both datasets are processed.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "modules"))

from preprocessing import resolve_latest_exports, load_all_assessments, write_silver_crla
from philiri_preprocessing import resolve_philiri_files, write_silver_philiri


def build_crla_silver():
    print("=" * 60)
    print("CRLA Silver")
    print("=" * 60)
    file_map = resolve_latest_exports()
    if not file_map:
        print("No CRLA bronze files found.")
        return
    print(f"Found {len(file_map)} timepoints: {sorted(file_map)}")
    df_all = load_all_assessments(file_map=file_map, source="local")
    write_silver_crla(df_all)
    print()


def build_philiri_silver():
    print("=" * 60)
    print("PhilIRI Silver")
    print("=" * 60)
    write_silver_philiri()
    print()


def main():
    parser = argparse.ArgumentParser(description="Build silver layer parquets.")
    parser.add_argument("--crla", action="store_true", help="Process CRLA only")
    parser.add_argument("--philiri", action="store_true", help="Process PhilIRI only")
    args = parser.parse_args()

    both = not args.crla and not args.philiri
    if args.crla or both:
        build_crla_silver()
    if args.philiri or both:
        build_philiri_silver()

    print("Done.")


if __name__ == "__main__":
    main()
