"""
Extract Nepal-only granular records from the BP0015 'Lodged' pivot cache.

Each record in pivotCacheRecords1.xml is one visa application, encoded as
11 <x v="idx"/> elements (indices into each field's shared-items list, in
cacheField order) followed by <n v="1"/> for the 'Total' count field.

This streams through the (potentially large) records XML using iterparse
so we never hold all 2M+ records in memory — only the ~few thousand that
match Citizenship Country == Nepal.

Usage:
    python extract_nepal_lodged.py
"""
import zipfile
import requests
import io
from xml.etree import ElementTree as ET
import pandas as pd

URL = (
    "https://data.gov.au/data/dataset/324aa4f7-46bb-4d56-bc2d-772333a2317e/"
    "resource/ef31b2b4-a894-484b-99bc-e35d62ace777/download/"
    "bp0015l-student-visas-lodged-report-locked-at-2026-05-31-v100.xlsx"
)

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

FIELD_NAMES = [
    'financial_year', 'fy_quarter', 'month', 'client_location',
    'lodgement_channel', 'sector', 'applicant_type', 'provider_state',
    'gender', 'citizenship_country', 'age_group',
]  # field index 11 ('Total') is handled separately as the count

print("Downloading...")
resp = requests.get(URL, timeout=120)
resp.raise_for_status()
content = resp.content
print(f"Downloaded {len(content):,} bytes\n")

zf = zipfile.ZipFile(io.BytesIO(content))

# ── Step 1: Parse cache definition to get shared-item lists per field ──────
def_xml = zf.read('xl/pivotCache/pivotCacheDefinition1.xml')
root = ET.fromstring(def_xml)
cache_fields = root.findall(f'.//{NS}cacheFields/{NS}cacheField')

shared_items_by_field = []
for f in cache_fields:
    items = []
    for s in f.findall(f'.//{NS}sharedItems/{NS}s'):
        items.append(s.get('v'))
    shared_items_by_field.append(items)

# Find Nepal's index in the Citizenship Country field (index 9)
country_items = shared_items_by_field[9]
nepal_matches = [(i, v) for i, v in enumerate(country_items) if 'nepal' in v.lower()]
print("Citizenship Country entries matching 'nepal':", nepal_matches)

if not nepal_matches:
    raise SystemExit("Could not find 'Nepal' in Citizenship Country shared items — stopping.")

nepal_idx = nepal_matches[0][0]
print(f"Using Nepal index = {nepal_idx}\n")

# ── Step 2: Stream through records, keep only Nepal rows ───────────────────
print("Streaming through 2M+ records (this will take a bit)...")
nepal_rows = []
count_total = 0

with zf.open('xl/pivotCache/pivotCacheRecords1.xml') as f:
    context = ET.iterparse(f, events=('end',))
    for event, elem in context:
        if elem.tag == f'{NS}r':
            count_total += 1
            children = list(elem)
            # children[9] corresponds to Citizenship Country (field index 9)
            country_idx_str = children[9].get('v')
            if country_idx_str is not None and int(country_idx_str) == nepal_idx:
                row = {}
                for fi, fname in enumerate(FIELD_NAMES):
                    idx = children[fi].get('v')
                    row[fname] = shared_items_by_field[fi][int(idx)] if idx is not None else None
                total_val = children[11].get('v')
                row['lodged_count'] = int(float(total_val)) if total_val is not None else 0
                nepal_rows.append(row)
            elem.clear()  # free memory
            if count_total % 500000 == 0:
                print(f"  ...processed {count_total:,} records, {len(nepal_rows):,} Nepal matches so far")

print(f"\nDone. Total records scanned: {count_total:,}")
print(f"Nepal records found: {len(nepal_rows):,}")

df = pd.DataFrame(nepal_rows)
print("\n─── Preview ───")
print(df.head(10).to_string())
print(f"\nShape: {df.shape}")
print(f"Total lodged (sum): {df['lodged_count'].sum():,}")

df.to_csv('nepal_lodged_extracted.csv', index=False)
print("\nSaved full extract to nepal_lodged_extracted.csv")