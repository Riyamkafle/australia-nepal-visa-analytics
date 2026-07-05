"""
Management command: python manage.py import_homeaffairs

Fetches the latest BP0015 student visa XLSX from data.gov.au,
processes it with pandas, and loads it into PostgreSQL.
"""

import io
import logging
import requests
import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from upload.models import UploadLog

logger = logging.getLogger(__name__)

# Public data.gov.au dataset URL for BP0015 student visa data
DATASET_API_URL = (
    "https://data.gov.au/api/3/action/package_show"
    "?id=student-visa-bp0015"
)

FALLBACK_DIRECT_URL = (
    "https://data.gov.au/data/dataset/student-visa-bp0015/"
    "resource/latest/download"
)


class Command(BaseCommand):
    help = 'Import latest Australian Student Visa BP0015 data from data.gov.au'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            help='Override direct download URL for the XLSX file',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Download and parse the file but do not write to the database',
        )
        parser.add_argument(
            '--country',
            type=str,
            default='Nepal',
            help='Filter by country of citizenship (default: Nepal)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('🔍 Fetching Home Affairs BP0015 dataset...'))

        direct_url = options.get('url')
        dry_run    = options.get('dry_run', False)
        country    = options.get('country', 'Nepal')

        # ── Step 1: Resolve download URL ──────────────────────────────────────
        if not direct_url:
            direct_url = self._resolve_download_url()

        if not direct_url:
            raise CommandError('Could not resolve a download URL for BP0015 dataset.')

        self.stdout.write(f'   URL: {direct_url}')

        # ── Step 2: Download file ─────────────────────────────────────────────
        try:
            resp = requests.get(direct_url, timeout=120, stream=True)
            resp.raise_for_status()
            content = resp.content
            self.stdout.write(f'   Downloaded: {len(content):,} bytes')
        except requests.RequestException as exc:
            raise CommandError(f'Download failed: {exc}')

        # ── Step 3: Parse XLSX ────────────────────────────────────────────────
        try:
            df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=0)
            self.stdout.write(f'   Raw rows: {len(df):,}, columns: {list(df.columns[:8])}...')
        except Exception as exc:
            raise CommandError(f'Failed to parse XLSX: {exc}')

        # ── Step 4: Filter for Nepal ──────────────────────────────────────────
        country_col = self._find_column(df, ['country', 'country_of_citizenship', 'citizenship'])
        if country_col:
            df = df[df[country_col].str.strip().str.title() == country.title()]
            self.stdout.write(f'   After filtering for {country}: {len(df):,} rows')
        else:
            self.stdout.write(self.style.WARNING('   ⚠ Country column not found; loading all rows.'))

        if len(df) == 0:
            raise CommandError(f'No rows found for country: {country}')

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'✓ Dry run complete — {len(df):,} rows would be loaded.'))
            return

        # ── Step 5: Load into nepal_merged ────────────────────────────────────
        df.columns = (
            df.columns.str.strip()
            .str.lower()
            .str.replace(' ', '_')
            .str.replace('-', '_')
            .str.replace('/', '_')
        )

        try:
            rows = self._bulk_insert(df, 'nepal_merged')
        except Exception as exc:
            UploadLog.objects.create(
                filename    = 'auto_import_bp0015.xlsx',
                file_type   = 'auto',
                rows_loaded = 0,
                status      = 'error',
                notes       = str(exc),
            )
            raise CommandError(f'Database insert failed: {exc}')

        UploadLog.objects.create(
            filename    = 'auto_import_bp0015.xlsx',
            file_type   = 'auto',
            rows_loaded = rows,
            status      = 'success',
            notes       = f'Automated import from data.gov.au BP0015 — {country} filter',
        )

        self.stdout.write(self.style.SUCCESS(
            f'✓ Successfully imported {rows:,} rows into nepal_merged.'
        ))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_download_url(self) -> str:
        """Query data.gov.au CKAN API to get the latest XLSX download URL."""
        try:
            resp = requests.get(DATASET_API_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            resources = data.get('result', {}).get('resources', [])
            for r in resources:
                fmt = (r.get('format') or '').upper()
                url = r.get('url', '')
                if fmt in ('XLSX', 'XLS') or url.lower().endswith(('.xlsx', '.xls')):
                    return url
            # fallback to first resource
            if resources:
                return resources[0].get('url', '')
        except Exception as exc:
            logger.warning('CKAN API lookup failed: %s', exc)
        return FALLBACK_DIRECT_URL

    def _find_column(self, df: pd.DataFrame, candidates: list) -> str | None:
        """Find the first matching column from a list of candidate names."""
        cols_lower = {c.lower(): c for c in df.columns}
        for name in candidates:
            if name.lower() in cols_lower:
                return cols_lower[name.lower()]
        return None

    def _bulk_insert(self, df: pd.DataFrame, table: str) -> int:
        """Truncate table and bulk-insert DataFrame rows."""
        with connection.cursor() as cur:
            cur.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')

        try:
            from sqlalchemy import create_engine
            from django.conf import settings
            db  = settings.DATABASES['default']
            url = (
                f"postgresql+psycopg2://{db['USER']}:{db['PASSWORD']}"
                f"@{db['HOST']}:{db['PORT']}/{db['NAME']}"
            )
            engine = create_engine(url)
            df.to_sql(table, engine, if_exists='append', index=False,
                      method='multi', chunksize=500)
        except ImportError:
            # Fallback: row-by-row insert via Django ORM cursor
            cols    = ', '.join(f'"{c}"' for c in df.columns)
            placeholders = ', '.join(['%s'] * len(df.columns))
            sql = f'INSERT INTO "{table}" ({cols}) VALUES ({placeholders})'
            with connection.cursor() as cur:
                for _, row in df.iterrows():
                    cur.execute(sql, list(row))

        return len(df)
