"""
Management command: python manage.py import_homeaffairs

Fetches the latest BP0015 student visa data from data.gov.au and loads it
into PostgreSQL. Two data sources, both from the same CKAN package:

1. Main BP0015 XLSX (summary rows) -> nepal_merged
2. Pivot-cache resources (Lodged / Granted / Grant Rates reports) -> real
   decision-based Nepal-only records, including applicant_type
   (Primary/Secondary) -> nepal_grant_rates table + CSV

Resource discovery is DYNAMIC (queries the CKAN package_show API and matches
resources by name pattern) rather than hardcoded URLs, because Home Affairs
publishes a new dated snapshot each month (e.g. "...locked-at-2026-05-31...")
and hardcoded resource IDs go stale.
"""

import io
import logging
import zipfile
from xml.etree import ElementTree as ET

import requests
import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from upload.models import UploadLog

logger = logging.getLogger(__name__)

PACKAGE_API_URL = (
    "https://data.gov.au/data/api/3/action/package_show"
    "?id=324aa4f7-46bb-4d56-bc2d-772333a2317e"
)
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

# Name patterns used to identify each pivot-cache resource dynamically,
# since the exact filename changes every month.
PIVOT_SOURCES = {
    'lodged':     {'match': ['lodged'],               'value_field': 'lodged_count'},
    'granted':    {'match': ['granted'],               'value_field': 'granted_count'},
    'grant_rates': {'match': ['grant rate', 'grant-rate'], 'value_field': None},  # has grant_total + refused_total
}

DIM_FIELD_MAP = {
    'financial year quarter': 'fy_quarter',
    'month': 'month',
    'client location': 'client_location',
    'lodgement channel': 'lodgement_channel',
    'sector': 'sector',
    'applicant type': 'applicant_type',
    'education provider registered state': 'provider_state',
    'gender': 'gender',
    'citizenship country': 'citizenship_country',
    'age group': 'age_group',
}


def canonical_dim_name(raw_name: str) -> str | None:
    n = raw_name.strip().lower()
    if n.startswith('financial year of'):
        return 'financial_year'
    return DIM_FIELD_MAP.get(n)


class Command(BaseCommand):
    help = 'Import latest Australian Student Visa BP0015 data from data.gov.au'

    def add_arguments(self, parser):
        parser.add_argument('--url', type=str, help='Override main BP0015 XLSX URL')
        parser.add_argument('--dry-run', action='store_true',
                             help='Download and parse but do not write to the database')
        parser.add_argument('--country', type=str, default='Nepal')
        parser.add_argument('--skip-pivot', action='store_true',
                             help='Skip the pivot-cache extraction (lodged/granted/grant_rates)')
        parser.add_argument('--skip-main', action='store_true',
                             help='Skip Step 1 (main XLSX import). Use this — the BP0015 XLSX '
                                  'resources are full pivot-table report workbooks, not flat '
                                  'data tables; sheet 0 is a cover/notes page, not data. The '
                                  'real data only exists in the pivot cache (Step 2).')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        country = options.get('country', 'Nepal')

        if not options.get('skip_main'):
            self.stdout.write(self.style.NOTICE('Step 1/2: Main BP0015 summary import'))
            self._import_main(options.get('url'), dry_run, country)
        else:
            self.stdout.write(self.style.WARNING('Skipping Step 1 (--skip-main).'))

        if not options.get('skip_pivot'):
            self.stdout.write(self.style.NOTICE('\nStep 2/2: Pivot-cache extraction (lodged/granted/grant_rates)'))
            self._import_pivot_caches(dry_run, country)
        else:
            self.stdout.write(self.style.WARNING('\nSkipping pivot-cache step (--skip-pivot).'))

    # ── Step 1: main summary import (unchanged logic from prior version) ──────

    def _import_main(self, direct_url, dry_run, country):
        if not direct_url:
            direct_url = self._resolve_url_by_format(['XLSX', 'XLS'])
        if not direct_url:
            raise CommandError('Could not resolve a download URL for the main BP0015 dataset.')

        self.stdout.write(f'   URL: {direct_url}')
        content = self._download(direct_url)

        try:
            df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=0)
            self.stdout.write(f'   Raw rows: {len(df):,}')
        except Exception as exc:
            raise CommandError(f'Failed to parse XLSX: {exc}')

        country_col = self._find_column(df, ['country', 'country_of_citizenship', 'citizenship'])
        if country_col:
            df = df[df[country_col].str.strip().str.title() == country.title()]
            self.stdout.write(f'   After filtering for {country}: {len(df):,} rows')

        if len(df) == 0:
            raise CommandError(f'No rows found for country: {country}')

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'   Dry run — {len(df):,} rows would be loaded.'))
            return

        df.columns = (df.columns.str.strip().str.lower()
                      .str.replace(' ', '_').str.replace('-', '_').str.replace('/', '_'))

        try:
            rows = self._bulk_insert(df, 'nepal_merged')
        except Exception as exc:
            UploadLog.objects.create(filename='auto_import_bp0015.xlsx', file_type='auto',
                                      rows_loaded=0, status='error', notes=str(exc))
            raise CommandError(f'Database insert failed: {exc}')

        UploadLog.objects.create(filename='auto_import_bp0015.xlsx', file_type='auto',
                                  rows_loaded=rows, status='success',
                                  notes=f'Automated main import — {country} filter')
        self.stdout.write(self.style.SUCCESS(f'   Loaded {rows:,} rows into nepal_merged.'))

    # ── Step 2: pivot-cache extraction (folds in the 4 extract_nepal_*.py scripts) ─

    def _import_pivot_caches(self, dry_run, country):
        resources = self._get_package_resources()
        extracted = {}

        for key, spec in PIVOT_SOURCES.items():
            url = self._match_resource_url(resources, spec['match'])
            if not url:
                self.stdout.write(self.style.WARNING(f'   [{key}] No matching resource found — skipped.'))
                continue

            self.stdout.write(f'   [{key}] {url}')
            content = self._download(url)
            df = self._extract_pivot_cache(content, country, key, spec['value_field'])
            extracted[key] = df
            self.stdout.write(f'   [{key}] Extracted {len(df):,} {country} rows.')

            csv_name = f'nepal_{key}_extracted.csv'
            df.to_csv(csv_name, index=False)
            self.stdout.write(f'   [{key}] Saved -> {csv_name}')

        if 'grant_rates' in extracted and not extracted['grant_rates'].empty:
            df = extracted['grant_rates']
            granted = df['grant_total'].sum()
            refused = df['refused_total'].sum()
            decided = granted + refused
            rate = round(granted / decided * 100, 2) if decided else 0.0
            self.stdout.write(self.style.SUCCESS(
                f'   Grant rate check: {granted:,} granted / {refused:,} refused '
                f'-> {rate}% (Granted / (Granted+Refused))'
            ))

            if not dry_run:
                rows = self._load_grant_rates_table(df)
                self.stdout.write(self.style.SUCCESS(f'   Loaded {rows:,} rows into nepal_grant_rates table.'))
            else:
                self.stdout.write(self.style.WARNING('   Dry run — nepal_grant_rates table not written.'))

    def _extract_pivot_cache(self, content, country, key, value_field):
        zf = zipfile.ZipFile(io.BytesIO(content))
        def_xml = zf.read('xl/pivotCache/pivotCacheDefinition1.xml')
        root = ET.fromstring(def_xml)
        cache_fields = root.findall(f'.//{NS}cacheFields/{NS}cacheField')

        dim_fields = []
        numeric_fields = {}
        country_pos = None

        for pos, f in enumerate(cache_fields):
            raw_name = f.get('name').strip()
            items = [s.get('v') for s in f.findall(f'.//{NS}sharedItems/{NS}s')]
            canon = canonical_dim_name(raw_name)
            if canon:
                dim_fields.append((pos, canon, items))
                if canon == 'citizenship_country':
                    country_pos = pos
            else:
                numeric_fields[raw_name.lower()] = pos

        if country_pos is None:
            raise CommandError(f'[{key}] Citizenship Country field not found in pivot cache.')

        country_items = next(items for pos, name, items in dim_fields if name == 'citizenship_country')
        nepal_matches = [i for i, v in enumerate(country_items) if country.lower() in v.lower()]
        if not nepal_matches:
            raise CommandError(f'[{key}] {country} not found in Citizenship Country items.')
        target_idx = nepal_matches[0]

        # Resolve numeric value column(s) by fuzzy name match (robust to reordering)
        if key == 'grant_rates':
            grant_pos = next((p for n, p in numeric_fields.items() if 'grant total' in n), None)
            refused_pos = next((p for n, p in numeric_fields.items() if 'refused total' in n), None)
            if grant_pos is None or refused_pos is None:
                raise CommandError(f'[{key}] Grant Total / Refused Total fields not found.')
        else:
            val_pos = next((p for n, p in numeric_fields.items() if 'total' in n), None)
            if val_pos is None:
                raise CommandError(f'[{key}] Total field not found.')

        rows = []
        with zf.open('xl/pivotCache/pivotCacheRecords1.xml') as f:
            for event, elem in ET.iterparse(f, events=('end',)):
                if elem.tag == f'{NS}r':
                    children = list(elem)
                    cv = children[country_pos].get('v')
                    if cv is not None and int(cv) == target_idx:
                        row = {}
                        for pos, canon, items in dim_fields:
                            v = children[pos].get('v')
                            row[canon] = items[int(v)] if (v is not None and items) else v
                        if key == 'grant_rates':
                            g = children[grant_pos].get('v') if grant_pos < len(children) else None
                            r = children[refused_pos].get('v') if refused_pos < len(children) else None
                            row['grant_total'] = int(float(g)) if g is not None else 0
                            row['refused_total'] = int(float(r)) if r is not None else 0
                        else:
                            v = children[val_pos].get('v') if val_pos < len(children) else None
                            row[value_field] = int(float(v)) if v is not None else 0
                        rows.append(row)
                    elem.clear()

        return pd.DataFrame(rows)

    def _load_grant_rates_table(self, df: pd.DataFrame) -> int:
        with connection.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS "nepal_grant_rates"')
            cur.execute('''
                CREATE TABLE "nepal_grant_rates" (
                    id SERIAL PRIMARY KEY,
                    financial_year TEXT,
                    fy_quarter TEXT,
                    month TEXT,
                    client_location TEXT,
                    lodgement_channel TEXT,
                    sector TEXT,
                    applicant_type TEXT,
                    provider_state TEXT,
                    gender TEXT,
                    citizenship_country TEXT,
                    age_group TEXT,
                    grant_total INTEGER,
                    refused_total INTEGER
                )
            ''')

        cols = ', '.join(f'"{c}"' for c in df.columns)
        placeholders = ', '.join(['%s'] * len(df.columns))
        sql = f'INSERT INTO "nepal_grant_rates" ({cols}) VALUES ({placeholders})'
        with connection.cursor() as cur:
            for _, row in df.iterrows():
                cur.execute(sql, list(row))
        return len(df)

    # ── Shared helpers ──────────────────────────────────────────────────────

    def _get_package_resources(self) -> list:
        try:
            resp = requests.get(PACKAGE_API_URL, timeout=30)
            resp.raise_for_status()
            return resp.json().get('result', {}).get('resources', [])
        except Exception as exc:
            raise CommandError(f'CKAN package lookup failed: {exc}')

    def _resolve_url_by_format(self, formats: list) -> str | None:
        resources = self._get_package_resources()
        for r in resources:
            fmt = (r.get('format') or '').upper()
            url = r.get('url', '')
            if fmt in formats or url.lower().endswith(tuple(f.lower() for f in formats)):
                return url
        return resources[0].get('url', '') if resources else None

    def _match_resource_url(self, resources: list, name_patterns: list) -> str | None:
        """Find a resource whose name contains any of the given patterns (case-insensitive).
        This is what makes discovery dynamic instead of relying on hardcoded, dated URLs."""
        for r in resources:
            name = (r.get('name') or '').lower()
            if any(p in name for p in name_patterns):
                return r.get('url', '')
        return None

    def _download(self, url: str) -> bytes:
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            raise CommandError(f'Download failed for {url}: {exc}')

    def _find_column(self, df: pd.DataFrame, candidates: list) -> str | None:
        cols_lower = {c.lower(): c for c in df.columns}
        for name in candidates:
            if name.lower() in cols_lower:
                return cols_lower[name.lower()]
        return None

    def _bulk_insert(self, df: pd.DataFrame, table: str) -> int:
        with connection.cursor() as cur:
            cur.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')
        try:
            from sqlalchemy import create_engine
            from django.conf import settings
            db = settings.DATABASES['default']
            url = f"postgresql+psycopg2://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"
            engine = create_engine(url)
            df.to_sql(table, engine, if_exists='append', index=False, method='multi', chunksize=500)
        except ImportError:
            cols = ', '.join(f'"{c}"' for c in df.columns)
            placeholders = ', '.join(['%s'] * len(df.columns))
            sql = f'INSERT INTO "{table}" ({cols}) VALUES ({placeholders})'
            with connection.cursor() as cur:
                for _, row in df.iterrows():
                    cur.execute(sql, list(row))
        return len(df)