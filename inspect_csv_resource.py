"""
Inspect the 'Student visa program Resources' CSV — this may be the
granular, non-pivoted dataset (with a Country column) that the XLSX
pivot exports don't give us.

Usage:
    python inspect_csv_resource.py
"""
import requests
import pandas as pd
import io

URL = (
    "https://data.gov.au/data/dataset/324aa4f7-46bb-4d56-bc2d-772333a2317e/"
    "resource/4c157925-d84f-4c9d-a95b-da8ce2580bc1/download/"
    "student-visa-program-resources.csv"
)

print("Downloading...")
resp = requests.get(URL, timeout=60)
resp.raise_for_status()
content = resp.content
print(f"Downloaded {len(content):,} bytes\n")
print("─── Raw first 2000 characters ───")
print(content[:2000].decode('utf-8', errors='replace'))
print()

try:
    df = pd.read_csv(io.BytesIO(content))
    print(f"─── Parsed as CSV: {df.shape[0]} rows, {df.shape[1]} columns ───")
    print("Columns:", list(df.columns))
    print()
    print(df.head(10).to_string())
except Exception as e:
    print(f"Could not parse as a data CSV: {e}")