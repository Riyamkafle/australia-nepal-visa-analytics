"""
Upload pipeline utilities.
Handles CSV and Excel ingestion into PostgreSQL via pandas.
"""

import io
import logging
from typing import Tuple, Dict, Any

import pandas as pd
from django.db import connection

logger = logging.getLogger(__name__)

# ─── Expected column schemas ──────────────────────────────────────────────────

SCHEMAS: Dict[str, Dict[str, Any]] = {
    'monthly_trend': {
        'required': ['year_month', 'lodged', 'granted'],
        'optional': ['grant_rate', 'refusal_rate', 'rolling_3m', 'cal_month', 'month_name'],
    },
    'by_sector': {
        'required': ['year_month', 'sector', 'lodged', 'granted'],
        'optional': ['grant_rate'],
    },
    'fy_summary': {
        'required': ['financial_year', 'lodged', 'granted', 'refused'],
        'optional': ['grant_rate', 'refusal_rate'],
    },
    'nepal_merged': {
        'required': ['financial_year', 'lodged_count'],
        'optional': [
            'fy_quarter', 'month', 'client_location', 'lodgement_channel', 'sector',
            'applicant_type', 'provider_state', 'gender', 'country', 'age_group',
            'date', 'year_month', 'granted_count', 'grant_rates_count', 'refused_count',
            'grant_rate_calc', 'refusal_rate_calc',
        ],
    },
    'forecast': {
        'required': ['year_month'],
        'optional': [
            'month_label', 'lodged_forecast', 'granted_forecast',
            'refused_forecast', 'grant_rate_forecast', 'upper_bound', 'lower_bound',
        ],
    },
}


def read_uploaded_file(file_obj, file_type: str) -> pd.DataFrame:
    """Read uploaded file object into a DataFrame."""
    content = file_obj.read()
    if file_type == 'csv':
        return pd.read_csv(io.BytesIO(content), low_memory=False)
    elif file_type in ('excel', 'xlsx', 'xls'):
        return pd.read_excel(io.BytesIO(content))
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def detect_table(df: pd.DataFrame) -> str:
    """
    Auto-detect which table the DataFrame belongs to
    by matching columns to known schemas.
    """
    cols = set(df.columns.str.lower().tolist())
    best_match = None
    best_score = 0

    for table_name, schema in SCHEMAS.items():
        required = set(schema['required'])
        optional = set(schema.get('optional', []))
        all_cols = required | optional

        if not required.issubset(cols):
            continue

        score = len(cols & all_cols)
        if score > best_score:
            best_score = score
            best_match = table_name

    if best_match is None:
        raise ValueError(
            f"Cannot detect table for columns: {list(cols)}. "
            f"Known schemas: {list(SCHEMAS.keys())}"
        )
    return best_match


def validate_dataframe(df: pd.DataFrame, table_name: str) -> Tuple[bool, str]:
    """Validate that a DataFrame has all required columns for the target table."""
    if table_name not in SCHEMAS:
        return False, f"Unknown table: {table_name}"

    required = set(SCHEMAS[table_name]['required'])
    cols = set(df.columns.str.lower().tolist())
    missing = required - cols

    if missing:
        return False, f"Missing required columns: {sorted(missing)}"
    return True, "OK"


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names and clean common data issues."""
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('-', '_')
    df = df.dropna(how='all')
    df = df.reset_index(drop=True)
    # Replace NaN-like strings
    df = df.replace({'nan': None, 'NaN': None, 'NULL': None, '': None})
    return df


def upsert_dataframe(df: pd.DataFrame, table_name: str) -> int:
    """
    Load a cleaned DataFrame into PostgreSQL using COPY.
    For unmanaged tables: truncate and reload.
    Returns number of rows loaded.
    """
    df = clean_dataframe(df)
    valid, msg = validate_dataframe(df, table_name)
    if not valid:
        raise ValueError(msg)

    # Keep only known columns
    schema = SCHEMAS[table_name]
    known_cols = set(schema['required']) | set(schema.get('optional', []))
    keep = [c for c in df.columns if c in known_cols]
    df = df[keep]

    rows = len(df)
    if rows == 0:
        raise ValueError("No data rows found in uploaded file.")

    with connection.cursor() as cursor:
        # Truncate existing data for a clean reload
        cursor.execute(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE')

    # Use pandas to_sql for the insert
    from django.db import connection as conn
    engine_url = _get_sqlalchemy_engine()
    df.to_sql(table_name, engine_url, if_exists='append', index=False, method='multi', chunksize=500)

    return rows


def _get_sqlalchemy_engine():
    """Build a SQLAlchemy engine from Django's DB settings."""
    try:
        from sqlalchemy import create_engine
        from django.conf import settings
        db = settings.DATABASES['default']
        url = (
            f"postgresql+psycopg2://{db['USER']}:{db['PASSWORD']}"
            f"@{db['HOST']}:{db['PORT']}/{db['NAME']}"
        )
        return create_engine(url)
    except ImportError:
        raise ImportError(
            "sqlalchemy is required for bulk uploads. "
            "Install with: pip install sqlalchemy"
        )


def process_upload(file_obj, file_type: str, target_table: str = None) -> Dict[str, Any]:
    """
    Full processing pipeline for an uploaded file.
    Returns a result dict with status, rows_loaded, table, and any errors.
    """
    try:
        df = read_uploaded_file(file_obj, file_type)
        table = target_table or detect_table(df)
        rows = upsert_dataframe(df, table)
        return {
            'status':      'success',
            'table':       table,
            'rows_loaded': rows,
            'error':       None,
        }
    except Exception as exc:
        logger.exception("Upload processing failed: %s", exc)
        return {
            'status':      'error',
            'table':       target_table or 'unknown',
            'rows_loaded': 0,
            'error':       str(exc),
        }
