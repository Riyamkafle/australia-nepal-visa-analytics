"""
One-time / repeatable script to load the CSV files in `data sources/`
into the local PostgreSQL database (student_visa_db).

This creates (or replaces) the tables that the Django models in
analytics/models.py expect, using the same db_table names.

Note: this does NOT load the `nepal_merged` table — that one is
populated separately via:
    python manage.py import_homeaffairs
which pulls live data from data.gov.au.

Usage:
    python load_csv_data.py
"""
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from decouple import config

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data sources'

DB_NAME = config('DB_NAME', default='student_visa_db')
DB_USER = config('DB_USER', default='postgres')
DB_PASSWORD = config('DB_PASSWORD', default='Admin')
DB_HOST = config('DB_HOST', default='localhost')
DB_PORT = config('DB_PORT', default='5432')

# CSV filename -> target Postgres table name (matches db_table in models.py)
CSV_TABLE_MAP = {
    'monthly_trend.csv':     'monthly_trend',
    'by_sector.csv':         'by_sector',
    'fy_summary.csv':        'fy_summary',
    'forecast.csv':          'forecast',
    'gender_breakdown.csv':  'gender_breakdown',
    'location_breakdown.csv': 'location_breakdown',
    'age_breakdown.csv':     'age_breakdown',
    'channel_breakdown.csv': 'channel_breakdown',
    'seasonal_pattern.csv':  'seasonal_pattern',
}


def main():
    url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(url)

    print(f"Connecting to {DB_NAME} at {DB_HOST}:{DB_PORT} as {DB_USER}...\n")

    for csv_file, table_name in CSV_TABLE_MAP.items():
        csv_path = DATA_DIR / csv_file
        if not csv_path.exists():
            print(f"  Skipping {csv_file} (not found in 'data sources/')")
            continue

        df = pd.read_csv(csv_path)
        df.to_sql(table_name, engine, if_exists='replace', index=False)
        print(f"  Loaded {len(df):,} rows -> '{table_name}' (from {csv_file})")

    print("\nDone.")
    print("Note: 'nepal_merged' was NOT loaded by this script.")
    print("Run `python manage.py import_homeaffairs` separately to fetch it")
    print("live from data.gov.au (requires internet access).")


if __name__ == '__main__':
    main()