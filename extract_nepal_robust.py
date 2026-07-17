"""
Extract Nepal-only granular records from a BP0015 pivot cache — ROBUST
version. Identifies each field by NAME (not hardcoded position), so an
extra/reordered field in one file (like 'Last Visa Held - Visa Category'
in the Granted file) can never silently misalign the data again.

Usage:
    python extract_nepal_robust.py lodged
    python extract_nepal_robust.py granted
"""
import sys
import zipfile
import requests
import io
from xml.etree import ElementTree as ET
import pandas as pd

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

SOURCES = {
    'lodged': (
        "https://data.gov.au/data/dataset/324aa4f7-46bb-4d56-bc2d-772333a2317e/"
        "resource/ef31b2b4-a894-484b-99bc-e35d62ace777/download/"
        "bp0015l-student-visas-lodged-report-locked-at-2026-05-31-v100.xlsx",
        'lodged_count',
    ),
    'granted': (
        "https://data.gov.au/data/dataset/324aa4f7-46bb-4d56-bc2d-772333a2317e/"
        "resource/dfc7a893-0523-4b8e-bc5a-829e35bec90f/download/"
        "bp0015l-student-visas-granted-report-locked-at-2026-05-31-v100-.xlsx",
        'granted_count',
    ),
}

# Maps raw field names (as they appear in either file) -> canonical column name.
# Using .lower() + startswith checks to handle "...of Visa Lodged" vs
# "...of Visa Grant" variants automatically.
def canonical_name(raw_name: str) -> str:
    n = raw_name.strip().lower()
    if n.startswith('financial year of visa'):
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
        'last visa held - visa category': 'last_visa_category',
        'total': None,  # handled separately as the count column
    }
    return mapping.get(n, n.replace(' ', '_').replace('-', '_'))


def extract(kind: str):
    url, count_col = SOURCES[kind]
    print(f"[{kind}] Downloading...")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    content = resp.content
    print(f"[{kind}] Downloaded {len(content):,} bytes")

    zf = zipfile.ZipFile(io.BytesIO(content))
    def_xml = zf.read('xl/pivotCache/pivotCacheDefinition1.xml')
    root = ET.fromstring(def_xml)
    cache_fields = root.findall(f'.//{NS}cacheFields/{NS}cacheField')

    field_info = []  # list of (position, raw_name, canonical_name, shared_items)
    total_pos = None
    country_pos = None
    for pos, f in enumerate(cache_fields):
        raw_name = f.get('name')
        canon = canonical_name(raw_name)
        items = [s.get('v') for s in f.findall(f'.//{NS}sharedItems/{NS}s')]
        field_info.append((pos, raw_name, canon, items))
        if raw_name.strip().lower() == 'total':
            total_pos = pos
        if canon == 'citizenship_country':
            country_pos = pos

    print(f"[{kind}] Field map: " + ", ".join(f"{p}={n}" for p, n, _, _ in [(a,b,c,d) for a,b,c,d in field_info]))
    print(f"[{kind}] 'Total' found at position {total_pos}, 'Citizenship Country' at position {country_pos}")

    if total_pos is None or country_pos is None:
        raise SystemExit(f"[{kind}] Could not locate required fields — stopping. "
                          f"Field names found: {[f[1] for f in field_info]}")

    country_items = field_info[country_pos][3]
    nepal_matches = [(i, v) for i, v in enumerate(country_items) if 'nepal' in v.lower()]
    if not nepal_matches:
        raise SystemExit(f"[{kind}] 'Nepal' not found in Citizenship Country items — stopping.")
    nepal_idx = nepal_matches[0][0]
    print(f"[{kind}] Nepal index = {nepal_idx}")

    print(f"[{kind}] Streaming through records...")
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
                    for pos, raw_name, canon, items in field_info:
                        if pos == total_pos:
                            continue
                        val = children[pos].get('v')
                        row[canon] = items[int(val)] if (val is not None and items) else val
                    total_val = children[total_pos].get('v')
                    row[count_col] = int(float(total_val)) if total_val is not None else 0
                    rows.append(row)
                elem.clear()
                if scanned % 500000 == 0:
                    print(f"[{kind}]   ...scanned {scanned:,}, {len(rows):,} Nepal matches")

    print(f"[{kind}] Done. Scanned {scanned:,} total, found {len(rows):,} Nepal rows.")
    df = pd.DataFrame(rows)
    print(f"[{kind}] Total {count_col} (sum): {df[count_col].sum():,}")
    print(df.head(5).to_string())

    out_file = f'nepal_{kind}_extracted.csv'
    df.to_csv(out_file, index=False)
    print(f"[{kind}] Saved to {out_file}\n")


if __name__ == '__main__':
    kind = sys.argv[1] if len(sys.argv) > 1 else None
    if kind not in SOURCES:
        print("Usage: python extract_nepal_robust.py [lodged|granted]")
        sys.exit(1)
    extract(kind)
    