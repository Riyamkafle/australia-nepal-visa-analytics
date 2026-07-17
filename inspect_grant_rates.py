"""
Inspect the pivot cache structure of the 'Grant Rates' XLSX — this file
may have a different field layout than Lodged/Granted (e.g. separate
Granted/Refused/Grant Rate numeric fields instead of one 'Total').

Usage:
    python inspect_grant_rates.py
"""
import zipfile
import requests
import io
from xml.etree import ElementTree as ET

URL = (
    "https://data.gov.au/data/dataset/324aa4f7-46bb-4d56-bc2d-772333a2317e/"
    "resource/b4775919-d0f5-4beb-8901-6384342774c6/download/"
    "bp0015l-student-visa-grant-rates-locked-at-2026-05-31-v100-.xlsx"
)

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

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

if not pivot_defs:
    print("\nNo pivot cache found. Falling back to sheet inspection:")
    xls_names = zf.namelist()
    sheet_files = [n for n in xls_names if n.startswith('xl/worksheets/sheet')]
    print("Worksheet XML files:", sheet_files)
    raise SystemExit()

def_xml = zf.read(pivot_defs[0])
root = ET.fromstring(def_xml)
cache_fields = root.findall(f'.//{NS}cacheFields/{NS}cacheField')

print(f"\n─── {len(cache_fields)} Cache Fields ───")
for i, f in enumerate(cache_fields):
    name = f.get('name')
    n_shared = len(f.findall(f'.//{NS}sharedItems/*', {}))
    sample = [s.get('v') for s in f.findall(f'.//{NS}sharedItems/{NS}s')[:5]]
    # Check for numeric-only sharedItems too
    n_nums = f.findall(f'.//{NS}sharedItems/{NS}n')
    print(f"  [{i}] {name}  (string items: {n_shared}, numeric items: {len(n_nums)}, sample: {sample})")

if pivot_recs:
    rec_xml = zf.read(pivot_recs[0])
    rec_root = ET.fromstring(rec_xml)
    records = rec_root.findall(f'.//{NS}r')
    print(f"\nTotal records: {len(records)}")
    print("First record raw XML:")
    print(ET.tostring(records[0], encoding='unicode') if records else "(none)")
    print("\nSecond record raw XML:")
    print(ET.tostring(records[1], encoding='unicode') if len(records) > 1 else "(none)")