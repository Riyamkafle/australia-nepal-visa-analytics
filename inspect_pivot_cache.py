"""
Inspect the raw pivot cache inside the 'Lodged' XLSX file.

An .xlsx is actually a zip archive. Excel PivotTables store their full,
un-aggregated source data in xl/pivotCache/pivotCacheDefinition*.xml
(field names + enumerated value lists) and pivotCacheRecords*.xml
(one <r> element per original row, referencing those enumerated values).
This is the granular, row-level data BEHIND the pivot table shown in the
'Lodged (Month)' sheet — including Citizenship Country, which is
collapsed to "(All)" in the visible sheet but still present here.

This script just explores the structure so we know exactly what we're
working with before writing the full parser.

Usage:
    python inspect_pivot_cache.py
"""
import zipfile
import requests
import io
from xml.etree import ElementTree as ET

URL = (
    "https://data.gov.au/data/dataset/324aa4f7-46bb-4d56-bc2d-772333a2317e/"
    "resource/ef31b2b4-a894-484b-99bc-e35d62ace777/download/"
    "bp0015l-student-visas-lodged-report-locked-at-2026-05-31-v100.xlsx"
)

print("Downloading...")
resp = requests.get(URL, timeout=120)
resp.raise_for_status()
content = resp.content
print(f"Downloaded {len(content):,} bytes\n")

zf = zipfile.ZipFile(io.BytesIO(content))
names = zf.namelist()

pivot_defs = [n for n in names if 'pivotCache/pivotCacheDefinition' in n]
pivot_recs = [n for n in names if 'pivotCache/pivotCacheRecords' in n]

print("Pivot cache definition file(s):", pivot_defs)
print("Pivot cache records file(s):   ", pivot_recs)
print()

if not pivot_defs:
    print("No pivot cache found in this file. Full file listing:")
    for n in names:
        print(" ", n)
else:
    NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    def_xml = zf.read(pivot_defs[0])
    root = ET.fromstring(def_xml)

    print("─── Cache Fields ───")
    fields = root.findall('.//x:cacheFields/x:cacheField', NS)
    for i, f in enumerate(fields):
        field_name = f.get('name')
        shared_items = f.findall('.//x:sharedItems/x:s', NS)
        sample_vals = [s.get('v') for s in shared_items[:5]]
        n_shared = len(f.findall('.//x:sharedItems/*', NS))
        print(f"  [{i}] {field_name}  (shared items: {n_shared}, sample: {sample_vals})")

    print()
    if pivot_recs:
        rec_xml = zf.read(pivot_recs[0])
        rec_root = ET.fromstring(rec_xml)
        records = rec_root.findall('.//x:r', NS)
        print(f"Total records in pivot cache: {len(records)}")
        print("First record's raw XML:")
        print(ET.tostring(records[0], encoding='unicode') if records else "(none)")