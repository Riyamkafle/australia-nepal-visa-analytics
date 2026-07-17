"""
Extract Nepal-only granular records from the BP0015 'Grant Rates' pivot
cache. This file has REAL decision-based counts: 'Grant Total' and
'Refused Total' (not inferred from lodged - granted), which is the
correct basis for computing an accurate grant rate.

'Grant Rate' itself is a calculated field (not stored per record) —
we compute it ourselves from Grant Total / (Grant Total + Refused Total).

Usage:
    python extract_nepal_grant_rates.py
"""
import zipfile
import requests
import io
from xml.etree import ElementTree as ET
import pandas as pd

URL = (
    "https://data.gov.au/data/dataset/324aa4f7-46bb-4d56-bc2d-772333a2317e/"
    "resource/b4775919-d0f5-4beb-8901-6384342774c6/download/"
    "bp0015l-student-visa-grant-rates-locked-at-2026-05-31-v100-.xlsx"
)

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

def canonical_name(raw_name: str) -> str:
    n = raw_name.strip().lower()
    if n.startswith('financial year of'):
        return 'financial_year'
    mapping = {
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
    return mapping.get(n)  # None for Grant Total / Refused Total / Total / Grant Rate — handled separately


print("Downloading...")
resp = requests.get(URL, timeout=120)
resp.raise_for_status()
content = resp.content
print(f"Downloaded {len(content):,} bytes")

zf = zipfile.ZipFile(io.BytesIO(content))
def_xml = zf.read('xl/pivotCache/pivotCacheDefinition1.xml')
root = ET.fromstring(def_xml)
cache_fields = root.findall(f'.//{NS}cacheFields/{NS}cacheField')

dim_fields = []       # (position, canonical_name, shared_items) for dimension fields
numeric_fields = {}   # raw_name -> position, for Grant Total / Refused Total / Total / Grant Rate
country_pos = None

for pos, f in enumerate(cache_fields):
    raw_name = f.get('name').strip()
    items = [s.get('v') for s in f.findall(f'.//{NS}sharedItems/{NS}s')]
    canon = canonical_name(raw_name)
    if canon:
        dim_fields.append((pos, canon, items))
        if canon == 'citizenship_country':
            country_pos = pos
    else:
        numeric_fields[raw_name] = pos

print("Dimension fields:", [(p, n) for p, n, _ in dim_fields])
print("Numeric fields:  ", numeric_fields)

grant_pos   = numeric_fields.get('Grant Total')
refused_pos = numeric_fields.get('Refused Total')
total_pos   = numeric_fields.get('Total')

if grant_pos is None or refused_pos is None or country_pos is None:
    raise SystemExit(f"Missing required fields — grant_pos={grant_pos}, "
                      f"refused_pos={refused_pos}, country_pos={country_pos}")

country_items = next(items for pos, name, items in dim_fields if name == 'citizenship_country')
nepal_matches = [(i, v) for i, v in enumerate(country_items) if 'nepal' in v.lower()]
if not nepal_matches:
    raise SystemExit("Nepal not found in Citizenship Country items.")
nepal_idx = nepal_matches[0][0]
print(f"Nepal index = {nepal_idx}")

print("Streaming through records...")
rows = []
scanned = 0

with zf.open('xl/pivotCache/pivotCacheRecords1.xml') as f:
    for event, elem in ET.iterparse(f, events=('end',)):
        if elem.tag == f'{NS}r':
            scanned += 1
            children = list(elem)
            country_val = children[country_pos].get('v')
            if country_val is not None and int(country_val) == nepal_idx:
                row = {}
                for pos, canon, items in dim_fields:
                    val = children[pos].get('v')
                    row[canon] = items[int(val)] if (val is not None and items) else val
                grant_val = children[grant_pos].get('v') if grant_pos < len(children) else None
                refused_val = children[refused_pos].get('v') if refused_pos < len(children) else None
                row['grant_total']   = int(float(grant_val)) if grant_val is not None else 0
                row['refused_total'] = int(float(refused_val)) if refused_val is not None else 0
                rows.append(row)
            elem.clear()
            if scanned % 500000 == 0:
                print(f"  ...scanned {scanned:,}, {len(rows):,} Nepal matches")

print(f"\nDone. Scanned {scanned:,} total, found {len(rows):,} Nepal rows.")
df = pd.DataFrame(rows)
print(f"Total grant_total (sum):   {df['grant_total'].sum():,}")
print(f"Total refused_total (sum): {df['refused_total'].sum():,}")
decided = df['grant_total'].sum() + df['refused_total'].sum()
rate = df['grant_total'].sum() / decided * 100 if decided else 0
print(f"Overall real grant rate: {rate:.2f}%")
print(df.head(5).to_string())

df.to_csv('nepal_grant_rates_extracted.csv', index=False)
print("\nSaved to nepal_grant_rates_extracted.csv")

# ── April 2026 sanity check against LinkedIn's reported figures ────────────
MONTH_MAP = {
    'M01 Jul': 7, 'M02 Aug': 8, 'M03 Sep': 9, 'M04 Oct': 10,
    'M05 Nov': 11, 'M06 Dec': 12, 'M07 Jan': 1, 'M08 Feb': 2,
    'M09 Mar': 3, 'M10 Apr': 4, 'M11 May': 5, 'M12 Jun': 6,
}
def compute_year_month(row):
    fy_start = int(row['financial_year'][:4])
    m_num = MONTH_MAP.get(row['month'])
    if m_num is None:
        return None
    year = fy_start if m_num >= 7 else fy_start + 1
    return f"{year:04d}-{m_num:02d}"

df['year_month'] = df.apply(compute_year_month, axis=1)
april = df[(df['year_month'] == '2026-04') &
           (df['client_location'] == 'Outside Australia') &
           (df['applicant_type'] == 'Primary')]
g = april['grant_total'].sum()
r = april['refused_total'].sum()
d = g + r
rate = g / d * 100 if d else 0
print(f"\n─── April 2026, Offshore, Primary (real decision-based) ───")
print(f"Granted: {g:,}   Refused: {r:,}   Decided: {d:,}")
print(f"Grant rate: {rate:.1f}%   (LinkedIn reported: 36.1%)")