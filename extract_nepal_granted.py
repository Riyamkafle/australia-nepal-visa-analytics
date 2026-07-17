"""
Extract Nepal-only granular records from the BP0015 'Granted' pivot cache.
Same technique as extract_nepal_lodged.py, but verifies the field order
matches (since this is a different file) before extracting, to avoid
silently misaligning columns.

Usage:
    python extract_nepal_granted.py
"""
import zipfile
import requests
import io
from xml.etree import ElementTree as ET
import pandas as pd

URL = (
    "https://data.gov.au/data/dataset/324aa4f7-46bb-4d56-bc2d-772333a2317e/"
    "resource/dfc7a893-0523-4b8e-bc5a-829e35bec90f/download/"
    "bp0015l-student-visas-granted-report-locked-at-2026-05-31-v100-.xlsx"
)

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

EXPECTED_FIELD_ORDER = [
    'Financial Year of Visa Granted', 'Financial Year Quarter', 'Month',
    'Client Location', 'Lodgement Channel', 'Sector', 'Applicant Type',
    'Education Provider Registered State', 'Gender', 'Citizenship Country',
    'Age Group', 'Total',
]

FIELD_NAMES = [
    'financial_year', 'fy_quarter', 'month', 'client_location',
    'lodgement_channel', 'sector', 'applicant_type', 'provider_state',
    'gender', 'citizenship_country', 'age_group',
]

print("Downloading...")
resp = requests.get(URL, timeout=120)
resp.raise_for_status()
content = resp.content
print(f"Downloaded {len(content):,} bytes\n")

zf = zipfile.ZipFile(io.BytesIO(content))

def_xml = zf.read('xl/pivotCache/pivotCacheDefinition1.xml')
root = ET.fromstring(def_xml)
cache_fields = root.findall(f'.//{NS}cacheFields/{NS}cacheField')

actual_names = [f.get('name') for f in cache_fields]
print("Actual field order:  ", actual_names)
print("Expected field order:", EXPECTED_FIELD_ORDER)
if [n.strip() for n in actual_names] != [n.strip() for n in EXPECTED_FIELD_ORDER]:
    print("\n⚠ WARNING: field order differs from the Lodged file! Check manually before trusting output.\n")
else:
    print("\n✓ Field order matches expected structure.\n")

shared_items_by_field = []
for f in cache_fields:
    items = [s.get('v') for s in f.findall(f'.//{NS}sharedItems/{NS}s')]
    shared_items_by_field.append(items)

country_items = shared_items_by_field[9]
nepal_matches = [(i, v) for i, v in enumerate(country_items) if 'nepal' in v.lower()]
print("Citizenship Country entries matching 'nepal':", nepal_matches)
if not nepal_matches:
    raise SystemExit("Could not find 'Nepal' — stopping.")
nepal_idx = nepal_matches[0][0]
print(f"Using Nepal index = {nepal_idx}\n")

print("Streaming through records...")
nepal_rows = []
count_total = 0

with zf.open('xl/pivotCache/pivotCacheRecords1.xml') as f:
    context = ET.iterparse(f, events=('end',))
    for event, elem in context:
        if elem.tag == f'{NS}r':
            count_total += 1
            children = list(elem)
            country_idx_str = children[9].get('v')
            if country_idx_str is not None and int(country_idx_str) == nepal_idx:
                row = {}
                for fi, fname in enumerate(FIELD_NAMES):
                    idx = children[fi].get('v')
                    row[fname] = shared_items_by_field[fi][int(idx)] if idx is not None else None
                total_val = children[11].get('v')
                row['granted_count'] = int(float(total_val)) if total_val is not None else 0
                nepal_rows.append(row)
            elem.clear()
            if count_total % 500000 == 0:
                print(f"  ...processed {count_total:,} records, {len(nepal_rows):,} Nepal matches so far")

print(f"\nDone. Total records scanned: {count_total:,}")
print(f"Nepal records found: {len(nepal_rows):,}")

df = pd.DataFrame(nepal_rows)
print("\n─── Preview ───")
print(df.head(10).to_string())
print(f"\nShape: {df.shape}")
print(f"Total granted (sum): {df['granted_count'].sum():,}")

df.to_csv('nepal_granted_extracted.csv', index=False)
print("\nSaved full extract to nepal_granted_extracted.csv")