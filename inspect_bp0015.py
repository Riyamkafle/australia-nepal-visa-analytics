"""
One-off diagnostic: inspect the real structure of the BP0015 'lodged' report
XLSX — sheet names, and the first ~15 raw rows of each sheet (no header
assumption), so we can find where the actual data table starts.

Usage:
    python inspect_bp0015.py
"""
import requests
import pandas as pd

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

xls = pd.ExcelFile(pd.io.common.BytesIO(content))
print("Sheet names:", xls.sheet_names)
print()

for sheet in xls.sheet_names:
    print(f"───── Sheet: '{sheet}' ─────")
    raw = pd.read_excel(xls, sheet_name=sheet, header=None, nrows=15)
    print(raw.to_string())
    print(f"(full sheet shape with header=None: {pd.read_excel(xls, sheet_name=sheet, header=None).shape})")
    print()